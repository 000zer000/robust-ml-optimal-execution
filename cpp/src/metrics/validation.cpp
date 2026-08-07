#include "robust_execution/metrics/metrics.hpp"

#include "robust_execution/util/sha256.hpp"

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <vector>

namespace robust_execution::metrics {
namespace {

model::TimestampNs time(std::int64_t value) {
  return model::TimestampNs{model::ClockDomain::Simulation, value};
}


std::string_view liquidity_role_name(model::LiquidityRole value) {
  switch (value) {
    case model::LiquidityRole::Maker:
      return "maker";
    case model::LiquidityRole::Taker:
      return "taker";
    case model::LiquidityRole::Unknown:
      return "unknown";
  }
  return "unknown";
}

model::InstrumentDefinition instrument() {
  return model::InstrumentDefinition{
      model::kEventSchemaVersion,
      model::VenueId{"synthetic"},
      model::InstrumentId{"METRIC-USD"},
      "METRIC",
      "USD",
      model::RationalIncrement{1U, 1U},
      model::RationalIncrement{1U, 1U},
      model::RationalIncrement{1U, 1U},
      model::QuantityLots{1U},
      model::QuantityLots{1'000'000U},
      "metrics-validation-v1",
  };
}

policy::ParentOrderDefinition parent(
    std::uint64_t parent_id,
    model::Side side,
    std::uint64_t quantity = 100U
) {
  return policy::ParentOrderDefinition{
      model::ParentOrderId{parent_id},
      side,
      model::QuantityLots{quantity},
      time(0),
      time(1'000),
      model::PriceTicks{100},
      "hard-completion-v1",
  };
}

EpisodeMetricInput detailed_input(model::Side side) {
  const bool buy = side == model::Side::Buy;
  EpisodeMetricInput input;
  input.episode_id = buy ? "detailed-buy" : "detailed-sell";
  input.instrument = instrument();
  input.parent = parent(buy ? 1U : 2U, side);
  input.fills = {
      ExecutionFillRecord{
          model::ExecutionId{1U},
          side,
          model::PriceTicks{buy ? 99 : 101},
          model::QuantityLots{40U},
          time(100),
          model::LiquidityRole::Maker,
          model::QuoteAtoms{-4},
          FillSource::Continuous,
      },
      ExecutionFillRecord{
          model::ExecutionId{2U},
          side,
          model::PriceTicks{buy ? 101 : 99},
          model::QuantityLots{30U},
          time(300),
          model::LiquidityRole::Taker,
          model::QuoteAtoms{3},
          FillSource::Continuous,
      },
      ExecutionFillRecord{
          model::ExecutionId{3U},
          side,
          model::PriceTicks{buy ? 102 : 98},
          model::QuantityLots{20U},
          time(700),
          model::LiquidityRole::Taker,
          model::QuoteAtoms{2},
          FillSource::Continuous,
      },
      ExecutionFillRecord{
          model::ExecutionId{4U},
          side,
          model::PriceTicks{buy ? 105 : 95},
          model::QuantityLots{10U},
          time(1'100),
          model::LiquidityRole::Taker,
          model::QuoteAtoms{2},
          FillSource::TerminalCompletion,
      },
  };
  input.markouts = {
      MarkoutRecord{
          model::ExecutionId{1U},
          100,
          time(200),
          model::PriceTicks{buy ? 98 : 102},
      },
      MarkoutRecord{
          model::ExecutionId{2U},
          100,
          time(400),
          model::PriceTicks{buy ? 102 : 98},
      },
      MarkoutRecord{
          model::ExecutionId{3U},
          100,
          time(800),
          model::PriceTicks{100},
      },
      MarkoutRecord{
          model::ExecutionId{4U},
          100,
          time(1'200),
          model::PriceTicks{buy ? 104 : 96},
      },
      MarkoutRecord{
          model::ExecutionId{1U},
          500,
          time(600),
          model::PriceTicks{100},
      },
      MarkoutRecord{
          model::ExecutionId{2U},
          500,
          time(800),
          model::PriceTicks{buy ? 99 : 101},
      },
  };
  input.decision_timings = {
      DecisionTimingRecord{model::DecisionId{1U}, time(80), time(100), time(110), 5, time(112)},
      DecisionTimingRecord{model::DecisionId{2U}, time(250), time(300), time(320), 8, time(325)},
      DecisionTimingRecord{model::DecisionId{3U}, time(650), time(700), time(740), std::nullopt, time(745)},
      DecisionTimingRecord{model::DecisionId{4U}, time(900), time(1'000), time(1'050), 20, time(1'060)},
  };
  input.actions = ActionActivity{4U, 3U, 1U, 1U, 0U, 0U};
  input.performance = PerformanceMeasurement{1'000U, 2'000'000, 8U * 1024U * 1024U};
  input.external_benchmarks = {
      BenchmarkPrice{"interval_mid", BenchmarkKind::External, model::PriceTicks{101}}
  };
  return input;
}

EpisodeMetricInput tail_input(std::size_t index) {
  EpisodeMetricInput input;
  input.episode_id = "tail-" + std::to_string(index);
  input.instrument = instrument();
  input.parent = parent(100U + index, index % 2U == 0U ? model::Side::Buy : model::Side::Sell);
  const auto fee = static_cast<std::int64_t>(-20 + static_cast<std::int64_t>(index) * 5);
  input.fills = {
      ExecutionFillRecord{
          model::ExecutionId{1U},
          input.parent.side,
          model::PriceTicks{100},
          model::QuantityLots{100U},
          time(500),
          index % 2U == 0U ? model::LiquidityRole::Maker : model::LiquidityRole::Taker,
          model::QuoteAtoms{fee},
          FillSource::Continuous,
      },
  };
  return input;
}

EpisodeMetricInput incomplete_input() {
  auto input = tail_input(50U);
  input.episode_id = "incomplete";
  input.fills.front().quantity = model::QuantityLots{50U};
  return input;
}

std::string detailed_ledger_json(const EpisodeMetricInput& input) {
  std::ostringstream output;
  output << '{';
  output << "\"episode_id\":\"" << input.episode_id << "\",";
  output << "\"actions\":{";
  output << "\"cancels\":" << input.actions.cancels << ',';
  output << "\"decisions\":" << input.actions.decisions << ',';
  output << "\"invalid_actions\":" << input.actions.invalid_actions << ',';
  output << "\"rejected_actions\":" << input.actions.rejected_actions << ',';
  output << "\"replaces\":" << input.actions.replaces << ',';
  output << "\"submits\":" << input.actions.submits << "},";
  output << "\"arrival_price_ticks\":" << input.parent.arrival_price.value() << ',';
  output << "\"decision_timings\":[";
  for (std::size_t index = 0; index < input.decision_timings.size(); ++index) {
    if (index != 0U) {
      output << ',';
    }
    const auto& timing = input.decision_timings[index];
    output << "{\"action_dispatch_time_ns\":";
    if (timing.action_dispatch_time.has_value()) {
      output << timing.action_dispatch_time->value();
    } else {
      output << "null";
    }
    output << ",\"decision_end_ns\":" << timing.decision_end.value();
    output << ",\"decision_id\":" << timing.decision_id.value();
    output << ",\"decision_start_ns\":" << timing.decision_start.value();
    output << ",\"inference_latency_ns\":";
    if (timing.inference_latency_ns.has_value()) {
      output << *timing.inference_latency_ns;
    } else {
      output << "null";
    }
    output << ",\"observation_cutoff_ns\":" << timing.observation_cutoff.value() << '}';
  }
  output << "],";
  output << "\"end_time_ns\":" << input.parent.end_time.value() << ',';
  output << "\"external_benchmarks\":[";
  for (std::size_t index = 0; index < input.external_benchmarks.size(); ++index) {
    if (index != 0U) {
      output << ',';
    }
    output << "{\"benchmark_id\":\"" << input.external_benchmarks[index].benchmark_id
           << "\",\"price_ticks\":" << input.external_benchmarks[index].price.value() << '}';
  }
  output << "],";
  output << "\"fills\":[";
  for (std::size_t index = 0; index < input.fills.size(); ++index) {
    if (index != 0U) {
      output << ',';
    }
    const auto& fill = input.fills[index];
    output << '{';
    output << "\"execution_id\":" << fill.execution_id.value() << ',';
    output << "\"explicit_fee_quote_atoms\":" << fill.explicit_fee.value() << ',';
    output << "\"fill_time_ns\":" << fill.fill_time.value() << ',';
    output << "\"liquidity_role\":\"" << liquidity_role_name(fill.liquidity_role) << "\",";
    output << "\"price_ticks\":" << fill.price.value() << ',';
    output << "\"quantity_lots\":" << fill.quantity.value() << ',';
    output << "\"source\":\"" << to_string(fill.source) << "\"";
    output << '}';
  }
  output << "],";
  output << "\"instrument\":{";
  output << "\"lot_denominator\":" << input.instrument.lot_size.denominator << ',';
  output << "\"lot_numerator\":" << input.instrument.lot_size.numerator << ',';
  output << "\"quote_atom_denominator\":" << input.instrument.quote_atom_size.denominator << ',';
  output << "\"quote_atom_numerator\":" << input.instrument.quote_atom_size.numerator << ',';
  output << "\"tick_denominator\":" << input.instrument.tick_size.denominator << ',';
  output << "\"tick_numerator\":" << input.instrument.tick_size.numerator << "},";
  output << "\"markouts\":[";
  for (std::size_t index = 0; index < input.markouts.size(); ++index) {
    if (index != 0U) {
      output << ',';
    }
    const auto& markout = input.markouts[index];
    output << "{\"execution_id\":" << markout.execution_id.value()
           << ",\"horizon_ns\":" << markout.horizon_ns
           << ",\"markout_mid_price_ticks\":" << markout.markout_mid_price.value()
           << ",\"markout_time_ns\":" << markout.markout_time.value() << '}';
  }
  output << "],";
  output << "\"parent_quantity_lots\":" << input.parent.total_quantity.value() << ',';
  output << "\"performance\":{";
  output << "\"events_processed\":" << input.performance.events_processed << ',';
  output << "\"peak_rss_bytes\":" << input.performance.peak_rss_bytes << ',';
  output << "\"wall_time_ns\":" << input.performance.wall_time_ns << "},";
  output << "\"side\":\"" << model::to_string(input.parent.side) << "\",";
  output << "\"start_time_ns\":" << input.parent.start_time.value();
  output << '}';
  return output.str();
}

std::string tail_rows_json(const std::vector<EpisodeMetrics>& episodes) {
  std::ostringstream output;
  output << std::setprecision(17) << '[';
  for (std::size_t index = 0; index < episodes.size(); ++index) {
    if (index != 0U) {
      output << ',';
    }
    output << "{\"episode_id\":\"" << episodes[index].episode_id
           << "\",\"implementation_shortfall_bps\":"
           << *episodes[index].implementation_shortfall_bps
           << ",\"terminal_fraction\":"
           << static_cast<double>(episodes[index].terminal_quantity.value()) /
                  static_cast<double>(episodes[index].parent_quantity.value())
           << '}';
  }
  output << ']';
  return output.str();
}

}  // namespace

MetricsValidationReport run_metrics_validation() {
  const auto buy_input = detailed_input(model::Side::Buy);
  const auto buy_result = calculate_episode_metrics(buy_input);
  if (!buy_result.ok()) {
    throw std::logic_error("detailed metrics validation input failed");
  }
  const auto buy_metrics = *buy_result.metrics;
  const auto buy_audit = audit_episode_metrics(buy_input, buy_metrics);

  const auto sell_input = detailed_input(model::Side::Sell);
  const auto sell_result = calculate_episode_metrics(sell_input);
  if (!sell_result.ok()) {
    throw std::logic_error("sell symmetry validation input failed");
  }
  const auto sell_audit = audit_episode_metrics(sell_input, *sell_result.metrics);
  const bool symmetry = sell_result.metrics->implementation_shortfall.has_value() &&
                        buy_metrics.implementation_shortfall.has_value() &&
                        sell_result.metrics->implementation_shortfall ==
                            buy_metrics.implementation_shortfall;

  std::vector<EpisodeMetrics> tail_episodes;
  std::vector<MetricAuditResult> tail_audits;
  tail_episodes.reserve(40U);
  tail_audits.reserve(40U);
  for (std::size_t index = 0; index < 40U; ++index) {
    const auto input = tail_input(index);
    const auto result = calculate_episode_metrics(input);
    if (!result.ok()) {
      throw std::logic_error("tail validation episode failed");
    }
    tail_episodes.push_back(*result.metrics);
    tail_audits.push_back(audit_episode_metrics(input, tail_episodes.back()));
  }
  const auto aggregate = summarize_tail_risk(tail_episodes, tail_audits);

  const auto incomplete = calculate_episode_metrics(incomplete_input());
  bool incomplete_rejected = false;
  if (incomplete.ok()) {
    const auto audit = audit_episode_metrics(incomplete_input(), *incomplete.metrics);
    try {
      const std::vector one_episode{*incomplete.metrics};
      const std::vector one_audit{audit};
      static_cast<void>(summarize_tail_risk(one_episode, one_audit));
    } catch (const std::invalid_argument&) {
      incomplete_rejected = true;
    }
  }

  MetricsValidationReport report;
  report.detailed_episode = buy_metrics;
  report.detailed_audit = buy_audit;
  report.aggregate = aggregate;
  report.aggregate_episode_count = tail_episodes.size();
  report.buy_sell_symmetry_passed = symmetry && sell_audit.passed;
  report.incomplete_episode_rejected_from_aggregate = incomplete_rejected;
  report.independent_audit_passed = buy_audit.passed && sell_audit.passed &&
                                    std::ranges::all_of(tail_audits, [](const auto& audit) {
                                      return audit.passed;
                                    });
  report.exact_accounting_passed = buy_metrics.gross_execution_notional.value() == 10'080 &&
                                   buy_metrics.explicit_fees.value() == 3 &&
                                   buy_metrics.net_cash_flow.value() == -10'083 &&
                                   buy_metrics.implementation_shortfall.has_value() &&
                                   buy_metrics.implementation_shortfall->value() == 83 &&
                                   buy_metrics.terminal_completion_cost.value() == 52;
  report.state_bounds_passed = buy_metrics.complete &&
                               buy_metrics.remaining_quantity.is_zero() &&
                               buy_metrics.inventory_trajectory.front().remaining.value() == 100U &&
                               buy_metrics.inventory_trajectory.back().remaining.is_zero();
  const auto second = calculate_episode_metrics(buy_input);
  report.deterministic = second.ok() &&
                         second.metrics->canonical_json == buy_metrics.canonical_json;

  std::ostringstream output;
  output << std::setprecision(17);
  output << '{';
  output << "\"aggregate\":" << aggregate.canonical_json << ',';
  output << "\"aggregate_episode_count\":" << report.aggregate_episode_count << ',';
  output << "\"buy_sell_symmetry_passed\":"
         << (report.buy_sell_symmetry_passed ? "true" : "false") << ',';
  output << "\"detailed_audit\":" << buy_audit.canonical_json << ',';
  output << "\"detailed_episode\":" << buy_metrics.canonical_json << ',';
  output << "\"detailed_ledger\":" << detailed_ledger_json(buy_input) << ',';
  output << "\"deterministic\":" << (report.deterministic ? "true" : "false") << ',';
  output << "\"exact_accounting_passed\":"
         << (report.exact_accounting_passed ? "true" : "false") << ',';
  output << "\"historical_results_claimed\":false,";
  output << "\"incomplete_episode_rejected_from_aggregate\":"
         << (report.incomplete_episode_rejected_from_aggregate ? "true" : "false") << ',';
  output << "\"independent_audit_passed\":"
         << (report.independent_audit_passed ? "true" : "false") << ',';
  output << "\"research_status\":\"synthetic_validation_only_non_research\",";
  output << "\"schema_version\":\"metrics-validation-v1\",";
  output << "\"state_bounds_passed\":"
         << (report.state_bounds_passed ? "true" : "false") << ',';
  output << "\"step\":17,";
  output << "\"tail_episodes\":" << tail_rows_json(tail_episodes);
  output << '}';
  report.canonical_json = output.str();
  report.sha256 = util::sha256_hex(report.canonical_json);
  return report;
}

}  // namespace robust_execution::metrics
