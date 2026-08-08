#include "robust_execution/validation/validation.hpp"

#include <cstdlib>
#include <string>

int main() {
  namespace validation = robust_execution::validation;
  const auto report = validation::run_simulator_validation();
  if (!validation::gate_passed(report) || report.decision != validation::GateDecision::Pass ||
      report.checks.size() != 7U || report.sensitivities.size() != 4U ||
      report.generated_seed_count != 64U || report.generated_step_count != 16'384U ||
      report.differential_seed_count != 32U ||
      report.differential_command_count != 64'000U || report.mutation_case_count != 2'048U ||
      report.report_sha256.size() != 64U ||
      report.canonical_json.find("\"decision\":\"pass\"") == std::string::npos) {
    return EXIT_FAILURE;
  }
  for (const auto& check : report.checks) if (!check.passed) return EXIT_FAILURE;
  for (const auto& sensitivity : report.sensitivities) {
    if (!sensitivity.passed) return EXIT_FAILURE;
  }
  auto changed = report;
  changed.limitations.push_back("mutation");
  if (validation::canonical_json(changed) == report.canonical_json) return EXIT_FAILURE;
  return EXIT_SUCCESS;
}
