#include "historical_test_support.hpp"

#include <cstdlib>

int main() {
  auto first_state = historical_test::state();
  auto second_state = historical_test::state();
  historical_test::historical::HistoricalReplayEngine engine{historical_test::config()};
  const auto first = engine.run({historical_test::connection()}, historical_test::checkpoints(), first_state);
  const auto second = engine.run({historical_test::connection()}, historical_test::checkpoints(), second_state);
  if (first.observations.size() != 3U || first.integrity.suppressed_checkpoint_count != 1U ||
      first.integrity.snapshot_count != 1U || first.integrity.depth_batch_count != 2U ||
      first.integrity.depth_update_count != 3U || first.integrity.trade_count != 1U ||
      first.integrity.delivered_event_count != 5U ||
      first.kernel_replay_hash != second.kernel_replay_hash ||
      first.kernel_state_hash != second.kernel_state_hash ||
      first.canonical_summary != second.canonical_summary ||
      first.integrity.exact_fifo_reconstructed || first.integrity.endogenous_impact_modelled) {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
