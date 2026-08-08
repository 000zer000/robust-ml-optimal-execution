#pragma once

#include "robust_execution/validation/types.hpp"

namespace robust_execution::validation {

[[nodiscard]] SimulatorValidationReport run_simulator_validation();
[[nodiscard]] std::string canonical_json(const SimulatorValidationReport& report);
[[nodiscard]] bool gate_passed(const SimulatorValidationReport& report) noexcept;

}  // namespace robust_execution::validation
