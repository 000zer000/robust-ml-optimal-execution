#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

namespace robust_execution {

// Bootstrap-only deterministic diagnostic. This is not a research RNG and must
// never be used for simulation, model training, or experiment randomisation.
[[nodiscard]] std::vector<std::uint64_t> diagnostic_sequence(
    std::uint64_t seed,
    std::size_t count
);

}  // namespace robust_execution
