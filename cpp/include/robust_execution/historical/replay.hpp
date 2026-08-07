#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include "robust_execution/historical/types.hpp"
#include "robust_execution/policy/policy.hpp"
#include "robust_execution/simulation/simulation.hpp"

namespace robust_execution::historical {

struct HistoricalReplayConfig {
  simulation::SimulationKernelConfig kernel;
  policy::PolicyEnvironment environment;
  std::int64_t observation_processing_delay_ns{0};
  model::SourceChannelId historical_channel{"historical-l2"};
  std::uint64_t first_event_id{10'000U};
  std::uint64_t first_canonical_sequence{10'000U};
  bool suppress_observations_until_sequence_bridge{true};
};

struct HistoricalReplayResult {
  std::vector<policy::PolicyObservation> observations;
  ReplayIntegrity integrity;
  std::string kernel_replay_hash;
  std::string kernel_state_hash;
  std::string final_observation_hash;
  std::string canonical_summary;
};

class HistoricalReplayEngine {
 public:
  explicit HistoricalReplayEngine(HistoricalReplayConfig config);

  [[nodiscard]] HistoricalReplayResult run(
      const std::vector<ReplayConnection>& connections,
      const std::vector<ReplayCheckpoint>& checkpoints,
      policy::ExecutionState& execution_state
  ) const;

  [[nodiscard]] const HistoricalReplayConfig& config() const noexcept;

 private:
  HistoricalReplayConfig config_;
};

}  // namespace robust_execution::historical
