#pragma once

#include <cstdint>
#include <vector>

#include "robust_execution/policy/state.hpp"
#include "robust_execution/simulation/kernel.hpp"

namespace robust_execution::policy {

struct DispatchedCommand {
  model::EventId request_event_id{};
  model::ActionTiming timing{};
  ActionCommand command;
};

struct DispatchResult {
  std::vector<DispatchedCommand> commands;
  std::uint64_t next_logical_index{0U};
};

[[nodiscard]] DispatchResult dispatch_validated_action(
    simulation::SimulationKernel& kernel,
    ExecutionState& state,
    const ValidatedPolicyAction& action,
    std::uint64_t first_logical_index
);

}  // namespace robust_execution::policy
