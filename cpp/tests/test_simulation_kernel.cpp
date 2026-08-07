#include "simulation_test_support.hpp"

#include <algorithm>
#include <cstdlib>
#include <string>

namespace {

struct ScenarioResult {
  std::string replay_hash;
  std::string state_hash;
  std::string trace;
  std::size_t delivered_count{0U};
};

ScenarioResult run_scenario(std::uint64_t buyer_quantity = 3U) {
  namespace model = robust_execution::model;
  namespace simulation = robust_execution::simulation;
  simulation::SimulationKernel kernel{simulation_test::kernel_config()};
  (void)kernel.schedule_market_event(simulation_test::market_trade(1U, 1U, 50), 1U);
  const auto maker = kernel.schedule_submit(
      simulation_test::limit(10U, model::Side::Sell, 3U, 101),
      simulation_test::time(100),
      10U
  );
  const auto taker = kernel.schedule_submit(
      simulation_test::market(11U, model::Side::Buy, buyer_quantity, 2U),
      simulation_test::time(200),
      11U
  );
  if (maker.timing.exchange_receive.value() != 106 ||
      maker.timing.exchange_process.value() != 109 ||
      maker.timing.acknowledgement_available.value() != 116 ||
      taker.timing.exchange_receive.value() != 206 ||
      taker.timing.exchange_process.value() != 209 ||
      taker.timing.acknowledgement_available.value() != 216) {
    return {};
  }
  kernel.run();
  return ScenarioResult{
      kernel.replay_hash(),
      kernel.state_hash(),
      kernel.canonical_trace(),
      kernel.delivered_events().size(),
  };
}

}  // namespace

int main() {
  namespace model = robust_execution::model;
  namespace simulation = robust_execution::simulation;
  const auto first = run_scenario();
  const auto second = run_scenario();
  const auto changed = run_scenario(2U);
  if (first.replay_hash.size() != 64U || first.state_hash.size() != 64U ||
      first.replay_hash != second.replay_hash || first.state_hash != second.state_hash ||
      first.trace != second.trace || first.delivered_count != 6U ||
      first.replay_hash == changed.replay_hash || first.state_hash == changed.state_hash) {
    return EXIT_FAILURE;
  }

  simulation::SimulationKernel partial{simulation_test::kernel_config()};
  (void)partial.schedule_submit(
      simulation_test::limit(20U, model::Side::Sell, 2U, 102),
      simulation_test::time(100),
      20U
  );
  partial.run_until(simulation_test::time(110));
  if (partial.empty() || !partial.delivered_events().empty() ||
      partial.exchange_received_events().size() != 1U ||
      partial.matching_engine().active_order_count() != 1U) {
    return EXIT_FAILURE;
  }
  partial.run();
  if (!partial.empty() || partial.delivered_events().size() != 1U ||
      model::event_kind(partial.delivered_events().front().payload) !=
          model::EventKind::OrderAcknowledged) {
    return EXIT_FAILURE;
  }

  return EXIT_SUCCESS;
}
