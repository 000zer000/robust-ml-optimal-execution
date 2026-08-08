#include "historical_test_support.hpp"

#include <cstdlib>
#include <stdexcept>

int main() {
  historical_test::historical::HistoricalReplayEngine engine{historical_test::config()};
  {
    auto bad = historical_test::connection();
    auto& depth = std::get<historical_test::historical::ReplayDepthBatch>(bad.messages.front());
    depth.first_update_id = 102U;
    bool rejected = false;
    try {
      auto state = historical_test::state();
      (void)engine.run({bad}, historical_test::checkpoints(), state);
    } catch (const std::invalid_argument&) {
      rejected = true;
    }
    if (!rejected) {
      return EXIT_FAILURE;
    }
  }
  {
    auto points = historical_test::checkpoints();
    points[1].decision_time = historical_test::time(103);
    bool rejected = false;
    try {
      auto state = historical_test::state();
      (void)engine.run({historical_test::connection()}, points, state);
    } catch (const std::invalid_argument&) {
      rejected = true;
    }
    if (!rejected) {
      return EXIT_FAILURE;
    }
  }
  {
    auto config = historical_test::config();
    config.observation_processing_delay_ns = -1;
    bool rejected = false;
    try {
      historical_test::historical::HistoricalReplayEngine bad_engine{config};
    } catch (const std::invalid_argument&) {
      rejected = true;
    }
    if (!rejected) {
      return EXIT_FAILURE;
    }
  }
  return EXIT_SUCCESS;
}
