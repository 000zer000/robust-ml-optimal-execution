#pragma once

#include <cstddef>
#include <optional>
#include <string>
#include <vector>

#include "robust_execution/exchange/matching_engine.hpp"
#include "robust_execution/policy/action.hpp"

namespace robust_execution::policy {

struct ChildOrderView {
  model::ParentOrderId parent_order_id{};
  model::ClientOrderId client_order_id{};
  std::optional<model::ExchangeOrderId> exchange_order_id;
  model::DecisionId decision_id{};
  model::Side side{model::Side::Buy};
  model::OrderType order_type{model::OrderType::Limit};
  model::TimeInForce time_in_force{model::TimeInForce::GoodTilCancelled};
  model::QuantityLots requested_quantity{};
  model::QuantityLots cumulative_filled{};
  model::QuantityLots leaves_quantity{};
  std::optional<model::PriceTicks> limit_price;
  bool post_only{false};
  model::OrderState state{model::OrderState::PendingNew};
  bool cancel_pending{false};
  bool replace_pending{false};

  [[nodiscard]] bool acknowledged_active() const noexcept;
};

struct ParentOrderSnapshot {
  model::ParentOrderId parent_order_id{};
  model::Side side{model::Side::Buy};
  model::TimestampNs start_time{};
  model::TimestampNs end_time{};
  model::PriceTicks arrival_price{};
  std::string terminal_rule_id;
  model::QuantityLots total_quantity{};
  model::QuantityLots cumulative_filled{};
  model::QuantityLots remaining_quantity{};
  model::QuoteAtoms gross_cash_flow{};
  model::QuoteAtoms explicit_fees{};
  model::QuoteAtoms net_cash_flow{};
  std::uint64_t fill_count{0U};
  ParentOrderStatus status{ParentOrderStatus::Pending};
  bool terminal_completion_applied{false};
};

struct StateUpdateIssue {
  std::string code;
  std::string detail;
};

class ExecutionState {
 public:
  ExecutionState(ParentOrderDefinition parent, PolicyEnvironment environment);
  ~ExecutionState();

  ExecutionState(const ExecutionState&) = delete;
  ExecutionState& operator=(const ExecutionState&) = delete;
  ExecutionState(ExecutionState&&) noexcept;
  ExecutionState& operator=(ExecutionState&&) noexcept;

  void register_action(const ValidatedPolicyAction& action);
  [[nodiscard]] std::vector<StateUpdateIssue> apply_delivered_event(
      const model::Event& event,
      model::TimestampNs delivery_time
  );
  void apply_engine_failure(
      const ActionCommand& command,
      const exchange::EngineFailure& failure
  );
  void mark_terminal_completion_pending();

  [[nodiscard]] const ParentOrderDefinition& parent_definition() const noexcept;
  [[nodiscard]] const PolicyEnvironment& environment() const noexcept;
  [[nodiscard]] const model::InstrumentDefinition& instrument() const noexcept;
  [[nodiscard]] ParentOrderSnapshot parent_snapshot(model::TimestampNs as_of) const;
  [[nodiscard]] std::vector<ChildOrderView> child_orders() const;
  [[nodiscard]] std::vector<ChildOrderView> acknowledged_active_orders() const;
  [[nodiscard]] std::size_t acknowledged_active_order_count() const noexcept;
  [[nodiscard]] std::size_t pending_command_count() const noexcept;
  [[nodiscard]] bool knows_client_order_id(model::ClientOrderId id) const noexcept;
  [[nodiscard]] std::optional<ChildOrderView> child_order(model::ClientOrderId id) const;
  [[nodiscard]] std::string canonical_state(model::TimestampNs as_of) const;
  [[nodiscard]] std::string state_hash(model::TimestampNs as_of) const;

 private:
  class Impl;
  Impl* impl_;
};

}  // namespace robust_execution::policy
