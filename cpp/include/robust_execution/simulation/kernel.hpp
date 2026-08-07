#pragma once

#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include "robust_execution/exchange/matching_engine.hpp"
#include "robust_execution/model/model.hpp"
#include "robust_execution/simulation/latency.hpp"
#include "robust_execution/simulation/scheduler.hpp"

namespace robust_execution::simulation {

struct SimulationKernelConfig {
  exchange::MatchingEngineConfig exchange;
  model::RunId run_id{"simulation-run"};
  std::uint64_t random_seed{0U};
  LatencyModelConfig latency{};
  model::SourceChannelId strategy_order_channel{"strategy-orders"};
  model::SourceChannelId exchange_order_channel{"exchange-orders"};
  model::SourceChannelId exchange_fill_channel{"exchange-fills"};
  model::SourceChannelId exchange_trade_channel{"exchange-trades"};
  model::SourceChannelId system_channel{"system"};
  std::uint64_t first_generated_event_id{1U};
  std::uint64_t first_generated_sequence{1U};
};

struct ScheduledAction {
  model::EventId request_event_id{};
  model::ActionTiming timing{};
};

enum class KernelTraceAction : std::uint8_t {
  Scheduled,
  Dispatched,
  EngineFailure,
};

[[nodiscard]] constexpr std::string_view to_string(KernelTraceAction action) noexcept {
  switch (action) {
    case KernelTraceAction::Scheduled:
      return "scheduled";
    case KernelTraceAction::Dispatched:
      return "dispatched";
    case KernelTraceAction::EngineFailure:
      return "engine_failure";
  }
  return "unknown";
}

struct KernelTraceRecord {
  std::uint64_t append_index{0U};
  KernelTraceAction action{KernelTraceAction::Scheduled};
  std::uint64_t task_id{0U};
  model::TimestampNs time{};
  KernelStage stage{KernelStage::System};
  KernelTaskKind task_kind{KernelTaskKind::ObserverDelivery};
  model::EventId event_id{};
  std::string detail;
  std::string previous_sha256;
  std::string record_sha256;
};

struct KernelFailureRecord {
  model::EventId request_event_id{};
  model::TimestampNs process_time{};
  exchange::EngineFailure failure{};
};

class SimulationKernel {
 public:
  explicit SimulationKernel(SimulationKernelConfig config);
  ~SimulationKernel();

  SimulationKernel(const SimulationKernel&) = delete;
  SimulationKernel& operator=(const SimulationKernel&) = delete;
  SimulationKernel(SimulationKernel&&) noexcept;
  SimulationKernel& operator=(SimulationKernel&&) noexcept;

  [[nodiscard]] model::EventId schedule_market_event(
      model::Event event,
      std::uint64_t logical_index
  );
  [[nodiscard]] model::EventId schedule_market_event_with_timing(
      model::Event event,
      model::TimestampNs receive_time,
      model::TimestampNs available_time
  );
  [[nodiscard]] ScheduledAction schedule_submit(
      model::OrderSubmit command,
      model::TimestampNs decision_start,
      std::uint64_t logical_index
  );
  [[nodiscard]] ScheduledAction schedule_cancel(
      model::CancelRequest command,
      model::TimestampNs decision_start,
      std::uint64_t logical_index
  );
  [[nodiscard]] ScheduledAction schedule_replace(
      model::ReplaceRequest command,
      model::TimestampNs decision_start,
      std::uint64_t logical_index
  );
  [[nodiscard]] model::EventId schedule_timer(model::Timer timer, model::TimestampNs time);
  [[nodiscard]] model::EventId schedule_terminal_completion(
      model::TerminalCompletion completion,
      model::TimestampNs time
  );

  void run();
  void run_until(model::TimestampNs inclusive_time);

  [[nodiscard]] bool empty() const noexcept;
  [[nodiscard]] std::size_t pending_task_count() const noexcept;
  [[nodiscard]] std::optional<model::TimestampNs> current_time() const noexcept;
  [[nodiscard]] const std::vector<model::Event>& delivered_events() const noexcept;
  [[nodiscard]] const std::vector<model::Event>& exchange_received_events() const noexcept;
  [[nodiscard]] const std::vector<KernelFailureRecord>& failures() const noexcept;
  [[nodiscard]] const std::vector<KernelTraceRecord>& trace() const noexcept;
  [[nodiscard]] std::string canonical_trace() const;
  [[nodiscard]] std::string replay_hash() const;
  [[nodiscard]] std::string state_hash() const;

  [[nodiscard]] const exchange::MatchingEngine& matching_engine() const noexcept;
  [[nodiscard]] const SimulationKernelConfig& config() const noexcept;

 private:
  class Impl;
  Impl* impl_;
};

}  // namespace robust_execution::simulation
