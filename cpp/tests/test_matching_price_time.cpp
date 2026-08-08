#include "matching_test_support.hpp"

#include <cstdlib>

int main() {
  namespace exchange = robust_execution::exchange;
  namespace model = robust_execution::model;
  auto engine = matching_test::engine();

  const auto first = engine.submit(matching_test::limit(1U, model::Side::Sell, 3U, 101));
  const auto second = engine.submit(matching_test::limit(2U, model::Side::Sell, 4U, 101));
  const auto third = engine.submit(matching_test::limit(3U, model::Side::Sell, 5U, 102));
  if (!first.accepted() || !second.accepted() || !third.accepted() ||
      engine.active_order_count() != 3U || engine.best_ask() != model::PriceTicks{101}) {
    return EXIT_FAILURE;
  }

  const auto aggressive = engine.submit(matching_test::limit(
      10U,
      model::Side::Buy,
      6U,
      102,
      model::TimeInForce::ImmediateOrCancel
  ));
  if (!aggressive.accepted() || aggressive.matches.size() != 2U ||
      aggressive.automatic_cancellation.has_value() ||
      aggressive.matches[0].maker_fill.client_order_id != model::ClientOrderId{1U} ||
      aggressive.matches[0].trade.price != model::PriceTicks{101} ||
      aggressive.matches[0].trade.quantity != model::QuantityLots{3U} ||
      aggressive.matches[1].maker_fill.client_order_id != model::ClientOrderId{2U} ||
      aggressive.matches[1].trade.quantity != model::QuantityLots{3U}) {
    return EXIT_FAILURE;
  }

  const auto order_one = engine.order(model::ClientOrderId{1U});
  const auto order_two = engine.order(model::ClientOrderId{2U});
  const auto taker = engine.order(model::ClientOrderId{10U});
  if (!order_one.has_value() || order_one->state != model::OrderState::Filled ||
      !order_two.has_value() || order_two->state != model::OrderState::PartiallyFilled ||
      order_two->leaves_quantity != model::QuantityLots{1U} || !taker.has_value() ||
      taker->state != model::OrderState::Filled ||
      engine.quantity_at(model::Side::Sell, model::PriceTicks{101}) !=
          model::QuantityLots{1U}) {
    return EXIT_FAILURE;
  }

  const auto next = engine.submit(matching_test::market(11U, model::Side::Buy, 2U));
  if (next.matches.size() != 2U ||
      next.matches[0].maker_fill.client_order_id != model::ClientOrderId{2U} ||
      next.matches[0].trade.price != model::PriceTicks{101} ||
      next.matches[1].maker_fill.client_order_id != model::ClientOrderId{3U} ||
      next.matches[1].trade.price != model::PriceTicks{102} ||
      engine.quantity_at(model::Side::Sell, model::PriceTicks{101}) !=
          model::QuantityLots{0U} ||
      engine.quantity_at(model::Side::Sell, model::PriceTicks{102}) !=
          model::QuantityLots{4U}) {
    return EXIT_FAILURE;
  }

  for (const exchange::MatchExecution* match : {
           &aggressive.matches[0],
           &aggressive.matches[1],
           &next.matches[0],
           &next.matches[1],
       }) {
    if (match->maker_fill.liquidity_role != model::LiquidityRole::Maker ||
        match->taker_fill.liquidity_role != model::LiquidityRole::Taker ||
        match->maker_fill.quantity != match->taker_fill.quantity ||
        match->maker_fill.price != match->taker_fill.price) {
      return EXIT_FAILURE;
    }
  }

  if (!engine.validate_invariants().empty()) {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
