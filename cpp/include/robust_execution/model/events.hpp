#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <variant>
#include <vector>

#include "robust_execution/model/enums.hpp"
#include "robust_execution/model/fixed_point.hpp"
#include "robust_execution/model/identifiers.hpp"
#include "robust_execution/model/time.hpp"

namespace robust_execution::model {

struct SchemaVersion {
  std::uint16_t major{1U};
  std::uint16_t minor{0U};

  [[nodiscard]] friend constexpr auto operator<=>(const SchemaVersion&, const SchemaVersion&) =
      default;
};

inline constexpr SchemaVersion kEventSchemaVersion{1U, 0U};
inline constexpr std::string_view kEventSchemaId =
    "https://robust-execution.local/schemas/event-model/event-envelope-v1.schema.json";

struct InstrumentDefinition {
  SchemaVersion schema{kEventSchemaVersion};
  VenueId venue{};
  InstrumentId instrument{};
  std::string base_asset;
  std::string quote_asset;
  RationalIncrement tick_size{};
  RationalIncrement lot_size{};
  RationalIncrement quote_atom_size{};
  QuantityLots minimum_order_quantity{};
  std::optional<QuantityLots> maximum_order_quantity;
  std::string metadata_version;
};

struct EventHeader {
  SchemaVersion schema{kEventSchemaVersion};
  EventId event_id{};
  RunId run_id{};
  VenueId venue{};
  InstrumentId instrument{};
  SourceChannelId source_channel{};
  EventOrigin origin{EventOrigin::System};
  TimestampNs event_time{};
  std::optional<TimestampNs> receive_time;
  std::optional<TimestampNs> available_time;
  EventOrdering ordering{};
  std::optional<std::string> original_timestamp;
};

struct BookLevel {
  PriceTicks price{};
  QuantityLots displayed_quantity{};
  std::optional<std::uint32_t> order_count;
};

struct BookSnapshot {
  std::vector<BookLevel> bids;
  std::vector<BookLevel> asks;
};

struct DepthUpdate {
  Side side{Side::Buy};
  PriceTicks price{};
  QuantityLots quantity_after{};
  BookUpdateAction action{BookUpdateAction::Set};
  std::optional<std::uint32_t> order_count_after;
};

struct Trade {
  TradeId trade_id{};
  std::optional<ExternalTradeId> external_trade_id;
  PriceTicks price{};
  QuantityLots quantity{};
  AggressorSide aggressor_side{AggressorSide::Unknown};
};

struct Decision {
  DecisionId decision_id{};
  StrategyId strategy_id{};
  TimestampNs observation_cutoff{};
  TimestampNs decision_start{};
  TimestampNs decision_end{};
  QuantityLots remaining_inventory{};
  std::string action_name;
  std::optional<std::string> model_artifact_id;
};

struct OrderSubmit {
  ParentOrderId parent_order_id{};
  ClientOrderId client_order_id{};
  DecisionId decision_id{};
  Side side{Side::Buy};
  OrderType order_type{OrderType::Limit};
  TimeInForce time_in_force{TimeInForce::GoodTilCancelled};
  QuantityLots quantity{};
  std::optional<PriceTicks> limit_price;
  bool post_only{false};
  TimestampNs decision_time{};
  TimestampNs outbound_send_time{};
  TimestampNs exchange_receive_time{};
};

struct OrderAcknowledged {
  ClientOrderId client_order_id{};
  ExchangeOrderId exchange_order_id{};
  std::optional<ExternalOrderId> external_order_id;
  QuantityLots accepted_quantity{};
  QuantityLots cumulative_filled{};
  QuantityLots leaves_quantity{};
  OrderState state{OrderState::Live};
};

struct OrderRejected {
  ClientOrderId client_order_id{};
  RejectReason reason{RejectReason::InternalError};
  std::string detail;
};

struct CancelRequest {
  ClientOrderId client_order_id{};
  ExchangeOrderId exchange_order_id{};
  DecisionId decision_id{};
  TimestampNs decision_time{};
  TimestampNs outbound_send_time{};
  TimestampNs exchange_receive_time{};
};

struct CancelAcknowledged {
  ClientOrderId client_order_id{};
  ExchangeOrderId exchange_order_id{};
  QuantityLots cumulative_filled{};
  QuantityLots cancelled_quantity{};
  QuantityLots leaves_quantity{};
  OrderState state{OrderState::Cancelled};
};

struct CancelRejected {
  ClientOrderId client_order_id{};
  ExchangeOrderId exchange_order_id{};
  RejectReason reason{RejectReason::InternalError};
  OrderState resulting_state{OrderState::Live};
  std::string detail;
};

struct ReplaceRequest {
  ClientOrderId client_order_id{};
  ExchangeOrderId exchange_order_id{};
  ClientOrderId replacement_client_order_id{};
  DecisionId decision_id{};
  QuantityLots new_quantity{};
  std::optional<PriceTicks> new_limit_price;
  TimestampNs decision_time{};
  TimestampNs outbound_send_time{};
  TimestampNs exchange_receive_time{};
};

struct ReplaceAcknowledged {
  ClientOrderId original_client_order_id{};
  ExchangeOrderId original_exchange_order_id{};
  ClientOrderId replacement_client_order_id{};
  ExchangeOrderId replacement_exchange_order_id{};
  QuantityLots accepted_quantity{};
  QuantityLots leaves_quantity{};
};

struct ReplaceRejected {
  ClientOrderId client_order_id{};
  ExchangeOrderId exchange_order_id{};
  ClientOrderId replacement_client_order_id{};
  RejectReason reason{RejectReason::InternalError};
  OrderState resulting_state{OrderState::Live};
  std::string detail;
};

struct Fill {
  ExecutionId execution_id{};
  ClientOrderId client_order_id{};
  ExchangeOrderId exchange_order_id{};
  std::optional<std::string> external_match_id;
  Side side{Side::Buy};
  PriceTicks price{};
  QuantityLots quantity{};
  QuantityLots cumulative_filled{};
  QuantityLots leaves_quantity{};
  LiquidityRole liquidity_role{LiquidityRole::Unknown};
};

struct Fee {
  ExecutionId execution_id{};
  FeeScheduleId fee_schedule_id{};
  QuoteAtoms amount{};
  LiquidityRole liquidity_role{LiquidityRole::Unknown};
};

struct TerminalCompletion {
  ParentOrderId parent_order_id{};
  Side side{Side::Buy};
  QuantityLots quantity{};
  PriceTicks price{};
  QuoteAtoms explicit_fee{};
  std::string rule_id;
};

struct Timer {
  std::string timer_name;
  std::uint64_t occurrence{0U};
};

using EventPayload = std::variant<
    BookSnapshot,
    DepthUpdate,
    Trade,
    Decision,
    OrderSubmit,
    OrderAcknowledged,
    OrderRejected,
    CancelRequest,
    CancelAcknowledged,
    CancelRejected,
    ReplaceRequest,
    ReplaceAcknowledged,
    ReplaceRejected,
    Fill,
    Fee,
    TerminalCompletion,
    Timer>;

struct Event {
  EventHeader header{};
  EventPayload payload{Timer{}};
};

[[nodiscard]] EventKind event_kind(const EventPayload& payload) noexcept;
[[nodiscard]] EventOrderKey event_order_key(const Event& event) noexcept;

}  // namespace robust_execution::model
