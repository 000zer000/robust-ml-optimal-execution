#include "robust_execution/historical/historical.hpp"

#include <cstdlib>

int main() {
  const auto first = robust_execution::historical::run_queue_model_validation();
  const auto second = robust_execution::historical::run_queue_model_validation();
  if (first.exact_comparison_count != 5U || first.bracketed_comparison_count != 5U ||
      first.monotonic_comparison_count != 5U || first.sensitivity.size() != 9U ||
      !first.trade_through_rule_passed || !first.no_fill_from_cancellation_only_passed ||
      !first.deterministic || first.exact_fifo_reconstructed_historically ||
      first.canonical_json != second.canonical_json || first.sha256 != second.sha256 ||
      first.sha256.size() != 64U) {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
