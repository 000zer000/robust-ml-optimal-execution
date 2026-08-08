#include "policy_test_support.hpp"

#include <cstdlib>
#include <stdexcept>

int main() {
  namespace model = robust_execution::model;
  namespace policy = robust_execution::policy;

  policy::ExecutionState state{policy_test::parent(), policy_test::environment()};
  const auto observation = policy_test::observation(state, model::DecisionId{1U}, 120);
  if (observation.elapsed_time_ns() != 120 || observation.time_remaining_ns() != 880) {
    return EXIT_FAILURE;
  }

  const auto submit = policy_test::validated_submit(10U, 100U);
  state.register_action(submit);
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
  if (!issues.empty()) {
    return EXIT_FAILURE;
  }

  issues = state.apply_delivered_event(
      policy_test::event(
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
              model::QuantityLots{45U},
              model::QuantityLots{55U},
              model::LiquidityRole::Maker,
          }
      ),
      policy_test::time(124)
  );
  if (issues.size() != 1U || issues.front().code != "fill_quantity_mismatch" ||
      state.parent_snapshot(policy_test::time(124)).cumulative_filled.value() != 0U) {
    return EXIT_FAILURE;
  }

  issues = state.apply_delivered_event(
      policy_test::event(
          12U,
          125,
          126,
          model::Fill{
              model::ExecutionId{71U},
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
      ),
      policy_test::time(126)
  );
  if (!issues.empty()) {
    return EXIT_FAILURE;
  }
  issues = state.apply_delivered_event(
      policy_test::event(
          13U,
          125,
          126,
          model::Fee{
              model::ExecutionId{71U},
              model::FeeScheduleId{"wrong-fee"},
              model::QuoteAtoms{7},
              model::LiquidityRole::Maker,
          }
      ),
      policy_test::time(126)
  );
  if (issues.size() != 1U || issues.front().code != "fee_schedule_mismatch" ||
      state.parent_snapshot(policy_test::time(126)).explicit_fees.value() != 0) {
    return EXIT_FAILURE;
  }

  state.mark_terminal_completion_pending();
  issues = state.apply_delivered_event(
      policy_test::event(
          14U,
          1'000,
          1'000,
          model::TerminalCompletion{
              model::ParentOrderId{1U},
              model::Side::Buy,
              model::QuantityLots{60U},
              model::PriceTicks{105},
              model::QuoteAtoms{3},
              "wrong-terminal-rule",
          },
          model::EventOrigin::System
      ),
      policy_test::time(1'000)
  );
  if (issues.size() != 1U || issues.front().code != "terminal_rule_mismatch" ||
      state.parent_snapshot(policy_test::time(1'000)).remaining_quantity.value() != 60U) {
    return EXIT_FAILURE;
  }

  policy::ObservationBuilder builder{policy_test::environment()};
  bool crossed_rejected = false;
  try {
    builder.ingest_delivered_event(
        policy_test::event(
            20U,
            100,
            110,
            model::BookSnapshot{
                {model::BookLevel{model::PriceTicks{102}, model::QuantityLots{1U}, 1U}},
                {model::BookLevel{model::PriceTicks{102}, model::QuantityLots{1U}, 1U}},
            }
        ),
        policy_test::time(110)
    );
  } catch (const std::invalid_argument&) {
    crossed_rejected = true;
  }
  if (!crossed_rejected) {
    return EXIT_FAILURE;
  }
  builder.ingest_delivered_event(policy_test::snapshot(21U, 111, 112), policy_test::time(112));
  const auto recovered = builder.build(model::DecisionId{2U}, policy_test::time(120), state);
  if (recovered.best_bid()->value() != 100 || recovered.best_ask()->value() != 102 ||
      recovered.lineage().delivered_event_count != 1U) {
    return EXIT_FAILURE;
  }

  auto other_environment = policy_test::environment();
  other_environment.fee_schedule_id = model::FeeScheduleId{"other-fee"};
  policy::ObservationBuilder other_builder{other_environment};
  bool mismatch_rejected = false;
  try {
    static_cast<void>(other_builder.build(model::DecisionId{2U}, policy_test::time(200), state));
  } catch (const std::invalid_argument&) {
    mismatch_rejected = true;
  }
  if (!mismatch_rejected) {
    return EXIT_FAILURE;
  }

  return EXIT_SUCCESS;
}
