#include "policy_test_support.hpp"

#include <cstdlib>

int main() {
  namespace model = robust_execution::model;
  namespace policy = robust_execution::policy;

  policy::TerminalCompletionPlanner planner{
      policy::TerminalRuleConfig{"hard-completion-v1", 1U, true}
  };
  policy::ExecutionState state{policy_test::parent(), policy_test::environment()};

  const auto pre_terminal = policy_test::observation(state, model::DecisionId{1U}, 900);
  if (planner.plan(pre_terminal, model::DecisionId{1U}, model::ClientOrderId{10U}).kind !=
      policy::TerminalPlanKind::None) {
    return EXIT_FAILURE;
  }

  const auto terminal_observation = policy_test::observation(state, model::DecisionId{2U}, 1'000);
  const auto aggressive = planner.plan(
      terminal_observation,
      model::DecisionId{2U},
      model::ClientOrderId{10U}
  );
  if (aggressive.kind != policy::TerminalPlanKind::SubmitAggressiveResidual ||
      !aggressive.action.has_value() || planner.aggressive_attempts() != 0U) {
    return EXIT_FAILURE;
  }
  const auto& submit = std::get<policy::SubmitChildAction>(aggressive.action->payload);
  if (submit.order_type != model::OrderType::Market ||
      submit.quantity_fraction != policy::QuantityFraction{1U, 1U}) {
    return EXIT_FAILURE;
  }

  planner.record_aggressive_attempt();
  const auto fallback_plan = planner.plan(
      terminal_observation,
      model::DecisionId{3U},
      model::ClientOrderId{11U}
  );
  if (fallback_plan.kind != policy::TerminalPlanKind::RequiresExplicitFallback) {
    return EXIT_FAILURE;
  }
  const auto fallback = planner.explicit_fallback(
      terminal_observation,
      model::PriceTicks{105},
      model::QuoteAtoms{7}
  );
  if (fallback.quantity.value() != 100U || fallback.price.value() != 105 ||
      fallback.rule_id != "hard-completion-v1") {
    return EXIT_FAILURE;
  }

  const auto submit_action = policy_test::validated_submit(20U, 100U);
  state.register_action(submit_action);
  const auto pending_observation = policy_test::observation(state, model::DecisionId{4U}, 1'001);
  if (planner.plan(pending_observation, model::DecisionId{4U}, model::ClientOrderId{21U}).kind !=
      policy::TerminalPlanKind::AwaitPendingCommands) {
    return EXIT_FAILURE;
  }

  auto issues = state.apply_delivered_event(
      policy_test::event(
          30U,
          1'002,
          1'003,
          model::OrderAcknowledged{
              model::ClientOrderId{20U},
              model::ExchangeOrderId{60U},
              std::nullopt,
              model::QuantityLots{100U},
              model::QuantityLots{0U},
              model::QuantityLots{100U},
              model::OrderState::Live,
          }
      ),
      policy_test::time(1'003)
  );
  if (!issues.empty()) {
    return EXIT_FAILURE;
  }
  const auto active_observation = policy_test::observation(state, model::DecisionId{5U}, 1'004);
  const auto cancel = planner.plan(
      active_observation,
      model::DecisionId{5U},
      model::ClientOrderId{21U}
  );
  if (cancel.kind != policy::TerminalPlanKind::CancelActiveChildren ||
      !cancel.action.has_value() ||
      std::get<policy::CancelChildAction>(cancel.action->payload).client_order_ids.size() != 1U) {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
