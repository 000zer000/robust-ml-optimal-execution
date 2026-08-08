#include "robust_execution/simulation/logical_rng.hpp"

#include <array>
#include <cstdlib>
#include <stdexcept>

int main() {
  namespace simulation = robust_execution::simulation;
  const auto known = simulation::LogicalRandom::philox4x32_10({0U, 0U, 0U, 0U}, {0U, 0U});
  const std::array<std::uint32_t, 4> expected{
      0x6627e8d5U,
      0xe169c58dU,
      0xbc57ac4cU,
      0x9b00dbd8U,
  };
  if (known != expected) {
    return EXIT_FAILURE;
  }

  const simulation::LogicalRandom random{123456789U};
  const simulation::LogicalRandomAddress address{77U, 91U};
  if (random.block(address) != random.block(address) ||
      random.block(address) == random.block({77U, 92U}) ||
      random.block(address) == simulation::LogicalRandom{123456788U}.block(address)) {
    return EXIT_FAILURE;
  }
  if (random.u64(address, 0U) == random.u64(address, 1U)) {
    return EXIT_FAILURE;
  }
  const auto unit = random.unit_open(address, 2U);
  if (!(unit > 0.0 && unit < 1.0)) {
    return EXIT_FAILURE;
  }
  for (std::uint64_t index = 0U; index < 1000U; ++index) {
    const auto value = random.bounded_u32({9U, index}, 7U);
    if (value >= 7U) {
      return EXIT_FAILURE;
    }
  }

  bool lane_failed = false;
  bool pair_failed = false;
  bool bound_failed = false;
  try {
    (void)random.u32(address, 4U);
  } catch (const std::out_of_range&) {
    lane_failed = true;
  }
  try {
    (void)random.u64(address, 2U);
  } catch (const std::out_of_range&) {
    pair_failed = true;
  }
  try {
    (void)random.bounded_u32(address, 0U);
  } catch (const std::invalid_argument&) {
    bound_failed = true;
  }
  return lane_failed && pair_failed && bound_failed ? EXIT_SUCCESS : EXIT_FAILURE;
}
