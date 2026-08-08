#include "policy_test_support.hpp"
#include "simulation_test_support.hpp"

#include <cstdlib>
#include <stdexcept>

int main() {
  namespace model = robust_execution::model;
  namespace policy = robust_execution::policy;
  namespace simulation = robust_execution::simulation;

  auto kernel_config = simulation_test::kernel_config();
  kernel_config.exchange.instrument = policy_test::instrument();
  kernel_config.run_id = model::RunId{"policy-dispatch-run"};
  simulation::SimulationKernel kernel{kernel_config};
  policy::ExecutionState state{policy_test::parent(), policy_test::environment()};

  const auto action = policy_test::validated_submit(10U, 20U);
  const auto dispatched = policy::dispatch_validated_action(kernel, state, action, 100U);
  if (dispatched.commands.size() != 1U || dispatched.next_logical_index != 101U ||
      state.pending_command_count() != 1U) {
    return EXIT_FAILURE;
  }
  kernel.run();
  for (const auto& event : kernel.delivered_events()) {
    const auto issues = state.apply_delivered_event(event, *event.header.available_time);
    if (!issues.empty()) {
      return EXIT_FAILURE;
    }
  }
  if (state.pending_command_count() != 0U || state.acknowledged_active_order_count() != 1U) {
    return EXIT_FAILURE;
  }

  policy::ValidatedPolicyAction duplicate{
      model::DecisionId{2U},
      policy_test::time(200),
      policy::PolicyActionKind::Submit,
      "submit",
      {model::OrderSubmit{
          model::ParentOrderId{1U},
          model::ClientOrderId{10U},
          model::DecisionId{2U},
          model::Side::Buy,
          model::OrderType::Limit,
          model::TimeInForce::GoodTilCancelled,
          model::QuantityLots{1U},
          model::PriceTicks{99},
          false,
          policy_test::time(200),
          policy_test::time(200),
          policy_test::time(200),
      }},
      model::QuantityLots{1U},
  };
  bool duplicate_rejected = false;
  try {
    state.register_action(duplicate);
  } catch (const std::logic_error&) {
    duplicate_rejected = true;
  }
  if (!duplicate_rejected) {
    return EXIT_FAILURE;
  }

  const auto child = state.child_order(model::ClientOrderId{10U});
  if (!child.has_value()) {
    return EXIT_FAILURE;
  }
  const auto cancel_command = model::CancelRequest{
      child->client_order_id,
      *child->exchange_order_id,
      model::DecisionId{3U},
      policy_test::time(300),
      policy_test::time(300),
      policy_test::time(300),
  };
  const auto cancel_action = policy::ValidatedPolicyAction{
      model::DecisionId{3U},
      policy_test::time(300),
      policy::PolicyActionKind::Cancel,
      "cancel",
      {cancel_command},
      model::QuantityLots{0U},
  };
  state.register_action(cancel_action);
  state.apply_engine_failure(
      cancel_command,
      robust_execution::exchange::EngineFailure{
          robust_execution::exchange::EngineFailureCode::AlreadyTerminal,
          model::RejectReason::AlreadyTerminal,
          child->client_order_id,
          child->exchange_order_id,
          model::OrderState::Filled,
          "synthetic failure path",
      }
  );
  const auto resolved = state.child_order(model::ClientOrderId{10U});
  if (!resolved.has_value() || resolved->cancel_pending ||
      resolved->state != model::OrderState::Filled) {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
