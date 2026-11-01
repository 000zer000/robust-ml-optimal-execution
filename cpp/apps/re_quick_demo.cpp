#include "robust_execution/metrics/metrics.hpp"
#include "robust_execution/strategies/baselines.hpp"

#include <cmath>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

using namespace robust_execution;

namespace {
model::TimestampNs time_at(std::int64_t value) {
  return {model::ClockDomain::Simulation, value};
}

model::InstrumentDefinition instrument() {
  return {model::kEventSchemaVersion, model::VenueId{"synthetic"},
          model::InstrumentId{"QUICK-DEMO-USD"}, "DEMO", "USD",
          model::RationalIncrement{1U, 1U}, model::RationalIncrement{1U, 1U},
          model::RationalIncrement{1U, 1U}, model::QuantityLots{1U},
          model::QuantityLots{1'000'000U}, "quick-demo-v1"};
}

void run_scenario(const char* name, const std::vector<std::int64_t>& asks,
                  const std::vector<long double>& expected, bool comma) {
  const policy::ParentOrderDefinition parent{
      model::ParentOrderId{1U}, model::Side::Buy, model::QuantityLots{100U},
      time_at(1'000), time_at(2'000), model::PriceTicks{100}, "hard-completion-v1"};
  const strategies::VolumeProfile profile{{1U, 2U, 3U, 4U}, time_at(999),
                                         "hand-authored-past-only-demo-profile"};
  const std::vector<strategies::BaselineSchedule> schedules{
      strategies::build_baseline_schedule(parent, {
          strategies::BaselineKind::ImmediateAggressive,
          strategies::ExecutionStyle::Aggressive, 1U, std::nullopt}),
      strategies::build_baseline_schedule(parent, {
          strategies::BaselineKind::Twap,
          strategies::ExecutionStyle::Aggressive, 4U, std::nullopt}),
      strategies::build_baseline_schedule(parent, {
          strategies::BaselineKind::PastVolumeInformed,
          strategies::ExecutionStyle::Aggressive, 0U, profile})};
  const std::vector<std::string> names{"Immediate", "TWAP", "Past-volume"};
  if (comma) std::cout << ',';
  std::cout << "{\"scenario\":\"" << name << "\",\"ask_ticks\":[";
  for (std::size_t i = 0; i < asks.size(); ++i) {
    if (i) std::cout << ',';
    std::cout << asks[i];
  }
  std::cout << "],\"policies\":[";
  for (std::size_t i = 0; i < schedules.size(); ++i) {
    metrics::EpisodeMetricInput input;
    input.episode_id = std::string{name} + names[i];
    input.instrument = instrument();
    input.parent = parent;
    for (std::size_t j = 0; j < schedules[i].slices.size(); ++j) {
      const auto& slice = schedules[i].slices[j];
      input.fills.push_back({model::ExecutionId{j + 1U}, model::Side::Buy,
          model::PriceTicks{asks.at(j)}, slice.quantity, slice.release_time,
          model::LiquidityRole::Taker, model::QuoteAtoms{0},
          metrics::FillSource::Continuous});
    }
    const auto result = metrics::calculate_episode_metrics(input);
    if (!result.ok() || !result.metrics->complete ||
        !metrics::audit_episode_metrics(input, *result.metrics).passed ||
        !result.metrics->implementation_shortfall_bps ||
        std::abs(*result.metrics->implementation_shortfall_bps - expected.at(i)) > 1e-9L) {
      throw std::runtime_error("quick demo failed independent hand-tape accounting");
    }
    if (i) std::cout << ',';
    std::cout << "{\"name\":\"" << names[i] << "\",\"shortfall_bps\":"
              << *result.metrics->implementation_shortfall_bps
              << ",\"complete\":true,\"quantity_lots\":100,\"slice_lots\":[";
    for (std::size_t j = 0; j < schedules[i].slices.size(); ++j) {
      if (j) std::cout << ',';
      std::cout << schedules[i].slices[j].quantity.value();
    }
    std::cout << "]}";
  }
  std::cout << "]}";
}
}  // namespace

int main() {
  std::cout << "{\"kind\":\"hand_authored_synthetic_teaching_example\","
               "\"historical_gate_c_open\":false,\"fees_quote_atoms\":0,"
               "\"reference_price_ticks\":100,\"profile_cutoff_ns\":999,"
               "\"episode_start_ns\":1000,\"scenarios\":[";
  run_scenario("Reverting asks", {101, 100, 99, 100}, {100, 0, -20}, false);
  run_scenario("Rising-ask stress", {101, 104, 106, 110}, {100, 525, 670}, true);
  std::cout << "]}\n";
}
