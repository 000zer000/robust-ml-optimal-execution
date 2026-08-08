#include "robust_execution/metrics/audit.hpp"

#include "robust_execution/util/sha256.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>
#include <numeric>
#include <set>
#include <sstream>
#include <string>
#include <utility>

namespace robust_execution::metrics {
namespace {

void add_issue(std::vector<MetricIssue>& issues, std::string code, std::string detail) {
  issues.push_back({MetricIssueSeverity::Error, std::move(code), std::move(detail)});
}

bool checked_add_i64(std::int64_t lhs, std::int64_t rhs, std::int64_t& output) noexcept {
  if ((rhs > 0 && lhs > std::numeric_limits<std::int64_t>::max() - rhs) ||
      (rhs < 0 && lhs < std::numeric_limits<std::int64_t>::min() - rhs)) {
    return false;
  }
  output = lhs + rhs;
  return true;
}

bool independent_notional(
    const model::InstrumentDefinition& instrument,
    model::PriceTicks price,
    model::QuantityLots quantity,
    std::int64_t& output
) noexcept {
  if (price.value() < 0 || !instrument.tick_size.valid() || !instrument.lot_size.valid() ||
      !instrument.quote_atom_size.valid()) {
    return false;
  }
  std::array<std::uint64_t, 5> top{
      static_cast<std::uint64_t>(price.value()),
      quantity.value(),
      instrument.tick_size.numerator,
      instrument.lot_size.numerator,
      instrument.quote_atom_size.denominator,
  };
  std::array<std::uint64_t, 3> bottom{
      instrument.tick_size.denominator,
      instrument.lot_size.denominator,
      instrument.quote_atom_size.numerator,
  };
  for (auto& denominator : bottom) {
    for (auto& numerator : top) {
      const auto factor = std::gcd(numerator, denominator);
      numerator /= factor;
      denominator /= factor;
    }
    if (denominator != 1U) {
      return false;
    }
  }
  std::uint64_t product = 1U;
  for (const auto factor : top) {
    if (factor != 0U && product > std::numeric_limits<std::uint64_t>::max() / factor) {
      return false;
    }
    product *= factor;
  }
  if (product > static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())) {
    return false;
  }
  output = static_cast<std::int64_t>(product);
  return true;
}

bool close(double lhs, double rhs) noexcept {
  const auto scale = std::max({1.0, std::abs(lhs), std::abs(rhs)});
  return std::abs(lhs - rhs) <= 1e-12 * scale;
}

std::string canonical_json(bool passed, const std::vector<MetricIssue>& issues) {
  std::ostringstream output;
  output << '{';
  output << "\"issue_count\":" << issues.size() << ',';
  output << "\"issues\":[";
  for (std::size_t index = 0; index < issues.size(); ++index) {
    if (index != 0U) {
      output << ',';
    }
    output << "{\"code\":\"" << issues[index].code << "\",\"severity\":\""
           << to_string(issues[index].severity) << "\"}";
  }
  output << "],";
  output << "\"passed\":" << (passed ? "true" : "false") << ',';
  output << "\"schema_version\":\"metric-audit-v1\"";
  output << '}';
  return output.str();
}

}  // namespace

MetricAuditResult audit_episode_metrics(
    const EpisodeMetricInput& input,
    const EpisodeMetrics& reported
) {
  MetricAuditResult audit;
  auto& issues = audit.issues;
  if (reported.episode_id != input.episode_id || reported.side != input.parent.side ||
      reported.parent_quantity != input.parent.total_quantity) {
    add_issue(issues, "identity_mismatch", "reported episode identity differs from source ledger");
  }

  std::set<std::uint64_t> executions;
  std::uint64_t filled = 0U;
  std::uint64_t passive = 0U;
  std::uint64_t aggressive = 0U;
  std::uint64_t unknown = 0U;
  std::uint64_t terminal_quantity = 0U;
  std::int64_t notional_total = 0;
  std::int64_t fee_total = 0;
  std::int64_t gross_cash = 0;
  std::int64_t terminal_notional = 0;
  std::int64_t terminal_fee = 0;
  for (const auto& fill : input.fills) {
    if (!executions.insert(fill.execution_id.value()).second) {
      add_issue(issues, "duplicate_execution", "audit found duplicate execution ID");
      continue;
    }
    if (filled > input.parent.total_quantity.value() ||
        fill.quantity.value() > input.parent.total_quantity.value() - filled) {
      add_issue(issues, "inventory_bounds", "audit found parent overfill");
      continue;
    }
    std::int64_t fill_notional = 0;
    if (!independent_notional(input.instrument, fill.price, fill.quantity, fill_notional)) {
      add_issue(issues, "notional_reconstruction", "audit could not reconstruct exact notional");
      continue;
    }
    std::int64_t next = 0;
    if (!checked_add_i64(notional_total, fill_notional, next)) {
      add_issue(issues, "notional_overflow", "audit notional sum overflowed");
      continue;
    }
    notional_total = next;
    const auto signed_cash = fill.side == model::Side::Buy ? -fill_notional : fill_notional;
    if (!checked_add_i64(gross_cash, signed_cash, next)) {
      add_issue(issues, "cash_overflow", "audit cash sum overflowed");
      continue;
    }
    gross_cash = next;
    if (!checked_add_i64(fee_total, fill.explicit_fee.value(), next)) {
      add_issue(issues, "fee_overflow", "audit fee sum overflowed");
      continue;
    }
    fee_total = next;
    filled += fill.quantity.value();
    if (fill.source == FillSource::TerminalCompletion) {
      terminal_quantity += fill.quantity.value();
      if (!checked_add_i64(terminal_notional, fill_notional, next)) {
        add_issue(issues, "terminal_notional_overflow", "audit terminal notional overflowed");
      } else {
        terminal_notional = next;
      }
      if (!checked_add_i64(terminal_fee, fill.explicit_fee.value(), next)) {
        add_issue(issues, "terminal_fee_overflow", "audit terminal fee overflowed");
      } else {
        terminal_fee = next;
      }
    }
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
  }

  std::int64_t net_cash = 0;
  if (!checked_add_i64(gross_cash, -fee_total, net_cash)) {
    add_issue(issues, "net_cash_overflow", "audit net cash overflowed");
  }
  const auto remaining = input.parent.total_quantity.value() -
                         std::min(filled, input.parent.total_quantity.value());
  if (reported.filled_quantity.value() != filled ||
      reported.remaining_quantity.value() != remaining ||
      reported.complete != (filled == input.parent.total_quantity.value()) ||
      !close(
          reported.completion_rate,
          static_cast<double>(filled) / static_cast<double>(input.parent.total_quantity.value())
      )) {
    add_issue(issues, "completion_mismatch", "reported completion differs from ledger reconstruction");
  }
  if (reported.gross_execution_notional.value() != notional_total ||
      reported.gross_cash_flow.value() != gross_cash || reported.explicit_fees.value() != fee_total ||
      reported.net_cash_flow.value() != net_cash) {
    add_issue(issues, "cash_mismatch", "reported cash or fee totals differ from reconstruction");
  }
  if (reported.passive_quantity.value() != passive ||
      reported.aggressive_quantity.value() != aggressive ||
      reported.unknown_liquidity_quantity.value() != unknown ||
      reported.terminal_quantity.value() != terminal_quantity) {
    add_issue(issues, "classification_mismatch", "reported fill classifications differ");
  }

  std::int64_t arrival_notional = 0;
  if (!independent_notional(
          input.instrument,
          input.parent.arrival_price,
          input.parent.total_quantity,
          arrival_notional
      )) {
    add_issue(issues, "arrival_notional", "audit could not reconstruct arrival notional");
  } else if (filled == input.parent.total_quantity.value()) {
    std::int64_t price_cost = input.parent.side == model::Side::Buy
                                  ? notional_total - arrival_notional
                                  : arrival_notional - notional_total;
    std::int64_t shortfall = 0;
    if (!checked_add_i64(price_cost, fee_total, shortfall) ||
        !reported.implementation_shortfall.has_value() ||
        reported.implementation_shortfall->value() != shortfall ||
        !reported.implementation_shortfall_bps.has_value() ||
        !close(
            *reported.implementation_shortfall_bps,
            static_cast<double>(shortfall) * 10'000.0 / static_cast<double>(arrival_notional)
        )) {
      add_issue(issues, "shortfall_mismatch", "reported implementation shortfall differs");
    }
  } else if (reported.implementation_shortfall.has_value() ||
             reported.implementation_shortfall_bps.has_value()) {
    add_issue(issues, "incomplete_shortfall", "incomplete episode reported final shortfall");
  }

  if (terminal_quantity > 0U) {
    std::int64_t terminal_benchmark = 0;
    if (!independent_notional(
            input.instrument,
            input.parent.arrival_price,
            model::QuantityLots{terminal_quantity},
            terminal_benchmark
        )) {
      add_issue(issues, "terminal_benchmark", "audit could not reconstruct terminal benchmark");
    } else {
      const auto price_cost = input.parent.side == model::Side::Buy
                                  ? terminal_notional - terminal_benchmark
                                  : terminal_benchmark - terminal_notional;
      std::int64_t terminal_cost = 0;
      if (!checked_add_i64(price_cost, terminal_fee, terminal_cost) ||
          reported.terminal_completion_cost.value() != terminal_cost) {
        add_issue(issues, "terminal_cost_mismatch", "reported terminal cost differs");
      }
    }
  } else if (reported.terminal_completion_cost.value() != 0) {
    add_issue(issues, "unexpected_terminal_cost", "terminal cost exists without terminal quantity");
  }

  if (reported.inventory_trajectory.empty()) {
    add_issue(issues, "missing_inventory_trajectory", "inventory trajectory is required");
  } else {
    auto prior_time = reported.inventory_trajectory.front().timestamp;
    auto prior_inventory = reported.inventory_trajectory.front().remaining.value();
    if (prior_time != input.parent.start_time ||
        prior_inventory != input.parent.total_quantity.value()) {
      add_issue(issues, "inventory_start", "inventory trajectory does not start at parent state");
    }
    for (const auto& point : reported.inventory_trajectory) {
      if (point.timestamp.domain() != input.parent.start_time.domain() ||
          point.timestamp.value() < prior_time.value() ||
          point.remaining.value() > input.parent.total_quantity.value() ||
          point.remaining.value() > prior_inventory) {
        add_issue(issues, "inventory_bounds", "inventory trajectory violates time or state bounds");
        break;
      }
      prior_time = point.timestamp;
      prior_inventory = point.remaining.value();
    }
    if (reported.inventory_trajectory.back().remaining.value() != remaining) {
      add_issue(issues, "inventory_end", "inventory trajectory final state differs from ledger");
    }
  }

  if (reported.performance.events_processed > 0U) {
    const auto expected = static_cast<double>(reported.performance.events_processed) * 1e9 /
                          static_cast<double>(reported.performance.wall_time_ns);
    if (!reported.events_per_second.has_value() || !close(*reported.events_per_second, expected)) {
      add_issue(issues, "throughput_mismatch", "reported throughput differs from raw measurement");
    }
  }
  if (input.actions.submits > 0U) {
    const auto expected = static_cast<double>(input.actions.cancels) /
                          static_cast<double>(input.actions.submits);
    if (!reported.cancel_to_submit_ratio.has_value() ||
        !close(*reported.cancel_to_submit_ratio, expected)) {
      add_issue(issues, "activity_ratio_mismatch", "cancel-to-submit ratio differs");
    }
  }

  audit.passed = issues.empty();
  audit.canonical_json = canonical_json(audit.passed, issues);
  audit.sha256 = util::sha256_hex(audit.canonical_json);
  return audit;
}

}  // namespace robust_execution::metrics
