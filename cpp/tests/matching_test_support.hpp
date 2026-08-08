#pragma once

#include "robust_execution/exchange/exchange.hpp"

#include <cstdint>
#include <optional>

namespace matching_test {

namespace exchange = robust_execution::exchange;
namespace model = robust_execution::model;

inline model::InstrumentDefinition instrument() {
  return model::InstrumentDefinition{
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
}

inline exchange::MatchingEngine engine() {
  return exchange::MatchingEngine{exchange::MatchingEngineConfig{instrument()}};
}

inline model::TimestampNs time(std::int64_t value) {
  return model::TimestampNs{model::ClockDomain::Simulation, value};
}

inline model::OrderSubmit limit(
    std::uint64_t client,
    model::Side side,
    std::uint64_t quantity,
    std::int64_t price,
    model::TimeInForce time_in_force = model::TimeInForce::GoodTilCancelled,
    bool post_only = false,
    std::uint64_t decision = 1U
) {
  return model::OrderSubmit{
      model::ParentOrderId{1U},
      model::ClientOrderId{client},
      model::DecisionId{decision},
      side,
      model::OrderType::Limit,
      time_in_force,
      model::QuantityLots{quantity},
      model::PriceTicks{price},
      post_only,
      time(10),
      time(11),
      time(12),
  };
}

inline model::OrderSubmit market(
    std::uint64_t client,
    model::Side side,
    std::uint64_t quantity,
    model::TimeInForce time_in_force = model::TimeInForce::ImmediateOrCancel,
    std::uint64_t decision = 1U
) {
  return model::OrderSubmit{
      model::ParentOrderId{1U},
      model::ClientOrderId{client},
      model::DecisionId{decision},
      side,
      model::OrderType::Market,
      time_in_force,
      model::QuantityLots{quantity},
      std::nullopt,
      false,
      time(10),
      time(11),
      time(12),
  };
}

inline model::CancelRequest cancel_request(
    std::uint64_t client,
    std::uint64_t exchange_id,
    std::uint64_t decision = 2U
) {
  return model::CancelRequest{
      model::ClientOrderId{client},
      model::ExchangeOrderId{exchange_id},
      model::DecisionId{decision},
      time(20),
      time(21),
      time(22),
  };
}

inline model::ReplaceRequest replace_request(
    std::uint64_t client,
    std::uint64_t exchange_id,
    std::uint64_t replacement_client,
    std::uint64_t quantity,
    std::int64_t price,
    std::uint64_t decision = 3U
) {
  return model::ReplaceRequest{
      model::ClientOrderId{client},
      model::ExchangeOrderId{exchange_id},
      model::ClientOrderId{replacement_client},
      model::DecisionId{decision},
      model::QuantityLots{quantity},
      model::PriceTicks{price},
      time(30),
      time(31),
      time(32),
  };
}

}  // namespace matching_test
