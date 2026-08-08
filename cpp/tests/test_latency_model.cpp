#include "simulation_test_support.hpp"

#include <cstdlib>
#include <limits>
#include <stdexcept>

int main() {
  namespace simulation = robust_execution::simulation;
  const simulation::LatencyModel fixed{17U, simulation_test::fixed_latency()};
  const auto observation = fixed.observation_timing(simulation_test::time(100), 1U);
  if (observation.receive_time.value() != 105 || observation.available_time.value() != 108) {
    return EXIT_FAILURE;
  }
  const auto action = fixed.action_timing(simulation_test::time(200), 2U);
  if (action.decision_end.value() != 202 || action.outbound_send.value() != 202 ||
      action.exchange_receive.value() != 206 || action.exchange_process.value() != 209 ||
      action.acknowledgement_send.value() != 209 ||
      action.acknowledgement_receive.value() != 214 ||
      action.acknowledgement_available.value() != 216) {
    return EXIT_FAILURE;
  }

  auto ranged = simulation_test::fixed_latency();
  ranged.market_data_network = simulation::LatencyRangeNs{2, 9, 100U};
  ranged.observation_processing = simulation::LatencyRangeNs{1, 4, 101U};
  const simulation::LatencyModel first{42U, ranged};
  const simulation::LatencyModel second{42U, ranged};
  for (std::uint64_t index = 0U; index < 100U; ++index) {
    const auto lhs = first.sample_observation(index);
    const auto rhs = second.sample_observation(index);
    if (lhs.network_ns != rhs.network_ns || lhs.processing_ns != rhs.processing_ns ||
        lhs.network_ns < 2 || lhs.network_ns > 9 || lhs.processing_ns < 1 ||
        lhs.processing_ns > 4) {
      return EXIT_FAILURE;
    }
  }

  bool invalid_range = false;
  bool empty_id = false;
  bool overflow = false;
  try {
    auto bad = ranged;
    bad.outbound_network = simulation::LatencyRangeNs{5, 4, 1U};
    (void)simulation::LatencyModel{1U, bad};
  } catch (const std::invalid_argument&) {
    invalid_range = true;
  }
  try {
    auto bad = ranged;
    bad.model_id.clear();
    (void)simulation::LatencyModel{1U, bad};
  } catch (const std::invalid_argument&) {
    empty_id = true;
  }
  try {
    (void)simulation::checked_add_duration(
        simulation_test::time(std::numeric_limits<std::int64_t>::max()),
        1
    );
  } catch (const std::overflow_error&) {
    overflow = true;
  }
  return invalid_range && empty_id && overflow ? EXIT_SUCCESS : EXIT_FAILURE;
}
