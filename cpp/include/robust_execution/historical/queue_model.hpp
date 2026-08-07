#pragma once

#include <string>
#include <vector>

#include "robust_execution/historical/queue_types.hpp"

namespace robust_execution::historical {

class AggregateL2QueueModel {
 public:
  AggregateL2QueueModel(QueueModelConfig config, PassiveOrderSpec order);

  [[nodiscard]] std::vector<QueueFillEstimate> on_trade(
      const model::Trade& trade,
      model::TimestampNs event_time
  );
  void on_level_quantity(model::QuantityLots quantity_after, model::TimestampNs event_time);
  void cancel(model::TimestampNs event_time);

  [[nodiscard]] QueueModelSnapshot snapshot() const noexcept;
  [[nodiscard]] const QueueModelConfig& config() const noexcept;
  [[nodiscard]] const PassiveOrderSpec& order() const noexcept;
  [[nodiscard]] std::string canonical_state() const;
  [[nodiscard]] std::string state_hash() const;

 private:
  QueueModelConfig config_;
  PassiveOrderSpec order_;
  QueueOrderStatus status_{QueueOrderStatus::Live};
  model::QuantityLots displayed_quantity_{};
  model::QuantityLots estimated_ahead_{};
  model::QuantityLots cumulative_filled_{};
  model::QuantityLots leaves_quantity_{};
  model::QuantityLots pending_trade_depletion_{};
  model::QuantityLots unexplained_reduction_{};
  model::QuantityLots cancellation_ahead_{};
  model::QuantityLots cancellation_behind_{};
  model::QuantityLots trade_quantity_at_price_{};
  std::uint64_t level_update_count_{0U};
  std::uint64_t relevant_trade_count_{0U};
  std::uint64_t trade_through_count_{0U};
  model::TimestampNs last_event_time_{};

  void require_event_time(model::TimestampNs event_time) const;
  [[nodiscard]] QueueFillEstimate apply_fill(
      model::QuantityLots quantity,
      QueueFillReason reason,
      model::TimestampNs event_time
  );
};

[[nodiscard]] QueueValidationReport run_queue_model_validation();

}  // namespace robust_execution::historical
