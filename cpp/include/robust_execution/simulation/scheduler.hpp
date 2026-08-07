#pragma once

#include <cstddef>
#include <cstdint>
#include <optional>
#include <queue>
#include <string>
#include <vector>

#include "robust_execution/model/events.hpp"
#include "robust_execution/model/time.hpp"

namespace robust_execution::simulation {

enum class KernelStage : std::uint8_t {
  Source = 0U,
  ExchangeReceive = 10U,
  ExchangeProcess = 20U,
  ExchangeEmit = 30U,
  ObserverAvailable = 40U,
  System = 50U,
};

[[nodiscard]] constexpr const char* to_string(KernelStage stage) noexcept {
  switch (stage) {
    case KernelStage::Source:
      return "source";
    case KernelStage::ExchangeReceive:
      return "exchange_receive";
    case KernelStage::ExchangeProcess:
      return "exchange_process";
    case KernelStage::ExchangeEmit:
      return "exchange_emit";
    case KernelStage::ObserverAvailable:
      return "observer_available";
    case KernelStage::System:
      return "system";
  }
  return "unknown";
}

enum class KernelTaskKind : std::uint8_t {
  ObserverDelivery,
  ExchangeReceive,
  ExchangeProcess,
};

[[nodiscard]] constexpr const char* to_string(KernelTaskKind kind) noexcept {
  switch (kind) {
    case KernelTaskKind::ObserverDelivery:
      return "observer_delivery";
    case KernelTaskKind::ExchangeReceive:
      return "exchange_receive";
    case KernelTaskKind::ExchangeProcess:
      return "exchange_process";
  }
  return "unknown";
}

struct KernelTask {
  KernelTaskKind kind{KernelTaskKind::ObserverDelivery};
  model::Event event{};
  std::optional<model::ActionTiming> action_timing;
};

struct ScheduledTask {
  std::uint64_t task_id{0U};
  model::TimestampNs scheduled_time{};
  KernelStage stage{KernelStage::System};
  std::uint64_t canonical_sequence{0U};
  KernelTask task{};
};

[[nodiscard]] bool scheduled_task_less(
    const ScheduledTask& lhs,
    const ScheduledTask& rhs
) noexcept;

class DeterministicScheduler {
 public:
  [[nodiscard]] std::uint64_t schedule(
      model::TimestampNs time,
      KernelStage stage,
      std::uint64_t canonical_sequence,
      KernelTask task
  );
  [[nodiscard]] ScheduledTask pop_next();
  [[nodiscard]] const ScheduledTask& peek_next() const;

  [[nodiscard]] bool empty() const noexcept { return queue_.empty(); }
  [[nodiscard]] std::size_t size() const noexcept { return queue_.size(); }
  [[nodiscard]] std::optional<model::TimestampNs> current_time() const noexcept {
    return current_time_;
  }
  [[nodiscard]] std::string canonical_queue() const;

 private:
  struct LaterFirst {
    [[nodiscard]] bool operator()(
        const ScheduledTask& lhs,
        const ScheduledTask& rhs
    ) const noexcept {
      return scheduled_task_less(rhs, lhs);
    }
  };

  std::priority_queue<ScheduledTask, std::vector<ScheduledTask>, LaterFirst> queue_;
  std::optional<model::ClockDomain> clock_domain_;
  std::optional<model::TimestampNs> current_time_;
  std::uint64_t next_task_id_{1U};
};

}  // namespace robust_execution::simulation
