#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include "robust_execution/policy/types.hpp"

namespace robust_execution::metrics {

namespace model = robust_execution::model;
namespace policy = robust_execution::policy;

enum class MetricIssueSeverity : std::uint8_t { Warning, Error };
enum class FillSource : std::uint8_t { Continuous, TerminalCompletion };

enum class BenchmarkKind : std::uint8_t { ArrivalPrice, External };

[[nodiscard]] constexpr std::string_view to_string(MetricIssueSeverity value) noexcept {
  switch (value) {
    case MetricIssueSeverity::Warning:
      return "warning";
    case MetricIssueSeverity::Error:
      return "error";
  }
  return "unknown";
}

[[nodiscard]] constexpr std::string_view to_string(FillSource value) noexcept {
  switch (value) {
    case FillSource::Continuous:
      return "continuous";
    case FillSource::TerminalCompletion:
      return "terminal_completion";
  }
  return "unknown";
}

[[nodiscard]] constexpr std::string_view to_string(BenchmarkKind value) noexcept {
  switch (value) {
    case BenchmarkKind::ArrivalPrice:
      return "arrival_price";
    case BenchmarkKind::External:
      return "external";
  }
  return "unknown";
}

struct MetricIssue {
  MetricIssueSeverity severity{MetricIssueSeverity::Error};
  std::string code;
  std::string detail;
};

struct ExecutionFillRecord {
  model::ExecutionId execution_id{};
  model::Side side{model::Side::Buy};
  model::PriceTicks price{};
  model::QuantityLots quantity{};
  model::TimestampNs fill_time{};
  model::LiquidityRole liquidity_role{model::LiquidityRole::Unknown};
  model::QuoteAtoms explicit_fee{};
  FillSource source{FillSource::Continuous};
};

struct MarkoutRecord {
  model::ExecutionId execution_id{};
  std::int64_t horizon_ns{0};
  model::TimestampNs markout_time{};
  model::PriceTicks markout_mid_price{};
};

struct DecisionTimingRecord {
  model::DecisionId decision_id{};
  model::TimestampNs observation_cutoff{};
  model::TimestampNs decision_start{};
  model::TimestampNs decision_end{};
  std::optional<std::int64_t> inference_latency_ns;
  std::optional<model::TimestampNs> action_dispatch_time;
};

struct ActionActivity {
  std::uint64_t decisions{0U};
  std::uint64_t submits{0U};
  std::uint64_t cancels{0U};
  std::uint64_t replaces{0U};
  std::uint64_t rejected_actions{0U};
  std::uint64_t invalid_actions{0U};
};

struct PerformanceMeasurement {
  std::uint64_t events_processed{0U};
  std::int64_t wall_time_ns{0};
  std::uint64_t peak_rss_bytes{0U};
};

struct BenchmarkPrice {
  std::string benchmark_id;
  BenchmarkKind kind{BenchmarkKind::External};
  model::PriceTicks price{};
};

struct EpisodeMetricInput {
  std::string episode_id;
  model::InstrumentDefinition instrument;
  policy::ParentOrderDefinition parent;
  std::vector<ExecutionFillRecord> fills;
  std::vector<MarkoutRecord> markouts;
  std::vector<DecisionTimingRecord> decision_timings;
  ActionActivity actions;
  PerformanceMeasurement performance;
  std::vector<BenchmarkPrice> external_benchmarks;
};

struct InventoryPoint {
  model::TimestampNs timestamp{};
  model::QuantityLots remaining{};
};

struct LatencySummary {
  std::uint64_t count{0U};
  std::int64_t minimum_ns{0};
  std::int64_t maximum_ns{0};
  double mean_ns{0.0};
  double p50_ns{0.0};
  double p95_ns{0.0};
  double p99_ns{0.0};
};

struct BenchmarkMetric {
  std::string benchmark_id;
  BenchmarkKind kind{BenchmarkKind::External};
  model::PriceTicks price{};
  model::QuoteAtoms benchmark_notional{};
  std::optional<model::QuoteAtoms> implementation_shortfall;
  std::optional<double> implementation_shortfall_bps;
};

struct AdverseSelectionMetric {
  std::int64_t horizon_ns{0};
  model::QuantityLots observed_quantity{};
  double coverage_fraction{0.0};
  model::QuoteAtoms directional_cost{};
  std::optional<double> directional_cost_bps;
};

struct EpisodeMetrics {
  std::string episode_id;
  model::Side side{model::Side::Buy};
  model::QuantityLots parent_quantity{};
  model::QuantityLots filled_quantity{};
  model::QuantityLots remaining_quantity{};
  double completion_rate{0.0};
  bool complete{false};
  bool terminal_completion_used{false};
  model::QuantityLots terminal_quantity{};
  model::QuoteAtoms gross_execution_notional{};
  model::QuoteAtoms gross_cash_flow{};
  model::QuoteAtoms explicit_fees{};
  model::QuoteAtoms net_cash_flow{};
  std::optional<double> average_execution_price_ticks;
  std::optional<double> average_execution_price_quote;
  std::optional<model::QuoteAtoms> implementation_shortfall;
  std::optional<double> implementation_shortfall_bps;
  model::QuoteAtoms terminal_completion_cost{};
  std::optional<double> terminal_completion_cost_bps;
  model::QuantityLots passive_quantity{};
  model::QuantityLots aggressive_quantity{};
  model::QuantityLots unknown_liquidity_quantity{};
  double passive_fraction{0.0};
  double aggressive_fraction{0.0};
  double unknown_liquidity_fraction{0.0};
  std::optional<std::int64_t> time_to_first_fill_ns;
  std::optional<std::int64_t> time_to_complete_ns;
  std::vector<InventoryPoint> inventory_trajectory;
  std::vector<BenchmarkMetric> benchmarks;
  std::vector<AdverseSelectionMetric> adverse_selection;
  LatencySummary controller_latency;
  LatencySummary inference_latency;
  LatencySummary observation_staleness;
  LatencySummary action_dispatch_latency;
  ActionActivity actions;
  std::optional<double> cancel_to_submit_ratio;
  PerformanceMeasurement performance;
  std::optional<double> events_per_second;
  std::vector<MetricIssue> issues;
  std::string canonical_json;
  std::string sha256;
};

struct TailRiskSummary {
  std::uint64_t episode_count{0U};
  double mean_bps{0.0};
  double sample_variance_bps2{0.0};
  double sample_stddev_bps{0.0};
  double minimum_bps{0.0};
  double maximum_bps{0.0};
  double median_bps{0.0};
  double var95_bps{0.0};
  double cvar95_bps{0.0};
  double var99_bps{0.0};
  double cvar99_bps{0.0};
  double mean_completion_rate{0.0};
  double minimum_completion_rate{0.0};
  double mean_terminal_fraction{0.0};
  std::string quantile_method{"empirical_nearest_rank"};
  std::string cvar_method{"fractional_worst_tail_mean"};
  std::string canonical_json;
  std::string sha256;
};

struct EpisodeMetricResult {
  std::optional<EpisodeMetrics> metrics;
  std::vector<MetricIssue> issues;

  [[nodiscard]] bool ok() const noexcept;
};

struct MetricAuditResult {
  bool passed{false};
  std::vector<MetricIssue> issues;
  std::string canonical_json;
  std::string sha256;
};

struct MetricsValidationReport {
  EpisodeMetrics detailed_episode;
  MetricAuditResult detailed_audit;
  TailRiskSummary aggregate;
  std::uint64_t aggregate_episode_count{0U};
  bool buy_sell_symmetry_passed{false};
  bool incomplete_episode_rejected_from_aggregate{false};
  bool independent_audit_passed{false};
  bool exact_accounting_passed{false};
  bool state_bounds_passed{false};
  bool deterministic{false};
  std::string canonical_json;
  std::string sha256;
};

}  // namespace robust_execution::metrics
