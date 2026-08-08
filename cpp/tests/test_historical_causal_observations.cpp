#include "historical_test_support.hpp"

#include <cstdlib>

int main() {
  auto state = historical_test::state();
  historical_test::historical::HistoricalReplayEngine engine{historical_test::config()};
  const auto result = engine.run({historical_test::connection()}, historical_test::checkpoints(), state);
  if (result.observations.size() != 3U) {
    return EXIT_FAILURE;
  }
  const auto& after_bridge = result.observations[0];
  const auto& after_trade = result.observations[1];
  const auto& after_delete = result.observations[2];
  if (!after_bridge.best_bid().has_value() || after_bridge.best_bid()->value() != 100 ||
      !after_bridge.best_ask().has_value() || after_bridge.best_ask()->value() != 102 ||
      after_bridge.recent_trades().size() != 0U ||
      after_trade.recent_trades().size() != 1U ||
      after_trade.recent_trades().front().trade.trade_id.value() != 500U ||
      !after_delete.best_ask().has_value() || after_delete.best_ask()->value() != 103 ||
      after_trade.lineage().maximum_available_time->value() > after_trade.decision_time().value()) {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
