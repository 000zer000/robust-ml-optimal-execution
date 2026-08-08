#pragma once

#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

#include "robust_execution/model/model.hpp"

namespace robust_execution::historical {

enum class QueueAssumption : std::uint8_t {
  Optimistic,
  Central,
  Pessimistic,
};

enum class QueueFillReason : std::uint8_t {
  TradeAtPrice,
  TradeThrough,
};

enum class QueueOrderStatus : std::uint8_t {
  Live,
  PartiallyFilled,
  Filled,
  Cancelled,
};

[[nodiscard]] constexpr std::string_view to_string(QueueAssumption value) noexcept {
  switch (value) {
    case QueueAssumption::Optimistic:
      return "optimistic";
    case QueueAssumption::Central:
      return "central";
    case QueueAssumption::Pessimistic:
      return "pessimistic";
  }
  return "unknown";
}

[[nodiscard]] constexpr std::string_view to_string(QueueFillReason value) noexcept {
  switch (value) {
    case QueueFillReason::TradeAtPrice:
      return "trade_at_price";
    case QueueFillReason::TradeThrough:
      return "trade_through";
  }
  return "unknown";
}

[[nodiscard]] constexpr std::string_view to_string(QueueOrderStatus value) noexcept {
  switch (value) {
    case QueueOrderStatus::Live:
      return "live";
    case QueueOrderStatus::PartiallyFilled:
      return "partially_filled";
    case QueueOrderStatus::Filled:
      return "filled";
    case QueueOrderStatus::Cancelled:
      return "cancelled";
  }
  return "unknown";
}

struct QueueModelConfig {
  QueueAssumption assumption{QueueAssumption::Central};
  std::uint32_t additional_initial_ahead_bps{0U};
  bool fill_on_trade_through{true};
  std::string model_version{"aggregate-l2-queue-v1"};
};

struct PassiveOrderSpec {
  model::ClientOrderId client_order_id{};
  model::Side side{model::Side::Buy};
  model::PriceTicks price{};
  model::QuantityLots quantity{};
  model::QuantityLots displayed_quantity_at_join{};
  model::TimestampNs join_time{};
};

struct QueueFillEstimate {
  model::ClientOrderId client_order_id{};
  model::PriceTicks price{};
  model::QuantityLots quantity{};
  model::QuantityLots cumulative_filled{};
  model::QuantityLots leaves_quantity{};
  model::LiquidityRole liquidity_role{model::LiquidityRole::Maker};
  QueueFillReason reason{QueueFillReason::TradeAtPrice};
  model::TimestampNs event_time{};
};

struct QueueModelSnapshot {
  QueueAssumption assumption{QueueAssumption::Central};
  QueueOrderStatus status{QueueOrderStatus::Live};
  model::QuantityLots displayed_quantity{};
  model::QuantityLots estimated_quantity_ahead{};
  model::QuantityLots cumulative_filled{};
  model::QuantityLots leaves_quantity{};
  model::QuantityLots unexplained_reduction{};
  model::QuantityLots cancellation_allocated_ahead{};
  model::QuantityLots cancellation_allocated_behind{};
  model::QuantityLots trade_quantity_at_price{};
  std::uint64_t level_update_count{0U};
  std::uint64_t relevant_trade_count{0U};
  std::uint64_t trade_through_count{0U};
};

struct QueueScenarioResult {
  std::string scenario_id;
  model::QuantityLots exact_fifo_fill{};
  model::QuantityLots optimistic_fill{};
  model::QuantityLots central_fill{};
  model::QuantityLots pessimistic_fill{};
  bool exact_within_model_bounds{false};
  bool model_ordering_valid{false};
};

struct QueueSensitivityResult {
  std::string scenario_id;
  QueueAssumption assumption{QueueAssumption::Central};
  std::uint32_t additional_initial_ahead_bps{0U};
  model::QuantityLots estimated_fill{};
  model::QuantityLots estimated_ahead_after_events{};
};

struct QueueValidationReport {
  std::vector<QueueScenarioResult> scenarios;
  std::vector<QueueSensitivityResult> sensitivity;
  std::uint64_t exact_comparison_count{0U};
  std::uint64_t bracketed_comparison_count{0U};
  std::uint64_t monotonic_comparison_count{0U};
  bool trade_through_rule_passed{false};
  bool no_fill_from_cancellation_only_passed{false};
  bool deterministic{false};
  bool exact_fifo_reconstructed_historically{false};
  std::string canonical_json;
  std::string sha256;
};

}  // namespace robust_execution::historical
