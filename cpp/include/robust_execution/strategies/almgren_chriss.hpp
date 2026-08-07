#pragma once

#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <vector>

#include "robust_execution/strategies/baselines.hpp"

namespace robust_execution::strategies {

struct AlmgrenChrissParameters {
  std::size_t slice_count{1U};
  long double risk_aversion_lambda{0.0L};
  long double volatility_sigma{0.0L};
  long double temporary_impact_eta{1.0L};
  long double permanent_impact_gamma{0.0L};
  long double fixed_cost_epsilon{0.0L};
  long double time_unit_ns{1'000'000'000.0L};
  ExecutionStyle style{ExecutionStyle::Aggressive};
  model::TimestampNs calibration_cutoff{};
  std::string parameter_provenance_id;
};

struct AlmgrenChrissDiagnostics {
  long double interval_tau{0.0L};
  long double eta_tilde{0.0L};
  long double kappa_tilde_squared{0.0L};
  long double kappa{0.0L};
  long double expected_cost_model_units{0.0L};
  long double variance_model_units{0.0L};
  long double objective_model_units{0.0L};
};

struct AlmgrenChrissSchedule {
  ExecutionStyle style{ExecutionStyle::Aggressive};
  std::vector<ScheduleSlice> slices;
  std::vector<long double> normalized_inventory_path;
  AlmgrenChrissDiagnostics diagnostics;
  std::string parameter_provenance_id;

  [[nodiscard]] model::QuantityLots total_quantity() const;
  [[nodiscard]] std::string canonical() const;
};

[[nodiscard]] AlmgrenChrissSchedule build_almgren_chriss_schedule(
    const policy::ParentOrderDefinition& parent,
    const AlmgrenChrissParameters& parameters
);

class AlmgrenChrissPolicy final : public policy::ExecutionPolicy {
 public:
  AlmgrenChrissPolicy(model::StrategyId strategy_id, AlmgrenChrissParameters parameters);
  [[nodiscard]] model::StrategyId strategy_id() const override;
  void reset(const policy::ParentOrderDefinition& parent, const policy::PolicyEnvironment& environment) override;
  [[nodiscard]] policy::PolicyAction on_observation(const policy::PolicyObservation& observation) override;
  [[nodiscard]] const AlmgrenChrissSchedule& schedule() const;

 private:
  model::StrategyId strategy_id_;
  AlmgrenChrissParameters parameters_;
  std::optional<AlmgrenChrissSchedule> schedule_;
  std::optional<policy::ParentOrderDefinition> parent_;
  std::optional<policy::PolicyEnvironment> environment_;
  std::uint64_t next_client_order_id_{1U};
};

}  // namespace robust_execution::strategies
