#include "robust_execution/model/fixed_point.hpp"

#include <cstdlib>
#include <cstdint>
#include <limits>

int main() {
  using robust_execution::model::PriceTicks;
  using robust_execution::model::QuantityLots;
  using robust_execution::model::QuoteAtoms;
  using robust_execution::model::RationalIncrement;
  using robust_execution::model::TickOffset;
  using robust_execution::model::checked_add;
  using robust_execution::model::checked_subtract;

  const auto price = checked_add(PriceTicks{100}, TickOffset{-3});
  if (!price.has_value() || price->value() != 97) {
    return EXIT_FAILURE;
  }
  if (checked_add(PriceTicks{std::numeric_limits<std::int64_t>::max()}, TickOffset{1})
          .has_value()) {
    return EXIT_FAILURE;
  }
  const auto quantity = checked_add(QuantityLots{7U}, QuantityLots{5U});
  if (!quantity.has_value() || quantity->value() != 12U) {
    return EXIT_FAILURE;
  }
  if (checked_add(
          QuantityLots{std::numeric_limits<std::uint64_t>::max()},
          QuantityLots{1U}
      )
          .has_value()) {
    return EXIT_FAILURE;
  }
  const auto remainder = checked_subtract(QuantityLots{12U}, QuantityLots{5U});
  if (!remainder.has_value() || remainder->value() != 7U ||
      checked_subtract(QuantityLots{1U}, QuantityLots{2U}).has_value()) {
    return EXIT_FAILURE;
  }
  const auto cash = checked_add(QuoteAtoms{-5}, QuoteAtoms{8});
  if (!cash.has_value() || cash->value() != 3) {
    return EXIT_FAILURE;
  }
  if (!RationalIncrement{1U, 100U}.valid() || RationalIncrement{0U, 1U}.valid()) {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
