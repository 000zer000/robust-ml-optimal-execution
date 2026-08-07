#include "matching_test_support.hpp"

#include <cstdlib>

int main() {
  namespace model = robust_execution::model;
  auto engine = matching_test::engine();

  if (engine.best_bid().has_value() || engine.best_ask().has_value() ||
      engine.would_cross(model::Side::Buy, model::PriceTicks{100}) ||
      engine.can_fully_execute(model::Side::Buy, model::QuantityLots{1U}, std::nullopt)) {
    return EXIT_FAILURE;
  }

  if (!engine.submit(matching_test::limit(1U, model::Side::Buy, 1U, 99)).accepted() ||
      !engine.submit(matching_test::limit(2U, model::Side::Buy, 2U, 100)).accepted() ||
      !engine.submit(matching_test::limit(3U, model::Side::Sell, 3U, 102)).accepted() ||
      !engine.submit(matching_test::limit(4U, model::Side::Sell, 4U, 103)).accepted()) {
    return EXIT_FAILURE;
  }

  if (engine.best_bid() != model::PriceTicks{100} ||
      engine.best_ask() != model::PriceTicks{102} ||
      !engine.would_cross(model::Side::Buy, model::PriceTicks{102}) ||
      engine.would_cross(model::Side::Buy, model::PriceTicks{101}) ||
      !engine.would_cross(model::Side::Sell, model::PriceTicks{100}) ||
      engine.would_cross(model::Side::Sell, model::PriceTicks{101})) {
    return EXIT_FAILURE;
  }

  if (!engine.can_fully_execute(
          model::Side::Buy,
          model::QuantityLots{7U},
          model::PriceTicks{103}
      ) ||
      engine.can_fully_execute(
          model::Side::Buy,
          model::QuantityLots{4U},
          model::PriceTicks{102}
      ) ||
      !engine.can_fully_execute(
          model::Side::Sell,
          model::QuantityLots{3U},
          model::PriceTicks{99}
      )) {
    return EXIT_FAILURE;
  }

  const auto one_level = engine.book(1U);
  if (one_level.bids.size() != 1U || one_level.asks.size() != 1U ||
      one_level.bids[0].price != model::PriceTicks{100} ||
      one_level.asks[0].price != model::PriceTicks{102}) {
    return EXIT_FAILURE;
  }
  const auto all = engine.book();
  if (all.bids.size() != 2U || all.asks.size() != 2U ||
      all.bids[1].price != model::PriceTicks{99} ||
      all.asks[1].price != model::PriceTicks{103}) {
    return EXIT_FAILURE;
  }

  if (!engine.validate_invariants().empty()) {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
