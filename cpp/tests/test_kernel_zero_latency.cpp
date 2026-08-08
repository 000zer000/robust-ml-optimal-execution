#include "simulation_test_support.hpp"

#include <cstdlib>
#include <vector>

int main() {
  namespace model = robust_execution::model;
  namespace simulation = robust_execution::simulation;
  auto config = simulation_test::kernel_config();
  config.latency = simulation::LatencyModelConfig{};
  simulation::SimulationKernel kernel{config};
  (void)kernel.schedule_submit(
      simulation_test::limit(40U, model::Side::Sell, 1U, 101),
      simulation_test::time(100),
      40U
  );
  (void)kernel.schedule_submit(
      simulation_test::market(41U, model::Side::Buy, 1U, 2U),
      simulation_test::time(100),
      41U
  );
  kernel.run();

  if (kernel.exchange_received_events().size() != 2U ||
      kernel.delivered_events().size() != 5U ||
      kernel.current_time()->value() != 100 ||
      !kernel.matching_engine().validate_invariants().empty()) {
    return EXIT_FAILURE;
  }
  const std::vector<model::EventKind> expected{
      model::EventKind::OrderAcknowledged,
      model::EventKind::OrderAcknowledged,
      model::EventKind::Trade,
      model::EventKind::Fill,
      model::EventKind::Fill,
  };
  std::vector<model::EventKind> actual;
  for (const auto& event : kernel.delivered_events()) {
    actual.push_back(model::event_kind(event.payload));
  }
  return actual == expected ? EXIT_SUCCESS : EXIT_FAILURE;
}
