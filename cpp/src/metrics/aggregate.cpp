#include "robust_execution/metrics/calculator.hpp"

#include "robust_execution/util/sha256.hpp"

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <vector>

namespace robust_execution::metrics {
namespace {

double nearest_rank(const std::vector<double>& sorted, double probability) {
  const auto rank = static_cast<std::size_t>(
      std::ceil(probability * static_cast<double>(sorted.size()))
  );
  return sorted[std::max<std::size_t>(1U, rank) - 1U];
}

double fractional_worst_tail_mean(const std::vector<double>& sorted, double probability) {
  const long double target = (1.0L - static_cast<long double>(probability)) *
                             static_cast<long double>(sorted.size());
  if (target <= 0.0L) {
    return sorted.back();
  }
  long double remaining = target;
  long double weighted_sum = 0.0L;
  for (auto iterator = sorted.rbegin(); iterator != sorted.rend() && remaining > 0.0L;
       ++iterator) {
    const long double weight = std::min(1.0L, remaining);
    weighted_sum += weight * static_cast<long double>(*iterator);
    remaining -= weight;
  }
  return static_cast<double>(weighted_sum / target);
}

std::string canonical_json(const TailRiskSummary& value) {
  std::ostringstream output;
  output << std::setprecision(17);
  output << '{';
  output << "\"cvar95_bps\":" << value.cvar95_bps << ',';
  output << "\"cvar99_bps\":" << value.cvar99_bps << ',';
  output << "\"cvar_method\":\"" << value.cvar_method << "\",";
  output << "\"episode_count\":" << value.episode_count << ',';
  output << "\"maximum_bps\":" << value.maximum_bps << ',';
  output << "\"mean_bps\":" << value.mean_bps << ',';
  output << "\"mean_completion_rate\":" << value.mean_completion_rate << ',';
  output << "\"mean_terminal_fraction\":" << value.mean_terminal_fraction << ',';
  output << "\"median_bps\":" << value.median_bps << ',';
  output << "\"minimum_bps\":" << value.minimum_bps << ',';
  output << "\"minimum_completion_rate\":" << value.minimum_completion_rate << ',';
  output << "\"quantile_method\":\"" << value.quantile_method << "\",";
  output << "\"sample_stddev_bps\":" << value.sample_stddev_bps << ',';
  output << "\"sample_variance_bps2\":" << value.sample_variance_bps2 << ',';
  output << "\"schema_version\":\"tail-risk-summary-v1\",";
  output << "\"var95_bps\":" << value.var95_bps << ',';
  output << "\"var99_bps\":" << value.var99_bps;
  output << '}';
  return output.str();
}

}  // namespace

TailRiskSummary summarize_tail_risk(
    std::span<const EpisodeMetrics> episodes,
    std::span<const MetricAuditResult> audits
) {
  if (episodes.empty()) {
    throw std::invalid_argument("tail-risk summary requires at least one episode");
  }
  if (episodes.size() != audits.size()) {
    throw std::invalid_argument("tail-risk summary requires one independent audit per episode");
  }
  std::vector<double> losses;
  losses.reserve(episodes.size());
  long double completion_sum = 0.0L;
  long double terminal_fraction_sum = 0.0L;
  double minimum_completion = 1.0;
  for (std::size_t index = 0; index < episodes.size(); ++index) {
    const auto& episode = episodes[index];
    if (!audits[index].passed || !episode.complete ||
        !episode.implementation_shortfall_bps.has_value()) {
      throw std::invalid_argument(
          "tail-risk summary forbids incomplete, unaudited, or undefined-shortfall episodes"
      );
    }
    losses.push_back(*episode.implementation_shortfall_bps);
    completion_sum += static_cast<long double>(episode.completion_rate);
    minimum_completion = std::min(minimum_completion, episode.completion_rate);
    terminal_fraction_sum += static_cast<long double>(episode.terminal_quantity.value()) /
                             static_cast<long double>(episode.parent_quantity.value());
  }
  std::ranges::sort(losses);
  long double sum = std::accumulate(losses.begin(), losses.end(), 0.0L);
  const long double mean = sum / static_cast<long double>(losses.size());
  long double squared = 0.0L;
  for (const auto loss : losses) {
    const long double difference = static_cast<long double>(loss) - mean;
    squared += difference * difference;
  }

  TailRiskSummary summary;
  summary.episode_count = losses.size();
  summary.mean_bps = static_cast<double>(mean);
  summary.sample_variance_bps2 = losses.size() > 1U
                                     ? static_cast<double>(
                                           squared / static_cast<long double>(losses.size() - 1U)
                                       )
                                     : 0.0;
  summary.sample_stddev_bps = std::sqrt(summary.sample_variance_bps2);
  summary.minimum_bps = losses.front();
  summary.maximum_bps = losses.back();
  if (losses.size() % 2U == 1U) {
    summary.median_bps = losses[losses.size() / 2U];
  } else {
    const auto upper = losses.size() / 2U;
    summary.median_bps = (losses[upper - 1U] + losses[upper]) / 2.0;
  }
  summary.var95_bps = nearest_rank(losses, 0.95);
  summary.cvar95_bps = fractional_worst_tail_mean(losses, 0.95);
  summary.var99_bps = nearest_rank(losses, 0.99);
  summary.cvar99_bps = fractional_worst_tail_mean(losses, 0.99);
  summary.mean_completion_rate = static_cast<double>(
      completion_sum / static_cast<long double>(episodes.size())
  );
  summary.minimum_completion_rate = minimum_completion;
  summary.mean_terminal_fraction = static_cast<double>(
      terminal_fraction_sum / static_cast<long double>(episodes.size())
  );
  summary.canonical_json = canonical_json(summary);
  summary.sha256 = util::sha256_hex(summary.canonical_json);
  return summary;
}

}  // namespace robust_execution::metrics
