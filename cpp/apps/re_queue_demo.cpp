#include "robust_execution/historical/historical.hpp"

#include <iostream>

int main() {
  const auto report = robust_execution::historical::run_queue_model_validation();
  std::cout << report.canonical_json << '\n';
  return report.exact_comparison_count == report.bracketed_comparison_count &&
                 report.exact_comparison_count == report.monotonic_comparison_count &&
                 report.trade_through_rule_passed &&
                 report.no_fill_from_cancellation_only_passed && report.deterministic
             ? 0
             : 1;
}
