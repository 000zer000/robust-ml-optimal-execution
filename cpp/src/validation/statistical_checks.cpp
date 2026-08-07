#include "internal.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>

namespace robust_execution::validation::detail {
namespace model = robust_execution::model;
namespace synthetic = robust_execution::synthetic;

synthetic::SyntheticMarketConfig base_config(std::uint64_t seed) {
  const model::InstrumentDefinition instrument{
      model::kEventSchemaVersion,
      model::VenueId{"synthetic-validation"},
      model::InstrumentId{"VAL-USD"},
      "VAL",
      "USD",
      model::RationalIncrement{1U, 100U},
      model::RationalIncrement{1U, 1000U},
      model::RationalIncrement{1U, 100U},
      model::QuantityLots{1U},
      model::QuantityLots{10'000U},
      "step10-validation-v1",
  };
  const synthetic::RegimeConfig regime{
      "validation-normal",
      synthetic::ScenarioClass::DesignedSynthetic,
      256U,
      350'000U,
      180'000U,
      140'000U,
      80'000U,
      500'000U,
      60'000U,
      800'000U,
      250'000U,
      400'000U,
      2U,
      5U,
      12U,
      1U,
      5U,
      2U,
      75'000,
      850'000U,
  };
  return synthetic::SyntheticMarketConfig{
      "synthetic-market-config-v1",
      "step10-validation",
      synthetic::ScenarioClass::DesignedSynthetic,
      instrument,
      model::RunId{"step10-validation-run"},
      seed,
      model::TimestampNs{model::ClockDomain::Simulation, 0},
      100'000,
      model::PriceTicks{10'000},
      {regime},
      {},
      synthetic::FeeScheduleConfig{
          model::FeeScheduleId{"validation-fees-v1"},
          model::QuoteAtoms{-1},
          model::QuoteAtoms{3},
      },
      1U,
      1U,
  };
}

BatchAggregate run_batch(
    const synthetic::SyntheticMarketConfig& prototype,
    std::uint64_t first_seed,
    std::uint64_t seed_count
) {
  BatchAggregate aggregate;
  if (seed_count == 0U) {
    aggregate.valid = false;
    aggregate.failure = "seed_count must be positive";
    return aggregate;
  }
  long double market = 0.0L;
  long double limits = 0.0L;
  long double cancels = 0.0L;
  long double trades = 0.0L;
  long double executed = 0.0L;
  long double minimum_depth = 0.0L;
  long double average_depth = 0.0L;
  long double reference_move = 0.0L;

  for (std::uint64_t offset = 0U; offset < seed_count; ++offset) {
    auto config = prototype;
    config.random_seed = first_seed + offset;
    config.run_id = model::RunId{"step10-validation-run-" + std::to_string(offset)};
    const auto tape = synthetic::SyntheticMarketGenerator{config}.generate();
    const auto issues = synthetic::validate_tape(tape);
    if (synthetic::has_errors(issues)) {
      aggregate.valid = false;
      aggregate.failure = "validate_tape failed for seed offset " + std::to_string(offset);
      return aggregate;
    }
    if (tape.steps.empty()) {
      aggregate.valid = false;
      aggregate.failure = "generated tape contained no steps";
      return aggregate;
    }
    std::uint64_t seed_minimum = std::numeric_limits<std::uint64_t>::max();
    long double seed_depth = 0.0L;
    for (const auto& step : tape.steps) {
      const auto depth = step.visible_bid_lots.value() + step.visible_ask_lots.value();
      seed_minimum = std::min(seed_minimum, depth);
      seed_depth += static_cast<long double>(depth);
      if (step.best_bid.has_value() && step.best_ask.has_value() &&
          step.best_bid->value() >= step.best_ask->value()) {
        aggregate.valid = false;
        aggregate.failure = "crossed book detected in generated step";
        return aggregate;
      }
    }
    market += static_cast<long double>(tape.summary.market_submissions);
    limits += static_cast<long double>(tape.summary.limit_submissions);
    cancels += static_cast<long double>(tape.summary.cancellations);
    trades += static_cast<long double>(tape.summary.trades);
    executed += static_cast<long double>(tape.summary.executed_lots.value());
    minimum_depth += static_cast<long double>(seed_minimum);
    average_depth += seed_depth / static_cast<long double>(tape.steps.size());
    reference_move += static_cast<long double>(std::llabs(
        tape.summary.final_reference_price.value() - config.initial_reference_price.value()
    ));
    aggregate.total_steps += tape.summary.total_steps;
  }
  const auto denominator = static_cast<long double>(seed_count);
  aggregate.mean_market_submissions = static_cast<double>(market / denominator);
  aggregate.mean_limit_submissions = static_cast<double>(limits / denominator);
  aggregate.mean_cancellations = static_cast<double>(cancels / denominator);
  aggregate.mean_trades = static_cast<double>(trades / denominator);
  aggregate.mean_executed_lots = static_cast<double>(executed / denominator);
  aggregate.mean_minimum_visible_depth = static_cast<double>(minimum_depth / denominator);
  aggregate.mean_average_visible_depth = static_cast<double>(average_depth / denominator);
  aggregate.mean_absolute_reference_move = static_cast<double>(reference_move / denominator);
  return aggregate;
}

std::vector<DirectionalSensitivity> run_sensitivity_checks() {
  constexpr std::uint64_t kSeeds = 32U;
  constexpr std::uint64_t kFirstSeed = 91'000U;
  std::vector<DirectionalSensitivity> results;

  auto low_market = base_config(kFirstSeed);
  auto high_market = low_market;
  low_market.regimes.front().market_order_probability_ppm = 40'000U;
  high_market.regimes.front().market_order_probability_ppm = 500'000U;
  const auto low_market_batch = run_batch(low_market, kFirstSeed, kSeeds);
  const auto high_market_batch = run_batch(high_market, kFirstSeed, kSeeds);
  results.push_back(DirectionalSensitivity{
      "SENS-MARKET-ARRIVAL",
      "Increasing market-order probability increases generated aggressive submissions.",
      low_market_batch.mean_market_submissions,
      high_market_batch.mean_market_submissions,
      "treatment > control + 50",
      low_market_batch.valid && high_market_batch.valid &&
          high_market_batch.mean_market_submissions >
              low_market_batch.mean_market_submissions + 50.0,
  });

  auto shallow = base_config(kFirstSeed);
  auto deep = shallow;
  shallow.regimes.front().target_lots_per_level = 3U;
  shallow.regimes.front().maximum_order_lots = 3U;
  deep.regimes.front().target_lots_per_level = 30U;
  deep.regimes.front().maximum_order_lots = 8U;
  const auto shallow_batch = run_batch(shallow, kFirstSeed, kSeeds);
  const auto deep_batch = run_batch(deep, kFirstSeed, kSeeds);
  results.push_back(DirectionalSensitivity{
      "SENS-DEPTH",
      "Increasing target visible lots increases mean visible book depth.",
      shallow_batch.mean_average_visible_depth,
      deep_batch.mean_average_visible_depth,
      "treatment > 1.5 * control",
      shallow_batch.valid && deep_batch.valid &&
          deep_batch.mean_average_visible_depth >
              1.5 * shallow_batch.mean_average_visible_depth,
  });

  auto calm = base_config(kFirstSeed);
  auto volatile_config = calm;
  calm.regimes.front().reference_move_probability_ppm = 20'000U;
  calm.regimes.front().maximum_reference_jump_ticks = 1U;
  calm.regimes.front().impact_microticks_per_lot = 0;
  volatile_config.regimes.front().reference_move_probability_ppm = 450'000U;
  volatile_config.regimes.front().maximum_reference_jump_ticks = 5U;
  volatile_config.regimes.front().impact_microticks_per_lot = 300'000;
  const auto calm_batch = run_batch(calm, kFirstSeed, kSeeds);
  const auto volatile_batch = run_batch(volatile_config, kFirstSeed, kSeeds);
  results.push_back(DirectionalSensitivity{
      "SENS-VOLATILITY",
      "Increasing reference-move frequency, jump size and impact raises absolute terminal displacement.",
      calm_batch.mean_absolute_reference_move,
      volatile_batch.mean_absolute_reference_move,
      "treatment > control + 10 ticks",
      calm_batch.valid && volatile_batch.valid &&
          volatile_batch.mean_absolute_reference_move >
              calm_batch.mean_absolute_reference_move + 10.0,
  });

  auto no_shock = base_config(kFirstSeed);
  auto shock = no_shock;
  shock.scenario_class = synthetic::ScenarioClass::AdversarialStress;
  shock.scenario_id = "step10-liquidity-shock";
  shock.shocks = {synthetic::ShockConfig{
      "validation-liquidity-vacuum",
      synthetic::ScenarioClass::AdversarialStress,
      96U,
      64U,
      100'000U,
      2'500'000U,
      2'000'000U,
      2'500'000U,
      3'000'000U,
      0,
      0,
  }};
  const auto no_shock_batch = run_batch(no_shock, kFirstSeed, kSeeds);
  const auto shock_batch = run_batch(shock, kFirstSeed, kSeeds);
  results.push_back(DirectionalSensitivity{
      "SENS-LIQUIDITY-SHOCK",
      "A liquidity-vacuum shock lowers minimum visible depth.",
      no_shock_batch.mean_minimum_visible_depth,
      shock_batch.mean_minimum_visible_depth,
      "treatment < control",
      no_shock_batch.valid && shock_batch.valid &&
          shock_batch.mean_minimum_visible_depth < no_shock_batch.mean_minimum_visible_depth,
  });

  return results;
}

}  // namespace robust_execution::validation::detail
