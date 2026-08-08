#include "policy_test_support.hpp"
#include "simulation_test_support.hpp"

#include <cstdlib>

int main() {
  namespace model = robust_execution::model;
  namespace policy = robust_execution::policy;
  namespace simulation = robust_execution::simulation;

  auto config = simulation_test::kernel_config();
  config.exchange.instrument = policy_test::instrument();
  config.run_id = model::RunId{"terminal-integration-run"};
  simulation::SimulationKernel kernel{config};
  policy::ExecutionState state{policy_test::parent(), policy_test::environment()};
  policy::ObservationBuilder builder{policy_test::environment()};
  policy::ActionValidator validator{policy_test::environment()};
  policy::TerminalCompletionPlanner planner{
      policy::TerminalRuleConfig{"hard-completion-v1", 1U, true}
  };

  builder.ingest_delivered_event(policy_test::snapshot(), policy_test::time(110));
  const auto terminal_observation = builder.build(
      model::DecisionId{1U},
      policy_test::time(1'000),
      state
  );
  const auto plan = planner.plan(
      terminal_observation,
      model::DecisionId{1U},
      model::ClientOrderId{10U}
  );
  if (plan.kind != policy::TerminalPlanKind::SubmitAggressiveResidual || !plan.action.has_value()) {
    return EXIT_FAILURE;
  }
  const auto validated = validator.validate(*plan.action, terminal_observation, state);
  if (!validated.valid()) {
    return EXIT_FAILURE;
  }
  planner.record_aggressive_attempt();
  if (planner.aggressive_attempts() != 1U) {
    return EXIT_FAILURE;
  }

  const auto fallback_plan = planner.plan(
      terminal_observation,
      model::DecisionId{2U},
      model::ClientOrderId{11U}
  );
  if (fallback_plan.kind != policy::TerminalPlanKind::RequiresExplicitFallback) {
    return EXIT_FAILURE;
  }
  const auto completion = planner.explicit_fallback(
      terminal_observation,
      model::PriceTicks{105},
      model::QuoteAtoms{7}
  );
  state.mark_terminal_completion_pending();
  const auto event_id = kernel.schedule_terminal_completion(completion, policy_test::time(1'001));
  if (!event_id.valid()) {
    return EXIT_FAILURE;
  }
  kernel.run();
  if (kernel.delivered_events().size() != 1U) {
    return EXIT_FAILURE;
  }
  const auto& event = kernel.delivered_events().front();
  builder.ingest_delivered_event(event, *event.header.available_time);
  const auto issues = state.apply_delivered_event(event, *event.header.available_time);
  if (!issues.empty()) {
    return EXIT_FAILURE;
  }

  const auto completed = state.parent_snapshot(policy_test::time(1'001));
  if (completed.status != policy::ParentOrderStatus::Completed ||
      completed.cumulative_filled.value() != 100U ||
      completed.remaining_quantity.value() != 0U ||
      completed.gross_cash_flow.value() != -10'500 ||
      completed.explicit_fees.value() != 7 ||
      completed.net_cash_flow.value() != -10'507 ||
      !completed.terminal_completion_applied) {
    return EXIT_FAILURE;
  }

  const auto final_observation = builder.build(
      model::DecisionId{3U},
      policy_test::time(1'001),
      state
  );
  const auto no_action = validator.validate(
      policy::PolicyAction{
          model::DecisionId{3U},
          policy_test::time(1'001),
          policy::NoAction{},
      },
      final_observation,
      state
  );
  if (!no_action.valid() || no_action.action->kind != policy::PolicyActionKind::NoAction) {
    return EXIT_FAILURE;
  }

  planner.reset();
  if (planner.aggressive_attempts() != 0U) {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
