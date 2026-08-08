#pragma once

#include <optional>
#include <string>

#include "robust_execution/policy/observation.hpp"

namespace robust_execution::policy {

struct TerminalPlan {
  TerminalPlanKind kind{TerminalPlanKind::None};
  std::optional<PolicyAction> action;
  model::QuantityLots residual_quantity{};
  std::string detail;
};

class TerminalCompletionPlanner {
 public:
  explicit TerminalCompletionPlanner(TerminalRuleConfig config);

  [[nodiscard]] TerminalPlan plan(
      const PolicyObservation& observation,
      model::DecisionId decision_id,
      model::ClientOrderId next_client_order_id
  );

  [[nodiscard]] model::TerminalCompletion explicit_fallback(
      const PolicyObservation& observation,
      model::PriceTicks completion_price,
      model::QuoteAtoms explicit_fee
  ) const;

  void record_aggressive_attempt();
  void reset() noexcept;

  [[nodiscard]] const TerminalRuleConfig& config() const noexcept;
  [[nodiscard]] std::size_t aggressive_attempts() const noexcept;

 private:
  TerminalRuleConfig config_;
  std::size_t aggressive_attempts_{0U};
};

}  // namespace robust_execution::policy
