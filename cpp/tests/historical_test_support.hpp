#pragma once

#include "robust_execution/historical/historical.hpp"

#include <cstdint>
#include <vector>

namespace historical_test {
namespace historical = robust_execution::historical;
namespace model = robust_execution::model;
namespace policy = robust_execution::policy;
namespace simulation = robust_execution::simulation;
namespace exchange = robust_execution::exchange;

inline model::TimestampNs time(std::int64_t value) {
  return model::TimestampNs{model::ClockDomain::Simulation, value};
}

inline model::InstrumentDefinition instrument() {
  return model::InstrumentDefinition{
      model::kEventSchemaVersion,
      model::VenueId{"binance_spot"},
      model::InstrumentId{"BTCUSDT"},
      "BTC",
      "USDT",
      model::RationalIncrement{1U, 100U},
      model::RationalIncrement{1U, 100'000U},
      model::RationalIncrement{1U, 100U},
      model::QuantityLots{1U},
      model::QuantityLots{1'000'000U},
      "historical-test-v1",
  };
}

inline policy::PolicyEnvironment environment() {
  return policy::PolicyEnvironment{
      instrument(),
      model::StrategyId{"historical-test-policy"},
      model::FeeScheduleId{"fee-v1"},
      model::LatencyModelId{"observed-capture-v1"},
      50,
      3U,
      8U,
      1U,
      1U,
      {policy::QuantityFraction{1U, 2U}, policy::QuantityFraction{1U, 1U}},
      {model::TickOffset{-1}, model::TickOffset{0}, model::TickOffset{1}},
      policy::LotRoundingPolicy::Floor,
      true,
      true,
      true,
  };
}

inline historical::HistoricalReplayConfig config() {
  simulation::SimulationKernelConfig kernel{
      exchange::MatchingEngineConfig{instrument()},
      model::RunId{"historical-test-run"},
      7U,
      simulation::LatencyModelConfig{},
      model::SourceChannelId{"strategy-orders"},
      model::SourceChannelId{"exchange-orders"},
      model::SourceChannelId{"exchange-fills"},
      model::SourceChannelId{"exchange-trades"},
      model::SourceChannelId{"system"},
      100'000U,
      100'000U,
  };
  return historical::HistoricalReplayConfig{
      kernel,
      environment(),
      5,
      model::SourceChannelId{"binance-historical-l2"},
      10'000U,
      10'000U,
      true,
  };
}

inline policy::ExecutionState state() {
  return policy::ExecutionState{
      policy::ParentOrderDefinition{
          model::ParentOrderId{1U},
          model::Side::Buy,
          model::QuantityLots{100U},
          time(0),
          time(1000),
          model::PriceTicks{101},
          "hard-completion-v1",
      },
      environment(),
  };
}

inline historical::ReplayConnection connection() {
  historical::ReplaySnapshot snapshot{
      "connection-0000",
      100U,
      time(0),
      time(100),
      {
          model::BookLevel{model::PriceTicks{100}, model::QuantityLots{50U}, std::nullopt},
          model::BookLevel{model::PriceTicks{99}, model::QuantityLots{60U}, std::nullopt},
      },
      {
          model::BookLevel{model::PriceTicks{102}, model::QuantityLots{55U}, std::nullopt},
          model::BookLevel{model::PriceTicks{103}, model::QuantityLots{65U}, std::nullopt},
      },
      1U,
  };
  historical::ReplayDepthBatch depth{
      2U,
      100U,
      101U,
      time(90),
      time(100),
      {
          model::DepthUpdate{
              model::Side::Buy,
              model::PriceTicks{100},
              model::QuantityLots{70U},
              model::BookUpdateAction::Set,
              std::nullopt,
          },
          model::DepthUpdate{
              model::Side::Sell,
              model::PriceTicks{102},
              model::QuantityLots{45U},
              model::BookUpdateAction::Set,
              std::nullopt,
          },
      },
  };
  historical::ReplayTrade trade{
      3U,
      time(145),
      time(150),
      model::Trade{
          model::TradeId{500U},
          model::ExternalTradeId{"500"},
          model::PriceTicks{102},
          model::QuantityLots{4U},
          model::AggressorSide::Buy,
      },
  };
  historical::ReplayDepthBatch second_depth{
      4U,
      102U,
      102U,
      time(195),
      time(200),
      {
          model::DepthUpdate{
              model::Side::Sell,
              model::PriceTicks{102},
              model::QuantityLots{0U},
              model::BookUpdateAction::Delete,
              std::nullopt,
          },
      },
  };
  return historical::ReplayConnection{
      std::move(snapshot),
      {std::move(depth), std::move(trade), std::move(second_depth)},
  };
}

inline std::vector<historical::ReplayCheckpoint> checkpoints() {
  return {
      historical::ReplayCheckpoint{model::DecisionId{1U}, time(104)},
      historical::ReplayCheckpoint{model::DecisionId{2U}, time(105)},
      historical::ReplayCheckpoint{model::DecisionId{3U}, time(160)},
      historical::ReplayCheckpoint{model::DecisionId{4U}, time(210)},
  };
}

}  // namespace historical_test
