#include "robust_execution/policy/action.hpp"
#include "robust_execution/policy/state.hpp"
#include "robust_execution/strategies/adaptive.hpp"

#include <cmath>
#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <vector>

using namespace robust_execution;

namespace {
void require(bool condition, const char* message) {
  if (!condition) {
    std::cerr << message << '\n';
    std::exit(1);
  }
}

model::TimestampNs t(std::int64_t value) {
  return {model::ClockDomain::Simulation, value};
}

model::InstrumentDefinition instrument() {
  return {
      model::kEventSchemaVersion,
      model::VenueId{"synthetic"},
      model::InstrumentId{"MLMPC-USD"},
      "MLMPC",
      "USD",
      model::RationalIncrement{1U, 1U},
      model::RationalIncrement{1U, 1U},
      model::RationalIncrement{1U, 1U},
      model::QuantityLots{1U},
      model::QuantityLots{1'000'000U},
      "step24-v1",
  };
}

policy::ParentOrderDefinition parent() {
  return {
      model::ParentOrderId{24U},
      model::Side::Buy,
      model::QuantityLots{100U},
      t(1'000),
      t(2'000),
      model::PriceTicks{100},
      "hard-completion-v1",
  };
}

policy::PolicyEnvironment environment(const char* strategy) {
  return {
      instrument(),
      model::StrategyId{strategy},
      model::FeeScheduleId{"synthetic-fees"},
      model::LatencyModelId{"zero-latency"},
      250,
      5U,
      16U,
      1U,
      1U,
      {
          policy::QuantityFraction{1U, 4U},
          policy::QuantityFraction{1U, 2U},
          policy::QuantityFraction{1U, 1U},
      },
      {model::TickOffset{0}},
      policy::LotRoundingPolicy::Floor,
      true,
      true,
      true,
  };
}

strategies::NonMlCalibration calibration() {
  return {
      t(999),
      "step24-shared-non-ml-calibration-v1",
      0.0L,
      0.0L,
      0.50L,
      0.45L,
      0.35L,
      1.0L,
      25.0L,
  };
}

strategies::MpcParameters base_parameters() {
  return {
      calibration(),
      4U,
      {{1U, 4U}, {1U, 2U}, {1U, 1U}},
      model::TickOffset{0},
      {1U, 2U},
      1.0L,
      200.0L,
      10.0L,
      "step20-non-ml-mpc-v1",
  };
}

policy::ParentOrderSnapshot snapshot(std::int64_t now, std::uint64_t filled) {
  return {
      model::ParentOrderId{24U},
      model::Side::Buy,
      t(1'000),
      t(2'000),
      model::PriceTicks{100},
      "hard-completion-v1",
      model::QuantityLots{100U},
      model::QuantityLots{filled},
      model::QuantityLots{100U - filled},
      model::QuoteAtoms{0},
      model::QuoteAtoms{0},
      model::QuoteAtoms{0},
      0U,
      now >= 2'000 ? policy::ParentOrderStatus::TerminalCompletionPending
                   : policy::ParentOrderStatus::Active,
      false,
  };
}

policy::PolicyObservation observation(
    const policy::PolicyEnvironment& env,
    std::int64_t now,
    std::uint64_t filled,
    std::int64_t bid,
    std::int64_t ask,
    std::uint64_t bid_quantity,
    std::uint64_t ask_quantity,
    bool favorable_flow,
    std::uint64_t decision_id = 1U
) {
  const auto first = favorable_flow ? model::AggressorSide::Sell : model::AggressorSide::Buy;
  const auto second = favorable_flow ? model::AggressorSide::Buy : model::AggressorSide::Sell;
  std::vector<policy::ObservedTrade> trades{
      {
          model::Trade{
              model::TradeId{decision_id * 2U - 1U},
              std::nullopt,
              model::PriceTicks{100},
              model::QuantityLots{80U},
              first,
          },
          t(now - 3),
          t(now - 2),
      },
      {
          model::Trade{
              model::TradeId{decision_id * 2U},
              std::nullopt,
              model::PriceTicks{100},
              model::QuantityLots{20U},
              second,
          },
          t(now - 3),
          t(now - 2),
      },
  };
  return {
      model::DecisionId{decision_id},
      t(now),
      t(now - 1),
      env,
      snapshot(now, filled),
      {{model::PriceTicks{bid}, model::QuantityLots{bid_quantity}, std::nullopt}},
      {{model::PriceTicks{ask}, model::QuantityLots{ask_quantity}, std::nullopt}},
      std::move(trades),
      {},
      0U,
      {},
  };
}

strategies::MpcPredictionInput prediction(
    const policy::PolicyObservation& obs,
    long double probability,
    long double base_rate,
    strategies::MpcPredictionKind kind = strategies::MpcPredictionKind::CalibratedModel
) {
  return {
      obs.decision_id(),
      obs.decision_time(),
      obs.observation_cutoff(),
      t(obs.decision_time().value() - 1),
      probability,
      base_rate,
      "5s",
      "causal_conv1d_lstm",
      "step23:5s:first-holdout-sequence",
      kind,
      std::nullopt,
  };
}

strategies::MlMpcParameters ml_parameters(long double weight) {
  return {
      base_parameters(),
      weight,
      "step24-precomputed-prediction-v1",
      "step24-ml-mpc-v1",
  };
}
}  // namespace

int main() {
  {
    const auto env = environment("shared-zero-weight");
    const auto obs = observation(env, 1'000, 0U, 98, 102, 20U, 200U, true);
    const auto non_ml = strategies::solve_non_ml_mpc(obs, base_parameters());
    const auto ml = strategies::solve_ml_mpc(
        obs, ml_parameters(0.0L), prediction(obs, 0.95L, 0.20L)
    );
    require(non_ml.mode == ml.mode, "zero prediction weight changed MPC mode");
    require(non_ml.fraction == ml.fraction, "zero prediction weight changed MPC fraction");
    require(non_ml.objective_bps == ml.objective_bps, "zero prediction weight changed objective");
    require(
        non_ml.passive_cost_bps == ml.passive_cost_bps,
        "zero prediction weight changed passive cost"
    );
    require(
        non_ml.evaluated_plan_nodes == ml.evaluated_plan_nodes,
        "zero prediction weight changed search tree"
    );
  }

  {
    const auto env = environment("base-rate-control");
    const auto obs = observation(env, 1'000, 0U, 98, 102, 20U, 200U, true);
    const auto non_ml = strategies::solve_non_ml_mpc(obs, base_parameters());
    const auto ml = strategies::solve_ml_mpc(
        obs,
        ml_parameters(1'000.0L),
        prediction(obs, 0.40L, 0.40L, strategies::MpcPredictionKind::TrainingBaseRate)
    );
    require(
        non_ml.mode == ml.mode && non_ml.fraction == ml.fraction,
        "base-rate control changed action"
    );
    require(non_ml.objective_bps == ml.objective_bps, "base-rate control changed objective");
    require(ml.prediction_adjustment_bps == 0.0L, "base-rate control must have zero adjustment");
  }

  {
    const auto env = environment("signal-sensitivity");
    const auto obs = observation(env, 1'000, 0U, 99, 100, 100U, 100U, true);
    const auto low = strategies::solve_ml_mpc(
        obs, ml_parameters(1'000.0L), prediction(obs, 0.0L, 0.5L)
    );
    const auto high = strategies::solve_ml_mpc(
        obs, ml_parameters(1'000.0L), prediction(obs, 1.0L, 0.5L)
    );
    require(
        low.mode == strategies::AdaptiveActionMode::Passive,
        "low depletion risk should preserve passive action"
    );
    require(
        high.mode != low.mode,
        "extreme prediction change must be capable of changing the MPC decision"
    );
    require(high.prediction_adjustment_bps == 500.0L, "prediction adjustment formula changed");
    require(
        low.prediction_adjustment_bps == -500.0L,
        "negative prediction adjustment formula changed"
    );
  }

  {
    const auto env = environment("causality");
    const auto obs = observation(env, 1'250, 0U, 99, 101, 100U, 100U, true, 2U);
    auto future_available = prediction(obs, 0.6L, 0.5L);
    future_available.available_time = t(1'251);
    bool rejected = false;
    try {
      (void)strategies::solve_ml_mpc(obs, ml_parameters(500.0L), future_available);
    } catch (const std::invalid_argument&) {
      rejected = true;
    }
    require(rejected, "future prediction availability must be rejected");

    auto future_feature = prediction(obs, 0.6L, 0.5L);
    future_feature.feature_cutoff_time = t(1'250);
    rejected = false;
    try {
      (void)strategies::solve_ml_mpc(obs, ml_parameters(500.0L), future_feature);
    } catch (const std::invalid_argument&) {
      rejected = true;
    }
    require(rejected, "prediction feature cutoff after observation cutoff must be rejected");

    auto wrong_decision = prediction(obs, 0.6L, 0.5L);
    wrong_decision.decision_id = model::DecisionId{3U};
    rejected = false;
    try {
      (void)strategies::solve_ml_mpc(obs, ml_parameters(500.0L), wrong_decision);
    } catch (const std::invalid_argument&) {
      rejected = true;
    }
    require(rejected, "prediction attached to the wrong decision must be rejected");
  }

  {
    const auto env = environment("stale-contract");
    const auto obs = observation(env, 1'250, 0U, 99, 101, 100U, 100U, true, 2U);
    auto stale = prediction(obs, 0.6L, 0.5L, strategies::MpcPredictionKind::Stale);
    bool rejected = false;
    try {
      (void)strategies::solve_ml_mpc(obs, ml_parameters(500.0L), stale);
    } catch (const std::invalid_argument&) {
      rejected = true;
    }
    require(rejected, "stale prediction without earlier source id must be rejected");
    stale.source_prediction_decision_id = model::DecisionId{1U};
    const auto accepted = strategies::solve_ml_mpc(obs, ml_parameters(500.0L), stale);
    require(accepted.prediction_kind == "stale", "valid stale ablation lost its audit kind");
  }

  {
    auto env = environment("ml-policy");
    const auto first_obs = observation(env, 1'000, 0U, 99, 101, 100U, 100U, true, 1U);
    auto first_prediction = prediction(first_obs, 0.55L, 0.50L);
    strategies::MlMpcPolicy policy{
        model::StrategyId{"ml-policy"},
        ml_parameters(500.0L),
        {first_prediction},
    };
    policy.reset(parent(), env);
    const auto action = policy.on_observation(first_obs);
    policy::ExecutionState state{parent(), env};
    policy::ActionValidator validator{env};
    const auto validated = validator.validate(action, first_obs, state);
    require(validated.valid(), "ML-MPC action must pass the common Step 8 action validator");

    const auto second_obs = observation(env, 1'250, 0U, 99, 101, 100U, 100U, true, 2U);
    bool rejected_missing = false;
    try {
      (void)policy.on_observation(second_obs);
    } catch (const std::logic_error&) {
      rejected_missing = true;
    }
    require(rejected_missing, "ML-MPC must fail closed when a prediction endpoint is missing");
  }

  {
    const auto env = environment("duplicate-tape");
    const auto obs = observation(env, 1'000, 0U, 99, 101, 100U, 100U, true, 1U);
    const auto p = prediction(obs, 0.5L, 0.5L);
    bool rejected = false;
    try {
      strategies::MlMpcPolicy policy{
          model::StrategyId{"duplicate-tape"},
          ml_parameters(500.0L),
          {p, p},
      };
      (void)policy;
    } catch (const std::invalid_argument&) {
      rejected = true;
    }
    require(rejected, "duplicate prediction endpoints must be rejected");
  }

  return 0;
}
