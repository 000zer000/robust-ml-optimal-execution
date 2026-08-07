#include "robust_execution/simulation/logical_rng.hpp"

#include <limits>
#include <stdexcept>

namespace robust_execution::simulation {
namespace {

constexpr std::uint32_t kPhiloxMultiplier0 = 0xD2511F53U;
constexpr std::uint32_t kPhiloxMultiplier1 = 0xCD9E8D57U;
constexpr std::uint32_t kPhiloxWeyl0 = 0x9E3779B9U;
constexpr std::uint32_t kPhiloxWeyl1 = 0xBB67AE85U;

struct ProductParts {
  std::uint32_t high;
  std::uint32_t low;
};

[[nodiscard]] constexpr ProductParts multiply_high_low(
    std::uint32_t lhs,
    std::uint32_t rhs
) noexcept {
  const auto product = static_cast<std::uint64_t>(lhs) * static_cast<std::uint64_t>(rhs);
  return ProductParts{
      static_cast<std::uint32_t>(product >> 32U),
      static_cast<std::uint32_t>(product),
  };
}

[[nodiscard]] constexpr std::array<std::uint32_t, 4> philox_round(
    const std::array<std::uint32_t, 4>& counter,
    const std::array<std::uint32_t, 2>& key
) noexcept {
  const auto first = multiply_high_low(kPhiloxMultiplier0, counter[0]);
  const auto second = multiply_high_low(kPhiloxMultiplier1, counter[2]);
  return {
      second.high ^ counter[1] ^ key[0],
      second.low,
      first.high ^ counter[3] ^ key[1],
      first.low,
  };
}

[[nodiscard]] constexpr std::array<std::uint32_t, 2> bump_key(
    const std::array<std::uint32_t, 2>& key
) noexcept {
  return {key[0] + kPhiloxWeyl0, key[1] + kPhiloxWeyl1};
}

}  // namespace

std::array<std::uint32_t, 4> LogicalRandom::philox4x32_10(
    std::array<std::uint32_t, 4> counter,
    std::array<std::uint32_t, 2> key
) noexcept {
  for (std::size_t round = 0U; round < 10U; ++round) {
    counter = philox_round(counter, key);
    if (round + 1U < 10U) {
      key = bump_key(key);
    }
  }
  return counter;
}

std::array<std::uint32_t, 4> LogicalRandom::block_offset(
    LogicalRandomAddress address,
    std::uint64_t block_offset_value
) const noexcept {
  const std::array<std::uint32_t, 4> counter{
      static_cast<std::uint32_t>(address.logical_index),
      static_cast<std::uint32_t>(address.logical_index >> 32U),
      static_cast<std::uint32_t>(address.stream_id),
      static_cast<std::uint32_t>(address.stream_id >> 32U),
  };
  const auto offset_low = static_cast<std::uint32_t>(block_offset_value);
  const auto offset_high = static_cast<std::uint32_t>(block_offset_value >> 32U);
  const std::array<std::uint32_t, 2> key{
      static_cast<std::uint32_t>(seed_) + offset_low * kPhiloxWeyl0,
      static_cast<std::uint32_t>(seed_ >> 32U) + offset_high * kPhiloxWeyl1 +
          offset_low * kPhiloxWeyl1,
  };
  return philox4x32_10(counter, key);
}

std::array<std::uint32_t, 4> LogicalRandom::block(
    LogicalRandomAddress address
) const noexcept {
  return block_offset(address, 0U);
}

std::uint32_t LogicalRandom::u32(
    LogicalRandomAddress address,
    std::size_t lane
) const {
  if (lane >= 4U) {
    throw std::out_of_range("logical-random lane must be in [0, 4)");
  }
  return block(address)[lane];
}

std::uint64_t LogicalRandom::u64(
    LogicalRandomAddress address,
    std::size_t pair
) const {
  if (pair >= 2U) {
    throw std::out_of_range("logical-random pair must be in [0, 2)");
  }
  const auto values = block(address);
  const auto lower_lane = pair * 2U;
  return static_cast<std::uint64_t>(values[lower_lane]) |
         (static_cast<std::uint64_t>(values[lower_lane + 1U]) << 32U);
}

double LogicalRandom::unit_open(
    LogicalRandomAddress address,
    std::size_t lane
) const {
  constexpr double kScale = 1.0 / 4294967296.0;
  return (static_cast<double>(u32(address, lane)) + 0.5) * kScale;
}

std::uint32_t LogicalRandom::bounded_u32(
    LogicalRandomAddress address,
    std::uint32_t upper_exclusive
) const {
  if (upper_exclusive == 0U) {
    throw std::invalid_argument("bounded logical-random draw requires a positive bound");
  }
  const auto threshold = static_cast<std::uint32_t>(-upper_exclusive) % upper_exclusive;
  for (std::uint64_t attempt = 0U;; ++attempt) {
    const auto block_index = attempt / 4U;
    const auto lane = static_cast<std::size_t>(attempt % 4U);
    const auto value = block_offset(address, block_index)[lane];
    if (value >= threshold) {
      return value % upper_exclusive;
    }
    if (attempt == std::numeric_limits<std::uint64_t>::max()) {
      throw std::overflow_error("logical-random rejection sequence exhausted its draw range");
    }
  }
}

}  // namespace robust_execution::simulation
