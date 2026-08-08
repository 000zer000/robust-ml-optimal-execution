#include "internal.hpp"
#include "robust_execution/validation/simulator_validation.hpp"
#include "robust_execution/util/sha256.hpp"

#include <iomanip>
#include <sstream>

namespace robust_execution::validation {
namespace {
void append_string_array(std::ostringstream& output, const std::vector<std::string>& values) {
  output << '[';
  for (std::size_t index = 0U; index < values.size(); ++index) {
    if (index != 0U) output << ',';
    output << '"' << detail::json_escape(values[index]) << '"';
  }
  output << ']';
}
}  // namespace

namespace detail {
std::string json_escape(std::string_view value) {
  std::ostringstream output;
  for (const char character : value) {
    switch (character) {
      case '\\': output << "\\\\"; break;
      case '"': output << "\\\""; break;
      case '\n': output << "\\n"; break;
      case '\r': output << "\\r"; break;
      case '\t': output << "\\t"; break;
      default: output << character; break;
    }
  }
  return output.str();
}
}  // namespace detail

std::string canonical_json(const SimulatorValidationReport& report) {
  std::ostringstream output;
  output << std::setprecision(17);
  output << '{'
         << "\"schema_id\":\"" << detail::json_escape(report.schema_id) << "\"," 
         << "\"gate_id\":\"" << detail::json_escape(report.gate_id) << "\"," 
         << "\"decision\":\"" << to_string(report.decision) << "\"," 
         << "\"generated_seed_count\":" << report.generated_seed_count << ','
         << "\"generated_step_count\":" << report.generated_step_count << ','
         << "\"differential_seed_count\":" << report.differential_seed_count << ','
         << "\"differential_command_count\":" << report.differential_command_count << ','
         << "\"mutation_case_count\":" << report.mutation_case_count << ','
         << "\"checks\":[";
  for (std::size_t index = 0U; index < report.checks.size(); ++index) {
    if (index != 0U) output << ',';
    const auto& check = report.checks[index];
    output << '{'
           << "\"check_id\":\"" << detail::json_escape(check.check_id) << "\"," 
           << "\"category\":\"" << detail::json_escape(check.category) << "\"," 
           << "\"description\":\"" << detail::json_escape(check.description) << "\"," 
           << "\"passed\":" << (check.passed ? "true" : "false") << ','
           << "\"evidence\":\"" << detail::json_escape(check.evidence) << "\"," 
           << "\"limitation\":\"" << detail::json_escape(check.limitation) << "\"}";
  }
  output << "],\"sensitivities\":[";
  for (std::size_t index = 0U; index < report.sensitivities.size(); ++index) {
    if (index != 0U) output << ',';
    const auto& sensitivity = report.sensitivities[index];
    output << '{'
           << "\"sensitivity_id\":\"" << detail::json_escape(sensitivity.sensitivity_id) << "\"," 
           << "\"description\":\"" << detail::json_escape(sensitivity.description) << "\"," 
           << "\"control_mean\":" << sensitivity.control_mean << ','
           << "\"treatment_mean\":" << sensitivity.treatment_mean << ','
           << "\"expected_relation\":\"" << detail::json_escape(sensitivity.expected_relation) << "\"," 
           << "\"passed\":" << (sensitivity.passed ? "true" : "false") << '}';
  }
  output << "],\"limitations\":";
  append_string_array(output, report.limitations);
  output << '}';
  return output.str();
}

bool gate_passed(const SimulatorValidationReport& report) noexcept {
  return report.decision == GateDecision::Pass;
}

SimulatorValidationReport run_simulator_validation() {
  SimulatorValidationReport report;
  report.generated_seed_count = 64U;
  report.generated_step_count = 64U * 256U;
  report.differential_seed_count = 32U;
  report.differential_command_count = 32U * 2'000U;
  report.mutation_case_count = 2'048U;
  report.checks = detail::run_hand_and_failure_checks();
  report.checks.push_back(detail::run_differential_check());
  report.sensitivities = detail::run_sensitivity_checks();
  report.limitations = {
      "Gate B validates exact synthetic mechanics and designed-process responsiveness, not historical realism.",
      "The Step 9 process remains explicitly uncalibrated until real data are selected and analysed.",
      "Visible-book simulation omits hidden liquidity and venue-specific matching rules not yet selected.",
      "Local TSan is unavailable because the installed Swift Clang runtime cannot link its libdispatch/Blocks interceptors.",
      "Historical aggregate replay and queue-model validity remain future Gates C and later sensitivity work.",
  };
  bool all_passed = true;
  for (const auto& check : report.checks) all_passed = all_passed && check.passed;
  for (const auto& sensitivity : report.sensitivities) all_passed = all_passed && sensitivity.passed;
  report.decision = all_passed ? GateDecision::Pass : GateDecision::Fail;
  report.canonical_json = canonical_json(report);
  report.report_sha256 = util::sha256_hex(report.canonical_json);
  return report;
}

}  // namespace robust_execution::validation
