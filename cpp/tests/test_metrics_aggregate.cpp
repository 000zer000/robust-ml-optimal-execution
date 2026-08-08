#include "robust_execution/metrics/metrics.hpp"

#include <cmath>
#include <cstdlib>
#include <vector>

int main() {
  namespace metrics = robust_execution::metrics;
  std::vector<metrics::EpisodeMetrics> episodes;
  std::vector<metrics::MetricAuditResult> audits;
  for (int value = 0; value < 40; ++value) {
    metrics::EpisodeMetrics row;
    row.episode_id = std::to_string(value);
    row.parent_quantity = robust_execution::model::QuantityLots{100U};
    row.filled_quantity = row.parent_quantity;
    row.remaining_quantity = robust_execution::model::QuantityLots{0U};
    row.completion_rate = 1.0;
    row.complete = true;
    row.implementation_shortfall_bps = -20.0 + 5.0 * static_cast<double>(value);
    episodes.push_back(row);
    metrics::MetricAuditResult audit;
    audit.passed = true;
    audits.push_back(audit);
  }
  const auto summary = metrics::summarize_tail_risk(episodes, audits);
  if (summary.episode_count != 40U || std::abs(summary.mean_bps - 77.5) > 1e-12 ||
      std::abs(summary.median_bps - 77.5) > 1e-12 ||
      std::abs(summary.var95_bps - 165.0) > 1e-12 ||
      std::abs(summary.cvar95_bps - 172.5) > 1e-12 ||
      std::abs(summary.var99_bps - 175.0) > 1e-12 ||
      std::abs(summary.cvar99_bps - 175.0) > 1e-12) {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
