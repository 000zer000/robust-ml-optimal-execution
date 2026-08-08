#include "robust_execution/policy/accounting.hpp"

#include <array>
#include <cstdint>
#include <limits>
#include <numeric>

namespace robust_execution::policy {
namespace {

void set_error(AccountingError* error, std::string detail) noexcept {
  if (error != nullptr) {
    error->detail = std::move(detail);
  }
}

bool multiply_checked(std::uint64_t lhs, std::uint64_t rhs, std::uint64_t& result) noexcept {
  if (lhs != 0U && rhs > std::numeric_limits<std::uint64_t>::max() / lhs) {
    return false;
  }
  result = lhs * rhs;
  return true;
}

}  // namespace

std::optional<model::QuoteAtoms> exact_quote_notional(
    const model::InstrumentDefinition& instrument,
    model::PriceTicks price,
    model::QuantityLots quantity,
    AccountingError* error
) noexcept {
  if (!instrument.tick_size.valid() || !instrument.lot_size.valid() ||
      !instrument.quote_atom_size.valid()) {
    set_error(error, "instrument increments must be positive");
    return std::nullopt;
  }
  if (price.value() < 0) {
    set_error(error, "negative prices are not supported by the exact accounting contract");
    return std::nullopt;
  }

  std::array<std::uint64_t, 5> numerators{
      static_cast<std::uint64_t>(price.value()),
      quantity.value(),
      instrument.tick_size.numerator,
      instrument.lot_size.numerator,
      instrument.quote_atom_size.denominator,
  };
  std::array<std::uint64_t, 3> denominators{
      instrument.tick_size.denominator,
      instrument.lot_size.denominator,
      instrument.quote_atom_size.numerator,
  };

  for (auto& denominator : denominators) {
    for (auto& numerator : numerators) {
      const auto divisor = std::gcd(numerator, denominator);
      numerator /= divisor;
      denominator /= divisor;
    }
  }
  for (const auto denominator : denominators) {
    if (denominator != 1U) {
      set_error(error, "price-times-quantity is not exactly representable in quote atoms");
      return std::nullopt;
    }
  }

  std::uint64_t magnitude = 1U;
  for (const auto factor : numerators) {
    std::uint64_t product = 0U;
    if (!multiply_checked(magnitude, factor, product)) {
      set_error(error, "quote notional exceeds unsigned accounting range");
      return std::nullopt;
    }
    magnitude = product;
  }
  if (magnitude > static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())) {
    set_error(error, "quote notional exceeds signed quote-atom range");
    return std::nullopt;
  }
  return model::QuoteAtoms{static_cast<std::int64_t>(magnitude)};
}

std::optional<model::QuoteAtoms> signed_cash_effect(
    const model::InstrumentDefinition& instrument,
    model::Side side,
    model::PriceTicks price,
    model::QuantityLots quantity,
    AccountingError* error
) noexcept {
  const auto notional = exact_quote_notional(instrument, price, quantity, error);
  if (!notional.has_value()) {
    return std::nullopt;
  }
  if (side == model::Side::Sell) {
    return notional;
  }
  if (notional->value() == std::numeric_limits<std::int64_t>::min()) {
    set_error(error, "buy cash effect cannot be negated safely");
    return std::nullopt;
  }
  return model::QuoteAtoms{-notional->value()};
}

}  // namespace robust_execution::policy
