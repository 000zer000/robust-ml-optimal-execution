#include "robust_execution/policy/dispatch.hpp"

#include <limits>
#include <stdexcept>
#include <type_traits>

namespace robust_execution::policy {

DispatchResult dispatch_validated_action(
    simulation::SimulationKernel& kernel,
    ExecutionState& state,
    const ValidatedPolicyAction& action,
    std::uint64_t first_logical_index
) {
  if (first_logical_index == 0U) {
    throw std::invalid_argument("policy dispatch logical index must start above zero");
  }
  DispatchResult result;
  result.next_logical_index = first_logical_index;
  result.commands.reserve(action.commands.size());
  for (const auto& command : action.commands) {
    const auto logical_index = result.next_logical_index;
    if (logical_index == std::numeric_limits<std::uint64_t>::max()) {
      throw std::overflow_error("policy dispatch logical index is exhausted");
    }
    const auto scheduled = std::visit(
        [&kernel, &action, logical_index](const auto& value) {
          using Command = std::decay_t<decltype(value)>;
          if constexpr (std::is_same_v<Command, model::OrderSubmit>) {
            return kernel.schedule_submit(value, action.decision_time, logical_index);
          } else if constexpr (std::is_same_v<Command, model::CancelRequest>) {
            return kernel.schedule_cancel(value, action.decision_time, logical_index);
          } else {
            static_assert(std::is_same_v<Command, model::ReplaceRequest>);
            return kernel.schedule_replace(value, action.decision_time, logical_index);
          }
        },
        command
    );
    result.commands.push_back(DispatchedCommand{
        scheduled.request_event_id,
        scheduled.timing,
        command,
    });
    ++result.next_logical_index;
  }
  state.register_action(action);
  return result;
}

}  // namespace robust_execution::policy
