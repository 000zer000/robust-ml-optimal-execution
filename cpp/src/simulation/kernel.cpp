#include "kernel_internal.hpp"

#include "robust_execution/model/validation.hpp"
#include "robust_execution/simulation/canonical_event.hpp"
#include "robust_execution/util/sha256.hpp"

#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>

namespace robust_execution::simulation {
namespace {

[[nodiscard]] bool same_instrument(
    const model::Event& event,
    const SimulationKernelConfig& config
) {
  return event.header.run_id == config.run_id &&
         event.header.venue == config.exchange.instrument.venue &&
         event.header.instrument == config.exchange.instrument.instrument;
}

[[nodiscard]] std::string trace_material(
    std::uint64_t append_index,
    KernelTraceAction action,
    const ScheduledTask& scheduled,
    const std::string& detail,
    const std::string& previous_hash
) {
  std::ostringstream output;
  output << append_index << '|' << to_string(action) << '|' << scheduled.task_id << '|'
         << static_cast<unsigned>(scheduled.scheduled_time.domain()) << '|'
         << scheduled.scheduled_time.value() << '|' << to_string(scheduled.stage) << '|'
         << scheduled.canonical_sequence << '|' << to_string(scheduled.task.kind) << '|'
         << scheduled.task.event.header.event_id.value() << '|' << detail.size() << ':' << detail
         << '|' << canonical_event(scheduled.task.event) << '|' << previous_hash;
  return output.str();
}

void ensure_clock(model::TimestampNs lhs, model::TimestampNs rhs, const char* context) {
  if (lhs.domain() != rhs.domain()) {
    throw std::invalid_argument(std::string{context} + " uses mixed clock domains");
  }
}

}  // namespace

SimulationKernel::Impl::Impl(SimulationKernelConfig config)
    : config_(std::move(config)),
      latency_(config_.random_seed, config_.latency),
      matching_engine_(config_.exchange),
      next_event_id_(config_.first_generated_event_id),
      next_sequence_(config_.first_generated_sequence) {
  if (!config_.run_id.valid() || !config_.strategy_order_channel.valid() ||
      !config_.exchange_order_channel.valid() || !config_.exchange_fill_channel.valid() ||
      !config_.exchange_trade_channel.valid() || !config_.system_channel.valid()) {
    throw std::invalid_argument("simulation-kernel identifiers and channels must be non-empty");
  }
  if (next_event_id_ == 0U || next_sequence_ == 0U) {
    throw std::invalid_argument("generated event and sequence counters must start above zero");
  }
}

model::EventId SimulationKernel::Impl::allocate_event_id() {
  if (next_event_id_ == 0U) {
    throw std::overflow_error("simulation event identifier sequence is exhausted");
  }
  while (event_ids_.contains(next_event_id_)) {
    if (next_event_id_ == std::numeric_limits<std::uint64_t>::max()) {
      throw std::overflow_error("simulation event identifier sequence is exhausted");
    }
    ++next_event_id_;
  }
  const auto value = next_event_id_;
  event_ids_.insert(value);
  if (next_event_id_ == std::numeric_limits<std::uint64_t>::max()) {
    next_event_id_ = 0U;
  } else {
    ++next_event_id_;
  }
  return model::EventId{value};
}

std::uint64_t SimulationKernel::Impl::allocate_sequence() {
  if (next_sequence_ == 0U) {
    throw std::overflow_error("simulation canonical-sequence allocator is exhausted");
  }
  const auto value = next_sequence_;
  if (next_sequence_ == std::numeric_limits<std::uint64_t>::max()) {
    next_sequence_ = 0U;
  } else {
    ++next_sequence_;
  }
  return value;
}

void SimulationKernel::Impl::register_existing_event(const model::Event& event) {
  const auto event_id = event.header.event_id.value();
  if (!event_ids_.insert(event_id).second) {
    throw std::invalid_argument("duplicate event_id scheduled in simulation kernel");
  }
  if (event_id >= next_event_id_) {
    if (event_id == std::numeric_limits<std::uint64_t>::max()) {
      next_event_id_ = 0U;
    } else {
      next_event_id_ = event_id + 1U;
    }
  }
  if (event.header.ordering.canonical_sequence >= next_sequence_) {
    if (event.header.ordering.canonical_sequence ==
        std::numeric_limits<std::uint64_t>::max()) {
      next_sequence_ = 0U;
    } else {
      next_sequence_ = event.header.ordering.canonical_sequence + 1U;
    }
  }
}

model::EventHeader SimulationKernel::Impl::generated_header(
    model::TimestampNs event_time,
    std::optional<model::TimestampNs> receive_time,
    std::optional<model::TimestampNs> available_time,
    model::EventOrigin origin,
    const model::SourceChannelId& channel
) {
  const auto sequence = allocate_sequence();
  return model::EventHeader{
      model::kEventSchemaVersion,
      allocate_event_id(),
      config_.run_id,
      config_.exchange.instrument.venue,
      config_.exchange.instrument.instrument,
      channel,
      origin,
      event_time,
      receive_time,
      available_time,
      model::EventOrdering{false, 0U, 0U, sequence, sequence},
      std::nullopt,
  };
}

void SimulationKernel::Impl::record_trace(
    KernelTraceAction action,
    const ScheduledTask& scheduled,
    std::string detail
) {
  const auto append_index = static_cast<std::uint64_t>(trace_.size());
  const auto material = trace_material(
      append_index,
      action,
      scheduled,
      detail,
      previous_trace_hash_
  );
  const auto record_hash = util::sha256_hex(material);
  trace_.push_back(KernelTraceRecord{
      append_index,
      action,
      scheduled.task_id,
      scheduled.scheduled_time,
      scheduled.stage,
      scheduled.task.kind,
      scheduled.task.event.header.event_id,
      std::move(detail),
      previous_trace_hash_,
      record_hash,
  });
  previous_trace_hash_ = record_hash;
}

model::EventId SimulationKernel::Impl::schedule_market_event(
    model::Event event,
    std::uint64_t logical_index
) {
  if (!same_instrument(event, config_)) {
    throw std::invalid_argument("market event run, venue, or instrument does not match kernel");
  }
  if (event.header.origin != model::EventOrigin::HistoricalFeed &&
      event.header.origin != model::EventOrigin::SyntheticExchange) {
    throw std::invalid_argument("schedule_market_event requires historical or synthetic origin");
  }
  const auto timing = latency_.observation_timing(event.header.event_time, logical_index);
  event.header.receive_time = timing.receive_time;
  event.header.available_time = timing.available_time;
  const auto issues = model::validate_event(event);
  if (model::has_errors(issues)) {
    throw std::invalid_argument("market event is invalid after latency stamping");
  }
  register_existing_event(event);
  const auto event_id = event.header.event_id;
  const auto sequence = event.header.ordering.canonical_sequence;
  KernelTask task{KernelTaskKind::ObserverDelivery, std::move(event), std::nullopt};
  const auto snapshot = task;
  const auto task_id = scheduler_.schedule(
      timing.available_time,
      KernelStage::ObserverAvailable,
      sequence,
      std::move(task)
  );
  record_trace(
      KernelTraceAction::Scheduled,
      ScheduledTask{task_id, timing.available_time, KernelStage::ObserverAvailable, sequence, snapshot},
      "market_event"
  );
  return event_id;
}

model::EventId SimulationKernel::Impl::schedule_market_event_with_timing(
    model::Event event,
    model::TimestampNs receive_time,
    model::TimestampNs available_time
) {
  if (!same_instrument(event, config_)) {
    throw std::invalid_argument("market event run, venue, or instrument does not match kernel");
  }
  if (event.header.origin != model::EventOrigin::HistoricalFeed &&
      event.header.origin != model::EventOrigin::SyntheticExchange) {
    throw std::invalid_argument(
        "schedule_market_event_with_timing requires historical or synthetic origin"
    );
  }
  ensure_clock(event.header.event_time, receive_time, "observed market timing");
  ensure_clock(receive_time, available_time, "observed market timing");
  if (event.header.event_time.value() > receive_time.value() ||
      receive_time.value() > available_time.value()) {
    throw std::invalid_argument(
        "observed market timing must satisfy event_time <= receive_time <= available_time"
    );
  }
  event.header.receive_time = receive_time;
  event.header.available_time = available_time;
  const auto issues = model::validate_event(event);
  if (model::has_errors(issues)) {
    throw std::invalid_argument("market event is invalid with explicit historical timing");
  }
  register_existing_event(event);
  const auto event_id = event.header.event_id;
  const auto sequence = event.header.ordering.canonical_sequence;
  KernelTask task{KernelTaskKind::ObserverDelivery, std::move(event), std::nullopt};
  const auto snapshot = task;
  const auto task_id = scheduler_.schedule(
      available_time, KernelStage::ObserverAvailable, sequence, std::move(task)
  );
  record_trace(
      KernelTraceAction::Scheduled,
      ScheduledTask{task_id, available_time, KernelStage::ObserverAvailable, sequence, snapshot},
      "market_event_explicit_timing"
  );
  return event_id;
}

ScheduledAction SimulationKernel::Impl::schedule_submit(
    model::OrderSubmit command,
    model::TimestampNs decision_start,
    std::uint64_t logical_index
) {
  const auto timing = latency_.action_timing(decision_start, logical_index);
  command.decision_time = timing.decision_end;
  command.outbound_send_time = timing.outbound_send;
  command.exchange_receive_time = timing.exchange_receive;
  auto event = model::Event{
      generated_header(
          timing.exchange_receive,
          timing.exchange_receive,
          timing.exchange_receive,
          model::EventOrigin::Strategy,
          config_.strategy_order_channel
      ),
      command,
  };
  const auto issues = model::validate_event(event);
  if (model::has_errors(issues)) {
    throw std::invalid_argument("order submission is invalid after latency stamping");
  }
  const auto event_id = event.header.event_id;
  const auto sequence = event.header.ordering.canonical_sequence;
  KernelTask task{KernelTaskKind::ExchangeReceive, std::move(event), timing};
  const auto snapshot = task;
  const auto task_id = scheduler_.schedule(
      timing.exchange_receive,
      KernelStage::ExchangeReceive,
      sequence,
      std::move(task)
  );
  record_trace(
      KernelTraceAction::Scheduled,
      ScheduledTask{task_id, timing.exchange_receive, KernelStage::ExchangeReceive, sequence, snapshot},
      "order_submit"
  );
  return ScheduledAction{event_id, timing};
}

ScheduledAction SimulationKernel::Impl::schedule_cancel(
    model::CancelRequest command,
    model::TimestampNs decision_start,
    std::uint64_t logical_index
) {
  const auto timing = latency_.action_timing(decision_start, logical_index);
  command.decision_time = timing.decision_end;
  command.outbound_send_time = timing.outbound_send;
  command.exchange_receive_time = timing.exchange_receive;
  auto event = model::Event{
      generated_header(
          timing.exchange_receive,
          timing.exchange_receive,
          timing.exchange_receive,
          model::EventOrigin::Strategy,
          config_.strategy_order_channel
      ),
      command,
  };
  const auto issues = model::validate_event(event);
  if (model::has_errors(issues)) {
    throw std::invalid_argument("cancel request is invalid after latency stamping");
  }
  const auto event_id = event.header.event_id;
  const auto sequence = event.header.ordering.canonical_sequence;
  KernelTask task{KernelTaskKind::ExchangeReceive, std::move(event), timing};
  const auto snapshot = task;
  const auto task_id = scheduler_.schedule(
      timing.exchange_receive,
      KernelStage::ExchangeReceive,
      sequence,
      std::move(task)
  );
  record_trace(
      KernelTraceAction::Scheduled,
      ScheduledTask{task_id, timing.exchange_receive, KernelStage::ExchangeReceive, sequence, snapshot},
      "cancel_request"
  );
  return ScheduledAction{event_id, timing};
}

ScheduledAction SimulationKernel::Impl::schedule_replace(
    model::ReplaceRequest command,
    model::TimestampNs decision_start,
    std::uint64_t logical_index
) {
  const auto timing = latency_.action_timing(decision_start, logical_index);
  command.decision_time = timing.decision_end;
  command.outbound_send_time = timing.outbound_send;
  command.exchange_receive_time = timing.exchange_receive;
  auto event = model::Event{
      generated_header(
          timing.exchange_receive,
          timing.exchange_receive,
          timing.exchange_receive,
          model::EventOrigin::Strategy,
          config_.strategy_order_channel
      ),
      command,
  };
  const auto issues = model::validate_event(event);
  if (model::has_errors(issues)) {
    throw std::invalid_argument("replace request is invalid after latency stamping");
  }
  const auto event_id = event.header.event_id;
  const auto sequence = event.header.ordering.canonical_sequence;
  KernelTask task{KernelTaskKind::ExchangeReceive, std::move(event), timing};
  const auto snapshot = task;
  const auto task_id = scheduler_.schedule(
      timing.exchange_receive,
      KernelStage::ExchangeReceive,
      sequence,
      std::move(task)
  );
  record_trace(
      KernelTraceAction::Scheduled,
      ScheduledTask{task_id, timing.exchange_receive, KernelStage::ExchangeReceive, sequence, snapshot},
      "replace_request"
  );
  return ScheduledAction{event_id, timing};
}

model::EventId SimulationKernel::Impl::schedule_timer(model::Timer timer, model::TimestampNs time) {
  auto event = model::Event{
      generated_header(
          time,
          time,
          time,
          model::EventOrigin::System,
          config_.system_channel
      ),
      std::move(timer),
  };
  const auto event_id = event.header.event_id;
  const auto sequence = event.header.ordering.canonical_sequence;
  KernelTask task{KernelTaskKind::ObserverDelivery, std::move(event), std::nullopt};
  const auto snapshot = task;
  const auto task_id = scheduler_.schedule(time, KernelStage::System, sequence, std::move(task));
  record_trace(
      KernelTraceAction::Scheduled,
      ScheduledTask{task_id, time, KernelStage::System, sequence, snapshot},
      "timer"
  );
  return event_id;
}

model::EventId SimulationKernel::Impl::schedule_terminal_completion(
    model::TerminalCompletion completion,
    model::TimestampNs time
) {
  auto event = model::Event{
      generated_header(
          time,
          time,
          time,
          model::EventOrigin::System,
          config_.system_channel
      ),
      std::move(completion),
  };
  const auto issues = model::validate_event(event);
  if (model::has_errors(issues)) {
    throw std::invalid_argument("terminal completion is invalid");
  }
  const auto event_id = event.header.event_id;
  const auto sequence = event.header.ordering.canonical_sequence;
  KernelTask task{KernelTaskKind::ObserverDelivery, std::move(event), std::nullopt};
  const auto snapshot = task;
  const auto task_id = scheduler_.schedule(time, KernelStage::System, sequence, std::move(task));
  record_trace(
      KernelTraceAction::Scheduled,
      ScheduledTask{task_id, time, KernelStage::System, sequence, snapshot},
      "terminal_completion"
  );
  return event_id;
}

void SimulationKernel::Impl::run() {
  while (!scheduler_.empty()) {
    dispatch(scheduler_.pop_next());
  }
}

void SimulationKernel::Impl::run_until(model::TimestampNs inclusive_time) {
  while (!scheduler_.empty()) {
    ensure_clock(scheduler_.peek_next().scheduled_time, inclusive_time, "run_until");
    if (scheduler_.peek_next().scheduled_time.value() > inclusive_time.value()) {
      break;
    }
    dispatch(scheduler_.pop_next());
  }
}

void SimulationKernel::Impl::dispatch(const ScheduledTask& scheduled) {
  record_trace(KernelTraceAction::Dispatched, scheduled, "");
  switch (scheduled.task.kind) {
    case KernelTaskKind::ObserverDelivery:
      delivered_events_.push_back(scheduled.task.event);
      return;
    case KernelTaskKind::ExchangeReceive: {
      if (!scheduled.task.action_timing.has_value()) {
        throw std::logic_error("exchange-receive task lacks action timing");
      }
      exchange_received_events_.push_back(scheduled.task.event);
      auto process_task = scheduled.task;
      process_task.kind = KernelTaskKind::ExchangeProcess;
      const auto process_time = scheduled.task.action_timing->exchange_process;
      const auto task_id = scheduler_.schedule(
          process_time,
          KernelStage::ExchangeProcess,
          scheduled.canonical_sequence,
          process_task
      );
      record_trace(
          KernelTraceAction::Scheduled,
          ScheduledTask{
              task_id,
              process_time,
              KernelStage::ExchangeProcess,
              scheduled.canonical_sequence,
              process_task,
          },
          "exchange_process"
      );
      return;
    }
    case KernelTaskKind::ExchangeProcess:
      process_exchange(scheduled);
      return;
  }
}

std::string SimulationKernel::Impl::canonical_trace() const {
  std::ostringstream output;
  for (const auto& record : trace_) {
    output << record.append_index << '|' << to_string(record.action) << '|' << record.task_id << '|'
           << record.time.value() << '|' << to_string(record.stage) << '|'
           << to_string(record.task_kind) << '|' << record.event_id.value() << '|'
           << record.previous_sha256 << '|' << record.record_sha256 << '|' << record.detail.size()
           << ':' << record.detail << '\n';
  }
  return output.str();
}

std::string SimulationKernel::Impl::replay_hash() const {
  return trace_.empty() ? util::sha256_hex("") : trace_.back().record_sha256;
}

std::string SimulationKernel::Impl::state_hash() const {
  std::ostringstream material;
  material << replay_hash() << '|' << scheduler_.canonical_queue() << '|'
           << matching_engine_.canonical_state() << '|';
  for (const auto& event : delivered_events_) {
    material << canonical_event(event) << '\n';
  }
  material << "|exchange|";
  for (const auto& event : exchange_received_events_) {
    material << canonical_event(event) << '\n';
  }
  material << "|failures|";
  for (const auto& failure : failures_) {
    material << failure.request_event_id.value() << '|' << failure.process_time.value() << '|'
             << static_cast<unsigned>(failure.failure.code) << '|' << failure.failure.detail << '\n';
  }
  return util::sha256_hex(material.str());
}

SimulationKernel::SimulationKernel(SimulationKernelConfig config)
    : impl_(new Impl(std::move(config))) {}

SimulationKernel::~SimulationKernel() { delete impl_; }

SimulationKernel::SimulationKernel(SimulationKernel&& other) noexcept : impl_(other.impl_) {
  other.impl_ = nullptr;
}

SimulationKernel& SimulationKernel::operator=(SimulationKernel&& other) noexcept {
  if (this != &other) {
    delete impl_;
    impl_ = other.impl_;
    other.impl_ = nullptr;
  }
  return *this;
}

model::EventId SimulationKernel::schedule_market_event(
    model::Event event,
    std::uint64_t logical_index
) {
  return impl_->schedule_market_event(std::move(event), logical_index);
}

model::EventId SimulationKernel::schedule_market_event_with_timing(
    model::Event event,
    model::TimestampNs receive_time,
    model::TimestampNs available_time
) {
  return impl_->schedule_market_event_with_timing(
      std::move(event), receive_time, available_time
  );
}

ScheduledAction SimulationKernel::schedule_submit(
    model::OrderSubmit command,
    model::TimestampNs decision_start,
    std::uint64_t logical_index
) {
  return impl_->schedule_submit(std::move(command), decision_start, logical_index);
}

ScheduledAction SimulationKernel::schedule_cancel(
    model::CancelRequest command,
    model::TimestampNs decision_start,
    std::uint64_t logical_index
) {
  return impl_->schedule_cancel(std::move(command), decision_start, logical_index);
}

ScheduledAction SimulationKernel::schedule_replace(
    model::ReplaceRequest command,
    model::TimestampNs decision_start,
    std::uint64_t logical_index
) {
  return impl_->schedule_replace(std::move(command), decision_start, logical_index);
}

model::EventId SimulationKernel::schedule_timer(model::Timer timer, model::TimestampNs time) {
  return impl_->schedule_timer(std::move(timer), time);
}

model::EventId SimulationKernel::schedule_terminal_completion(
    model::TerminalCompletion completion,
    model::TimestampNs time
) {
  return impl_->schedule_terminal_completion(std::move(completion), time);
}

void SimulationKernel::run() { impl_->run(); }

void SimulationKernel::run_until(model::TimestampNs inclusive_time) {
  impl_->run_until(inclusive_time);
}

bool SimulationKernel::empty() const noexcept { return impl_->scheduler_.empty(); }

std::size_t SimulationKernel::pending_task_count() const noexcept {
  return impl_->scheduler_.size();
}

std::optional<model::TimestampNs> SimulationKernel::current_time() const noexcept {
  return impl_->scheduler_.current_time();
}

const std::vector<model::Event>& SimulationKernel::delivered_events() const noexcept {
  return impl_->delivered_events_;
}

const std::vector<model::Event>& SimulationKernel::exchange_received_events() const noexcept {
  return impl_->exchange_received_events_;
}

const std::vector<KernelFailureRecord>& SimulationKernel::failures() const noexcept {
  return impl_->failures_;
}

const std::vector<KernelTraceRecord>& SimulationKernel::trace() const noexcept {
  return impl_->trace_;
}

std::string SimulationKernel::canonical_trace() const { return impl_->canonical_trace(); }

std::string SimulationKernel::replay_hash() const { return impl_->replay_hash(); }

std::string SimulationKernel::state_hash() const { return impl_->state_hash(); }

const exchange::MatchingEngine& SimulationKernel::matching_engine() const noexcept {
  return impl_->matching_engine_;
}

const SimulationKernelConfig& SimulationKernel::config() const noexcept {
  return impl_->config_;
}

}  // namespace robust_execution::simulation
