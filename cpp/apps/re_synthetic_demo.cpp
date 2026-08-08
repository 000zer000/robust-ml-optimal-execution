#include "robust_execution/synthetic/synthetic.hpp"

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {
namespace model = robust_execution::model;
namespace synthetic = robust_execution::synthetic;

model::InstrumentDefinition instrument() {
  return model::InstrumentDefinition{
      model::kEventSchemaVersion,
      model::VenueId{"synthetic"},
      model::InstrumentId{"DEMO-USD"},
      "DEMO",
      "USD",
      model::RationalIncrement{1U, 100U},
      model::RationalIncrement{1U, 1000U},
      model::RationalIncrement{1U, 100U},
      model::QuantityLots{1U},
      model::QuantityLots{1000U},
      "step9-demo-v1",
  };
}

synthetic::SyntheticMarketConfig config() {
  const synthetic::RegimeConfig normal{
      "normal",
      synthetic::ScenarioClass::DesignedSynthetic,
      120U,
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
  auto stressed = normal;
  stressed.regime_id = "thin-high-vol";
  stressed.scenario_class = synthetic::ScenarioClass::AdversarialStress;
  stressed.steps = 80U;
  stressed.target_lots_per_level = 4U;
  stressed.market_order_probability_ppm = 400'000U;
  stressed.reference_move_probability_ppm = 220'000U;
  return synthetic::SyntheticMarketConfig{
      "synthetic-market-config-v1",
      "step9-demo-adversarial",
      synthetic::ScenarioClass::AdversarialStress,
      instrument(),
      model::RunId{"step9-demo-run"},
      20260806U,
      model::TimestampNs{model::ClockDomain::Simulation, 0},
      100'000,
      model::PriceTicks{10'000},
      {normal, stressed},
      {synthetic::ShockConfig{
          "liquidity-vacuum",
          synthetic::ScenarioClass::AdversarialStress,
          140U,
          30U,
          250'000U,
          2'500'000U,
          3'000'000U,
          2'000'000U,
          2'500'000U,
          150'000,
          -25,
      }},
      synthetic::FeeScheduleConfig{
          model::FeeScheduleId{"synthetic-fees-v1"},
          model::QuoteAtoms{-1},
          model::QuoteAtoms{3},
      },
      1U,
      1U,
  };
}
}  // namespace

int main(int argc, char** argv) {
  const auto tape = synthetic::SyntheticMarketGenerator{config()}.generate();
  if (argc == 3 && std::string{argv[1]} == "--output-dir") {
    const std::filesystem::path output_dir{argv[2]};
    std::filesystem::create_directories(output_dir);
    std::ofstream tape_file{output_dir / "tape.txt", std::ios::binary | std::ios::trunc};
    std::ofstream manifest_file{output_dir / "manifest.json", std::ios::binary | std::ios::trunc};
    if (!tape_file || !manifest_file) {
      throw std::runtime_error("failed to create synthetic demo artifacts");
    }
    tape_file << tape.canonical_text;
    manifest_file << tape.manifest_json << '\n';
  } else if (argc != 1) {
    std::cerr << "usage: robust_execution_synthetic_demo [--output-dir PATH]\n";
    return EXIT_FAILURE;
  }
  std::cout << "step=9\n"
            << "scenario_id=" << tape.config.scenario_id << '\n'
            << "scenario_class=" << synthetic::to_string(tape.config.scenario_class) << '\n'
            << "calibration_status=not_calibrated_step9\n"
            << "total_steps=" << tape.summary.total_steps << '\n'
            << "actions=" << tape.actions.size() << '\n'
            << "trades=" << tape.summary.trades << '\n'
            << "executed_lots=" << tape.summary.executed_lots.value() << '\n'
            << "shocks_applied=" << tape.summary.shocks_applied << '\n'
            << "rejected_commands=" << tape.summary.rejected_commands << '\n'
            << "final_reference_ticks=" << tape.summary.final_reference_price.value() << '\n'
            << "final_best_bid_ticks="
            << (tape.summary.final_best_bid.has_value() ? tape.summary.final_best_bid->value() : 0)
            << '\n'
            << "final_best_ask_ticks="
            << (tape.summary.final_best_ask.has_value() ? tape.summary.final_best_ask->value() : 0)
            << '\n'
            << "tape_sha256=" << tape.tape_sha256 << '\n'
            << "manifest_sha256=" << tape.manifest_sha256 << '\n';
  return EXIT_SUCCESS;
}
