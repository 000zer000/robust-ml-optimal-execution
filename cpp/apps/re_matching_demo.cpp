#include "robust_execution/exchange/exchange.hpp"

#include <cstdlib>
#include <iostream>
#include <optional>

namespace exchange = robust_execution::exchange;
namespace model = robust_execution::model;

namespace {

model::TimestampNs time(std::int64_t value) {
  return model::TimestampNs{model::ClockDomain::Simulation, value};
}

model::OrderSubmit limit(
    std::uint64_t client,
    model::Side side,
    std::uint64_t quantity,
    std::int64_t price,
    model::TimeInForce tif = model::TimeInForce::GoodTilCancelled
) {
  return model::OrderSubmit{
      model::ParentOrderId{1U},
      model::ClientOrderId{client},
      model::DecisionId{client},
      side,
      model::OrderType::Limit,
      tif,
      model::QuantityLots{quantity},
      model::PriceTicks{price},
      false,
      time(10),
      time(11),
      time(12),
  };
}

}  // namespace

int main() {
  const model::InstrumentDefinition instrument{
      model::kEventSchemaVersion,
      model::VenueId{"synthetic"},
      model::InstrumentId{"TEST-USD"},
      "TEST",
      "USD",
      model::RationalIncrement{1U, 100U},
      model::RationalIncrement{1U, 1000U},
      model::RationalIncrement{1U, 100U},
      model::QuantityLots{1U},
      model::QuantityLots{1000U},
      "synthetic-v1",
  };
  exchange::MatchingEngine engine{exchange::MatchingEngineConfig{instrument}};

  const auto ask_one = engine.submit(limit(1U, model::Side::Sell, 2U, 101));
  const auto ask_two = engine.submit(limit(2U, model::Side::Sell, 3U, 102));
  const auto buyer = engine.submit(limit(
      3U,
      model::Side::Buy,
      4U,
      102,
      model::TimeInForce::ImmediateOrCancel
  ));
  if (!ask_one.accepted() || !ask_two.accepted() || !buyer.accepted() ||
      buyer.matches.size() != 2U) {
    return EXIT_FAILURE;
  }

  const auto remaining_ask = engine.order(model::ClientOrderId{2U});
  if (!remaining_ask.has_value()) {
    return EXIT_FAILURE;
  }
  const auto replacement = engine.replace(model::ReplaceRequest{
      remaining_ask->client_order_id,
      remaining_ask->exchange_order_id,
      model::ClientOrderId{4U},
      model::DecisionId{4U},
      model::QuantityLots{2U},
      model::PriceTicks{103},
      time(20),
      time(21),
      time(22),
  });
  const auto bid = engine.submit(limit(5U, model::Side::Buy, 2U, 100));
  const auto seller = engine.submit(model::OrderSubmit{
      model::ParentOrderId{1U},
      model::ClientOrderId{6U},
      model::DecisionId{6U},
      model::Side::Sell,
      model::OrderType::Market,
      model::TimeInForce::ImmediateOrCancel,
      model::QuantityLots{1U},
      std::nullopt,
      false,
      time(30),
      time(31),
      time(32),
  });

  if (!replacement.accepted() || !bid.accepted() || !seller.accepted() ||
      seller.matches.size() != 1U || !engine.validate_invariants().empty()) {
    return EXIT_FAILURE;
  }

  std::cout << engine.canonical_state();
  return EXIT_SUCCESS;
}
