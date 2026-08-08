#pragma once

#include "robust_execution/simulation/simulation.hpp"

#include <cstdint>
#include <optional>

namespace simulation_test {

namespace exchange = robust_execution::exchange;
namespace model = robust_execution::model;
namespace simulation = robust_execution::simulation;

inline model::TimestampNs time(std::int64_t value) {
  return model::TimestampNs{model::ClockDomain::Simulation, value};
}

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
      "simulation-test-v1",
  };
}

inline simulation::LatencyModelConfig fixed_latency() {
  return simulation::LatencyModelConfig{
      "fixed-test-v1",
      simulation::LatencyRangeNs{5, 5, 1U},
      simulation::LatencyRangeNs{3, 3, 2U},
      simulation::LatencyRangeNs{2, 2, 3U},
      simulation::LatencyRangeNs{4, 4, 4U},
      simulation::LatencyRangeNs{3, 3, 5U},
      simulation::LatencyRangeNs{5, 5, 6U},
      simulation::LatencyRangeNs{2, 2, 7U},
  };
}

inline simulation::SimulationKernelConfig kernel_config(std::uint64_t seed = 17U) {
  return simulation::SimulationKernelConfig{
      exchange::MatchingEngineConfig{instrument()},
      model::RunId{"step7-test-run"},
      seed,
      fixed_latency(),
      model::SourceChannelId{"strategy-orders"},
      model::SourceChannelId{"exchange-orders"},
      model::SourceChannelId{"exchange-fills"},
      model::SourceChannelId{"exchange-trades"},
      model::SourceChannelId{"system"},
      1000U,
      1000U,
  };
}

inline model::OrderSubmit limit(
    std::uint64_t client_id,
    model::Side side,
    std::uint64_t quantity,
    std::int64_t price,
    model::TimeInForce tif = model::TimeInForce::GoodTilCancelled,
    bool post_only = false,
    std::uint64_t decision_id = 1U
) {
  return model::OrderSubmit{
      model::ParentOrderId{1U},
      model::ClientOrderId{client_id},
      model::DecisionId{decision_id},
      side,
      model::OrderType::Limit,
      tif,
      model::QuantityLots{quantity},
      model::PriceTicks{price},
      post_only,
      time(0),
      time(0),
      time(0),
  };
}

inline model::OrderSubmit market(
    std::uint64_t client_id,
    model::Side side,
    std::uint64_t quantity,
    std::uint64_t decision_id = 1U
) {
  return model::OrderSubmit{
      model::ParentOrderId{1U},
      model::ClientOrderId{client_id},
      model::DecisionId{decision_id},
      side,
      model::OrderType::Market,
      model::TimeInForce::ImmediateOrCancel,
      model::QuantityLots{quantity},
      std::nullopt,
      false,
      time(0),
      time(0),
      time(0),
  };
}

inline model::CancelRequest cancel(
    std::uint64_t client_id,
    std::uint64_t exchange_id,
    std::uint64_t decision_id = 2U
) {
  return model::CancelRequest{
      model::ClientOrderId{client_id},
      model::ExchangeOrderId{exchange_id},
      model::DecisionId{decision_id},
      time(0),
      time(0),
      time(0),
  };
}

inline model::ReplaceRequest replace(
    std::uint64_t client_id,
    std::uint64_t exchange_id,
    std::uint64_t replacement_client_id,
    std::uint64_t quantity,
    std::int64_t price,
    std::uint64_t decision_id = 3U
) {
  return model::ReplaceRequest{
      model::ClientOrderId{client_id},
      model::ExchangeOrderId{exchange_id},
      model::ClientOrderId{replacement_client_id},
      model::DecisionId{decision_id},
      model::QuantityLots{quantity},
      model::PriceTicks{price},
      time(0),
      time(0),
      time(0),
  };
}

inline model::Event market_trade(
    std::uint64_t event_id,
    std::uint64_t canonical_sequence,
    std::int64_t event_time
) {
  return model::Event{
      model::EventHeader{
          model::kEventSchemaVersion,
          model::EventId{event_id},
          model::RunId{"step7-test-run"},
          model::VenueId{"synthetic"},
          model::InstrumentId{"TEST-USD"},
          model::SourceChannelId{"market"},
          model::EventOrigin::SyntheticExchange,
          time(event_time),
          std::nullopt,
          std::nullopt,
          model::EventOrdering{true, event_id, 0U, canonical_sequence, canonical_sequence},
          std::nullopt,
      },
      model::Trade{
          model::TradeId{event_id},
          std::nullopt,
          model::PriceTicks{101},
          model::QuantityLots{1U},
          model::AggressorSide::Buy,
      },
  };
}

}  // namespace simulation_test
