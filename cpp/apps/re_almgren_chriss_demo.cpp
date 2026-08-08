#include "robust_execution/metrics/metrics.hpp"
#include "robust_execution/strategies/almgren_chriss.hpp"
#include "robust_execution/strategies/baselines.hpp"
#include "robust_execution/util/sha256.hpp"

#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <vector>

using namespace robust_execution;

namespace {
model::TimestampNs t(std::int64_t value) { return {model::ClockDomain::Simulation, value}; }
model::InstrumentDefinition instrument() {
  return {model::kEventSchemaVersion, model::VenueId{"synthetic"}, model::InstrumentId{"AC-USD"}, "AC", "USD",
          model::RationalIncrement{1U,1U}, model::RationalIncrement{1U,1U}, model::RationalIncrement{1U,1U},
          model::QuantityLots{1U}, model::QuantityLots{1'000'000U}, "step19-v1"};
}
policy::ParentOrderDefinition parent() {
  return {model::ParentOrderId{19U}, model::Side::Buy, model::QuantityLots{100U}, t(1'000), t(2'000), model::PriceTicks{100}, "hard-completion-v1"};
}
strategies::AlmgrenChrissParameters params(long double lambda, const char* provenance) {
  return {4U, lambda, 1.0L, 1.0L, 0.0L, 0.0L, 250.0L, strategies::ExecutionStyle::Aggressive, t(999), provenance};
}
metrics::EpisodeMetrics evaluate(const std::string& id, const strategies::AlmgrenChrissSchedule& schedule) {
  static const std::vector<std::int64_t> asks{101,100,99,100};
  metrics::EpisodeMetricInput input;
  input.episode_id = id;
  input.instrument = instrument();
  input.parent = parent();
  for (std::size_t i = 0U; i < schedule.slices.size(); ++i) {
    input.fills.push_back({model::ExecutionId{i+1U}, model::Side::Buy, model::PriceTicks{asks.at(i)}, schedule.slices[i].quantity,
                           schedule.slices[i].release_time, model::LiquidityRole::Taker, model::QuoteAtoms{0}, metrics::FillSource::Continuous});
  }
  const auto result = metrics::calculate_episode_metrics(input);
  if (!result.ok()) throw std::runtime_error("AC metric calculation failed");
  const auto audit = metrics::audit_episode_metrics(input, *result.metrics);
  if (!audit.passed) throw std::runtime_error("AC metric audit failed");
  return *result.metrics;
}
std::string decimal(long double value) {
  std::ostringstream out;
  out << std::fixed << std::setprecision(12) << value;
  return out.str();
}
void emit(std::ostringstream& out, const char* name, const strategies::AlmgrenChrissSchedule& schedule, const strategies::AlmgrenChrissParameters& parameters, const metrics::EpisodeMetrics& metrics) {
  out << '"' << name << "\":{";
  out << "\"canonical\":\"" << schedule.canonical() << "\",";
  out << "\"implementation_shortfall_bps\":" << *metrics.implementation_shortfall_bps << ',';
  out << "\"parameters\":{";
  out << "\"slice_count\":" << parameters.slice_count << ',';
  out << "\"risk_aversion_lambda\":\"" << decimal(parameters.risk_aversion_lambda) << "\",";
  out << "\"volatility_sigma\":\"" << decimal(parameters.volatility_sigma) << "\",";
  out << "\"temporary_impact_eta\":\"" << decimal(parameters.temporary_impact_eta) << "\",";
  out << "\"permanent_impact_gamma\":\"" << decimal(parameters.permanent_impact_gamma) << "\",";
  out << "\"fixed_cost_epsilon\":\"" << decimal(parameters.fixed_cost_epsilon) << "\",";
  out << "\"time_unit_ns\":\"" << decimal(parameters.time_unit_ns) << "\",";
  out << "\"calibration_cutoff_ns\":" << parameters.calibration_cutoff.value() << ',';
  out << "\"provenance_id\":\"" << parameters.parameter_provenance_id << "\"},";
  out << "\"kappa\":\"" << decimal(schedule.diagnostics.kappa) << "\",";
  out << "\"eta_tilde\":\"" << decimal(schedule.diagnostics.eta_tilde) << "\",";
  out << "\"expected_cost_model_units\":\"" << decimal(schedule.diagnostics.expected_cost_model_units) << "\",";
  out << "\"variance_model_units\":\"" << decimal(schedule.diagnostics.variance_model_units) << "\",";
  out << "\"objective_model_units\":\"" << decimal(schedule.diagnostics.objective_model_units) << "\",";
  out << "\"slices\":[";
  for (std::size_t i = 0U; i < schedule.slices.size(); ++i) {
    if (i) out << ',';
    out << "{\"quantity_lots\":" << schedule.slices[i].quantity.value() << ",\"release_time_ns\":" << schedule.slices[i].release_time.value() << '}';
  }
  out << "]}";
}
}

int main() {
  const auto p = parent();
  const auto neutral_parameters = params(0.0L, "ac-risk-neutral-v1");
  const auto moderate_parameters = params(0.5L, "ac-moderate-risk-v1");
  const auto high_parameters = params(2.0L, "ac-high-risk-v1");
  const auto neutral = strategies::build_almgren_chriss_schedule(p, neutral_parameters);
  const auto moderate = strategies::build_almgren_chriss_schedule(p, moderate_parameters);
  const auto high = strategies::build_almgren_chriss_schedule(p, high_parameters);
  const auto twap = strategies::build_baseline_schedule(p, {strategies::BaselineKind::Twap, strategies::ExecutionStyle::Aggressive, 4U, std::nullopt});
  const auto mn = evaluate("ac-neutral", neutral);
  const auto mm = evaluate("ac-moderate", moderate);
  const auto mh = evaluate("ac-high", high);

  std::ostringstream body;
  body << '{';
  body << "\"evidence_status\":\"synthetic_validation_only_non_research\",";
  body << "\"model\":\"discrete_linear_almgren_chriss_zero_drift\",";
  bool risk_neutral_matches_twap = neutral.slices.size() == twap.slices.size();
  if (risk_neutral_matches_twap) {
    for (std::size_t i = 0U; i < neutral.slices.size(); ++i) {
      if (neutral.slices[i].release_time != twap.slices[i].release_time || neutral.slices[i].quantity != twap.slices[i].quantity) {
        risk_neutral_matches_twap = false;
        break;
      }
    }
  }
  body << "\"risk_neutral_matches_twap\":" << (risk_neutral_matches_twap ? "true" : "false") << ',';
  emit(body, "risk_neutral", neutral, neutral_parameters, mn); body << ',';
  emit(body, "moderate_risk", moderate, moderate_parameters, mm); body << ',';
  emit(body, "high_risk", high, high_parameters, mh);
  body << '}';
  const auto canonical = body.str();
  std::cout << "{\"payload\":" << canonical << ",\"sha256\":\"" << util::sha256_hex(canonical) << "\"}\n";
}
