#pragma once

#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include "robust_execution/model/model.hpp"

namespace robust_execution::exchange {

namespace model = robust_execution::model;

enum class EngineFailureCode : std::uint8_t {
  InvalidCommand,
  DuplicateClientOrderId,
  UnknownOrder,
  OrderIdentifierMismatch,
  AlreadyTerminal,
  PostOnlyWouldCross,
  InsufficientLiquidity,
  UnsupportedCombination,
  QuantityBelowMinimum,
  QuantityAboveMaximum,
  MissingLimitPrice,
  UnexpectedLimitPrice,
  InternalSequenceExhausted,
};

[[nodiscard]] constexpr std::string_view to_string(EngineFailureCode code) noexcept {
  switch (code) {
    case EngineFailureCode::InvalidCommand:
      return "invalid_command";
    case EngineFailureCode::DuplicateClientOrderId:
      return "duplicate_client_order_id";
    case EngineFailureCode::UnknownOrder:
      return "unknown_order";
    case EngineFailureCode::OrderIdentifierMismatch:
      return "order_identifier_mismatch";
    case EngineFailureCode::AlreadyTerminal:
      return "already_terminal";
    case EngineFailureCode::PostOnlyWouldCross:
      return "post_only_would_cross";
    case EngineFailureCode::InsufficientLiquidity:
      return "insufficient_liquidity";
    case EngineFailureCode::UnsupportedCombination:
      return "unsupported_combination";
    case EngineFailureCode::QuantityBelowMinimum:
      return "quantity_below_minimum";
    case EngineFailureCode::QuantityAboveMaximum:
      return "quantity_above_maximum";
    case EngineFailureCode::MissingLimitPrice:
      return "missing_limit_price";
    case EngineFailureCode::UnexpectedLimitPrice:
      return "unexpected_limit_price";
    case EngineFailureCode::InternalSequenceExhausted:
      return "internal_sequence_exhausted";
  }
  return "unknown";
}

struct EngineFailure {
  EngineFailureCode code{EngineFailureCode::InvalidCommand};
  model::RejectReason event_model_reason{model::RejectReason::InternalError};
  model::ClientOrderId client_order_id{};
  std::optional<model::ExchangeOrderId> exchange_order_id;
  std::optional<model::OrderState> current_state;
  std::string detail;

  [[nodiscard]] friend bool operator==(const EngineFailure&, const EngineFailure&) = default;
};

struct MatchingEngineConfig {
  model::InstrumentDefinition instrument;
  bool allow_market_orders{true};
  bool allow_immediate_or_cancel{true};
  bool allow_fill_or_kill{true};
  bool allow_post_only{true};
  std::size_t expected_order_count{0U};
};

struct OrderView {
  model::ParentOrderId parent_order_id{};
  model::ClientOrderId client_order_id{};
  model::ExchangeOrderId exchange_order_id{};
  model::DecisionId decision_id{};
  model::Side side{model::Side::Buy};
  model::OrderType order_type{model::OrderType::Limit};
  model::TimeInForce time_in_force{model::TimeInForce::GoodTilCancelled};
  model::QuantityLots original_quantity{};
  model::QuantityLots cumulative_filled{};
  model::QuantityLots leaves_quantity{};
  std::optional<model::PriceTicks> limit_price;
  bool post_only{false};
  model::OrderState state{model::OrderState::PendingNew};
  std::uint64_t priority_sequence{0U};

  [[nodiscard]] friend bool operator==(const OrderView&, const OrderView&) = default;
};

struct PriceLevelView {
  model::PriceTicks price{};
  model::QuantityLots displayed_quantity{};
  std::uint32_t order_count{0U};

  [[nodiscard]] friend bool operator==(const PriceLevelView&, const PriceLevelView&) = default;
};

struct BookView {
  std::vector<PriceLevelView> bids;
  std::vector<PriceLevelView> asks;

  [[nodiscard]] friend bool operator==(const BookView&, const BookView&) = default;
};

struct MatchExecution {
  std::uint64_t match_sequence{0U};
  model::Trade trade;
  model::Fill maker_fill;
  model::Fill taker_fill;

};

struct SubmitResult {
  std::optional<model::OrderAcknowledged> acknowledgement;
  std::optional<model::OrderRejected> rejection;
  std::optional<EngineFailure> failure;
  std::vector<MatchExecution> matches;
  std::optional<model::CancelAcknowledged> automatic_cancellation;
  std::optional<OrderView> final_order;

  [[nodiscard]] bool accepted() const noexcept { return acknowledgement.has_value(); }
};

struct CancelResult {
  std::optional<model::CancelAcknowledged> acknowledgement;
  std::optional<EngineFailure> failure;

  [[nodiscard]] bool accepted() const noexcept { return acknowledgement.has_value(); }
};

struct ReplaceResult {
  std::optional<model::ReplaceAcknowledged> acknowledgement;
  std::optional<EngineFailure> failure;
  std::vector<MatchExecution> matches;
  std::optional<OrderView> replacement_order;

  [[nodiscard]] bool accepted() const noexcept { return acknowledgement.has_value(); }
};

struct InvariantViolation {
  std::string code;
  std::string detail;

  [[nodiscard]] friend bool operator==(const InvariantViolation&, const InvariantViolation&) =
      default;
};

class MatchingEngine {
 public:
  explicit MatchingEngine(MatchingEngineConfig config);
  ~MatchingEngine();

  MatchingEngine(const MatchingEngine&) = delete;
  MatchingEngine& operator=(const MatchingEngine&) = delete;
  MatchingEngine(MatchingEngine&&) noexcept;
  MatchingEngine& operator=(MatchingEngine&&) noexcept;

  [[nodiscard]] SubmitResult submit(const model::OrderSubmit& command);
  [[nodiscard]] CancelResult cancel(const model::CancelRequest& command);
  [[nodiscard]] ReplaceResult replace(const model::ReplaceRequest& command);

  [[nodiscard]] std::optional<OrderView> order(model::ClientOrderId client_order_id) const;
  [[nodiscard]] std::optional<model::PriceTicks> best_bid() const noexcept;
  [[nodiscard]] std::optional<model::PriceTicks> best_ask() const noexcept;
  [[nodiscard]] model::QuantityLots quantity_at(model::Side side, model::PriceTicks price) const;
  [[nodiscard]] std::size_t active_order_count() const noexcept;
  [[nodiscard]] BookView book(std::size_t maximum_levels_per_side = 0U) const;
  [[nodiscard]] bool would_cross(
      model::Side side,
      std::optional<model::PriceTicks> limit_price
  ) const noexcept;
  [[nodiscard]] bool can_fully_execute(
      model::Side side,
      model::QuantityLots quantity,
      std::optional<model::PriceTicks> limit_price
  ) const noexcept;
  [[nodiscard]] std::vector<InvariantViolation> validate_invariants() const;
  [[nodiscard]] std::string canonical_state() const;

  [[nodiscard]] const MatchingEngineConfig& config() const noexcept;

 private:
  class Impl;
  Impl* impl_;
};

}  // namespace robust_execution::exchange
