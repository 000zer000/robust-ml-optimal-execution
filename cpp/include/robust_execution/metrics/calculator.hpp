#pragma once

#include <span>

#include "robust_execution/metrics/types.hpp"

namespace robust_execution::metrics {

[[nodiscard]] EpisodeMetricResult calculate_episode_metrics(const EpisodeMetricInput& input);

[[nodiscard]] TailRiskSummary summarize_tail_risk(
    std::span<const EpisodeMetrics> episodes,
    std::span<const MetricAuditResult> audits
);

[[nodiscard]] MetricsValidationReport run_metrics_validation();

}  // namespace robust_execution::metrics
