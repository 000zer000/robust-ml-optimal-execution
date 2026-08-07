#include "robust_execution/policy/state.hpp"

#include "robust_execution/model/validation.hpp"
#include "robust_execution/policy/accounting.hpp"
#include "robust_execution/util/sha256.hpp"

#include <algorithm>
#include <limits>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <utility>

namespace robust_execution::policy {
namespace {

bool add_quote(model::QuoteAtoms lhs, model::QuoteAtoms rhs, model::QuoteAtoms& output) noexcept {
  const auto left = lhs.value();
  const auto right = rhs.value();
  if ((right > 0 && left > std::numeric_limits<std::int64_t>::max() - right) ||
      (right < 0 && left < std::numeric_limits<std::int64_t>::min() - right)) {
    return false;
  }
  output = model::QuoteAtoms{left + right};
  return true;
}

bool subtract_quote(
    model::QuoteAtoms lhs,
    model::QuoteAtoms rhs,
    model::QuoteAtoms& output
) noexcept {
  if (rhs.value() == std::numeric_limits<std::int64_t>::min()) {
    return false;
  }
  return add_quote(lhs, model::QuoteAtoms{-rhs.value()}, output);
}

bool at_or_after(model::TimestampNs lhs, model::TimestampNs rhs) {
  return lhs.domain() == rhs.domain() && lhs.value() >= rhs.value();
}

bool before(model::TimestampNs lhs, model::TimestampNs rhs) {
  return lhs.domain() == rhs.domain() && lhs.value() < rhs.value();
}

void require_parent_definition(
    const ParentOrderDefinition& parent,
    const model::InstrumentDefinition& instrument
) {
  if (!parent.parent_order_id.valid() || parent.total_quantity.is_zero() ||
      parent.arrival_price.value() <= 0 || parent.terminal_rule_id.empty()) {
    throw std::invalid_argument("parent-order identifiers, quantity, price and terminal rule are required");
  }
  if (parent.start_time.domain() != parent.end_time.domain() ||
      parent.start_time.value() >= parent.end_time.value()) {
    throw std::invalid_argument("parent-order start and end must share a clock and be increasing");
  }
  if (!instrument.venue.valid() || !instrument.instrument.valid() ||
      !instrument.tick_size.valid() || !instrument.lot_size.valid() ||
      !instrument.quote_atom_size.valid()) {
    throw std::invalid_argument("execution state requires a valid instrument definition");
  }
}

}  // namespace

bool ChildOrderView::acknowledged_active() const noexcept {
  return exchange_order_id.has_value() &&
         (state == model::OrderState::Live || state == model::OrderState::PartiallyFilled ||
          state == model::OrderState::PendingCancel);
}

class ExecutionState::Impl {
 public:
  Impl(ParentOrderDefinition parent, PolicyEnvironment environment)
      : parent_(std::move(parent)), environment_(std::move(environment)) {
    require_parent_definition(parent_, environment_.instrument);
    if (!environment_.fee_schedule_id.valid() || !environment_.strategy_id.valid() ||
        !environment_.latency_model_id.valid()) {
      throw std::invalid_argument("execution state requires complete policy environment IDs");
    }
  }

  ParentOrderDefinition parent_;
  PolicyEnvironment environment_;
  std::map<std::uint64_t, ChildOrderView> children_;
  std::set<std::uint64_t> applied_event_ids_;
  std::set<std::uint64_t> applied_execution_ids_;
  std::set<std::uint64_t> applied_fee_execution_ids_;
  std::map<std::uint64_t, model::ClientOrderId> execution_to_client_;
  model::QuantityLots cumulative_filled_{};
  model::QuoteAtoms gross_cash_flow_{};
  model::QuoteAtoms explicit_fees_{};
  std::uint64_t fill_count_{0U};
  bool terminal_completion_applied_{false};
  bool terminal_pending_{false};

  void register_submit(const model::OrderSubmit& command) {
    if (children_.contains(command.client_order_id.value())) {
      throw std::logic_error("validated action attempted to reuse a client order identifier");
    }
    children_.emplace(
        command.client_order_id.value(),
        ChildOrderView{
            command.parent_order_id,
            command.client_order_id,
            std::nullopt,
            command.decision_id,
            command.side,
            command.order_type,
            command.time_in_force,
            command.quantity,
            model::QuantityLots{0U},
            command.quantity,
            command.limit_price,
            command.post_only,
            model::OrderState::PendingNew,
            false,
            false,
        }
    );
  }

  void register_cancel(const model::CancelRequest& command) {
    auto iterator = children_.find(command.client_order_id.value());
    if (iterator == children_.end()) {
      throw std::logic_error("validated cancel references an unknown child order");
    }
    iterator->second.cancel_pending = true;
  }

  void register_replace(const model::ReplaceRequest& command) {
    auto iterator = children_.find(command.client_order_id.value());
    if (iterator == children_.end()) {
      throw std::logic_error("validated replace references an unknown child order");
    }
    iterator->second.replace_pending = true;
    const auto& original = iterator->second;
    if (children_.contains(command.replacement_client_order_id.value())) {
      throw std::logic_error("validated replace reuses a client order identifier");
    }
    children_.emplace(
        command.replacement_client_order_id.value(),
        ChildOrderView{
            original.parent_order_id,
            command.replacement_client_order_id,
            std::nullopt,
            command.decision_id,
            original.side,
            original.order_type,
            original.time_in_force,
            command.new_quantity,
            model::QuantityLots{0U},
            command.new_quantity,
            command.new_limit_price,
            original.post_only,
            model::OrderState::PendingNew,
            false,
            false,
        }
    );
  }

  bool update_parent_fill(const model::Fill& fill, std::vector<StateUpdateIssue>& issues) {
    if (fill.side != parent_.side) {
      issues.push_back({"fill_side_mismatch", "owned fill side differs from parent order side"});
      return false;
    }
    const auto remaining = model::checked_subtract(parent_.total_quantity, cumulative_filled_);
    if (!remaining.has_value() || fill.quantity.value() > remaining->value()) {
      issues.push_back({"parent_overfill", "fill quantity exceeds remaining parent inventory"});
      return false;
    }
    AccountingError accounting_error;
    const auto cash = signed_cash_effect(
        environment_.instrument,
        fill.side,
        fill.price,
        fill.quantity,
        &accounting_error
    );
    if (!cash.has_value()) {
      issues.push_back({"notional_error", accounting_error.detail});
      return false;
    }
    const auto next_quantity = model::checked_add(cumulative_filled_, fill.quantity);
    model::QuoteAtoms next_cash;
    if (!next_quantity.has_value() || !add_quote(gross_cash_flow_, *cash, next_cash)) {
      issues.push_back({"accounting_overflow", "parent fill accounting overflow"});
      return false;
    }
    cumulative_filled_ = *next_quantity;
    gross_cash_flow_ = next_cash;
    ++fill_count_;
    execution_to_client_[fill.execution_id.value()] = fill.client_order_id;
    return true;
  }

  void apply_order_ack(const model::OrderAcknowledged& value) {
    auto iterator = children_.find(value.client_order_id.value());
    if (iterator == children_.end()) {
      return;
    }
    auto& child = iterator->second;
    child.exchange_order_id = value.exchange_order_id;
    child.requested_quantity = value.accepted_quantity;
    child.cumulative_filled = value.cumulative_filled;
    child.leaves_quantity = value.leaves_quantity;
    child.state = value.state;
  }

  void apply_order_rejection(const model::OrderRejected& value) {
    auto iterator = children_.find(value.client_order_id.value());
    if (iterator == children_.end()) {
      return;
    }
    iterator->second.state = model::OrderState::Rejected;
    iterator->second.leaves_quantity = model::QuantityLots{0U};
  }

  void apply_cancel_ack(const model::CancelAcknowledged& value) {
    auto iterator = children_.find(value.client_order_id.value());
    if (iterator == children_.end()) {
      return;
    }
    auto& child = iterator->second;
    child.exchange_order_id = value.exchange_order_id;
    child.cumulative_filled = value.cumulative_filled;
    child.leaves_quantity = value.leaves_quantity;
    child.state = value.state;
    child.cancel_pending = false;
  }

  void apply_cancel_rejection(const model::CancelRejected& value) {
    auto iterator = children_.find(value.client_order_id.value());
    if (iterator == children_.end()) {
      return;
    }
    iterator->second.cancel_pending = false;
    iterator->second.state = value.resulting_state;
  }

  void apply_replace_ack(const model::ReplaceAcknowledged& value) {
    auto original = children_.find(value.original_client_order_id.value());
    if (original != children_.end()) {
      original->second.state = model::OrderState::Replaced;
      original->second.leaves_quantity = model::QuantityLots{0U};
      original->second.replace_pending = false;
    }
    auto replacement = children_.find(value.replacement_client_order_id.value());
    if (replacement != children_.end()) {
      replacement->second.exchange_order_id = value.replacement_exchange_order_id;
      replacement->second.requested_quantity = value.accepted_quantity;
      replacement->second.leaves_quantity = value.leaves_quantity;
      replacement->second.state = model::OrderState::Live;
    }
  }

  void apply_replace_rejection(const model::ReplaceRejected& value) {
    auto original = children_.find(value.client_order_id.value());
    if (original != children_.end()) {
      original->second.replace_pending = false;
      original->second.state = value.resulting_state;
    }
    children_.erase(value.replacement_client_order_id.value());
  }

  void apply_fill(const model::Fill& value, std::vector<StateUpdateIssue>& issues) {
    auto iterator = children_.find(value.client_order_id.value());
    if (iterator == children_.end()) {
      return;
    }
    const auto& prior = iterator->second;
    if (prior.exchange_order_id.has_value() && *prior.exchange_order_id != value.exchange_order_id) {
      issues.push_back({"fill_order_id_mismatch", "fill exchange ID differs from the tracked child"});
      return;
    }
    const auto expected_cumulative = model::checked_add(prior.cumulative_filled, value.quantity);
    const auto conserved = model::checked_add(value.cumulative_filled, value.leaves_quantity);
    if (!expected_cumulative.has_value() || *expected_cumulative != value.cumulative_filled ||
        !conserved.has_value() || *conserved != prior.requested_quantity) {
      issues.push_back({"fill_quantity_mismatch", "fill increment, cumulative quantity and leaves are inconsistent"});
      return;
    }
    if (!applied_execution_ids_.insert(value.execution_id.value()).second) {
      issues.push_back({"duplicate_execution", "execution identifier was applied more than once"});
      return;
    }
    if (!update_parent_fill(value, issues)) {
      applied_execution_ids_.erase(value.execution_id.value());
      return;
    }
    auto& child = iterator->second;
    child.exchange_order_id = value.exchange_order_id;
    child.cumulative_filled = value.cumulative_filled;
    child.leaves_quantity = value.leaves_quantity;
    child.state = value.leaves_quantity.is_zero() ? model::OrderState::Filled
                                                  : model::OrderState::PartiallyFilled;
  }

  void apply_fee(const model::Fee& value, std::vector<StateUpdateIssue>& issues) {
    if (!execution_to_client_.contains(value.execution_id.value())) {
      return;
    }
    if (value.fee_schedule_id != environment_.fee_schedule_id) {
      issues.push_back({"fee_schedule_mismatch", "fee event uses an unexpected schedule ID"});
      return;
    }
    if (!applied_fee_execution_ids_.insert(value.execution_id.value()).second) {
      issues.push_back({"duplicate_fee", "fee for execution identifier was applied more than once"});
      return;
    }
    model::QuoteAtoms next_fee;
    if (!add_quote(explicit_fees_, value.amount, next_fee)) {
      issues.push_back({"accounting_overflow", "fee accounting overflow"});
      return;
    }
    explicit_fees_ = next_fee;
  }

  void apply_terminal(
      const model::TerminalCompletion& value,
      std::vector<StateUpdateIssue>& issues
  ) {
    if (value.parent_order_id != parent_.parent_order_id) {
      return;
    }
    if (terminal_completion_applied_) {
      issues.push_back({"duplicate_terminal_completion", "terminal completion was already applied"});
      return;
    }
    if (value.side != parent_.side) {
      issues.push_back({"terminal_side_mismatch", "terminal completion side differs from parent"});
      return;
    }
    if (value.rule_id != parent_.terminal_rule_id) {
      issues.push_back({"terminal_rule_mismatch", "terminal completion uses an unexpected rule ID"});
      return;
    }
    const auto remaining = model::checked_subtract(parent_.total_quantity, cumulative_filled_);
    if (!remaining.has_value() || value.quantity != *remaining) {
      issues.push_back({"terminal_quantity_mismatch", "terminal completion must equal exact residual"});
      return;
    }
    AccountingError accounting_error;
    const auto cash = signed_cash_effect(
        environment_.instrument,
        value.side,
        value.price,
        value.quantity,
        &accounting_error
    );
    model::QuoteAtoms next_cash;
    model::QuoteAtoms next_fee;
    if (!cash.has_value() || !add_quote(gross_cash_flow_, *cash, next_cash) ||
        !add_quote(explicit_fees_, value.explicit_fee, next_fee)) {
      issues.push_back({"terminal_accounting_error", cash.has_value() ? "terminal accounting overflow"
                                                                      : accounting_error.detail});
      return;
    }
    cumulative_filled_ = parent_.total_quantity;
    gross_cash_flow_ = next_cash;
    explicit_fees_ = next_fee;
    terminal_completion_applied_ = true;
    terminal_pending_ = false;
    ++fill_count_;
  }
};

ExecutionState::ExecutionState(ParentOrderDefinition parent, PolicyEnvironment environment)
    : impl_(new Impl(std::move(parent), std::move(environment))) {}

ExecutionState::~ExecutionState() { delete impl_; }

ExecutionState::ExecutionState(ExecutionState&& other) noexcept : impl_(other.impl_) {
  other.impl_ = nullptr;
}

ExecutionState& ExecutionState::operator=(ExecutionState&& other) noexcept {
  if (this != &other) {
    delete impl_;
    impl_ = other.impl_;
    other.impl_ = nullptr;
  }
  return *this;
}

void ExecutionState::register_action(const ValidatedPolicyAction& action) {
  for (const auto& command : action.commands) {
    std::visit(
        [this](const auto& value) {
          using Command = std::decay_t<decltype(value)>;
          if constexpr (std::is_same_v<Command, model::OrderSubmit>) {
            impl_->register_submit(value);
          } else if constexpr (std::is_same_v<Command, model::CancelRequest>) {
            impl_->register_cancel(value);
          } else {
            static_assert(std::is_same_v<Command, model::ReplaceRequest>);
            impl_->register_replace(value);
          }
        },
        command
    );
  }
}

std::vector<StateUpdateIssue> ExecutionState::apply_delivered_event(
    const model::Event& event,
    model::TimestampNs delivery_time
) {
  std::vector<StateUpdateIssue> issues;
  const auto validation_issues = model::validate_event(event);
  if (model::has_errors(validation_issues)) {
    issues.push_back({"invalid_event", "delivered event fails the canonical event-model contract"});
    return issues;
  }
  if (event.header.venue != impl_->environment_.instrument.venue ||
      event.header.instrument != impl_->environment_.instrument.instrument) {
    issues.push_back({"instrument_mismatch", "delivered event belongs to another venue or instrument"});
    return issues;
  }
  if (!event.header.available_time.has_value() ||
      event.header.available_time->domain() != delivery_time.domain() ||
      event.header.available_time->value() > delivery_time.value()) {
    issues.push_back({"causal_delivery_violation", "event was applied before its availability time"});
    return issues;
  }
  if (!impl_->applied_event_ids_.insert(event.header.event_id.value()).second) {
    issues.push_back({"duplicate_event", "event identifier was applied more than once"});
    return issues;
  }

  std::visit(
      [this, &issues](const auto& value) {
        using Payload = std::decay_t<decltype(value)>;
        if constexpr (std::is_same_v<Payload, model::OrderAcknowledged>) {
          impl_->apply_order_ack(value);
        } else if constexpr (std::is_same_v<Payload, model::OrderRejected>) {
          impl_->apply_order_rejection(value);
        } else if constexpr (std::is_same_v<Payload, model::CancelAcknowledged>) {
          impl_->apply_cancel_ack(value);
        } else if constexpr (std::is_same_v<Payload, model::CancelRejected>) {
          impl_->apply_cancel_rejection(value);
        } else if constexpr (std::is_same_v<Payload, model::ReplaceAcknowledged>) {
          impl_->apply_replace_ack(value);
        } else if constexpr (std::is_same_v<Payload, model::ReplaceRejected>) {
          impl_->apply_replace_rejection(value);
        } else if constexpr (std::is_same_v<Payload, model::Fill>) {
          impl_->apply_fill(value, issues);
        } else if constexpr (std::is_same_v<Payload, model::Fee>) {
          impl_->apply_fee(value, issues);
        } else if constexpr (std::is_same_v<Payload, model::TerminalCompletion>) {
          impl_->apply_terminal(value, issues);
        }
      },
      event.payload
  );
  return issues;
}

void ExecutionState::apply_engine_failure(
    const ActionCommand& command,
    const exchange::EngineFailure& failure
) {
  std::visit(
      [this, &failure](const auto& value) {
        using Command = std::decay_t<decltype(value)>;
        auto iterator = impl_->children_.find(value.client_order_id.value());
        if (iterator == impl_->children_.end()) {
          return;
        }
        if constexpr (std::is_same_v<Command, model::OrderSubmit>) {
          iterator->second.state = model::OrderState::Rejected;
          iterator->second.leaves_quantity = model::QuantityLots{0U};
        } else if constexpr (std::is_same_v<Command, model::CancelRequest>) {
          iterator->second.cancel_pending = false;
          if (failure.current_state.has_value()) {
            iterator->second.state = *failure.current_state;
          }
        } else {
          static_assert(std::is_same_v<Command, model::ReplaceRequest>);
          iterator->second.replace_pending = false;
          if (failure.current_state.has_value()) {
            iterator->second.state = *failure.current_state;
          }
          impl_->children_.erase(value.replacement_client_order_id.value());
        }
      },
      command
  );
}

void ExecutionState::mark_terminal_completion_pending() { impl_->terminal_pending_ = true; }

const ParentOrderDefinition& ExecutionState::parent_definition() const noexcept {
  return impl_->parent_;
}

const PolicyEnvironment& ExecutionState::environment() const noexcept {
  return impl_->environment_;
}

const model::InstrumentDefinition& ExecutionState::instrument() const noexcept {
  return impl_->environment_.instrument;
}

ParentOrderSnapshot ExecutionState::parent_snapshot(model::TimestampNs as_of) const {
  if (as_of.domain() != impl_->parent_.start_time.domain()) {
    throw std::invalid_argument("parent snapshot uses a different clock domain");
  }
  const auto remaining = model::checked_subtract(
      impl_->parent_.total_quantity,
      impl_->cumulative_filled_
  );
  if (!remaining.has_value()) {
    throw std::logic_error("parent-order accounting exceeded total quantity");
  }
  ParentOrderStatus status = ParentOrderStatus::Active;
  if (remaining->is_zero()) {
    status = ParentOrderStatus::Completed;
  } else if (impl_->terminal_pending_ || at_or_after(as_of, impl_->parent_.end_time)) {
    status = ParentOrderStatus::TerminalCompletionPending;
  } else if (before(as_of, impl_->parent_.start_time)) {
    status = ParentOrderStatus::Pending;
  }
  model::QuoteAtoms net;
  if (!subtract_quote(impl_->gross_cash_flow_, impl_->explicit_fees_, net)) {
    throw std::overflow_error("net cash-flow accounting overflow");
  }
  return ParentOrderSnapshot{
      impl_->parent_.parent_order_id,
      impl_->parent_.side,
      impl_->parent_.start_time,
      impl_->parent_.end_time,
      impl_->parent_.arrival_price,
      impl_->parent_.terminal_rule_id,
      impl_->parent_.total_quantity,
      impl_->cumulative_filled_,
      *remaining,
      impl_->gross_cash_flow_,
      impl_->explicit_fees_,
      net,
      impl_->fill_count_,
      status,
      impl_->terminal_completion_applied_,
  };
}

std::vector<ChildOrderView> ExecutionState::child_orders() const {
  std::vector<ChildOrderView> output;
  output.reserve(impl_->children_.size());
  for (const auto& [identifier, child] : impl_->children_) {
    static_cast<void>(identifier);
    output.push_back(child);
  }
  return output;
}

std::vector<ChildOrderView> ExecutionState::acknowledged_active_orders() const {
  std::vector<ChildOrderView> output;
  for (const auto& [identifier, child] : impl_->children_) {
    static_cast<void>(identifier);
    if (child.acknowledged_active()) {
      output.push_back(child);
    }
  }
  return output;
}

std::size_t ExecutionState::acknowledged_active_order_count() const noexcept {
  return static_cast<std::size_t>(std::count_if(
      impl_->children_.begin(),
      impl_->children_.end(),
      [](const auto& entry) { return entry.second.acknowledged_active(); }
  ));
}

std::size_t ExecutionState::pending_command_count() const noexcept {
  std::size_t count = 0U;
  for (const auto& [identifier, child] : impl_->children_) {
    static_cast<void>(identifier);
    if (child.state == model::OrderState::PendingNew) {
      ++count;
    }
    if (child.cancel_pending) {
      ++count;
    }
    if (child.replace_pending) {
      ++count;
    }
  }
  return count;
}

bool ExecutionState::knows_client_order_id(model::ClientOrderId id) const noexcept {
  return impl_->children_.contains(id.value());
}

std::optional<ChildOrderView> ExecutionState::child_order(model::ClientOrderId id) const {
  const auto iterator = impl_->children_.find(id.value());
  if (iterator == impl_->children_.end()) {
    return std::nullopt;
  }
  return iterator->second;
}

std::string ExecutionState::canonical_state(model::TimestampNs as_of) const {
  const auto parent = parent_snapshot(as_of);
  std::ostringstream output;
  output << parent.parent_order_id.value() << '|' << static_cast<unsigned>(parent.side) << '|'
         << parent.total_quantity.value() << '|' << parent.cumulative_filled.value() << '|'
         << parent.remaining_quantity.value() << '|' << parent.gross_cash_flow.value() << '|'
         << parent.explicit_fees.value() << '|' << parent.net_cash_flow.value() << '|'
         << parent.fill_count << '|' << to_string(parent.status) << '|'
         << parent.terminal_completion_applied << '|';
  for (const auto& [identifier, child] : impl_->children_) {
    output << identifier << '|';
    if (child.exchange_order_id.has_value()) {
      output << child.exchange_order_id->value();
    }
    output << '|' << child.decision_id.value() << '|' << static_cast<unsigned>(child.side) << '|'
           << static_cast<unsigned>(child.order_type) << '|'
           << static_cast<unsigned>(child.time_in_force) << '|'
           << child.requested_quantity.value() << '|' << child.cumulative_filled.value() << '|'
           << child.leaves_quantity.value() << '|';
    if (child.limit_price.has_value()) {
      output << child.limit_price->value();
    }
    output << '|' << child.post_only << '|' << static_cast<unsigned>(child.state) << '|'
           << child.cancel_pending << '|' << child.replace_pending << '|';
  }
  return output.str();
}

std::string ExecutionState::state_hash(model::TimestampNs as_of) const {
  return util::sha256_hex(canonical_state(as_of));
}

}  // namespace robust_execution::policy
