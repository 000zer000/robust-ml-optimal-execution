#include "robust_execution/metrics/metrics.hpp"
#include "robust_execution/strategies/baselines.hpp"
#include "robust_execution/util/sha256.hpp"

#include <iostream>
#include <sstream>
#include <stdexcept>
#include <vector>

using namespace robust_execution;

namespace {
model::TimestampNs t(std::int64_t v) { return {model::ClockDomain::Simulation, v}; }
model::InstrumentDefinition instrument() {
  return {model::kEventSchemaVersion, model::VenueId{"synthetic"}, model::InstrumentId{"BASELINE-USD"}, "BASE", "USD",
          model::RationalIncrement{1U,1U}, model::RationalIncrement{1U,1U}, model::RationalIncrement{1U,1U},
          model::QuantityLots{1U}, model::QuantityLots{1'000'000U}, "step18-v1"};
}
policy::ParentOrderDefinition parent() {
  return {model::ParentOrderId{18U}, model::Side::Buy, model::QuantityLots{100U}, t(1'000), t(2'000), model::PriceTicks{100}, "hard-completion-v1"};
}
metrics::EpisodeMetrics evaluate(const std::string& id, const strategies::BaselineSchedule& schedule) {
  static const std::vector<std::int64_t> asks{101,100,99,100};
  metrics::EpisodeMetricInput input;
  input.episode_id=id; input.instrument=instrument(); input.parent=parent();
  for (std::size_t i=0;i<schedule.slices.size();++i) {
    const auto price = schedule.slices.size()==1U ? 101 : asks.at(i);
    input.fills.push_back({model::ExecutionId{i+1U}, model::Side::Buy, model::PriceTicks{price}, schedule.slices[i].quantity,
                           schedule.slices[i].release_time, model::LiquidityRole::Taker, model::QuoteAtoms{0}, metrics::FillSource::Continuous});
  }
  const auto result=metrics::calculate_episode_metrics(input);
  if (!result.ok()) throw std::runtime_error("baseline metric calculation failed");
  const auto audit = metrics::audit_episode_metrics(input, *result.metrics);
  if (!audit.passed) throw std::runtime_error("baseline metric audit failed");
  return *result.metrics;
}
void emit_schedule(std::ostringstream& out, const char* name, const strategies::BaselineSchedule& schedule, const metrics::EpisodeMetrics& metrics) {
  out << "\"" << name << "\":{";
  out << "\"canonical\":\"" << schedule.canonical() << "\",";
  out << "\"implementation_shortfall_bps\":" << *metrics.implementation_shortfall_bps << ',';
  out << "\"slices\":[";
  for (std::size_t i=0;i<schedule.slices.size();++i) { if(i) out << ','; out << "{\"quantity_lots\":" << schedule.slices[i].quantity.value() << ",\"release_time_ns\":" << schedule.slices[i].release_time.value() << '}'; }
  out << "]}";
}
}

int main() {
  const auto p=parent();
  const auto immediate=strategies::build_baseline_schedule(p,{strategies::BaselineKind::ImmediateAggressive,strategies::ExecutionStyle::Aggressive,1U,std::nullopt});
  const auto twap=strategies::build_baseline_schedule(p,{strategies::BaselineKind::Twap,strategies::ExecutionStyle::Aggressive,4U,std::nullopt});
  const auto passive_twap=strategies::build_baseline_schedule(p,{strategies::BaselineKind::Twap,strategies::ExecutionStyle::Passive,4U,std::nullopt});
  strategies::VolumeProfile profile{{1U,2U,3U,4U},t(999),"training-only-volume-profile-v1"};
  const auto volume=strategies::build_baseline_schedule(p,{strategies::BaselineKind::PastVolumeInformed,strategies::ExecutionStyle::Aggressive,0U,profile});
  const auto mi=evaluate("immediate",immediate), mt=evaluate("twap",twap), mv=evaluate("volume",volume);
  std::ostringstream body; body << '{';
  body << "\"evidence_status\":\"synthetic_validation_only_non_research\",";
  emit_schedule(body,"immediate",immediate,mi); body << ',';
  emit_schedule(body,"twap",twap,mt); body << ',';
  emit_schedule(body,"past_volume_informed",volume,mv); body << ',';
  body << "\"passive_twap_canonical\":\"" << passive_twap.canonical() << "\",";
  body << "\"past_only_cutoff_ns\":" << profile.training_cutoff.value() << ',';
  body << "\"episode_start_ns\":" << p.start_time.value();
  body << '}';
  const auto canonical=body.str();
  std::cout << "{\"payload\":" << canonical << ",\"sha256\":\"" << util::sha256_hex(canonical) << "\"}\n";
}
