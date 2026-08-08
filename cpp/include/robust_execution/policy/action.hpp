#pragma once

#include <optional>
#include <string>
#include <variant>
#include <vector>

#include "robust_execution/policy/types.hpp"

namespace robust_execution::policy {

class PolicyObservation;
class ExecutionState;

struct NoAction {};

struct SubmitChildAction {
  model::ClientOrderId client_order_id{};
  QuantityFraction quantity_fraction{};
  model::OrderType order_type{model::OrderType::Limit};
  model::TimeInForce time_in_force{model::TimeInForce::GoodTilCancelled};
  std::optional<LimitPlacement> placement;
  bool post_only{false};
};

struct CancelChildAction {
  std::vector<model::ClientOrderId> client_order_ids;
};

struct ReplaceChildAction {
  model::ClientOrderId client_order_id{};
  model::ClientOrderId replacement_client_order_id{};
  QuantityFraction quantity_fraction{};
  std::optional<LimitPlacement> placement;
};

using PolicyActionPayload =
    std::variant<NoAction, SubmitChildAction, CancelChildAction, ReplaceChildAction>;

struct PolicyAction {
  model::DecisionId decision_id{};
  model::TimestampNs decision_time{};
  PolicyActionPayload payload{NoAction{}};
};

using ActionCommand =
    std::variant<model::OrderSubmit, model::CancelRequest, model::ReplaceRequest>;

struct ValidatedPolicyAction {
  model::DecisionId decision_id{};
  model::TimestampNs decision_time{};
  PolicyActionKind kind{PolicyActionKind::NoAction};
  std::string action_name;
  std::vector<ActionCommand> commands;
  model::QuantityLots reserved_quantity{};
};

struct ActionValidationIssue {
  ActionValidationCode code{ActionValidationCode::InvalidDecision};
  std::string detail;
};

struct ActionValidationResult {
  std::optional<ValidatedPolicyAction> action;
  std::vector<ActionValidationIssue> issues;

  [[nodiscard]] bool valid() const noexcept {
    return action.has_value() && issues.empty();
  }
};

class ActionValidator {
 public:
  explicit ActionValidator(PolicyEnvironment environment);

  [[nodiscard]] ActionValidationResult validate(
      const PolicyAction& action,
      const PolicyObservation& observation,
      const ExecutionState& state
  ) const;

  [[nodiscard]] const PolicyEnvironment& environment() const noexcept;

 private:
  PolicyEnvironment environment_;
};

[[nodiscard]] PolicyActionKind action_kind(const PolicyActionPayload& payload) noexcept;
[[nodiscard]] std::string canonical_action(const ValidatedPolicyAction& action);

}  // namespace robust_execution::policy
