#include "robust_execution/diagnostic_sequence.hpp"

namespace robust_execution {

std::vector<std::uint64_t> diagnostic_sequence(
    const std::uint64_t seed,
    const std::size_t count
) {
  std::vector<std::uint64_t> output;
  output.reserve(count);

  std::uint64_t value = seed;
  for (std::size_t index = 0; index < count; ++index) {
    // Unsigned overflow is defined modulo 2^64. The constants make this a
    // deterministic build diagnostic only; they are not a quality RNG claim.
    value = value * UINT64_C(6364136223846793005) + UINT64_C(1442695040888963407);
    output.push_back(value ^ static_cast<std::uint64_t>(index));
  }
  return output;
}

}  // namespace robust_execution
