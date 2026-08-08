#pragma once

#include "robust_execution/metrics/types.hpp"

namespace robust_execution::metrics {

[[nodiscard]] MetricAuditResult audit_episode_metrics(
    const EpisodeMetricInput& input,
    const EpisodeMetrics& reported
);

}  // namespace robust_execution::metrics
