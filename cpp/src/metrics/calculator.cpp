#include "robust_execution/metrics/calculator.hpp"

#include "robust_execution/policy/accounting.hpp"
#include "robust_execution/util/sha256.hpp"

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <limits>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <tuple>
#include <utility>

namespace robust_execution::metrics {
namespace {

bool add_i64(std::int64_t lhs, std::int64_t rhs, std::int64_t& output) noexcept {
  if ((rhs > 0 && lhs > std::numeric_limits<std::int64_t>::max() - rhs) ||
      (rhs < 0 && lhs < std::numeric_limits<std::int64_t>::min() - rhs)) {
    return false;
  }
  output = lhs + rhs;
  return true;
}

bool subtract_i64(std::int64_t lhs, std::int64_t rhs, std::int64_t& output) noexcept {
  if (rhs == std::numeric_limits<std::int64_t>::min()) {
    return false;
  }
  return add_i64(lhs, -rhs, output);
}

void error(std::vector<MetricIssue>& issues, std::string code, std::string detail) {
  issues.push_back({MetricIssueSeverity::Error, std::move(code), std::move(detail)});
}

void warning(std::vector<MetricIssue>& issues, std::string code, std::string detail) {
  issues.push_back({MetricIssueSeverity::Warning, std::move(code), std::move(detail)});
}

bool has_errors(const std::vector<MetricIssue>& issues) {
  return std::ranges::any_of(issues, [](const auto& issue) {
    return issue.severity == MetricIssueSeverity::Error;
  });
}

std::string escape_json(std::string_view value) {
  std::ostringstream output;
  for (const char character : value) {
    switch (character) {
      case '\\':
        output << "\\\\";
        break;
      case '"':
        output << "\\\"";
        break;
      case '\n':
        output << "\\n";
        break;
      case '\r':
        output << "\\r";
        break;
      case '\t':
        output << "\\t";
        break;
      default:
        output << character;
        break;
    }
  }
  return output.str();
}

void append_optional_i64(std::ostringstream& output, const std::optional<std::int64_t>& value) {
  if (value.has_value()) {
    output << *value;
  } else {
    output << "null";
  }
}

void append_optional_double(std::ostringstream& output, const std::optional<double>& value) {
  if (value.has_value()) {
    output << *value;
  } else {
    output << "null";
  }
}

void append_optional_quote(
    std::ostringstream& output,
    const std::optional<model::QuoteAtoms>& value
) {
  if (value.has_value()) {
    output << value->value();
  } else {
    output << "null";
  }
}

std::optional<model::QuoteAtoms> notional(
    const model::InstrumentDefinition& instrument,
    model::PriceTicks price,
    model::QuantityLots quantity,
    std::vector<MetricIssue>& issues,
    std::string_view code
) {
  policy::AccountingError accounting_error;
  const auto result = policy::exact_quote_notional(instrument, price, quantity, &accounting_error);
  if (!result.has_value()) {
    error(issues, std::string(code), accounting_error.detail);
  }
  return result;
}

std::optional<model::QuoteAtoms> directional_cost(
    model::Side side,
    model::QuoteAtoms execution_notional,
    model::QuoteAtoms benchmark_notional,
    model::QuoteAtoms fees,
    std::vector<MetricIssue>& issues,
    std::string_view code
) {
  std::int64_t price_difference = 0;
  const bool difference_ok = side == model::Side::Buy
                                 ? subtract_i64(
                                       execution_notional.value(),
                                       benchmark_notional.value(),
                                       price_difference
                                   )
                                 : subtract_i64(
                                       benchmark_notional.value(),
                                       execution_notional.value(),
                                       price_difference
                                   );
  std::int64_t total = 0;
  if (!difference_ok || !add_i64(price_difference, fees.value(), total)) {
    error(issues, std::string(code), "directional cost exceeds signed quote-atom range");
    return std::nullopt;
  }
  return model::QuoteAtoms{total};
}

std::optional<double> bps(model::QuoteAtoms cost, model::QuoteAtoms denominator) {
  if (denominator.value() <= 0) {
    return std::nullopt;
  }
  return static_cast<double>(cost.value()) * 10'000.0 /
         static_cast<double>(denominator.value());
}

std::optional<double> average_price_quote(
    const model::InstrumentDefinition& instrument,
    const std::optional<double>& average_ticks
) {
  if (!average_ticks.has_value() || !instrument.tick_size.valid()) {
    return std::nullopt;
  }
  return *average_ticks * static_cast<double>(instrument.tick_size.numerator) /
         static_cast<double>(instrument.tick_size.denominator);
}

LatencySummary summarize_latency(std::vector<std::int64_t> values) {
  LatencySummary summary;
  if (values.empty()) {
    return summary;
  }
  std::ranges::sort(values);
  summary.count = values.size();
  summary.minimum_ns = values.front();
  summary.maximum_ns = values.back();
  long double sum = 0.0L;
  for (const auto value : values) {
    sum += static_cast<long double>(value);
  }
  summary.mean_ns = static_cast<double>(sum / static_cast<long double>(values.size()));
  const auto nearest_rank = [&values](double probability) {
    const auto rank = static_cast<std::size_t>(
        std::ceil(probability * static_cast<double>(values.size()))
    );
    return static_cast<double>(values[std::max<std::size_t>(1U, rank) - 1U]);
  };
  summary.p50_ns = nearest_rank(0.50);
  summary.p95_ns = nearest_rank(0.95);
  summary.p99_ns = nearest_rank(0.99);
  return summary;
}

std::string canonical_episode_json(const EpisodeMetrics& value) {
  std::ostringstream output;
  output << std::setprecision(17);
  output << '{';
  output << "\"actions\":{";
  output << "\"cancels\":" << value.actions.cancels << ',';
  output << "\"decisions\":" << value.actions.decisions << ',';
  output << "\"invalid_actions\":" << value.actions.invalid_actions << ',';
  output << "\"rejected_actions\":" << value.actions.rejected_actions << ',';
  output << "\"replaces\":" << value.actions.replaces << ',';
  output << "\"submits\":" << value.actions.submits << "},";
  output << "\"action_dispatch_latency\":{";
  output << "\"count\":" << value.action_dispatch_latency.count << ',';
  output << "\"maximum_ns\":" << value.action_dispatch_latency.maximum_ns << ',';
  output << "\"mean_ns\":" << value.action_dispatch_latency.mean_ns << ',';
  output << "\"minimum_ns\":" << value.action_dispatch_latency.minimum_ns << ',';
  output << "\"p50_ns\":" << value.action_dispatch_latency.p50_ns << ',';
  output << "\"p95_ns\":" << value.action_dispatch_latency.p95_ns << ',';
  output << "\"p99_ns\":" << value.action_dispatch_latency.p99_ns << "},";
  output << "\"adverse_selection\":[";
  for (std::size_t index = 0; index < value.adverse_selection.size(); ++index) {
    if (index != 0U) {
      output << ',';
    }
    const auto& row = value.adverse_selection[index];
    output << '{';
    output << "\"coverage_fraction\":" << row.coverage_fraction << ',';
    output << "\"directional_cost_bps\":";
    append_optional_double(output, row.directional_cost_bps);
    output << ',';
    output << "\"directional_cost_quote_atoms\":" << row.directional_cost.value() << ',';
    output << "\"horizon_ns\":" << row.horizon_ns << ',';
    output << "\"observed_quantity_lots\":" << row.observed_quantity.value();
    output << '}';
  }
  output << "],";
  output << "\"aggressive_fraction\":" << value.aggressive_fraction << ',';
  output << "\"aggressive_quantity_lots\":" << value.aggressive_quantity.value() << ',';
  output << "\"average_execution_price_quote\":";
  append_optional_double(output, value.average_execution_price_quote);
  output << ',';
  output << "\"average_execution_price_ticks\":";
  append_optional_double(output, value.average_execution_price_ticks);
  output << ',';
  output << "\"benchmarks\":[";
  for (std::size_t index = 0; index < value.benchmarks.size(); ++index) {
    if (index != 0U) {
      output << ',';
    }
    const auto& row = value.benchmarks[index];
    output << '{';
    output << "\"benchmark_id\":\"" << escape_json(row.benchmark_id) << "\",";
    output << "\"benchmark_notional_quote_atoms\":" << row.benchmark_notional.value() << ',';
    output << "\"implementation_shortfall_bps\":";
    append_optional_double(output, row.implementation_shortfall_bps);
    output << ',';
    output << "\"implementation_shortfall_quote_atoms\":";
    append_optional_quote(output, row.implementation_shortfall);
    output << ',';
    output << "\"kind\":\"" << to_string(row.kind) << "\",";
    output << "\"price_ticks\":" << row.price.value();
    output << '}';
  }
  output << "],";
  output << "\"cancel_to_submit_ratio\":";
  append_optional_double(output, value.cancel_to_submit_ratio);
  output << ',';
  output << "\"complete\":" << (value.complete ? "true" : "false") << ',';
  output << "\"completion_rate\":" << value.completion_rate << ',';
  output << "\"controller_latency\":{";
  output << "\"count\":" << value.controller_latency.count << ',';
  output << "\"maximum_ns\":" << value.controller_latency.maximum_ns << ',';
  output << "\"mean_ns\":" << value.controller_latency.mean_ns << ',';
  output << "\"minimum_ns\":" << value.controller_latency.minimum_ns << ',';
  output << "\"p50_ns\":" << value.controller_latency.p50_ns << ',';
  output << "\"p95_ns\":" << value.controller_latency.p95_ns << ',';
  output << "\"p99_ns\":" << value.controller_latency.p99_ns << "},";
  output << "\"episode_id\":\"" << escape_json(value.episode_id) << "\",";
  output << "\"events_per_second\":";
  append_optional_double(output, value.events_per_second);
  output << ',';
  output << "\"explicit_fees_quote_atoms\":" << value.explicit_fees.value() << ',';
  output << "\"filled_quantity_lots\":" << value.filled_quantity.value() << ',';
  output << "\"gross_cash_flow_quote_atoms\":" << value.gross_cash_flow.value() << ',';
  output << "\"gross_execution_notional_quote_atoms\":"
         << value.gross_execution_notional.value() << ',';
  output << "\"implementation_shortfall_bps\":";
  append_optional_double(output, value.implementation_shortfall_bps);
  output << ',';
  output << "\"implementation_shortfall_quote_atoms\":";
  append_optional_quote(output, value.implementation_shortfall);
  output << ',';
  output << "\"inference_latency\":{";
  output << "\"count\":" << value.inference_latency.count << ',';
  output << "\"maximum_ns\":" << value.inference_latency.maximum_ns << ',';
  output << "\"mean_ns\":" << value.inference_latency.mean_ns << ',';
  output << "\"minimum_ns\":" << value.inference_latency.minimum_ns << ',';
  output << "\"p50_ns\":" << value.inference_latency.p50_ns << ',';
  output << "\"p95_ns\":" << value.inference_latency.p95_ns << ',';
  output << "\"p99_ns\":" << value.inference_latency.p99_ns << "},";
  output << "\"inventory_trajectory\":[";
  for (std::size_t index = 0; index < value.inventory_trajectory.size(); ++index) {
    if (index != 0U) {
      output << ',';
    }
    const auto& point = value.inventory_trajectory[index];
    output << "{\"remaining_lots\":" << point.remaining.value()
           << ",\"timestamp_ns\":" << point.timestamp.value() << '}';
  }
  output << "],";
  output << "\"net_cash_flow_quote_atoms\":" << value.net_cash_flow.value() << ',';
  output << "\"observation_staleness\":{";
  output << "\"count\":" << value.observation_staleness.count << ',';
  output << "\"maximum_ns\":" << value.observation_staleness.maximum_ns << ',';
  output << "\"mean_ns\":" << value.observation_staleness.mean_ns << ',';
  output << "\"minimum_ns\":" << value.observation_staleness.minimum_ns << ',';
  output << "\"p50_ns\":" << value.observation_staleness.p50_ns << ',';
  output << "\"p95_ns\":" << value.observation_staleness.p95_ns << ',';
  output << "\"p99_ns\":" << value.observation_staleness.p99_ns << "},";
  output << "\"parent_quantity_lots\":" << value.parent_quantity.value() << ',';
  output << "\"passive_fraction\":" << value.passive_fraction << ',';
  output << "\"passive_quantity_lots\":" << value.passive_quantity.value() << ',';
  output << "\"performance\":{";
  output << "\"events_processed\":" << value.performance.events_processed << ',';
  output << "\"peak_rss_bytes\":" << value.performance.peak_rss_bytes << ',';
  output << "\"wall_time_ns\":" << value.performance.wall_time_ns << "},";
  output << "\"remaining_quantity_lots\":" << value.remaining_quantity.value() << ',';
  output << "\"schema_version\":\"episode-metrics-v1\",";
  output << "\"side\":\"" << model::to_string(value.side) << "\",";
  output << "\"terminal_completion_cost_bps\":";
  append_optional_double(output, value.terminal_completion_cost_bps);
  output << ',';
  output << "\"terminal_completion_cost_quote_atoms\":"
         << value.terminal_completion_cost.value() << ',';
  output << "\"terminal_completion_used\":"
         << (value.terminal_completion_used ? "true" : "false") << ',';
  output << "\"terminal_quantity_lots\":" << value.terminal_quantity.value() << ',';
  output << "\"time_to_complete_ns\":";
  append_optional_i64(output, value.time_to_complete_ns);
  output << ',';
  output << "\"time_to_first_fill_ns\":";
  append_optional_i64(output, value.time_to_first_fill_ns);
  output << ',';
  output << "\"unknown_liquidity_fraction\":" << value.unknown_liquidity_fraction << ',';
  output << "\"unknown_liquidity_quantity_lots\":"
         << value.unknown_liquidity_quantity.value();
  output << '}';
  return output.str();
}

}  // namespace

bool EpisodeMetricResult::ok() const noexcept {
  return metrics.has_value() && !has_errors(issues);
}

EpisodeMetricResult calculate_episode_metrics(const EpisodeMetricInput& input) {
  EpisodeMetricResult result;
  auto& issues = result.issues;
  if (input.episode_id.empty()) {
    error(issues, "missing_episode_id", "episode_id is required");
  }
  if (!input.instrument.tick_size.valid() || !input.instrument.lot_size.valid() ||
      !input.instrument.quote_atom_size.valid()) {
    error(issues, "invalid_instrument", "instrument increments must be positive");
  }
  if (!input.parent.parent_order_id.valid() || input.parent.total_quantity.is_zero() ||
      input.parent.arrival_price.value() <= 0) {
    error(issues, "invalid_parent", "parent identifier, quantity and arrival price are required");
  }
  if (input.parent.start_time.domain() != input.parent.end_time.domain() ||
      input.parent.start_time.value() >= input.parent.end_time.value()) {
    error(issues, "invalid_parent_time", "parent start and end must share a clock and increase");
  }
  if (has_errors(issues)) {
    return result;
  }

  std::vector<ExecutionFillRecord> fills = input.fills;
  std::ranges::sort(fills, [](const auto& lhs, const auto& rhs) {
    if (lhs.fill_time.domain() != rhs.fill_time.domain()) {
      return static_cast<unsigned>(lhs.fill_time.domain()) < static_cast<unsigned>(rhs.fill_time.domain());
    }
    if (lhs.fill_time.value() != rhs.fill_time.value()) {
      return lhs.fill_time.value() < rhs.fill_time.value();
    }
    return lhs.execution_id.value() < rhs.execution_id.value();
  });
  std::set<std::uint64_t> execution_ids;
  std::map<std::uint64_t, ExecutionFillRecord> fill_by_execution;
  std::uint64_t filled = 0U;
  std::uint64_t passive = 0U;
  std::uint64_t aggressive = 0U;
  std::uint64_t unknown = 0U;
  std::uint64_t terminal_quantity = 0U;
  std::size_t terminal_count = 0U;
  bool terminal_seen = false;
  std::int64_t execution_notional = 0;
  std::int64_t gross_cash = 0;
  std::int64_t fee_total = 0;
  std::int64_t terminal_notional = 0;
  std::int64_t terminal_fee = 0;
  std::vector<InventoryPoint> inventory;
  inventory.push_back({input.parent.start_time, input.parent.total_quantity});
  bool inserted_end_point = false;
  std::optional<std::int64_t> first_fill_time;
  std::optional<std::int64_t> completion_time;

  for (const auto& fill : fills) {
    if (!fill.execution_id.valid() || !execution_ids.insert(fill.execution_id.value()).second) {
      error(issues, "duplicate_execution", "fill execution identifiers must be valid and unique");
      continue;
    }
    if (fill.side != input.parent.side) {
      error(issues, "fill_side_mismatch", "every fill must match the parent side");
    }
    if (fill.price.value() <= 0 || fill.quantity.is_zero()) {
      error(issues, "invalid_fill", "fill price and quantity must be positive");
    }
    if (fill.fill_time.domain() != input.parent.start_time.domain() ||
        fill.fill_time.value() < input.parent.start_time.value()) {
      error(issues, "invalid_fill_time", "fill time must share the parent clock and follow start");
    }
    if (terminal_seen && fill.source != FillSource::TerminalCompletion) {
      error(issues, "post_terminal_fill", "continuous fills cannot follow terminal completion");
    }
    if (fill.source == FillSource::TerminalCompletion) {
      terminal_seen = true;
      ++terminal_count;
      if (terminal_count > 1U) {
        error(issues, "multiple_terminal_fills", "at most one terminal-completion fill is allowed");
      }
    }
    if (fill.quantity.value() > input.parent.total_quantity.value() -
                                    std::min(filled, input.parent.total_quantity.value())) {
      error(issues, "parent_overfill", "fill quantity exceeds remaining parent inventory");
      continue;
    }

    const auto fill_notional = notional(
        input.instrument,
        fill.price,
        fill.quantity,
        issues,
        "fill_notional_error"
    );
    policy::AccountingError cash_error;
    const auto fill_cash = policy::signed_cash_effect(
        input.instrument,
        fill.side,
        fill.price,
        fill.quantity,
        &cash_error
    );
    if (!fill_cash.has_value()) {
      error(issues, "fill_cash_error", cash_error.detail);
    }
    std::int64_t next_execution_notional = 0;
    std::int64_t next_gross_cash = 0;
    std::int64_t next_fees = 0;
    if (!fill_notional.has_value() || !fill_cash.has_value() ||
        !add_i64(execution_notional, fill_notional->value(), next_execution_notional) ||
        !add_i64(gross_cash, fill_cash->value(), next_gross_cash) ||
        !add_i64(fee_total, fill.explicit_fee.value(), next_fees)) {
      error(issues, "fill_accounting_overflow", "fill accounting exceeds signed range");
      continue;
    }
    execution_notional = next_execution_notional;
    gross_cash = next_gross_cash;
    fee_total = next_fees;
    filled += fill.quantity.value();
    fill_by_execution.emplace(fill.execution_id.value(), fill);
    if (!first_fill_time.has_value()) {
      first_fill_time = fill.fill_time.value();
    }
    if (filled == input.parent.total_quantity.value()) {
      completion_time = fill.fill_time.value();
    }
    if (!inserted_end_point && fill.fill_time.value() > input.parent.end_time.value()) {
      inventory.push_back(
          {input.parent.end_time, model::QuantityLots{input.parent.total_quantity.value() -
                                                      (filled - fill.quantity.value())}}
      );
      inserted_end_point = true;
    }
    inventory.push_back(
        {fill.fill_time, model::QuantityLots{input.parent.total_quantity.value() - filled}}
    );
    switch (fill.liquidity_role) {
      case model::LiquidityRole::Maker:
        passive += fill.quantity.value();
        break;
      case model::LiquidityRole::Taker:
        aggressive += fill.quantity.value();
        break;
      case model::LiquidityRole::Unknown:
        unknown += fill.quantity.value();
        break;
    }
    if (fill.source == FillSource::TerminalCompletion) {
      terminal_quantity += fill.quantity.value();
      std::int64_t next_terminal_notional = 0;
      std::int64_t next_terminal_fee = 0;
      if (!add_i64(terminal_notional, fill_notional->value(), next_terminal_notional) ||
          !add_i64(terminal_fee, fill.explicit_fee.value(), next_terminal_fee)) {
        error(issues, "terminal_accounting_overflow", "terminal accounting exceeds range");
      } else {
        terminal_notional = next_terminal_notional;
        terminal_fee = next_terminal_fee;
      }
    }
  }

  if (!inserted_end_point &&
      (inventory.empty() || inventory.back().timestamp.value() < input.parent.end_time.value())) {
    inventory.push_back(
        {input.parent.end_time, model::QuantityLots{input.parent.total_quantity.value() - filled}}
    );
  }
  if (terminal_count == 1U && filled != input.parent.total_quantity.value()) {
    error(issues, "terminal_not_complete", "terminal completion must finish the exact parent residual");
  }

  std::set<std::pair<std::uint64_t, std::int64_t>> markout_keys;
  std::map<std::int64_t, std::pair<std::uint64_t, std::int64_t>> markout_accumulator;
  for (const auto& markout : input.markouts) {
    const auto fill_iterator = fill_by_execution.find(markout.execution_id.value());
    if (fill_iterator == fill_by_execution.end()) {
      error(issues, "unknown_markout_execution", "markout references an unknown execution");
      continue;
    }
    if (markout.horizon_ns <= 0 || markout.markout_mid_price.value() <= 0) {
      error(issues, "invalid_markout", "markout horizon and price must be positive");
      continue;
    }
    if (!markout_keys.insert({markout.execution_id.value(), markout.horizon_ns}).second) {
      error(issues, "duplicate_markout", "execution/horizon markouts must be unique");
      continue;
    }
    const auto& fill = fill_iterator->second;
    if (markout.markout_time.domain() != fill.fill_time.domain() ||
        markout.markout_time.value() - fill.fill_time.value() != markout.horizon_ns) {
      error(issues, "markout_time_mismatch", "markout timestamp must equal fill time plus horizon");
      continue;
    }
    const auto fill_notional = notional(
        input.instrument,
        fill.price,
        fill.quantity,
        issues,
        "markout_fill_notional_error"
    );
    const auto markout_notional = notional(
        input.instrument,
        markout.markout_mid_price,
        fill.quantity,
        issues,
        "markout_mid_notional_error"
    );
    if (!fill_notional.has_value() || !markout_notional.has_value()) {
      continue;
    }
    std::int64_t cost = 0;
    const bool ok = input.parent.side == model::Side::Buy
                        ? subtract_i64(fill_notional->value(), markout_notional->value(), cost)
                        : subtract_i64(markout_notional->value(), fill_notional->value(), cost);
    auto& accumulator = markout_accumulator[markout.horizon_ns];
    std::int64_t next_cost = 0;
    if (!ok || !add_i64(accumulator.second, cost, next_cost) ||
        accumulator.first > std::numeric_limits<std::uint64_t>::max() - fill.quantity.value()) {
      error(issues, "markout_accounting_overflow", "markout accounting exceeds range");
      continue;
    }
    accumulator.first += fill.quantity.value();
    accumulator.second = next_cost;
  }

  std::set<std::uint64_t> decision_ids;
  std::vector<std::int64_t> controller_latencies;
  std::vector<std::int64_t> inference_latencies;
  std::vector<std::int64_t> observation_staleness;
  std::vector<std::int64_t> dispatch_latencies;
  for (const auto& timing : input.decision_timings) {
    if (!timing.decision_id.valid() || !decision_ids.insert(timing.decision_id.value()).second) {
      error(issues, "duplicate_decision", "decision timing IDs must be valid and unique");
      continue;
    }
    const auto domain = timing.observation_cutoff.domain();
    if (timing.decision_start.domain() != domain || timing.decision_end.domain() != domain ||
        timing.observation_cutoff.value() > timing.decision_start.value() ||
        timing.decision_start.value() > timing.decision_end.value()) {
      error(issues, "invalid_decision_timing", "decision clocks must be causal and ordered");
      continue;
    }
    const auto controller = timing.decision_end.value() - timing.decision_start.value();
    controller_latencies.push_back(controller);
    observation_staleness.push_back(
        timing.decision_start.value() - timing.observation_cutoff.value()
    );
    if (timing.inference_latency_ns.has_value()) {
      if (*timing.inference_latency_ns < 0 || *timing.inference_latency_ns > controller) {
        error(issues, "invalid_inference_latency", "inference latency must fit inside controller latency");
      } else {
        inference_latencies.push_back(*timing.inference_latency_ns);
      }
    }
    if (timing.action_dispatch_time.has_value()) {
      if (timing.action_dispatch_time->domain() != domain ||
          timing.action_dispatch_time->value() < timing.decision_end.value()) {
        error(issues, "invalid_dispatch_time", "action dispatch must follow decision completion");
      } else {
        dispatch_latencies.push_back(
            timing.action_dispatch_time->value() - timing.decision_end.value()
        );
      }
    }
  }
  if (!input.decision_timings.empty() &&
      input.actions.decisions != input.decision_timings.size()) {
    error(issues, "decision_count_mismatch", "action decision count differs from timing records");
  }
  if (input.performance.events_processed > 0U && input.performance.wall_time_ns <= 0) {
    error(issues, "invalid_performance_measurement", "positive event count requires positive wall time");
  }
  if (input.performance.events_processed == 0U && input.performance.wall_time_ns != 0) {
    error(issues, "invalid_performance_measurement", "zero event count requires zero wall time");
  }

  std::set<std::string> benchmark_ids{"arrival_price"};
  for (const auto& benchmark : input.external_benchmarks) {
    if (benchmark.benchmark_id.empty() || benchmark.benchmark_id == "arrival_price" ||
        !benchmark_ids.insert(benchmark.benchmark_id).second || benchmark.price.value() <= 0 ||
        benchmark.kind != BenchmarkKind::External) {
      error(issues, "invalid_benchmark", "external benchmark IDs and prices must be unique and valid");
    }
  }

  if (has_errors(issues)) {
    return result;
  }

  EpisodeMetrics metrics;
  metrics.episode_id = input.episode_id;
  metrics.side = input.parent.side;
  metrics.parent_quantity = input.parent.total_quantity;
  metrics.filled_quantity = model::QuantityLots{filled};
  metrics.remaining_quantity = model::QuantityLots{input.parent.total_quantity.value() - filled};
  metrics.completion_rate = static_cast<double>(filled) /
                            static_cast<double>(input.parent.total_quantity.value());
  metrics.complete = filled == input.parent.total_quantity.value();
  metrics.terminal_completion_used = terminal_count == 1U;
  metrics.terminal_quantity = model::QuantityLots{terminal_quantity};
  metrics.gross_execution_notional = model::QuoteAtoms{execution_notional};
  metrics.gross_cash_flow = model::QuoteAtoms{gross_cash};
  metrics.explicit_fees = model::QuoteAtoms{fee_total};
  std::int64_t net_cash = 0;
  if (!subtract_i64(gross_cash, fee_total, net_cash)) {
    error(issues, "net_cash_overflow", "net cash flow exceeds signed range");
    return result;
  }
  metrics.net_cash_flow = model::QuoteAtoms{net_cash};
  if (filled > 0U) {
    const auto tick_scale = static_cast<double>(input.instrument.tick_size.denominator) /
                            (static_cast<double>(input.instrument.tick_size.numerator) *
                             static_cast<double>(input.instrument.lot_size.numerator) /
                             static_cast<double>(input.instrument.lot_size.denominator) *
                             static_cast<double>(input.instrument.quote_atom_size.denominator) /
                             static_cast<double>(input.instrument.quote_atom_size.numerator));
    metrics.average_execution_price_ticks = static_cast<double>(execution_notional) * tick_scale /
                                            static_cast<double>(filled);
    metrics.average_execution_price_quote = average_price_quote(
        input.instrument,
        metrics.average_execution_price_ticks
    );
  }
  metrics.passive_quantity = model::QuantityLots{passive};
  metrics.aggressive_quantity = model::QuantityLots{aggressive};
  metrics.unknown_liquidity_quantity = model::QuantityLots{unknown};
  if (filled > 0U) {
    metrics.passive_fraction = static_cast<double>(passive) / static_cast<double>(filled);
    metrics.aggressive_fraction = static_cast<double>(aggressive) / static_cast<double>(filled);
    metrics.unknown_liquidity_fraction = static_cast<double>(unknown) / static_cast<double>(filled);
  }
  if (first_fill_time.has_value()) {
    metrics.time_to_first_fill_ns = *first_fill_time - input.parent.start_time.value();
  }
  if (completion_time.has_value()) {
    metrics.time_to_complete_ns = *completion_time - input.parent.start_time.value();
  }
  metrics.inventory_trajectory = std::move(inventory);
  metrics.actions = input.actions;
  if (input.actions.submits > 0U) {
    metrics.cancel_to_submit_ratio = static_cast<double>(input.actions.cancels) /
                                     static_cast<double>(input.actions.submits);
  } else if (input.actions.cancels > 0U) {
    warning(issues, "cancel_without_submit", "cancel-to-submit ratio is undefined with no submits");
  }
  metrics.performance = input.performance;
  if (input.performance.events_processed > 0U) {
    metrics.events_per_second = static_cast<double>(input.performance.events_processed) * 1e9 /
                                static_cast<double>(input.performance.wall_time_ns);
  }
  metrics.controller_latency = summarize_latency(std::move(controller_latencies));
  metrics.inference_latency = summarize_latency(std::move(inference_latencies));
  metrics.observation_staleness = summarize_latency(std::move(observation_staleness));
  metrics.action_dispatch_latency = summarize_latency(std::move(dispatch_latencies));

  std::vector<BenchmarkPrice> benchmarks{
      BenchmarkPrice{"arrival_price", BenchmarkKind::ArrivalPrice, input.parent.arrival_price}
  };
  benchmarks.insert(
      benchmarks.end(),
      input.external_benchmarks.begin(),
      input.external_benchmarks.end()
  );
  for (const auto& benchmark : benchmarks) {
    const auto benchmark_notional = notional(
        input.instrument,
        benchmark.price,
        input.parent.total_quantity,
        issues,
        "benchmark_notional_error"
    );
    if (!benchmark_notional.has_value()) {
      return result;
    }
    BenchmarkMetric row{
        benchmark.benchmark_id,
        benchmark.kind,
        benchmark.price,
        *benchmark_notional,
        std::nullopt,
        std::nullopt,
    };
    if (metrics.complete) {
      row.implementation_shortfall = directional_cost(
          input.parent.side,
          metrics.gross_execution_notional,
          *benchmark_notional,
          metrics.explicit_fees,
          issues,
          "implementation_shortfall_overflow"
      );
      if (row.implementation_shortfall.has_value()) {
        row.implementation_shortfall_bps = bps(*row.implementation_shortfall, *benchmark_notional);
      }
    }
    metrics.benchmarks.push_back(row);
  }
  if (metrics.complete && !metrics.benchmarks.empty()) {
    metrics.implementation_shortfall = metrics.benchmarks.front().implementation_shortfall;
    metrics.implementation_shortfall_bps = metrics.benchmarks.front().implementation_shortfall_bps;
  } else {
    warning(
        issues,
        "incomplete_implementation_shortfall",
        "implementation shortfall is withheld until the full parent quantity is accounted"
    );
  }

  if (terminal_quantity > 0U) {
    const auto terminal_benchmark = notional(
        input.instrument,
        input.parent.arrival_price,
        model::QuantityLots{terminal_quantity},
        issues,
        "terminal_benchmark_error"
    );
    if (!terminal_benchmark.has_value()) {
      return result;
    }
    const auto terminal_cost = directional_cost(
        input.parent.side,
        model::QuoteAtoms{terminal_notional},
        *terminal_benchmark,
        model::QuoteAtoms{terminal_fee},
        issues,
        "terminal_cost_overflow"
    );
    if (!terminal_cost.has_value()) {
      return result;
    }
    metrics.terminal_completion_cost = *terminal_cost;
    metrics.terminal_completion_cost_bps = bps(*terminal_cost, *terminal_benchmark);
  }

  for (const auto& [horizon, accumulated] : markout_accumulator) {
    const auto observed_quantity = model::QuantityLots{accumulated.first};
    const auto denominator = notional(
        input.instrument,
        input.parent.arrival_price,
        observed_quantity,
        issues,
        "markout_denominator_error"
    );
    if (!denominator.has_value()) {
      return result;
    }
    metrics.adverse_selection.push_back(
        AdverseSelectionMetric{
            horizon,
            observed_quantity,
            filled == 0U ? 0.0
                         : static_cast<double>(observed_quantity.value()) /
                               static_cast<double>(filled),
            model::QuoteAtoms{accumulated.second},
            bps(model::QuoteAtoms{accumulated.second}, *denominator),
        }
    );
  }

  metrics.issues = issues;
  metrics.canonical_json = canonical_episode_json(metrics);
  metrics.sha256 = util::sha256_hex(metrics.canonical_json);
  result.metrics = std::move(metrics);
  return result;
}

}  // namespace robust_execution::metrics
