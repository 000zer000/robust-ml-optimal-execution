#pragma once

#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <vector>

#include "robust_execution/policy/execution_policy.hpp"

namespace robust_execution::strategies {

namespace model = robust_execution::model;
namespace policy = robust_execution::policy;

enum class AdaptiveActionMode : std::uint8_t { NoAction, Passive, Aggressive, Cancel };

enum class MpcPredictionKind : std::uint8_t {
  CalibratedModel,
  TrainingBaseRate,
  ShuffledWithinDayInstrument,
  Stale,
  UncalibratedModel,
  PerfectEventOracle,
};

struct MpcPredictionInput {
  model::DecisionId decision_id{};
  model::TimestampNs endpoint_time{};
  model::TimestampNs feature_cutoff_time{};
  model::TimestampNs available_time{};
  long double probability{0.5L};
  long double training_base_rate{0.5L};
  std::string horizon_id;
  std::string model_id;
  std::string provenance_id;
  MpcPredictionKind kind{MpcPredictionKind::CalibratedModel};
  std::optional<model::DecisionId> source_prediction_decision_id;
};

struct NonMlCalibration {
  model::TimestampNs calibration_cutoff{};
  std::string provenance_id;
  long double maker_fee_bps{0.0L};
  long double taker_fee_bps{0.0L};
  long double passive_fill_base{0.50L};
  long double passive_queue_weight{0.45L};
  long double passive_trade_weight{0.35L};
  long double passive_adverse_selection_bps{1.0L};
  long double insufficient_depth_penalty_bps{25.0L};
};

struct AdaptiveSignals {
  long double midpoint_ticks{0.0L};
  long double spread_ticks{0.0L};
  long double same_side_best_lots{0.0L};
  long double opposite_side_best_lots{0.0L};
  long double same_side_queue_share{0.5L};
  long double passive_fill_pressure{0.5L};
  long double passive_fill_probability{0.5L};
  long double elapsed_fraction{0.0L};
  long double filled_fraction{0.0L};
  long double remaining_fraction{1.0L};
  long double progress_lag{0.0L};
  long double time_remaining_fraction{1.0L};
};

struct QueueAwareHeuristicParameters {
  NonMlCalibration calibration;
  policy::QuantityFraction passive_fraction{1U, 4U};
  policy::QuantityFraction aggressive_fraction{1U, 2U};
  model::TickOffset passive_tick_offset{0};
  long double aggressive_lag_threshold{0.15L};
  long double minimum_passive_fill_probability{0.45L};
  std::int64_t terminal_aggressive_window_ns{250'000'000};
  std::string configuration_id;
};

struct MpcParameters {
  NonMlCalibration calibration;
  std::size_t planning_horizon_steps{4U};
  std::vector<policy::QuantityFraction> action_fractions{
      policy::QuantityFraction{1U, 4U},
      policy::QuantityFraction{1U, 2U},
      policy::QuantityFraction{1U, 1U},
  };
  model::TickOffset passive_tick_offset{0};
  policy::QuantityFraction maximum_passive_fraction{1U, 2U};
  long double inventory_risk_bps{2.0L};
  long double terminal_penalty_bps{20.0L};
  long double terminal_inventory_quadratic_bps{10.0L};
  std::string configuration_id;
};

struct MlMpcParameters {
  MpcParameters base;
  long double prediction_risk_weight_bps{0.0L};
  std::string prediction_contract_id;
  std::string configuration_id;
};

struct MpcDecision {
  AdaptiveActionMode mode{AdaptiveActionMode::NoAction};
  std::optional<policy::QuantityFraction> fraction;
  long double objective_bps{0.0L};
  long double aggressive_cost_bps{0.0L};
  long double passive_cost_bps{0.0L};
  std::size_t planning_horizon_steps_used{0U};
  std::uint64_t evaluated_plan_nodes{0U};
  AdaptiveSignals signals;
  bool prediction_used{false};
  long double prediction_probability{0.5L};
  long double prediction_training_base_rate{0.5L};
  long double prediction_adjustment_bps{0.0L};
  std::string prediction_kind;
  std::string prediction_provenance_id;
  std::string prediction_horizon_id;
  std::string canonical;
};

[[nodiscard]] std::string_view to_string(AdaptiveActionMode value) noexcept;
[[nodiscard]] std::string_view to_string(MpcPredictionKind value) noexcept;

[[nodiscard]] AdaptiveSignals calculate_adaptive_signals(
    const policy::PolicyObservation& observation,
    const NonMlCalibration& calibration
);

[[nodiscard]] MpcDecision solve_non_ml_mpc(
    const policy::PolicyObservation& observation,
    const MpcParameters& parameters
);

[[nodiscard]] MpcDecision solve_ml_mpc(
    const policy::PolicyObservation& observation,
    const MlMpcParameters& parameters,
    const MpcPredictionInput& prediction
);

class QueueAwareHeuristicPolicy final : public policy::ExecutionPolicy {
 public:
  QueueAwareHeuristicPolicy(model::StrategyId strategy_id, QueueAwareHeuristicParameters parameters);
  [[nodiscard]] model::StrategyId strategy_id() const override;
  void reset(const policy::ParentOrderDefinition& parent, const policy::PolicyEnvironment& environment) override;
  [[nodiscard]] policy::PolicyAction on_observation(const policy::PolicyObservation& observation) override;
  [[nodiscard]] const std::optional<AdaptiveSignals>& last_signals() const noexcept;

 private:
  model::StrategyId strategy_id_;
  QueueAwareHeuristicParameters parameters_;
  std::optional<policy::ParentOrderDefinition> parent_;
  std::optional<policy::PolicyEnvironment> environment_;
  std::optional<AdaptiveSignals> last_signals_;
  std::uint64_t next_client_order_id_{1U};
};

class NonMlMpcPolicy final : public policy::ExecutionPolicy {
 public:
  NonMlMpcPolicy(model::StrategyId strategy_id, MpcParameters parameters);
  [[nodiscard]] model::StrategyId strategy_id() const override;
  void reset(const policy::ParentOrderDefinition& parent, const policy::PolicyEnvironment& environment) override;
  [[nodiscard]] policy::PolicyAction on_observation(const policy::PolicyObservation& observation) override;
  [[nodiscard]] const std::optional<MpcDecision>& last_decision() const noexcept;

 private:
  model::StrategyId strategy_id_;
  MpcParameters parameters_;
  std::optional<policy::ParentOrderDefinition> parent_;
  std::optional<policy::PolicyEnvironment> environment_;
  std::optional<MpcDecision> last_decision_;
  std::uint64_t next_client_order_id_{1U};
};

class MlMpcPolicy final : public policy::ExecutionPolicy {
 public:
  MlMpcPolicy(
      model::StrategyId strategy_id,
      MlMpcParameters parameters,
      std::vector<MpcPredictionInput> prediction_tape
  );
  [[nodiscard]] model::StrategyId strategy_id() const override;
  void reset(
      const policy::ParentOrderDefinition& parent,
      const policy::PolicyEnvironment& environment
  ) override;
  [[nodiscard]] policy::PolicyAction on_observation(
      const policy::PolicyObservation& observation
  ) override;
  [[nodiscard]] const std::optional<MpcDecision>& last_decision() const noexcept;

 private:
  [[nodiscard]] const MpcPredictionInput& prediction_for(model::DecisionId decision_id) const;
  model::StrategyId strategy_id_;
  MlMpcParameters parameters_;
  std::vector<MpcPredictionInput> prediction_tape_;
  std::optional<policy::ParentOrderDefinition> parent_;
  std::optional<policy::PolicyEnvironment> environment_;
  std::optional<MpcDecision> last_decision_;
  std::uint64_t next_client_order_id_{1U};
};

}  // namespace robust_execution::strategies
