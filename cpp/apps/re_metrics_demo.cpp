#include "robust_execution/metrics/metrics.hpp"

#include <iostream>

int main() {
  const auto report = robust_execution::metrics::run_metrics_validation();
  std::cout << report.canonical_json << '\n';
  return report.buy_sell_symmetry_passed &&
                 report.incomplete_episode_rejected_from_aggregate &&
                 report.independent_audit_passed && report.exact_accounting_passed &&
                 report.state_bounds_passed && report.deterministic
             ? 0
             : 1;
}
