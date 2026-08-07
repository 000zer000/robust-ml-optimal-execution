#include "policy_test_support.hpp"

#include <cstdlib>
#include <limits>

int main() {
  namespace model = robust_execution::model;
  namespace policy = robust_execution::policy;

  auto instrument = policy_test::instrument();
  const auto notional = policy::exact_quote_notional(
      instrument,
      model::PriceTicks{101},
      model::QuantityLots{3U}
  );
  const auto buy = policy::signed_cash_effect(
      instrument,
      model::Side::Buy,
      model::PriceTicks{101},
      model::QuantityLots{3U}
  );
  const auto sell = policy::signed_cash_effect(
      instrument,
      model::Side::Sell,
      model::PriceTicks{101},
      model::QuantityLots{3U}
  );
  if (!notional.has_value() || notional->value() != 303 || !buy.has_value() ||
      buy->value() != -303 || !sell.has_value() || sell->value() != 303) {
    return EXIT_FAILURE;
  }

  instrument.tick_size = model::RationalIncrement{1U, 100U};
  instrument.lot_size = model::RationalIncrement{1U, 1000U};
  instrument.quote_atom_size = model::RationalIncrement{1U, 100000U};
  const auto rational = policy::exact_quote_notional(
      instrument,
      model::PriceTicks{100},
      model::QuantityLots{2U}
  );
  if (!rational.has_value() || rational->value() != 200) {
    return EXIT_FAILURE;
  }

  instrument.quote_atom_size = model::RationalIncrement{3U, 10U};
  policy::AccountingError error;
  if (policy::exact_quote_notional(
          instrument,
          model::PriceTicks{1},
          model::QuantityLots{1U},
          &error
      ).has_value() || error.detail.empty()) {
    return EXIT_FAILURE;
  }

  instrument = policy_test::instrument();
  if (policy::exact_quote_notional(
          instrument,
          model::PriceTicks{std::numeric_limits<std::int64_t>::max()},
          model::QuantityLots{2U},
          &error
      ).has_value()) {
    return EXIT_FAILURE;
  }
  if (policy::exact_quote_notional(
          instrument,
          model::PriceTicks{-1},
          model::QuantityLots{1U},
          &error
      ).has_value()) {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
