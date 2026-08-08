#pragma once

#include <string>

#include "robust_execution/model/events.hpp"

namespace robust_execution::simulation {

[[nodiscard]] std::string canonical_event(const model::Event& event);

}  // namespace robust_execution::simulation
