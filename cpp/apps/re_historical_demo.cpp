#include "robust_execution/historical/historical.hpp"

#include <iostream>
#include <optional>
#include <vector>

namespace historical = robust_execution::historical;
namespace model = robust_execution::model;
namespace policy = robust_execution::policy;
namespace simulation = robust_execution::simulation;
namespace exchange = robust_execution::exchange;

namespace {
model::TimestampNs ts(std::int64_t value) {
  return model::TimestampNs{model::ClockDomain::Simulation, value};
}
model::InstrumentDefinition instrument() {
  return model::InstrumentDefinition{
      model::kEventSchemaVersion, model::VenueId{"binance_spot"}, model::InstrumentId{"BTCUSDT"},
      "BTC", "USDT", model::RationalIncrement{1U,100U}, model::RationalIncrement{1U,100000U},
      model::RationalIncrement{1U,100U}, model::QuantityLots{1U}, model::QuantityLots{1000000U},
      "step15-demo-v1"};
}
policy::PolicyEnvironment environment() {
  return policy::PolicyEnvironment{instrument(), model::StrategyId{"replay-demo"},
      model::FeeScheduleId{"fee-v1"}, model::LatencyModelId{"observed-v1"}, 50, 2U, 4U, 1U, 1U,
      {policy::QuantityFraction{1U,1U}}, {model::TickOffset{0}},
      policy::LotRoundingPolicy::Floor, true, true, true};
}
}

int main() {
  auto env = environment();
  simulation::SimulationKernelConfig kernel{exchange::MatchingEngineConfig{instrument()},
      model::RunId{"step15-demo-run"}, 1U, simulation::LatencyModelConfig{},
      model::SourceChannelId{"strategy"}, model::SourceChannelId{"orders"},
      model::SourceChannelId{"fills"}, model::SourceChannelId{"trades"},
      model::SourceChannelId{"system"}, 100000U, 100000U};
  historical::HistoricalReplayConfig config{kernel, env, 5,
      model::SourceChannelId{"historical-l2"}, 10000U, 10000U, true};
  historical::ReplayConnection connection{
      historical::ReplaySnapshot{"connection-0000", 100U, ts(0), ts(100),
          {model::BookLevel{model::PriceTicks{100}, model::QuantityLots{50U}, std::nullopt}},
          {model::BookLevel{model::PriceTicks{102}, model::QuantityLots{55U}, std::nullopt}}, 1U},
      {historical::ReplayDepthBatch{2U,100U,101U,ts(90),ts(100),
          {model::DepthUpdate{model::Side::Buy,model::PriceTicks{100},model::QuantityLots{70U},
              model::BookUpdateAction::Set,std::nullopt}}},
       historical::ReplayTrade{3U,ts(145),ts(150),
          model::Trade{model::TradeId{500U},model::ExternalTradeId{"500"},model::PriceTicks{102},
              model::QuantityLots{4U},model::AggressorSide::Buy}}}};
  policy::ExecutionState state{policy::ParentOrderDefinition{model::ParentOrderId{1U},model::Side::Buy,
      model::QuantityLots{100U},ts(0),ts(1000),model::PriceTicks{101},"hard-completion-v1"},env};
  historical::HistoricalReplayEngine engine{config};
  auto result = engine.run({connection},
      {{model::DecisionId{1U},ts(104)},{model::DecisionId{2U},ts(105)},
       {model::DecisionId{3U},ts(160)}},state);
  std::cout << "step=15\n" << result.canonical_summary;
  return 0;
}
