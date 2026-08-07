#include "simulation_test_support.hpp"

#include <cstdlib>
#include <stdexcept>

int main() {
  namespace model = robust_execution::model;
  namespace simulation = robust_execution::simulation;

  simulation::SimulationKernel kernel{simulation_test::kernel_config()};
  auto event = simulation_test::market_trade(900U, 900U, 50);
  const auto event_id = kernel.schedule_market_event_with_timing(
      event,
      simulation_test::time(80),
      simulation_test::time(90)
  );
  if (event_id.value() != 900U || kernel.pending_task_count() != 1U) {
    return EXIT_FAILURE;
  }
  kernel.run_until(simulation_test::time(89));
  if (!kernel.delivered_events().empty() || kernel.pending_task_count() != 1U) {
    return EXIT_FAILURE;
  }
  kernel.run_until(simulation_test::time(90));
  if (kernel.delivered_events().size() != 1U || !kernel.empty()) {
    return EXIT_FAILURE;
  }
  const auto& delivered = kernel.delivered_events().front();
  if (delivered.header.event_time.value() != 50 ||
      !delivered.header.receive_time.has_value() ||
      delivered.header.receive_time->value() != 80 ||
      !delivered.header.available_time.has_value() ||
      delivered.header.available_time->value() != 90) {
    return EXIT_FAILURE;
  }

  {
    simulation::SimulationKernel invalid{simulation_test::kernel_config()};
    bool rejected = false;
    try {
      (void)invalid.schedule_market_event_with_timing(
          simulation_test::market_trade(901U, 901U, 100),
          simulation_test::time(99),
          simulation_test::time(110)
      );
    } catch (const std::invalid_argument&) {
      rejected = true;
    }
    if (!rejected) {
      return EXIT_FAILURE;
    }
  }

  {
    simulation::SimulationKernel invalid{simulation_test::kernel_config()};
    bool rejected = false;
    try {
      (void)invalid.schedule_market_event_with_timing(
          simulation_test::market_trade(902U, 902U, 100),
          simulation_test::time(110),
          simulation_test::time(109)
      );
    } catch (const std::invalid_argument&) {
      rejected = true;
    }
    if (!rejected) {
      return EXIT_FAILURE;
    }
  }

  {
    simulation::SimulationKernel invalid{simulation_test::kernel_config()};
    auto wrong_origin = simulation_test::market_trade(903U, 903U, 100);
    wrong_origin.header.origin = model::EventOrigin::Strategy;
    bool rejected = false;
    try {
      (void)invalid.schedule_market_event_with_timing(
          std::move(wrong_origin),
          simulation_test::time(100),
          simulation_test::time(100)
      );
    } catch (const std::invalid_argument&) {
      rejected = true;
    }
    if (!rejected) {
      return EXIT_FAILURE;
    }
  }

  return EXIT_SUCCESS;
}
