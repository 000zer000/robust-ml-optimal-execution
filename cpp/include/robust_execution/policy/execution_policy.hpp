#pragma once

#include "robust_execution/policy/observation.hpp"

namespace robust_execution::policy {

class ExecutionPolicy {
 public:
  virtual ~ExecutionPolicy() = default;

  [[nodiscard]] virtual model::StrategyId strategy_id() const = 0;
  virtual void reset(
      const ParentOrderDefinition& parent,
      const PolicyEnvironment& environment
  ) = 0;
  [[nodiscard]] virtual PolicyAction on_observation(const PolicyObservation& observation) = 0;
};

}  // namespace robust_execution::policy
