#include "simulation_test_support.hpp"

#include <cstdlib>

int main() {
  namespace model = robust_execution::model;
  namespace simulation = robust_execution::simulation;
  simulation::SimulationKernel kernel{simulation_test::kernel_config()};
  (void)kernel.schedule_submit(
      simulation_test::limit(30U, model::Side::Sell, 1U, 101),
      simulation_test::time(100),
      30U
  );
  kernel.run();
  const auto view = kernel.matching_engine().order(model::ClientOrderId{30U});
  if (!view.has_value() || view->exchange_order_id.value() != 1U) {
    return EXIT_FAILURE;
  }

  (void)kernel.schedule_submit(
      simulation_test::limit(30U, model::Side::Buy, 1U, 100, model::TimeInForce::GoodTilCancelled, false, 2U),
      simulation_test::time(200),
      31U
  );
  kernel.run();
  if (kernel.failures().size() != 1U ||
      kernel.failures().front().failure.code !=
          robust_execution::exchange::EngineFailureCode::DuplicateClientOrderId ||
      model::event_kind(kernel.delivered_events().back().payload) != model::EventKind::OrderRejected) {
    return EXIT_FAILURE;
  }

  (void)kernel.schedule_cancel(
      simulation_test::cancel(30U, 1U, 3U),
      simulation_test::time(300),
      32U
  );
  kernel.run();
  if (model::event_kind(kernel.delivered_events().back().payload) !=
      model::EventKind::CancelAcknowledged) {
    return EXIT_FAILURE;
  }

  const auto delivered_before = kernel.delivered_events().size();
  (void)kernel.schedule_cancel(
      simulation_test::cancel(30U, 1U, 4U),
      simulation_test::time(400),
      33U
  );
  kernel.run();
  if (kernel.failures().size() != 2U ||
      kernel.failures().back().failure.code !=
          robust_execution::exchange::EngineFailureCode::AlreadyTerminal ||
      kernel.delivered_events().size() != delivered_before) {
    return EXIT_FAILURE;
  }

  return EXIT_SUCCESS;
}
