#include "policy_test_support.hpp"

#include <cstdlib>

namespace {

class PassivePolicy final : public robust_execution::policy::ExecutionPolicy {
 public:
  [[nodiscard]] robust_execution::model::StrategyId strategy_id() const override {
    return robust_execution::model::StrategyId{"test-policy"};
  }

  void reset(
      const robust_execution::policy::ParentOrderDefinition& parent,
      const robust_execution::policy::PolicyEnvironment& environment
  ) override {
    parent_id_ = parent.parent_order_id;
    environment_id_ = environment.strategy_id;
  }

  [[nodiscard]] robust_execution::policy::PolicyAction on_observation(
      const robust_execution::policy::PolicyObservation& observation
  ) override {
    return robust_execution::policy::PolicyAction{
        observation.decision_id(),
        observation.decision_time(),
        robust_execution::policy::NoAction{},
    };
  }

  robust_execution::model::ParentOrderId parent_id_{};
  robust_execution::model::StrategyId environment_id_{};
};

}  // namespace

int main() {
  PassivePolicy policy;
  auto parent = policy_test::parent();
  auto environment = policy_test::environment();
  robust_execution::policy::ExecutionState state{parent, environment};
  policy.reset(parent, environment);
  const auto observation = policy_test::observation(state);
  const auto action = policy.on_observation(observation);
  if (policy.strategy_id() != environment.strategy_id || policy.parent_id_ != parent.parent_order_id ||
      policy.environment_id_ != environment.strategy_id ||
      robust_execution::policy::action_kind(action.payload) !=
          robust_execution::policy::PolicyActionKind::NoAction) {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
