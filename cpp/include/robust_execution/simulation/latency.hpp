#pragma once

#include <cstdint>
#include <string>

#include "robust_execution/model/time.hpp"
#include "robust_execution/simulation/logical_rng.hpp"

namespace robust_execution::simulation {

struct LatencyRangeNs {
  std::int64_t minimum{0};
  std::int64_t maximum{0};
  std::uint64_t stream_id{0U};

  [[nodiscard]] friend constexpr auto operator<=>(const LatencyRangeNs&, const LatencyRangeNs&) =
      default;
};

struct LatencyModelConfig {
  std::string model_id{"zero-latency-v1"};
  LatencyRangeNs market_data_network{};
  LatencyRangeNs observation_processing{};
  LatencyRangeNs decision_processing{};
  LatencyRangeNs outbound_network{};
  LatencyRangeNs exchange_processing{};
  LatencyRangeNs acknowledgement_network{};
  LatencyRangeNs acknowledgement_processing{};
};

struct ObservationLatencySample {
  std::int64_t network_ns{0};
  std::int64_t processing_ns{0};
};

struct ActionLatencySample {
  std::int64_t decision_processing_ns{0};
  std::int64_t outbound_network_ns{0};
  std::int64_t exchange_processing_ns{0};
  std::int64_t acknowledgement_network_ns{0};
  std::int64_t acknowledgement_processing_ns{0};
};

class LatencyModel {
 public:
  LatencyModel(std::uint64_t seed, LatencyModelConfig config);

  [[nodiscard]] ObservationLatencySample sample_observation(
      std::uint64_t logical_index
  ) const;
  [[nodiscard]] ActionLatencySample sample_action(std::uint64_t logical_index) const;
  [[nodiscard]] model::ObservationTiming observation_timing(
      model::TimestampNs event_time,
      std::uint64_t logical_index
  ) const;
  [[nodiscard]] model::ActionTiming action_timing(
      model::TimestampNs decision_start,
      std::uint64_t logical_index
  ) const;

  [[nodiscard]] const LatencyModelConfig& config() const noexcept { return config_; }
  [[nodiscard]] std::uint64_t seed() const noexcept { return random_.seed(); }

 private:
  [[nodiscard]] std::int64_t draw(
      const LatencyRangeNs& range,
      std::uint64_t logical_index
  ) const;

  LogicalRandom random_;
  LatencyModelConfig config_;
};

[[nodiscard]] model::TimestampNs checked_add_duration(
    model::TimestampNs timestamp,
    std::int64_t duration_ns
);

}  // namespace robust_execution::simulation
