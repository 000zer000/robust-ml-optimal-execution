#pragma once

#include "robust_execution/synthetic/synthetic.hpp"

namespace synthetic_test {

namespace model = robust_execution::model;
namespace synthetic = robust_execution::synthetic;

inline model::InstrumentDefinition instrument() {
  return model::InstrumentDefinition{
      model::kEventSchemaVersion,
      model::VenueId{"synthetic"},
      model::InstrumentId{"SYN-USD"},
      "SYN",
      "USD",
      model::RationalIncrement{1U, 100U},
      model::RationalIncrement{1U, 1000U},
      model::RationalIncrement{1U, 100U},
      model::QuantityLots{1U},
      model::QuantityLots{1'000U},
      "synthetic-test-v1",
  };
}

inline synthetic::RegimeConfig normal_regime(std::uint64_t steps = 120U) {
  return synthetic::RegimeConfig{
      "normal",
      synthetic::ScenarioClass::DesignedSynthetic,
      steps,
      420'000U,
      210'000U,
      160'000U,
      90'000U,
      500'000U,
      80'000U,
      750'000U,
      300'000U,
      450'000U,
      2U,
      5U,
      12U,
      1U,
      5U,
      2U,
      90'000,
      850'000U,
  };
}

inline synthetic::SyntheticMarketConfig config(std::uint64_t seed = 20260806U) {
  return synthetic::SyntheticMarketConfig{
      "synthetic-market-config-v1",
      "step9-test-normal",
      synthetic::ScenarioClass::DesignedSynthetic,
      instrument(),
      model::RunId{"step9-test-run"},
      seed,
      model::TimestampNs{model::ClockDomain::Simulation, 0},
      100'000,
      model::PriceTicks{10'000},
      {normal_regime()},
      {},
      synthetic::FeeScheduleConfig{
          model::FeeScheduleId{"synthetic-fees-v1"},
          model::QuoteAtoms{-1},
          model::QuoteAtoms{3},
      },
      1U,
      1U,
  };
}

inline synthetic::SyntheticMarketConfig stress_config(std::uint64_t seed = 20260806U) {
  auto result = config(seed);
  result.scenario_id = "step9-test-adversarial";
  result.scenario_class = synthetic::ScenarioClass::AdversarialStress;
  result.regimes = {normal_regime(80U), normal_regime(80U)};
  result.regimes[1].regime_id = "thin-high-vol";
  result.regimes[1].scenario_class = synthetic::ScenarioClass::AdversarialStress;
  result.regimes[1].target_lots_per_level = 4U;
  result.regimes[1].market_order_probability_ppm = 400'000U;
  result.regimes[1].reference_move_probability_ppm = 220'000U;
  result.shocks = {
      synthetic::ShockConfig{
          "liquidity-vacuum",
          synthetic::ScenarioClass::AdversarialStress,
          90U,
          30U,
          250'000U,
          2'500'000U,
          3'000'000U,
          2'000'000U,
          2'500'000U,
          150'000,
          -25,
      },
  };
  return result;
}

}  // namespace synthetic_test
