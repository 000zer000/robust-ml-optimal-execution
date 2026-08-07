#include "policy_test_support.hpp"

#include <cstdlib>

int main() {
  namespace model = robust_execution::model;
  namespace policy = robust_execution::policy;

  auto environment = policy_test::environment();
  policy::ExecutionState state{policy_test::parent(), policy_test::environment()};
  const auto observation = policy_test::observation(state);
  policy::ActionValidator validator{environment};

  const auto submit = validator.validate(
      policy::PolicyAction{
          model::DecisionId{1U},
          policy_test::time(120),
          policy::SubmitChildAction{
              model::ClientOrderId{10U},
              policy::QuantityFraction{1U, 2U},
              model::OrderType::Limit,
              model::TimeInForce::GoodTilCancelled,
              policy::LimitPlacement{policy::LimitReference::SameSideBest, model::TickOffset{0}},
              true,
          },
      },
      observation,
      state
  );
  if (!submit.valid() || submit.action->commands.size() != 1U ||
      submit.action->reserved_quantity.value() != 50U ||
      std::get<model::OrderSubmit>(submit.action->commands.front()).limit_price->value() != 100 ||
      policy::canonical_action(*submit.action).empty()) {
    return EXIT_FAILURE;
  }
  state.register_action(*submit.action);

  const auto pending_rejection = validator.validate(
      policy::PolicyAction{
          model::DecisionId{2U},
          policy_test::time(121),
          policy::SubmitChildAction{
              model::ClientOrderId{11U},
              policy::QuantityFraction{1U, 4U},
              model::OrderType::Market,
              model::TimeInForce::ImmediateOrCancel,
              std::nullopt,
              false,
          },
      },
      policy_test::observation(state, model::DecisionId{2U}, 121),
      state
  );
  if (pending_rejection.valid() || pending_rejection.issues.empty() ||
      pending_rejection.issues.front().code != policy::ActionValidationCode::PendingCommandConflict) {
    return EXIT_FAILURE;
  }

  const auto ack = policy_test::event(
      20U,
      122,
      123,
      model::OrderAcknowledged{
          model::ClientOrderId{10U},
          model::ExchangeOrderId{50U},
          std::nullopt,
          model::QuantityLots{50U},
          model::QuantityLots{0U},
          model::QuantityLots{50U},
          model::OrderState::Live,
      }
  );
  if (!state.apply_delivered_event(ack, policy_test::time(123)).empty()) {
    return EXIT_FAILURE;
  }
  const auto active_observation = policy_test::observation(state, model::DecisionId{3U}, 130);
  const auto too_many = validator.validate(
      policy::PolicyAction{
          model::DecisionId{3U},
          policy_test::time(130),
          policy::SubmitChildAction{
              model::ClientOrderId{11U},
              policy::QuantityFraction{1U, 4U},
              model::OrderType::Market,
              model::TimeInForce::ImmediateOrCancel,
              std::nullopt,
              false,
          },
      },
      active_observation,
      state
  );
  if (too_many.valid() || too_many.issues.front().code != policy::ActionValidationCode::TooManyLiveChildren) {
    return EXIT_FAILURE;
  }

  const auto cancel = validator.validate(
      policy::PolicyAction{
          model::DecisionId{3U},
          policy_test::time(130),
          policy::CancelChildAction{{model::ClientOrderId{10U}}},
      },
      active_observation,
      state
  );
  if (!cancel.valid() || !std::holds_alternative<model::CancelRequest>(cancel.action->commands.front())) {
    return EXIT_FAILURE;
  }

  const auto replace = validator.validate(
      policy::PolicyAction{
          model::DecisionId{3U},
          policy_test::time(130),
          policy::ReplaceChildAction{
              model::ClientOrderId{10U},
              model::ClientOrderId{12U},
              policy::QuantityFraction{1U, 1U},
              policy::LimitPlacement{policy::LimitReference::SameSideBest, model::TickOffset{-1}},
          },
      },
      active_observation,
      state
  );
  if (!replace.valid() ||
      std::get<model::ReplaceRequest>(replace.action->commands.front()).new_limit_price->value() != 99) {
    return EXIT_FAILURE;
  }

  const auto bad_market = validator.validate(
      policy::PolicyAction{
          model::DecisionId{3U},
          policy_test::time(130),
          policy::SubmitChildAction{
              model::ClientOrderId{13U},
              policy::QuantityFraction{1U, 3U},
              model::OrderType::Market,
              model::TimeInForce::GoodTilCancelled,
              std::nullopt,
              false,
          },
      },
      active_observation,
      state
  );
  if (bad_market.valid()) {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
