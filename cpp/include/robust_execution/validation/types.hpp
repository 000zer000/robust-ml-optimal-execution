#pragma once

#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

namespace robust_execution::validation {

enum class GateDecision : std::uint8_t {
  Pass,
  ConditionalPass,
  Fail,
};

[[nodiscard]] constexpr std::string_view to_string(GateDecision decision) noexcept {
  switch (decision) {
    case GateDecision::Pass:
      return "pass";
    case GateDecision::ConditionalPass:
      return "conditional_pass";
    case GateDecision::Fail:
      return "fail";
  }
  return "unknown";
}

struct ValidationCheck {
  std::string check_id;
  std::string category;
  std::string description;
  bool passed{false};
  std::string evidence;
  std::string limitation;
};

struct DirectionalSensitivity {
  std::string sensitivity_id;
  std::string description;
  double control_mean{0.0};
  double treatment_mean{0.0};
  std::string expected_relation;
  bool passed{false};
};

struct SimulatorValidationReport {
  std::string schema_id{"simulator-validation-report-v1"};
  std::string gate_id{"gate-b"};
  GateDecision decision{GateDecision::Fail};
  std::uint64_t generated_seed_count{0U};
  std::uint64_t generated_step_count{0U};
  std::uint64_t differential_seed_count{0U};
  std::uint64_t differential_command_count{0U};
  std::uint64_t mutation_case_count{0U};
  std::vector<ValidationCheck> checks;
  std::vector<DirectionalSensitivity> sensitivities;
  std::vector<std::string> limitations;
  std::string canonical_json;
  std::string report_sha256;
};

}  // namespace robust_execution::validation
