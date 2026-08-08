#include "synthetic_test_support.hpp"

#include <cstdlib>

int main() {
  using namespace synthetic_test;
  const auto tape = synthetic::SyntheticMarketGenerator{stress_config()}.generate();
  if (tape.summary.total_steps != 160U || tape.summary.shocks_applied != 1U) {
    return EXIT_FAILURE;
  }
  bool saw_shock = false;
  bool saw_second_regime = false;
  for (const auto& action : tape.actions) {
    if (action.kind == synthetic::SyntheticActionKind::ShockApplied &&
        action.shock_id == std::optional<std::string>{"liquidity-vacuum"}) {
      saw_shock = true;
      if (!action.price.has_value() || action.price->value() >= 10'000) {
        return EXIT_FAILURE;
      }
    }
    if (action.regime_id == "thin-high-vol") {
      saw_second_regime = true;
    }
  }
  if (!saw_shock || !saw_second_regime ||
      tape.manifest_json.find("adversarial_stress") == std::string::npos) {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
