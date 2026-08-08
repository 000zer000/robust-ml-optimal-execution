#include "robust_execution/policy/terminal.hpp"

#include <stdexcept>
#include <utility>

namespace robust_execution::policy {

TerminalCompletionPlanner::TerminalCompletionPlanner(TerminalRuleConfig config)
    : config_(std::move(config)) {
  if (config_.rule_id.empty() || config_.maximum_aggressive_attempts == 0U ||
      !config_.allow_explicit_fallback) {
    throw std::invalid_argument(
        "hard-completion rule requires an ID, at least one aggressive attempt and explicit fallback"
    );
  }
}

TerminalPlan TerminalCompletionPlanner::plan(
    const PolicyObservation& observation,
    model::DecisionId decision_id,
    model::ClientOrderId next_client_order_id
) {
  if (observation.parent().status == ParentOrderStatus::Completed ||
      observation.parent().remaining_quantity.is_zero()) {
    return TerminalPlan{
        TerminalPlanKind::Complete,
        std::nullopt,
        model::QuantityLots{0U},
        "parent order is complete",
    };
  }
  if (observation.parent().status != ParentOrderStatus::TerminalCompletionPending) {
    return TerminalPlan{
        TerminalPlanKind::None,
        std::nullopt,
        observation.parent().remaining_quantity,
        "parent order has not reached its terminal horizon",
    };
  }
  if (observation.pending_command_count() != 0U) {
    return TerminalPlan{
        TerminalPlanKind::AwaitPendingCommands,
        std::nullopt,
        observation.parent().remaining_quantity,
        "terminal controller waits for pending child commands",
    };
  }
  if (!observation.active_orders().empty()) {
    CancelChildAction cancel;
    cancel.client_order_ids.reserve(observation.active_orders().size());
    for (const auto& child : observation.active_orders()) {
      cancel.client_order_ids.push_back(child.client_order_id);
    }
    return TerminalPlan{
        TerminalPlanKind::CancelActiveChildren,
        PolicyAction{decision_id, observation.decision_time(), std::move(cancel)},
        observation.parent().remaining_quantity,
        "cancel acknowledged live children before terminal aggression",
    };
  }
  if (aggressive_attempts_ < config_.maximum_aggressive_attempts) {
    return TerminalPlan{
        TerminalPlanKind::SubmitAggressiveResidual,
        PolicyAction{
            decision_id,
            observation.decision_time(),
            SubmitChildAction{
                next_client_order_id,
                QuantityFraction{1U, 1U},
                model::OrderType::Market,
                model::TimeInForce::ImmediateOrCancel,
                std::nullopt,
                false,
            },
        },
        observation.parent().remaining_quantity,
        "submit the full residual as an immediate-or-cancel market order",
    };
  }
  return TerminalPlan{
      TerminalPlanKind::RequiresExplicitFallback,
      std::nullopt,
      observation.parent().remaining_quantity,
      "mode-specific terminal price and fee are required for hard completion",
  };
}

model::TerminalCompletion TerminalCompletionPlanner::explicit_fallback(
    const PolicyObservation& observation,
    model::PriceTicks completion_price,
    model::QuoteAtoms explicit_fee
) const {
  if (observation.parent().status != ParentOrderStatus::TerminalCompletionPending ||
      observation.parent().remaining_quantity.is_zero()) {
    throw std::invalid_argument("explicit terminal fallback requires a non-zero terminal residual");
  }
  if (completion_price.value() <= 0) {
    throw std::invalid_argument("explicit terminal fallback price must be positive");
  }
  if (observation.parent().terminal_rule_id != config_.rule_id) {
    throw std::invalid_argument("terminal planner rule does not match the parent order");
  }
  return model::TerminalCompletion{
      observation.parent().parent_order_id,
      observation.parent().side,
      observation.parent().remaining_quantity,
      completion_price,
      explicit_fee,
      config_.rule_id,
  };
}

void TerminalCompletionPlanner::record_aggressive_attempt() {
  if (aggressive_attempts_ >= config_.maximum_aggressive_attempts) {
    throw std::logic_error("terminal aggressive-attempt budget is exhausted");
  }
  ++aggressive_attempts_;
}

void TerminalCompletionPlanner::reset() noexcept { aggressive_attempts_ = 0U; }

const TerminalRuleConfig& TerminalCompletionPlanner::config() const noexcept { return config_; }
std::size_t TerminalCompletionPlanner::aggressive_attempts() const noexcept {
  return aggressive_attempts_;
}

}  // namespace robust_execution::policy
