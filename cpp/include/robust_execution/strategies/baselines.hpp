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

enum class BaselineKind : std::uint8_t { ImmediateAggressive, Twap, PastVolumeInformed };
enum class ExecutionStyle : std::uint8_t { Aggressive, Passive };

struct VolumeObservation {
  model::TimestampNs event_time{};
  std::size_t bucket_index{0U};
  model::QuantityLots executed_quantity{};
};

struct VolumeProfile {
  std::vector<std::uint64_t> bucket_weights;
  model::TimestampNs training_cutoff{};
  std::string provenance_id;
};

struct BaselineConfig {
  BaselineKind kind{BaselineKind::ImmediateAggressive};
  ExecutionStyle style{ExecutionStyle::Aggressive};
  std::size_t slice_count{1U};
  std::optional<VolumeProfile> volume_profile;
};

struct ScheduleSlice {
  model::TimestampNs release_time{};
  model::QuantityLots quantity{};
};

struct BaselineSchedule {
  BaselineKind kind{BaselineKind::ImmediateAggressive};
  ExecutionStyle style{ExecutionStyle::Aggressive};
  std::vector<ScheduleSlice> slices;
  std::string provenance_id;

  [[nodiscard]] model::QuantityLots total_quantity() const;
  [[nodiscard]] std::string canonical() const;
};

[[nodiscard]] VolumeProfile build_past_volume_profile(
    std::size_t bucket_count,
    const std::vector<VolumeObservation>& observations,
    model::TimestampNs training_cutoff,
    std::string provenance_id
);

[[nodiscard]] BaselineSchedule build_baseline_schedule(
    const policy::ParentOrderDefinition& parent,
    const BaselineConfig& config
);

[[nodiscard]] std::string_view to_string(BaselineKind value) noexcept;
[[nodiscard]] std::string_view to_string(ExecutionStyle value) noexcept;

class ScheduledBaselinePolicy final : public policy::ExecutionPolicy {
 public:
  ScheduledBaselinePolicy(model::StrategyId strategy_id, BaselineConfig config);
  [[nodiscard]] model::StrategyId strategy_id() const override;
  void reset(const policy::ParentOrderDefinition& parent, const policy::PolicyEnvironment& environment) override;
  [[nodiscard]] policy::PolicyAction on_observation(const policy::PolicyObservation& observation) override;
  [[nodiscard]] const BaselineSchedule& schedule() const;

 private:
  model::StrategyId strategy_id_;
  BaselineConfig config_;
  std::optional<BaselineSchedule> schedule_;
  std::optional<policy::ParentOrderDefinition> parent_;
  std::optional<policy::PolicyEnvironment> environment_;
  std::uint64_t next_client_order_id_{1U};
};

}  // namespace robust_execution::strategies
