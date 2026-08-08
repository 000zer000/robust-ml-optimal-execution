#include "robust_execution/metrics/metrics.hpp"
#include "robust_execution/strategies/adaptive.hpp"
#include "robust_execution/util/sha256.hpp"

#include <algorithm>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace robust_execution;

namespace {
model::TimestampNs t(std::int64_t value) { return {model::ClockDomain::Simulation, value}; }
model::InstrumentDefinition instrument() {
  return {model::kEventSchemaVersion, model::VenueId{"synthetic"}, model::InstrumentId{"ADAPT-USD"}, "ADAPT", "USD",
          model::RationalIncrement{1U,1U}, model::RationalIncrement{1U,1U}, model::RationalIncrement{1U,1U},
          model::QuantityLots{1U}, model::QuantityLots{1'000'000U}, "step20-v1"};
}
policy::ParentOrderDefinition parent() {
  return {model::ParentOrderId{20U}, model::Side::Buy, model::QuantityLots{100U}, t(1'000), t(2'000), model::PriceTicks{100}, "hard-completion-v1"};
}
policy::PolicyEnvironment environment(const std::string& strategy_id) {
  return {instrument(), model::StrategyId{strategy_id}, model::FeeScheduleId{"synthetic-zero-fees"}, model::LatencyModelId{"zero-latency"},
          250, 5U, 16U, 1U, 1U,
          {policy::QuantityFraction{1U,4U}, policy::QuantityFraction{1U,2U}, policy::QuantityFraction{1U,1U}},
          {model::TickOffset{0}}, policy::LotRoundingPolicy::Floor, true, true, true};
}
strategies::NonMlCalibration calibration() {
  return {t(999), "step20-synthetic-calibration-v1", 0.0L, 0.0L, 0.50L, 0.45L, 0.35L, 1.0L, 25.0L};
}

struct MarketStep {
  std::int64_t time;
  std::int64_t bid;
  std::int64_t ask;
  std::uint64_t bid_quantity;
  std::uint64_t ask_quantity;
  bool favorable_passive_flow;
};

policy::PolicyObservation make_observation(
    const policy::PolicyEnvironment& env,
    const MarketStep& step,
    std::uint64_t filled,
    std::uint64_t decision_id
) {
  policy::ParentOrderSnapshot snap{model::ParentOrderId{20U}, model::Side::Buy, t(1'000), t(2'000), model::PriceTicks{100}, "hard-completion-v1",
      model::QuantityLots{100U}, model::QuantityLots{filled}, model::QuantityLots{100U-filled}, model::QuoteAtoms{0}, model::QuoteAtoms{0}, model::QuoteAtoms{0},
      decision_id-1U, policy::ParentOrderStatus::Active, false};
  const auto first = step.favorable_passive_flow ? model::AggressorSide::Sell : model::AggressorSide::Buy;
  const auto second = step.favorable_passive_flow ? model::AggressorSide::Buy : model::AggressorSide::Sell;
  std::vector<policy::ObservedTrade> trades{
      {model::Trade{model::TradeId{decision_id*2U-1U}, std::nullopt, model::PriceTicks{100}, model::QuantityLots{80U}, first}, t(step.time-2), t(step.time-1)},
      {model::Trade{model::TradeId{decision_id*2U}, std::nullopt, model::PriceTicks{100}, model::QuantityLots{20U}, second}, t(step.time-2), t(step.time-1)}};
  return {model::DecisionId{decision_id}, t(step.time), t(step.time), env, snap,
      {{model::PriceTicks{step.bid}, model::QuantityLots{step.bid_quantity}, std::nullopt}},
      {{model::PriceTicks{step.ask}, model::QuantityLots{step.ask_quantity}, std::nullopt}}, std::move(trades), {}, 0U, {}};
}

std::uint64_t action_quantity(std::uint64_t remaining, policy::QuantityFraction fraction) {
  if (fraction.denominator == 0U || fraction.numerator == 0U) throw std::runtime_error("invalid validation fraction");
  const auto product = remaining * fraction.numerator;
  auto result = product / fraction.denominator;
  if (result == 0U) result = remaining;
  return std::min(result, remaining);
}

struct EpisodeResult {
  metrics::EpisodeMetrics metrics;
  std::vector<std::string> actions;
  std::vector<std::string> diagnostics;
};

EpisodeResult run_policy(policy::ExecutionPolicy& strategy, const policy::PolicyEnvironment& env, bool record_mpc) {
  const auto p = parent();
  strategy.reset(p, env);
  const std::vector<MarketStep> path{
      {1'000, 98, 102, 20U, 200U, true},
      {1'250, 99, 101, 50U, 120U, true},
      {1'500, 99, 101, 220U, 20U, false},
      {1'750, 100, 102, 500U, 10U, false},
  };
  metrics::EpisodeMetricInput input;
  input.episode_id = env.strategy_id.value();
  input.instrument = instrument();
  input.parent = p;
  std::uint64_t filled = 0U;
  std::uint64_t execution_id = 1U;
  EpisodeResult result;

  for (std::size_t i = 0U; i < path.size(); ++i) {
    if (filled >= 100U) break;
    const auto obs = make_observation(env, path[i], filled, i+1U);
    const auto action = strategy.on_observation(obs);
    if (const auto* submit = std::get_if<policy::SubmitChildAction>(&action.payload)) {
      const auto quantity = action_quantity(100U-filled, submit->quantity_fraction);
      const bool passive = submit->order_type == model::OrderType::Limit;
      const auto price = model::PriceTicks{passive ? path[i].bid : path[i].ask};
      input.fills.push_back({model::ExecutionId{execution_id++}, model::Side::Buy, price, model::QuantityLots{quantity}, t(path[i].time+1),
          passive ? model::LiquidityRole::Maker : model::LiquidityRole::Taker, model::QuoteAtoms{0}, metrics::FillSource::Continuous});
      filled += quantity;
      std::ostringstream action_text;
      action_text << (passive ? "passive" : "aggressive") << ':' << quantity << '@' << price.value();
      result.actions.push_back(action_text.str());
    } else if (std::holds_alternative<policy::NoAction>(action.payload)) {
      result.actions.push_back("no_action");
    } else if (std::holds_alternative<policy::CancelChildAction>(action.payload)) {
      result.actions.push_back("cancel");
    } else {
      result.actions.push_back("replace");
    }
    if (record_mpc) {
      const auto* mpc = dynamic_cast<strategies::NonMlMpcPolicy*>(&strategy);
      if (mpc != nullptr && mpc->last_decision().has_value()) result.diagnostics.push_back(mpc->last_decision()->canonical);
    }
  }
  if (filled < 100U) {
    const auto residual = 100U-filled;
    input.fills.push_back({model::ExecutionId{execution_id}, model::Side::Buy, model::PriceTicks{103}, model::QuantityLots{residual}, t(2'000),
        model::LiquidityRole::Taker, model::QuoteAtoms{0}, metrics::FillSource::TerminalCompletion});
    result.actions.push_back("terminal_aggressive:" + std::to_string(residual) + "@103");
  }
  input.actions.decisions = static_cast<std::uint64_t>(path.size());
  input.actions.submits = static_cast<std::uint64_t>(std::count_if(result.actions.begin(), result.actions.end(), [](const auto& action) {
    return action.rfind("passive:",0U)==0U || action.rfind("aggressive:",0U)==0U || action.rfind("terminal_aggressive:",0U)==0U;
  }));
  const auto calculated = metrics::calculate_episode_metrics(input);
  if (!calculated.ok()) throw std::runtime_error("Step 20 validation metric calculation failed");
  const auto audit = metrics::audit_episode_metrics(input, *calculated.metrics);
  if (!audit.passed) throw std::runtime_error("Step 20 validation metric audit failed");
  result.metrics = *calculated.metrics;
  return result;
}

std::string decimal(long double value) {
  std::ostringstream out;
  out << std::fixed << std::setprecision(12) << value;
  return out.str();
}

void emit_string_array(std::ostringstream& out, const std::vector<std::string>& values) {
  out << '[';
  for (std::size_t i=0U;i<values.size();++i) { if (i) out << ','; out << '"' << values[i] << '"'; }
  out << ']';
}
}

int main() {
  strategies::QueueAwareHeuristicPolicy heuristic{model::StrategyId{"queue-aware-heuristic"},
      {calibration(), {1U,4U}, {1U,2U}, model::TickOffset{0}, 0.15L, 0.45L, 150, "step20-queue-aware-v1"}};
  auto mpc_params = strategies::MpcParameters{calibration(), 4U, {{1U,4U},{1U,2U},{1U,1U}}, model::TickOffset{0}, {1U,2U},
      1.0L, 200.0L, 10.0L, "step20-non-ml-mpc-v1"};
  strategies::NonMlMpcPolicy mpc{model::StrategyId{"non-ml-mpc"}, mpc_params};
  const auto heuristic_result = run_policy(heuristic, environment("queue-aware-heuristic"), false);
  const auto mpc_result = run_policy(mpc, environment("non-ml-mpc"), true);

  const auto early_obs = make_observation(environment("oracle-early"), MarketStep{1'000,98,102,10U,200U,true}, 0U, 1U);
  const auto late_obs = make_observation(environment("oracle-late"), MarketStep{1'900,99,101,500U,10U,false}, 0U, 2U);
  const auto early = strategies::solve_non_ml_mpc(early_obs, mpc_params);
  const auto late = strategies::solve_non_ml_mpc(late_obs, mpc_params);

  std::ostringstream body;
  body << '{';
  body << "\"evidence_status\":\"synthetic_validation_only_non_research\",";
  body << "\"gate_d_status\":\"engineering_pass_research_activation_requires_gate_c\",";
  body << "\"historical_exact_queue_used\":false,";
  body << "\"ml_or_learned_signal_used\":false,";
  body << "\"calibration_cutoff_ns\":999,";
  body << "\"calibration_provenance\":\"step20-synthetic-calibration-v1\",";
  body << "\"mpc_model\":\"finite_horizon_expected_cost_frozen_observation_receding_horizon\",";
  body << "\"mpc_early_oracle\":{\"mode\":\"" << strategies::to_string(early.mode) << "\",\"objective_bps\":\"" << decimal(early.objective_bps)
       << "\",\"passive_fill_probability\":\"" << decimal(early.signals.passive_fill_probability) << "\",\"nodes\":" << early.evaluated_plan_nodes << "},";
  body << "\"mpc_late_oracle\":{\"mode\":\"" << strategies::to_string(late.mode) << "\",\"objective_bps\":\"" << decimal(late.objective_bps)
       << "\",\"passive_fill_probability\":\"" << decimal(late.signals.passive_fill_probability) << "\",\"nodes\":" << late.evaluated_plan_nodes << "},";
  body << "\"queue_aware_heuristic\":{\"actions\":"; emit_string_array(body, heuristic_result.actions);
  body << ",\"implementation_shortfall_bps\":" << *heuristic_result.metrics.implementation_shortfall_bps << ",\"complete\":" << (heuristic_result.metrics.complete?"true":"false") << "},";
  body << "\"non_ml_mpc\":{\"actions\":"; emit_string_array(body, mpc_result.actions);
  body << ",\"diagnostics\":"; emit_string_array(body, mpc_result.diagnostics);
  body << ",\"implementation_shortfall_bps\":" << *mpc_result.metrics.implementation_shortfall_bps << ",\"complete\":" << (mpc_result.metrics.complete?"true":"false") << "}";
  body << '}';
  const auto canonical = body.str();
  std::cout << "{\"payload\":" << canonical << ",\"sha256\":\"" << util::sha256_hex(canonical) << "\"}\n";
}
