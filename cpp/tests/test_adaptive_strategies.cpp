#include "robust_execution/policy/action.hpp"
#include "robust_execution/policy/state.hpp"
#include "robust_execution/strategies/adaptive.hpp"

#include <cmath>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <vector>

using namespace robust_execution;

namespace {
void require(bool condition, const char* message) {
  if (!condition) { std::cerr << message << '\n'; std::exit(1); }
}
model::TimestampNs t(std::int64_t value) { return {model::ClockDomain::Simulation, value}; }

model::InstrumentDefinition instrument() {
  return {model::kEventSchemaVersion, model::VenueId{"synthetic"}, model::InstrumentId{"ADAPT-USD"}, "ADAPT", "USD",
          model::RationalIncrement{1U,1U}, model::RationalIncrement{1U,1U}, model::RationalIncrement{1U,1U},
          model::QuantityLots{1U}, model::QuantityLots{1'000'000U}, "step20-v1"};
}
policy::ParentOrderDefinition parent() {
  return {model::ParentOrderId{20U}, model::Side::Buy, model::QuantityLots{100U}, t(1'000), t(2'000), model::PriceTicks{100}, "hard-completion-v1"};
}
policy::PolicyEnvironment environment(const char* strategy) {
  return {instrument(), model::StrategyId{strategy}, model::FeeScheduleId{"synthetic-fees"}, model::LatencyModelId{"zero-latency"},
          250, 5U, 16U, 1U, 1U,
          {policy::QuantityFraction{1U,4U}, policy::QuantityFraction{1U,2U}, policy::QuantityFraction{1U,1U}},
          {model::TickOffset{0}}, policy::LotRoundingPolicy::Floor, true, true, true};
}
strategies::NonMlCalibration calibration() {
  return {t(999), "step20-synthetic-calibration-v1", -0.20L, 1.00L, 0.50L, 0.45L, 0.35L, 1.0L, 25.0L};
}
policy::ParentOrderSnapshot snapshot(std::int64_t now, std::uint64_t filled) {
  return {model::ParentOrderId{20U}, model::Side::Buy, t(1'000), t(2'000), model::PriceTicks{100}, "hard-completion-v1",
          model::QuantityLots{100U}, model::QuantityLots{filled}, model::QuantityLots{100U-filled},
          model::QuoteAtoms{0}, model::QuoteAtoms{0}, model::QuoteAtoms{0}, 0U,
          now >= 2'000 ? policy::ParentOrderStatus::TerminalCompletionPending : policy::ParentOrderStatus::Active, false};
}
policy::PolicyObservation observation(
    const policy::PolicyEnvironment& env,
    std::int64_t now,
    std::uint64_t filled,
    std::uint64_t bid_qty,
    std::uint64_t ask_qty,
    std::int64_t bid_price,
    std::int64_t ask_price,
    bool favorable_trades,
    std::vector<policy::ChildOrderView> active = {}
) {
  std::vector<policy::ObservedTrade> trades;
  const auto aggressor = favorable_trades ? model::AggressorSide::Sell : model::AggressorSide::Buy;
  trades.push_back({model::Trade{model::TradeId{1U}, std::nullopt, model::PriceTicks{100}, model::QuantityLots{80U}, aggressor}, t(now-2), t(now-1)});
  trades.push_back({model::Trade{model::TradeId{2U}, std::nullopt, model::PriceTicks{100}, model::QuantityLots{20U}, favorable_trades ? model::AggressorSide::Buy : model::AggressorSide::Sell}, t(now-2), t(now-1)});
  return {model::DecisionId{static_cast<std::uint64_t>(now)}, t(now), t(now), env, snapshot(now, filled),
          {{model::PriceTicks{bid_price}, model::QuantityLots{bid_qty}, std::nullopt}},
          {{model::PriceTicks{ask_price}, model::QuantityLots{ask_qty}, std::nullopt}},
          std::move(trades), std::move(active), 0U, {}};
}
}

int main() {
  {
    const auto env = environment("signals");
    const auto obs = observation(env, 1'000, 0U, 20U, 100U, 99, 101, true);
    const auto signals = strategies::calculate_adaptive_signals(obs, calibration());
    require(std::abs(signals.midpoint_ticks - 100.0L) < 1e-15L, "adaptive midpoint oracle failed");
    require(std::abs(signals.spread_ticks - 2.0L) < 1e-15L, "adaptive spread oracle failed");
    require(std::abs(signals.passive_fill_pressure - 0.8L) < 1e-15L, "adaptive trade-pressure oracle failed");
    require(signals.passive_fill_probability > 0.70L, "favorable queue/trade state should imply high rule-based passive fill probability");
    require(std::abs(signals.progress_lag) < 1e-15L, "initial progress lag must be zero");
  }

  {
    const auto env = environment("heuristic");
    strategies::QueueAwareHeuristicParameters params{calibration(), {1U,4U}, {1U,2U}, model::TickOffset{0}, 0.15L, 0.45L, 150, "queue-aware-v1"};
    strategies::QueueAwareHeuristicPolicy strategy{model::StrategyId{"heuristic"}, params};
    strategy.reset(parent(), env);
    const auto early = observation(env, 1'000, 0U, 20U, 100U, 99, 101, true);
    const auto early_action = strategy.on_observation(early);
    const auto* passive = std::get_if<policy::SubmitChildAction>(&early_action.payload);
    require(passive != nullptr, "queue-aware heuristic should submit under favorable early state");
    require(passive->order_type == model::OrderType::Limit && passive->post_only, "queue-aware early action must be passive post-only");
    require((passive->quantity_fraction == policy::QuantityFraction{1U,4U}), "queue-aware passive fraction mismatch");

    const auto late = observation(env, 1'850, 0U, 500U, 10U, 99, 101, false);
    const auto late_action = strategy.on_observation(late);
    const auto* aggressive = std::get_if<policy::SubmitChildAction>(&late_action.payload);
    require(aggressive != nullptr, "queue-aware heuristic should submit when badly behind schedule");
    require(aggressive->order_type == model::OrderType::Market, "queue-aware late action must be aggressive");
    auto terminal_snap = snapshot(2'000, 50U);
    terminal_snap.status = policy::ParentOrderStatus::TerminalCompletionPending;
    policy::PolicyObservation terminal_obs{model::DecisionId{9999U}, t(2'000), t(2'000), env, terminal_snap,
        {{model::PriceTicks{99}, model::QuantityLots{100U}, std::nullopt}}, {{model::PriceTicks{101}, model::QuantityLots{100U}, std::nullopt}}, {}, {}, 0U, {}};
    const auto terminal_action = strategy.on_observation(terminal_obs);
    require(std::holds_alternative<policy::NoAction>(terminal_action.payload), "terminal completion must remain owned by the Step 8 terminal layer");
  }

  {
    const auto env = environment("heuristic-active");
    strategies::QueueAwareHeuristicPolicy strategy{model::StrategyId{"heuristic-active"},
        {calibration(), {1U,4U}, {1U,2U}, model::TickOffset{0}, 0.15L, 0.45L, 150, "queue-aware-active-v1"}};
    strategy.reset(parent(), env);
    policy::ChildOrderView child{model::ParentOrderId{20U}, model::ClientOrderId{7U}, model::ExchangeOrderId{7U}, model::DecisionId{1U}, model::Side::Buy,
        model::OrderType::Limit, model::TimeInForce::GoodTilCancelled, model::QuantityLots{25U}, model::QuantityLots{0U}, model::QuantityLots{25U},
        model::PriceTicks{98}, true, model::OrderState::Live, false, false};
    const auto obs = observation(env, 1'200, 10U, 20U, 100U, 99, 101, true, {child});
    const auto action = strategy.on_observation(obs);
    const auto* cancel = std::get_if<policy::CancelChildAction>(&action.payload);
    require(cancel != nullptr && cancel->client_order_ids.size() == 1U, "stale passive child must be cancelled for repricing");
  }

  {
    auto params = strategies::MpcParameters{calibration(), 4U,
        {{1U,4U},{1U,2U},{1U,1U}}, model::TickOffset{0}, {1U,2U}, 1.0L, 200.0L, 10.0L, "mpc-v1"};
    const auto early_env = environment("mpc-early");
    const auto early = observation(early_env, 1'000, 0U, 10U, 200U, 98, 102, true);
    const auto early_decision = strategies::solve_non_ml_mpc(early, params);
    require(early_decision.mode == strategies::AdaptiveActionMode::Passive, "MPC should exploit a high-fill wide-spread early passive opportunity");
    require(early_decision.fraction.has_value(), "MPC passive action must carry a fraction");
    require(early_decision.planning_horizon_steps_used == 4U, "MPC must use the configured receding horizon early in episode");
    require(early_decision.evaluated_plan_nodes > 4U, "MPC must evaluate a multi-step action tree");

    const auto late_env = environment("mpc-late");
    const auto late = observation(late_env, 1'900, 0U, 500U, 10U, 99, 101, false);
    const auto late_decision = strategies::solve_non_ml_mpc(late, params);
    require(late_decision.mode == strategies::AdaptiveActionMode::Aggressive, "MPC should choose aggressive execution when late with low passive fill probability");
    require(late_decision.planning_horizon_steps_used == 1U, "MPC horizon must shrink near terminal time");
    require(std::isfinite(late_decision.objective_bps), "MPC objective must be finite");
  }

  {
    auto params = strategies::MpcParameters{calibration(), 3U,
        {{1U,4U},{1U,2U},{1U,1U}}, model::TickOffset{0}, {1U,2U}, 1.0L, 40.0L, 10.0L, "mpc-policy-v1"};
    const auto env = environment("mpc-policy");
    strategies::NonMlMpcPolicy strategy{model::StrategyId{"mpc-policy"}, params};
    strategy.reset(parent(), env);
    const auto obs = observation(env, 1'000, 0U, 10U, 200U, 98, 102, true);
    const auto action = strategy.on_observation(obs);
    require(std::holds_alternative<policy::SubmitChildAction>(action.payload), "MPC policy must translate its chosen control into the shared action contract");

    policy::ExecutionState state{parent(), env};
    const auto state_snapshot = state.parent_snapshot(t(1'000));
    policy::PolicyObservation state_obs{model::DecisionId{1000U}, t(1'000), t(1'000), env, state_snapshot,
        {{model::PriceTicks{98}, model::QuantityLots{10U}, std::nullopt}}, {{model::PriceTicks{102}, model::QuantityLots{200U}, std::nullopt}}, {}, {}, 0U, {}};
    const auto state_action = strategy.on_observation(state_obs);
    policy::ActionValidator validator{env};
    const auto validated = validator.validate(state_action, state_obs, state);
    require(validated.valid(), "MPC action must pass the common Step 8 action validator");
  }

  {
    bool rejected_leak = false;
    try {
      auto bad = strategies::MpcParameters{calibration(), 4U, {{1U,1U}}, model::TickOffset{0}, {1U,2U}, 1.0L, 10.0L, 1.0L, "bad"};
      bad.calibration.calibration_cutoff = t(1'000);
      const auto env = environment("bad-mpc");
      strategies::NonMlMpcPolicy strategy{model::StrategyId{"bad-mpc"}, bad};
      strategy.reset(parent(), env);
    } catch (const std::invalid_argument&) { rejected_leak = true; }
    require(rejected_leak, "MPC leaked calibration cutoff must be rejected");

    bool rejected_direct_leak = false;
    try {
      auto bad = strategies::MpcParameters{calibration(), 4U, {{1U,1U}}, model::TickOffset{0}, {1U,2U}, 1.0L, 10.0L, 1.0L, "bad-direct-leak"};
      bad.calibration.calibration_cutoff = t(1'000);
      const auto obs = observation(environment("bad-direct-leak"), 1'000, 0U, 10U, 10U, 99, 101, true);
      (void)strategies::solve_non_ml_mpc(obs, bad);
    } catch (const std::invalid_argument&) { rejected_direct_leak = true; }
    require(rejected_direct_leak, "direct MPC solver must reject leaked calibration cutoff");

    bool rejected_noncanonical = false;
    try {
      auto bad = strategies::MpcParameters{calibration(), 4U, {{2U,4U},{1U,1U}}, model::TickOffset{0}, {1U,2U}, 1.0L, 10.0L, 1.0L, "bad-fraction"};
      const auto obs = observation(environment("bad-fraction"), 1'000, 0U, 10U, 10U, 99, 101, true);
      (void)strategies::solve_non_ml_mpc(obs, bad);
    } catch (const std::invalid_argument&) { rejected_noncanonical = true; }
    require(rejected_noncanonical, "MPC non-canonical equivalent fractions must be rejected");

    bool rejected_nan = false;
    try {
      auto bad = strategies::MpcParameters{calibration(), 4U, {{1U,1U}}, model::TickOffset{0}, {1U,2U}, std::numeric_limits<long double>::quiet_NaN(), 10.0L, 1.0L, "bad-nan"};
      const auto obs = observation(environment("bad-nan"), 1'000, 0U, 10U, 10U, 99, 101, true);
      (void)strategies::solve_non_ml_mpc(obs, bad);
    } catch (const std::invalid_argument&) { rejected_nan = true; }
    require(rejected_nan, "MPC non-finite costs must be rejected");
  }

  {
    auto sell_parent = parent();
    sell_parent.side = model::Side::Sell;
    auto env = environment("sell-heuristic");
    strategies::QueueAwareHeuristicPolicy strategy{model::StrategyId{"sell-heuristic"},
        {calibration(), {1U,4U}, {1U,2U}, model::TickOffset{0}, 0.15L, 0.45L, 150, "sell-heuristic-v1"}};
    strategy.reset(sell_parent, env);
    auto snap = snapshot(1'000, 0U);
    snap.side = model::Side::Sell;
    std::vector<policy::ObservedTrade> trades{
      {model::Trade{model::TradeId{11U}, std::nullopt, model::PriceTicks{100}, model::QuantityLots{80U}, model::AggressorSide::Buy}, t(998), t(999)},
      {model::Trade{model::TradeId{12U}, std::nullopt, model::PriceTicks{100}, model::QuantityLots{20U}, model::AggressorSide::Sell}, t(998), t(999)}};
    policy::PolicyObservation obs{model::DecisionId{2000U}, t(1'000), t(1'000), env, snap,
        {{model::PriceTicks{99}, model::QuantityLots{200U}, std::nullopt}}, {{model::PriceTicks{101}, model::QuantityLots{10U}, std::nullopt}},
        std::move(trades), {}, 0U, {}};
    const auto action = strategy.on_observation(obs);
    const auto* submit = std::get_if<policy::SubmitChildAction>(&action.payload);
    require(submit != nullptr && submit->order_type == model::OrderType::Limit, "sell-side favorable passive state must be handled symmetrically");
  }

  return 0;
}
