#pragma once

#include <compare>
#include <cstdint>
#include <limits>
#include <optional>

namespace robust_execution::model {

class PriceTicks {
 public:
  constexpr PriceTicks() noexcept = default;
  constexpr explicit PriceTicks(std::int64_t value) noexcept : value_(value) {}

  [[nodiscard]] constexpr std::int64_t value() const noexcept { return value_; }
  [[nodiscard]] friend constexpr auto operator<=>(const PriceTicks&, const PriceTicks&) = default;

 private:
  std::int64_t value_{0};
};

class TickOffset {
 public:
  constexpr TickOffset() noexcept = default;
  constexpr explicit TickOffset(std::int32_t value) noexcept : value_(value) {}

  [[nodiscard]] constexpr std::int32_t value() const noexcept { return value_; }
  [[nodiscard]] friend constexpr auto operator<=>(const TickOffset&, const TickOffset&) = default;

 private:
  std::int32_t value_{0};
};

class QuantityLots {
 public:
  constexpr QuantityLots() noexcept = default;
  constexpr explicit QuantityLots(std::uint64_t value) noexcept : value_(value) {}

  [[nodiscard]] constexpr std::uint64_t value() const noexcept { return value_; }
  [[nodiscard]] constexpr bool is_zero() const noexcept { return value_ == 0U; }
  [[nodiscard]] friend constexpr auto operator<=>(const QuantityLots&, const QuantityLots&) = default;

 private:
  std::uint64_t value_{0U};
};

class QuoteAtoms {
 public:
  constexpr QuoteAtoms() noexcept = default;
  constexpr explicit QuoteAtoms(std::int64_t value) noexcept : value_(value) {}

  [[nodiscard]] constexpr std::int64_t value() const noexcept { return value_; }
  [[nodiscard]] friend constexpr auto operator<=>(const QuoteAtoms&, const QuoteAtoms&) = default;

 private:
  std::int64_t value_{0};
};

struct RationalIncrement {
  std::uint64_t numerator{1U};
  std::uint64_t denominator{1U};

  [[nodiscard]] constexpr bool valid() const noexcept {
    return numerator > 0U && denominator > 0U;
  }

  [[nodiscard]] friend constexpr auto operator<=>(
      const RationalIncrement&,
      const RationalIncrement&
  ) = default;
};

[[nodiscard]] constexpr std::optional<PriceTicks> checked_add(
    PriceTicks lhs,
    TickOffset rhs
) noexcept {
  const auto left = lhs.value();
  const auto right = static_cast<std::int64_t>(rhs.value());
  if ((right > 0 && left > std::numeric_limits<std::int64_t>::max() - right) ||
      (right < 0 && left < std::numeric_limits<std::int64_t>::min() - right)) {
    return std::nullopt;
  }
  return PriceTicks{left + right};
}

[[nodiscard]] constexpr std::optional<QuantityLots> checked_add(
    QuantityLots lhs,
    QuantityLots rhs
) noexcept {
  if (rhs.value() > std::numeric_limits<std::uint64_t>::max() - lhs.value()) {
    return std::nullopt;
  }
  return QuantityLots{lhs.value() + rhs.value()};
}

[[nodiscard]] constexpr std::optional<QuantityLots> checked_subtract(
    QuantityLots lhs,
    QuantityLots rhs
) noexcept {
  if (rhs.value() > lhs.value()) {
    return std::nullopt;
  }
  return QuantityLots{lhs.value() - rhs.value()};
}

[[nodiscard]] constexpr std::optional<QuoteAtoms> checked_add(
    QuoteAtoms lhs,
    QuoteAtoms rhs
) noexcept {
  const auto left = lhs.value();
  const auto right = rhs.value();
  if ((right > 0 && left > std::numeric_limits<std::int64_t>::max() - right) ||
      (right < 0 && left < std::numeric_limits<std::int64_t>::min() - right)) {
    return std::nullopt;
  }
  return QuoteAtoms{left + right};
}

}  // namespace robust_execution::model
