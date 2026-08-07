#include "matching_test_support.hpp"

#include <cstdlib>

int main() {
  namespace exchange = robust_execution::exchange;
  namespace model = robust_execution::model;
  auto engine = matching_test::engine();

  const auto first = engine.submit(matching_test::limit(1U, model::Side::Buy, 2U, 100));
  const auto second = engine.submit(matching_test::limit(2U, model::Side::Buy, 2U, 100));
  const auto third = engine.submit(matching_test::limit(3U, model::Side::Buy, 2U, 100));
  if (!first.accepted() || !second.accepted() || !third.accepted()) {
    return EXIT_FAILURE;
  }
  const auto second_exchange = second.acknowledgement->exchange_order_id.value();
  const auto cancelled = engine.cancel(matching_test::cancel_request(2U, second_exchange));
  if (!cancelled.accepted() || cancelled.acknowledgement->cancelled_quantity !=
                                   model::QuantityLots{2U} ||
      engine.quantity_at(model::Side::Buy, model::PriceTicks{100}) !=
          model::QuantityLots{4U}) {
    return EXIT_FAILURE;
  }

  const auto repeat_cancel = engine.cancel(matching_test::cancel_request(2U, second_exchange));
  if (repeat_cancel.accepted() || !repeat_cancel.failure.has_value() ||
      repeat_cancel.failure->code != exchange::EngineFailureCode::AlreadyTerminal ||
      repeat_cancel.failure->current_state != model::OrderState::Cancelled) {
    return EXIT_FAILURE;
  }
  const auto mismatched = engine.cancel(matching_test::cancel_request(
      1U,
      third.acknowledgement->exchange_order_id.value()
  ));
  if (mismatched.accepted() || mismatched.failure->code !=
                                   exchange::EngineFailureCode::OrderIdentifierMismatch) {
    return EXIT_FAILURE;
  }

  const auto invalid_replace = engine.replace(matching_test::replace_request(
      1U,
      first.acknowledgement->exchange_order_id.value(),
      4U,
      0U,
      100
  ));
  if (invalid_replace.accepted() || !invalid_replace.failure.has_value() ||
      invalid_replace.failure->code != exchange::EngineFailureCode::QuantityBelowMinimum ||
      engine.quantity_at(model::Side::Buy, model::PriceTicks{100}) !=
          model::QuantityLots{4U}) {
    return EXIT_FAILURE;
  }

  const auto replacement = engine.replace(matching_test::replace_request(
      1U,
      first.acknowledgement->exchange_order_id.value(),
      4U,
      2U,
      100
  ));
  if (!replacement.accepted() || !replacement.replacement_order.has_value() ||
      replacement.replacement_order->priority_sequence <=
          engine.order(model::ClientOrderId{3U})->priority_sequence ||
      engine.order(model::ClientOrderId{1U})->state != model::OrderState::Replaced) {
    return EXIT_FAILURE;
  }

  const auto sell = engine.submit(matching_test::limit(
      10U,
      model::Side::Sell,
      3U,
      100,
      model::TimeInForce::ImmediateOrCancel
  ));
  if (sell.matches.size() != 2U ||
      sell.matches[0].maker_fill.client_order_id != model::ClientOrderId{3U} ||
      sell.matches[0].trade.quantity != model::QuantityLots{2U} ||
      sell.matches[1].maker_fill.client_order_id != model::ClientOrderId{4U} ||
      sell.matches[1].trade.quantity != model::QuantityLots{1U}) {
    return EXIT_FAILURE;
  }

  if (!engine.submit(matching_test::limit(20U, model::Side::Sell, 2U, 105)).accepted()) {
    return EXIT_FAILURE;
  }
  const auto crossing_replace = engine.replace(matching_test::replace_request(
      4U,
      replacement.acknowledgement->replacement_exchange_order_id.value(),
      5U,
      3U,
      106
  ));
  if (!crossing_replace.accepted() || crossing_replace.matches.size() != 1U ||
      crossing_replace.matches[0].maker_fill.client_order_id != model::ClientOrderId{20U} ||
      !crossing_replace.replacement_order.has_value() ||
      crossing_replace.replacement_order->state != model::OrderState::PartiallyFilled ||
      crossing_replace.replacement_order->leaves_quantity != model::QuantityLots{1U} ||
      engine.best_bid() != model::PriceTicks{106}) {
    return EXIT_FAILURE;
  }

  if (!engine.validate_invariants().empty()) {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
