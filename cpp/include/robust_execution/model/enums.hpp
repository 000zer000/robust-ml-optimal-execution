#pragma once

#include <cstdint>
#include <string_view>

namespace robust_execution::model {

enum class Side : std::uint8_t { Buy, Sell };
enum class AggressorSide : std::uint8_t { Unknown, Buy, Sell };
enum class OrderType : std::uint8_t { Limit, Market };
enum class TimeInForce : std::uint8_t { GoodTilCancelled, ImmediateOrCancel, FillOrKill };
enum class LiquidityRole : std::uint8_t { Unknown, Maker, Taker };
enum class BookUpdateAction : std::uint8_t { Set, Delete };
enum class EventOrigin : std::uint8_t { HistoricalFeed, SyntheticExchange, Strategy, System };
enum class Severity : std::uint8_t { Error, Warning };

enum class OrderState : std::uint8_t {
  PendingNew,
  Live,
  PartiallyFilled,
  PendingCancel,
  Cancelled,
  Filled,
  Rejected,
  Expired,
  Replaced,
};

enum class RejectReason : std::uint8_t {
  InvalidPrice,
  InvalidQuantity,
  TickViolation,
  LotViolation,
  DuplicateClientOrderId,
  UnknownOrder,
  AlreadyTerminal,
  PostOnlyWouldCross,
  InsufficientInventory,
  RateLimit,
  UnsupportedOrderType,
  InvalidState,
  InternalError,
};

enum class EventKind : std::uint8_t {
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
  Timer,
};

[[nodiscard]] constexpr std::string_view to_string(Side value) noexcept {
  return value == Side::Buy ? "buy" : "sell";
}

[[nodiscard]] constexpr std::string_view to_string(OrderState value) noexcept {
  switch (value) {
    case OrderState::PendingNew:
      return "pending_new";
    case OrderState::Live:
      return "live";
    case OrderState::PartiallyFilled:
      return "partially_filled";
    case OrderState::PendingCancel:
      return "pending_cancel";
    case OrderState::Cancelled:
      return "cancelled";
    case OrderState::Filled:
      return "filled";
    case OrderState::Rejected:
      return "rejected";
    case OrderState::Expired:
      return "expired";
    case OrderState::Replaced:
      return "replaced";
  }
  return "unknown";
}

[[nodiscard]] constexpr std::string_view to_string(EventKind value) noexcept {
  switch (value) {
    case EventKind::BookSnapshot:
      return "book_snapshot";
    case EventKind::DepthUpdate:
      return "depth_update";
    case EventKind::Trade:
      return "trade";
    case EventKind::Decision:
      return "decision";
    case EventKind::OrderSubmit:
      return "order_submit";
    case EventKind::OrderAcknowledged:
      return "order_acknowledged";
    case EventKind::OrderRejected:
      return "order_rejected";
    case EventKind::CancelRequest:
      return "cancel_request";
    case EventKind::CancelAcknowledged:
      return "cancel_acknowledged";
    case EventKind::CancelRejected:
      return "cancel_rejected";
    case EventKind::ReplaceRequest:
      return "replace_request";
    case EventKind::ReplaceAcknowledged:
      return "replace_acknowledged";
    case EventKind::ReplaceRejected:
      return "replace_rejected";
    case EventKind::Fill:
      return "fill";
    case EventKind::Fee:
      return "fee";
    case EventKind::TerminalCompletion:
      return "terminal_completion";
    case EventKind::Timer:
      return "timer";
  }
  return "unknown";
}

[[nodiscard]] constexpr bool is_terminal(OrderState value) noexcept {
  return value == OrderState::Cancelled || value == OrderState::Filled ||
         value == OrderState::Rejected || value == OrderState::Expired ||
         value == OrderState::Replaced;
}

[[nodiscard]] constexpr bool valid_order_state_transition(
    OrderState from,
    OrderState to
) noexcept {
  if (from == to) {
    return from == OrderState::PartiallyFilled || from == OrderState::PendingCancel;
  }
  switch (from) {
    case OrderState::PendingNew:
      return to == OrderState::Live || to == OrderState::PartiallyFilled ||
             to == OrderState::Filled || to == OrderState::Rejected;
    case OrderState::Live:
      return to == OrderState::PartiallyFilled || to == OrderState::PendingCancel ||
             to == OrderState::Cancelled || to == OrderState::Filled ||
             to == OrderState::Expired || to == OrderState::Replaced;
    case OrderState::PartiallyFilled:
      return to == OrderState::PendingCancel || to == OrderState::Cancelled ||
             to == OrderState::Filled || to == OrderState::Expired ||
             to == OrderState::Replaced;
    case OrderState::PendingCancel:
      return to == OrderState::Live || to == OrderState::PartiallyFilled ||
             to == OrderState::Cancelled || to == OrderState::Filled;
    case OrderState::Cancelled:
    case OrderState::Filled:
    case OrderState::Rejected:
    case OrderState::Expired:
    case OrderState::Replaced:
      return false;
  }
  return false;
}

}  // namespace robust_execution::model
