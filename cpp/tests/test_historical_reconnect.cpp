#include "historical_test_support.hpp"

#include <cstdlib>
#include <utility>

namespace {

historical_test::historical::ReplayConnection second_connection() {
  namespace historical = historical_test::historical;
  namespace model = historical_test::model;

  historical::ReplaySnapshot snapshot{
      "connection-0001",
      200U,
      historical_test::time(220),
      historical_test::time(300),
      {model::BookLevel{model::PriceTicks{104}, model::QuantityLots{60U}, std::nullopt}},
      {model::BookLevel{model::PriceTicks{106}, model::QuantityLots{60U}, std::nullopt}},
      5U,
  };
  historical::ReplayTrade pre_bridge_trade{
      5U,
      historical_test::time(245),
      historical_test::time(250),
      model::Trade{
          model::TradeId{501U},
          model::ExternalTradeId{"501"},
          model::PriceTicks{105},
          model::QuantityLots{2U},
          model::AggressorSide::Buy,
      },
  };
  historical::ReplayDepthBatch bridge{
      6U,
      200U,
      201U,
      historical_test::time(295),
      historical_test::time(300),
      {
          model::DepthUpdate{
              model::Side::Buy,
              model::PriceTicks{104},
              model::QuantityLots{70U},
              model::BookUpdateAction::Set,
              std::nullopt,
          },
          model::DepthUpdate{
              model::Side::Sell,
              model::PriceTicks{106},
              model::QuantityLots{50U},
              model::BookUpdateAction::Set,
              std::nullopt,
          },
      },
  };
  return historical::ReplayConnection{
      std::move(snapshot),
      {std::move(pre_bridge_trade), std::move(bridge)},
  };
}

}  // namespace

int main() {
  auto state = historical_test::state();
  historical_test::historical::HistoricalReplayEngine engine{historical_test::config()};
  auto checkpoints = historical_test::checkpoints();
  checkpoints.push_back(
      historical_test::historical::ReplayCheckpoint{
          historical_test::model::DecisionId{5U}, historical_test::time(260)}
  );
  checkpoints.push_back(
      historical_test::historical::ReplayCheckpoint{
          historical_test::model::DecisionId{6U}, historical_test::time(304)}
  );
  checkpoints.push_back(
      historical_test::historical::ReplayCheckpoint{
          historical_test::model::DecisionId{7U}, historical_test::time(305)}
  );

  const auto result = engine.run(
      {historical_test::connection(), second_connection()}, checkpoints, state
  );
  if (result.integrity.connection_count != 2U ||
      result.integrity.synchronized_connection_count != 2U ||
      result.integrity.suppressed_checkpoint_count != 3U ||
      result.observations.size() != 4U) {
    return EXIT_FAILURE;
  }
  const auto& after_reconnect = result.observations.back();
  if (!after_reconnect.best_bid().has_value() || after_reconnect.best_bid()->value() != 104 ||
      !after_reconnect.best_ask().has_value() || after_reconnect.best_ask()->value() != 106 ||
      after_reconnect.recent_trades().size() != 1U ||
      after_reconnect.recent_trades().front().trade.trade_id.value() != 501U) {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
