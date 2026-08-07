#include "synthetic_test_support.hpp"

#include <cstdlib>
#include <stdexcept>

int main() {
  using namespace synthetic_test;
  auto valid = config();
  if (synthetic::has_errors(synthetic::validate(valid))) {
    return EXIT_FAILURE;
  }
  if (synthetic::canonical_config(valid).find("regime|normal|") == std::string::npos) {
    return EXIT_FAILURE;
  }

  auto invalid = valid;
  invalid.scenario_id.clear();
  invalid.grid_step_ns = 0;
  invalid.regimes[0].steps = 0U;
  invalid.regimes[0].buy_probability_ppm = 1'000'001U;
  invalid.regimes[0].maximum_order_lots = 0U;
  if (synthetic::validate(invalid).size() < 5U) {
    return EXIT_FAILURE;
  }
  try {
    const synthetic::SyntheticMarketGenerator generator{invalid};
    (void)generator;
    return EXIT_FAILURE;
  } catch (const std::invalid_argument&) {
  }

  auto wrong_class = valid;
  wrong_class.shocks.push_back(synthetic::ShockConfig{
      "stress", synthetic::ScenarioClass::AdversarialStress, 2U, 2U
  });
  if (!synthetic::has_errors(synthetic::validate(wrong_class))) {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
