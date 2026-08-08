#include "simulation_test_support.hpp"

#include <cstdlib>
#include <stdexcept>
#include <vector>

namespace {

robust_execution::simulation::KernelTask task(std::uint64_t event_id) {
  auto event = simulation_test::market_trade(event_id, event_id, 10);
  return robust_execution::simulation::KernelTask{
      robust_execution::simulation::KernelTaskKind::ObserverDelivery,
      std::move(event),
      std::nullopt,
  };
}

}  // namespace

int main() {
  namespace model = robust_execution::model;
  namespace simulation = robust_execution::simulation;
  simulation::DeterministicScheduler scheduler;
  const auto id1 = scheduler.schedule(
      simulation_test::time(20), simulation::KernelStage::ObserverAvailable, 2U, task(2U)
  );
  const auto id2 = scheduler.schedule(
      simulation_test::time(10), simulation::KernelStage::System, 3U, task(3U)
  );
  const auto id3 = scheduler.schedule(
      simulation_test::time(10), simulation::KernelStage::ExchangeReceive, 4U, task(4U)
  );
  const auto id4 = scheduler.schedule(
      simulation_test::time(10), simulation::KernelStage::ExchangeReceive, 1U, task(1U)
  );
  if (id1 != 1U || id2 != 2U || id3 != 3U || id4 != 4U || scheduler.size() != 4U) {
    return EXIT_FAILURE;
  }
  std::vector<std::uint64_t> order;
  while (!scheduler.empty()) {
    order.push_back(scheduler.pop_next().task.event.header.event_id.value());
  }
  if (order != std::vector<std::uint64_t>{1U, 4U, 3U, 2U}) {
    return EXIT_FAILURE;
  }

  bool mixed_clock = false;
  bool past = false;
  bool empty = false;
  bool zero_sequence = false;
  try {
    (void)scheduler.schedule(
        model::TimestampNs{model::ClockDomain::UnixUtc, 30},
        simulation::KernelStage::System,
        1U,
        task(5U)
    );
  } catch (const std::invalid_argument&) {
    mixed_clock = true;
  }
  try {
    (void)scheduler.schedule(
        simulation_test::time(19), simulation::KernelStage::System, 1U, task(6U)
    );
  } catch (const std::invalid_argument&) {
    past = true;
  }
  try {
    (void)scheduler.pop_next();
  } catch (const std::out_of_range&) {
    empty = true;
  }
  try {
    simulation::DeterministicScheduler fresh;
    (void)fresh.schedule(
        simulation_test::time(1), simulation::KernelStage::System, 0U, task(7U)
    );
  } catch (const std::invalid_argument&) {
    zero_sequence = true;
  }
  return mixed_clock && past && empty && zero_sequence ? EXIT_SUCCESS : EXIT_FAILURE;
}
