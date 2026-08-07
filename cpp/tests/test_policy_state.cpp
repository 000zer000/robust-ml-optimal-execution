#include "policy_test_support.hpp"

#include <cstdlib>

int main() {
  namespace model = robust_execution::model;
  namespace policy = robust_execution::policy;

  policy::ExecutionState state{policy_test::parent(), policy_test::environment()};
  const auto submit = policy_test::validated_submit(10U, 100U);
  state.register_action(submit);
  if (state.pending_command_count() != 1U || state.acknowledged_active_order_count() != 0U) {
    return EXIT_FAILURE;
  }

  auto issues = state.apply_delivered_event(
      policy_test::event(
          10U,
          121,
          122,
          model::OrderAcknowledged{
              model::ClientOrderId{10U},
              model::ExchangeOrderId{50U},
              std::nullopt,
              model::QuantityLots{100U},
              model::QuantityLots{0U},
              model::QuantityLots{100U},
              model::OrderState::Live,
          }
      ),
      policy_test::time(122)
  );
  if (!issues.empty() || state.pending_command_count() != 0U ||
      state.acknowledged_active_order_count() != 1U) {
    return EXIT_FAILURE;
  }

  const auto fill_event = policy_test::event(
      11U,
      123,
      124,
      model::Fill{
          model::ExecutionId{70U},
          model::ClientOrderId{10U},
          model::ExchangeOrderId{50U},
          std::nullopt,
          model::Side::Buy,
          model::PriceTicks{101},
          model::QuantityLots{40U},
          model::QuantityLots{40U},
          model::QuantityLots{60U},
          model::LiquidityRole::Maker,
      }
  );
  issues = state.apply_delivered_event(fill_event, policy_test::time(124));
  issues = state.apply_delivered_event(
      policy_test::event(
          12U,
          123,
          124,
          model::Fee{
              model::ExecutionId{70U},
              model::FeeScheduleId{"fee-v1"},
              model::QuoteAtoms{5},
              model::LiquidityRole::Maker,
          }
      ),
      policy_test::time(124)
  );
  const auto snapshot = state.parent_snapshot(policy_test::time(200));
  if (!issues.empty() || snapshot.cumulative_filled.value() != 40U ||
      snapshot.remaining_quantity.value() != 60U || snapshot.gross_cash_flow.value() != -4040 ||
      snapshot.explicit_fees.value() != 5 || snapshot.net_cash_flow.value() != -4045 ||
      snapshot.fill_count != 1U || snapshot.status != policy::ParentOrderStatus::Active) {
    return EXIT_FAILURE;
  }

  const auto duplicate = state.apply_delivered_event(fill_event, policy_test::time(124));
  if (duplicate.size() != 1U || duplicate.front().code != "duplicate_event") {
    return EXIT_FAILURE;
  }

  const auto cancel = policy::ValidatedPolicyAction{
      model::DecisionId{2U},
      policy_test::time(300),
      policy::PolicyActionKind::Cancel,
      "cancel",
      {model::CancelRequest{
          model::ClientOrderId{10U},
          model::ExchangeOrderId{50U},
          model::DecisionId{2U},
          policy_test::time(300),
          policy_test::time(300),
          policy_test::time(300),
      }},
      model::QuantityLots{0U},
  };
  state.register_action(cancel);
  if (state.pending_command_count() != 1U) {
    return EXIT_FAILURE;
  }
  issues = state.apply_delivered_event(
      policy_test::event(
          13U,
          301,
          302,
          model::CancelAcknowledged{
              model::ClientOrderId{10U},
              model::ExchangeOrderId{50U},
              model::QuantityLots{40U},
              model::QuantityLots{60U},
              model::QuantityLots{0U},
              model::OrderState::Cancelled,
          }
      ),
      policy_test::time(302)
  );
  if (!issues.empty() || state.acknowledged_active_order_count() != 0U) {
    return EXIT_FAILURE;
  }

  state.mark_terminal_completion_pending();
  issues = state.apply_delivered_event(
      policy_test::event(
          14U,
          1'001,
          1'002,
          model::TerminalCompletion{
              model::ParentOrderId{1U},
              model::Side::Buy,
              model::QuantityLots{60U},
              model::PriceTicks{102},
              model::QuoteAtoms{6},
              "hard-completion-v1",
          },
          model::EventOrigin::System
      ),
      policy_test::time(1'002)
  );
  const auto completed = state.parent_snapshot(policy_test::time(1'002));
  if (!issues.empty() || completed.status != policy::ParentOrderStatus::Completed ||
      completed.remaining_quantity.value() != 0U || completed.gross_cash_flow.value() != -10160 ||
      completed.explicit_fees.value() != 11 || completed.net_cash_flow.value() != -10171 ||
      !completed.terminal_completion_applied || completed.fill_count != 2U ||
      state.state_hash(policy_test::time(1'002)).size() != 64U) {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
