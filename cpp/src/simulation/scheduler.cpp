#include "robust_execution/simulation/scheduler.hpp"

#include <limits>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace robust_execution::simulation {

bool scheduled_task_less(
    const ScheduledTask& lhs,
    const ScheduledTask& rhs
) noexcept {
  if (lhs.scheduled_time.domain() != rhs.scheduled_time.domain()) {
    return static_cast<std::uint8_t>(lhs.scheduled_time.domain()) <
           static_cast<std::uint8_t>(rhs.scheduled_time.domain());
  }
  if (lhs.scheduled_time.value() != rhs.scheduled_time.value()) {
    return lhs.scheduled_time.value() < rhs.scheduled_time.value();
  }
  if (lhs.stage != rhs.stage) {
    return static_cast<std::uint8_t>(lhs.stage) < static_cast<std::uint8_t>(rhs.stage);
  }
  if (lhs.canonical_sequence != rhs.canonical_sequence) {
    return lhs.canonical_sequence < rhs.canonical_sequence;
  }
  return lhs.task_id < rhs.task_id;
}

std::uint64_t DeterministicScheduler::schedule(
    model::TimestampNs time,
    KernelStage stage,
    std::uint64_t canonical_sequence,
    KernelTask task
) {
  if (canonical_sequence == 0U) {
    throw std::invalid_argument("scheduler canonical_sequence must be non-zero");
  }
  if (next_task_id_ == 0U) {
    throw std::overflow_error("scheduler task identifier sequence is exhausted");
  }
  if (!clock_domain_.has_value()) {
    clock_domain_ = time.domain();
  } else if (*clock_domain_ != time.domain()) {
    throw std::invalid_argument("scheduler cannot mix clock domains");
  }
  if (current_time_.has_value() && time.value() < current_time_->value()) {
    throw std::invalid_argument("scheduler cannot insert an event in the processed past");
  }
  const auto task_id = next_task_id_;
  if (next_task_id_ == std::numeric_limits<std::uint64_t>::max()) {
    next_task_id_ = 0U;
  } else {
    ++next_task_id_;
  }
  queue_.push(ScheduledTask{task_id, time, stage, canonical_sequence, std::move(task)});
  return task_id;
}

const ScheduledTask& DeterministicScheduler::peek_next() const {
  if (queue_.empty()) {
    throw std::out_of_range("cannot peek at an empty deterministic scheduler");
  }
  return queue_.top();
}

ScheduledTask DeterministicScheduler::pop_next() {
  if (queue_.empty()) {
    throw std::out_of_range("cannot pop from an empty deterministic scheduler");
  }
  auto next = queue_.top();
  queue_.pop();
  current_time_ = next.scheduled_time;
  return next;
}

std::string DeterministicScheduler::canonical_queue() const {
  auto copy = queue_;
  std::ostringstream output;
  while (!copy.empty()) {
    const auto& item = copy.top();
    output << item.scheduled_time.value() << '|' << static_cast<unsigned>(item.stage) << '|'
           << item.canonical_sequence << '|' << item.task_id << '|'
           << static_cast<unsigned>(item.task.kind) << '|'
           << item.task.event.header.event_id.value() << '\n';
    copy.pop();
  }
  return output.str();
}

}  // namespace robust_execution::simulation
