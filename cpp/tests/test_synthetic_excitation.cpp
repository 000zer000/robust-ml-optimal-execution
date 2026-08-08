#include "synthetic_test_support.hpp"

#include <cstdlib>

int main() {
  using namespace synthetic_test;
  auto independent = config(99U);
  independent.scenario_id = "independent-grid";
  independent.regimes[0].steps = 400U;
  independent.regimes[0].limit_add_probability_ppm = 80'000U;
  independent.regimes[0].market_order_probability_ppm = 0U;
  independent.regimes[0].cancel_probability_ppm = 0U;
  independent.regimes[0].reference_move_probability_ppm = 0U;
  independent.regimes[0].excitation_increment_ppm = 0U;
  independent.regimes[0].excitation_cap_ppm = 0U;

  auto clustered = independent;
  clustered.scenario_id = "self-exciting-grid";
  clustered.regimes[0].excitation_increment_ppm = 350'000U;
  clustered.regimes[0].excitation_decay_ppm = 800'000U;
  clustered.regimes[0].excitation_cap_ppm = 850'000U;

  const auto independent_tape = synthetic::SyntheticMarketGenerator{independent}.generate();
  const auto clustered_tape = synthetic::SyntheticMarketGenerator{clustered}.generate();
  if (independent_tape.summary.limit_submissions >= clustered_tape.summary.limit_submissions ||
      clustered_tape.summary.limit_submissions < independent_tape.summary.limit_submissions * 3U) {
    return EXIT_FAILURE;
  }
  bool saw_positive_excitation = false;
  for (const auto& step : clustered_tape.steps) {
    if (step.limit_excitation_ppm > clustered.regimes[0].excitation_cap_ppm) {
      return EXIT_FAILURE;
    }
    saw_positive_excitation = saw_positive_excitation || step.limit_excitation_ppm > 0U;
  }
  return saw_positive_excitation ? EXIT_SUCCESS : EXIT_FAILURE;
}
