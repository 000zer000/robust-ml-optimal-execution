#pragma once

#include "robust_execution/simulation/kernel.hpp"

#include <cstdint>
#include <string>
#include <unordered_set>
#include <vector>

namespace robust_execution::simulation {

class SimulationKernel::Impl {
 public:
  explicit Impl(SimulationKernelConfig config);

  model::EventId schedule_market_event(model::Event event, std::uint64_t logical_index);
  model::EventId schedule_market_event_with_timing(
      model::Event event,
      model::TimestampNs receive_time,
      model::TimestampNs available_time
  );
  ScheduledAction schedule_submit(
      model::OrderSubmit command,
      model::TimestampNs decision_start,
      std::uint64_t logical_index
  );
  ScheduledAction schedule_cancel(
      model::CancelRequest command,
      model::TimestampNs decision_start,
      std::uint64_t logical_index
  );
  ScheduledAction schedule_replace(
      model::ReplaceRequest command,
      model::TimestampNs decision_start,
      std::uint64_t logical_index
  );
  model::EventId schedule_timer(model::Timer timer, model::TimestampNs time);
  model::EventId schedule_terminal_completion(
      model::TerminalCompletion completion,
      model::TimestampNs time
  );

  void run();
  void run_until(model::TimestampNs inclusive_time);

  [[nodiscard]] std::string canonical_trace() const;
  [[nodiscard]] std::string replay_hash() const;
  [[nodiscard]] std::string state_hash() const;

  [[nodiscard]] model::EventId allocate_event_id();
  [[nodiscard]] std::uint64_t allocate_sequence();
  void register_existing_event(const model::Event& event);
  [[nodiscard]] model::EventHeader generated_header(
      model::TimestampNs event_time,
      std::optional<model::TimestampNs> receive_time,
      std::optional<model::TimestampNs> available_time,
      model::EventOrigin origin,
      const model::SourceChannelId& channel
  );
  void record_trace(
      KernelTraceAction action,
      const ScheduledTask& scheduled,
      std::string detail
  );
  void dispatch(const ScheduledTask& scheduled);
  void process_exchange(const ScheduledTask& scheduled);
  [[nodiscard]] model::Event make_response_event(
      model::EventPayload payload,
      const model::ActionTiming& timing,
      const model::SourceChannelId& channel,
      bool execution_time
  );
  void emit_event(model::Event event, const model::ActionTiming& timing, std::string detail);
  void emit_submit_result(
      const ScheduledTask& scheduled,
      const exchange::SubmitResult& result,
      const model::ActionTiming& timing
  );
  void emit_cancel_result(
      const ScheduledTask& scheduled,
      const exchange::CancelResult& result,
      const model::ActionTiming& timing
  );
  void emit_replace_result(
      const ScheduledTask& scheduled,
      const exchange::ReplaceResult& result,
      const model::ActionTiming& timing
  );
  void emit_matches(
      const std::vector<exchange::MatchExecution>& matches,
      const model::ActionTiming& timing
  );
  void record_failure(
      const ScheduledTask& scheduled,
      const exchange::EngineFailure& failure
  );

  SimulationKernelConfig config_;
  LatencyModel latency_;
  exchange::MatchingEngine matching_engine_;
  DeterministicScheduler scheduler_;
  std::uint64_t next_event_id_{1U};
  std::uint64_t next_sequence_{1U};
  std::unordered_set<std::uint64_t> event_ids_;
  std::vector<model::Event> delivered_events_;
  std::vector<model::Event> exchange_received_events_;
  std::vector<KernelFailureRecord> failures_;
  std::vector<KernelTraceRecord> trace_;
  std::string previous_trace_hash_{64U, '0'};
};

}  // namespace robust_execution::simulation
