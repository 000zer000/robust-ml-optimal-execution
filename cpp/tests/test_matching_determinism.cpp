#include "matching_test_support.hpp"

#include <cstdlib>
#include <cstdint>
#include <string>

namespace {

std::string run_sequence() {
  namespace model = robust_execution::model;
  auto engine = matching_test::engine();
  std::uint64_t state = 17U;
  std::uint64_t next_client = 1U;

  for (std::uint64_t index = 0U; index < 400U; ++index) {
    state = state * UINT64_C(6364136223846793005) + UINT64_C(1442695040888963407);
    const auto side = ((state >> 8U) & 1U) == 0U ? model::Side::Buy : model::Side::Sell;
    const auto quantity = 1U + ((state >> 16U) % 5U);
    const auto offset = static_cast<std::int64_t>((state >> 24U) % 7U);
    const auto price = side == model::Side::Buy ? 99 + offset : 99 + offset;
    const auto time_in_force = ((state >> 32U) % 5U) == 0U
                                   ? model::TimeInForce::ImmediateOrCancel
                                   : model::TimeInForce::GoodTilCancelled;
    const auto result = engine.submit(matching_test::limit(
        next_client,
        side,
        quantity,
        price,
        time_in_force,
        false,
        index + 1U
    ));
    if (!result.accepted()) {
      return "unexpected rejection";
    }
    ++next_client;
    if (!engine.validate_invariants().empty()) {
      return "invariant failure";
    }

    if (index % 11U == 0U) {
      const auto view = engine.order(model::ClientOrderId{next_client - 1U});
      if (view.has_value() &&
          (view->state == model::OrderState::Live ||
           view->state == model::OrderState::PartiallyFilled)) {
        const auto cancelled = engine.cancel(matching_test::cancel_request(
            view->client_order_id.value(),
            view->exchange_order_id.value(),
            index + 1000U
        ));
        if (!cancelled.accepted()) {
          return "unexpected cancel rejection";
        }
      }
    }
  }
  return engine.canonical_state();
}

}  // namespace

int main() {
  const auto first = run_sequence();
  const auto second = run_sequence();
  if (first != second || first == "unexpected rejection" || first == "invariant failure" ||
      first == "unexpected cancel rejection") {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
