#include "matching_test_support.hpp"

#include <cstdlib>

int main() {
  namespace exchange = robust_execution::exchange;
  namespace model = robust_execution::model;
  auto engine = matching_test::engine();

  if (!engine.submit(matching_test::limit(1U, model::Side::Sell, 2U, 101)).accepted() ||
      !engine.submit(matching_test::limit(2U, model::Side::Sell, 3U, 102)).accepted()) {
    return EXIT_FAILURE;
  }
  const auto state_before_rejections = engine.canonical_state();

  const auto post_only = engine.submit(matching_test::limit(
      3U,
      model::Side::Buy,
      1U,
      101,
      model::TimeInForce::GoodTilCancelled,
      true
  ));
  if (post_only.accepted() || !post_only.failure.has_value() ||
      post_only.failure->code != exchange::EngineFailureCode::PostOnlyWouldCross ||
      engine.canonical_state() != state_before_rejections) {
    return EXIT_FAILURE;
  }

  const auto insufficient_fok = engine.submit(matching_test::limit(
      4U,
      model::Side::Buy,
      6U,
      102,
      model::TimeInForce::FillOrKill
  ));
  if (insufficient_fok.accepted() || !insufficient_fok.failure.has_value() ||
      insufficient_fok.failure->code != exchange::EngineFailureCode::InsufficientLiquidity ||
      engine.canonical_state() != state_before_rejections) {
    return EXIT_FAILURE;
  }

  const auto exact_fok = engine.submit(matching_test::limit(
      4U,
      model::Side::Buy,
      5U,
      102,
      model::TimeInForce::FillOrKill
  ));
  if (!exact_fok.accepted() || exact_fok.matches.size() != 2U ||
      exact_fok.automatic_cancellation.has_value() || engine.active_order_count() != 0U) {
    return EXIT_FAILURE;
  }

  if (!engine.submit(matching_test::limit(5U, model::Side::Sell, 2U, 103)).accepted()) {
    return EXIT_FAILURE;
  }
  const auto partial_market = engine.submit(matching_test::market(6U, model::Side::Buy, 5U));
  if (!partial_market.accepted() || partial_market.matches.size() != 1U ||
      !partial_market.automatic_cancellation.has_value() ||
      partial_market.automatic_cancellation->cancelled_quantity != model::QuantityLots{3U} ||
      !partial_market.final_order.has_value() ||
      partial_market.final_order->state != model::OrderState::Cancelled ||
      partial_market.final_order->cumulative_filled != model::QuantityLots{2U}) {
    return EXIT_FAILURE;
  }

  auto invalid_market = matching_test::market(
      7U,
      model::Side::Buy,
      1U,
      model::TimeInForce::GoodTilCancelled
  );
  const auto market_gtc = engine.submit(invalid_market);
  if (market_gtc.accepted() || !market_gtc.failure.has_value() ||
      market_gtc.failure->code != exchange::EngineFailureCode::UnsupportedCombination) {
    return EXIT_FAILURE;
  }

  auto missing_price = matching_test::limit(8U, model::Side::Buy, 1U, 100);
  missing_price.limit_price = std::nullopt;
  if (engine.submit(missing_price).failure->code !=
      exchange::EngineFailureCode::MissingLimitPrice) {
    return EXIT_FAILURE;
  }

  auto unexpected_price = matching_test::market(9U, model::Side::Buy, 1U);
  unexpected_price.limit_price = model::PriceTicks{100};
  if (engine.submit(unexpected_price).failure->code !=
      exchange::EngineFailureCode::UnexpectedLimitPrice) {
    return EXIT_FAILURE;
  }

  const auto zero_quantity = engine.submit(matching_test::limit(10U, model::Side::Buy, 0U, 100));
  if (!zero_quantity.failure.has_value() ||
      zero_quantity.failure->code != exchange::EngineFailureCode::QuantityBelowMinimum) {
    return EXIT_FAILURE;
  }
  const auto excessive = engine.submit(matching_test::limit(11U, model::Side::Buy, 1001U, 100));
  if (!excessive.failure.has_value() ||
      excessive.failure->code != exchange::EngineFailureCode::QuantityAboveMaximum) {
    return EXIT_FAILURE;
  }

  if (!engine.validate_invariants().empty()) {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
