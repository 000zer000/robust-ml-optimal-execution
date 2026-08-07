#include "robust_execution/validation/validation.hpp"

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

int main(int argc, char** argv) {
  namespace validation = robust_execution::validation;
  const auto report = validation::run_simulator_validation();
  if (argc == 3 && std::string{argv[1]} == "--output-dir") {
    const std::filesystem::path output_dir{argv[2]};
    std::filesystem::create_directories(output_dir);
    std::ofstream report_file{output_dir / "report.json", std::ios::binary | std::ios::trunc};
    if (!report_file) throw std::runtime_error("failed to create Step 10 report artifact");
    report_file << report.canonical_json << '\n';
  } else if (argc != 1) {
    std::cerr << "usage: robust_execution_validation_demo [--output-dir PATH]\n";
    return EXIT_FAILURE;
  }
  std::size_t passed_checks = 0U;
  for (const auto& check : report.checks) passed_checks += check.passed ? 1U : 0U;
  std::size_t passed_sensitivities = 0U;
  for (const auto& sensitivity : report.sensitivities) {
    passed_sensitivities += sensitivity.passed ? 1U : 0U;
  }
  std::cout << "step=10\n"
            << "gate_id=" << report.gate_id << '\n'
            << "decision=" << validation::to_string(report.decision) << '\n'
            << "checks_passed=" << passed_checks << '/' << report.checks.size() << '\n'
            << "sensitivities_passed=" << passed_sensitivities << '/'
            << report.sensitivities.size() << '\n'
            << "generated_seeds=" << report.generated_seed_count << '\n'
            << "generated_steps=" << report.generated_step_count << '\n'
            << "differential_seeds=" << report.differential_seed_count << '\n'
            << "differential_commands=" << report.differential_command_count << '\n'
            << "mutation_cases=" << report.mutation_case_count << '\n'
            << "report_sha256=" << report.report_sha256 << '\n';
  return validation::gate_passed(report) ? EXIT_SUCCESS : EXIT_FAILURE;
}
