#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

namespace robust_execution::simulation {

struct LogicalRandomAddress {
  std::uint64_t stream_id{0U};
  std::uint64_t logical_index{0U};

  [[nodiscard]] friend constexpr auto operator<=>(
      const LogicalRandomAddress&,
      const LogicalRandomAddress&
  ) = default;
};

class LogicalRandom {
 public:
  explicit constexpr LogicalRandom(std::uint64_t seed) noexcept : seed_(seed) {}

  [[nodiscard]] std::array<std::uint32_t, 4> block(
      LogicalRandomAddress address
  ) const noexcept;
  [[nodiscard]] std::uint32_t u32(
      LogicalRandomAddress address,
      std::size_t lane
  ) const;
  [[nodiscard]] std::uint64_t u64(
      LogicalRandomAddress address,
      std::size_t pair
  ) const;
  [[nodiscard]] double unit_open(
      LogicalRandomAddress address,
      std::size_t lane
  ) const;
  [[nodiscard]] std::uint32_t bounded_u32(
      LogicalRandomAddress address,
      std::uint32_t upper_exclusive
  ) const;

  [[nodiscard]] constexpr std::uint64_t seed() const noexcept { return seed_; }

  [[nodiscard]] static std::array<std::uint32_t, 4> philox4x32_10(
      std::array<std::uint32_t, 4> counter,
      std::array<std::uint32_t, 2> key
  ) noexcept;

 private:
  [[nodiscard]] std::array<std::uint32_t, 4> block_offset(
      LogicalRandomAddress address,
      std::uint64_t block_offset
  ) const noexcept;

  std::uint64_t seed_{0U};
};

}  // namespace robust_execution::simulation
