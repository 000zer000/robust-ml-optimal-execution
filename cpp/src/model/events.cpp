#include "robust_execution/model/events.hpp"

#include <type_traits>

namespace robust_execution::model {

EventKind event_kind(const EventPayload& payload) noexcept {
  return std::visit(
      [](const auto& value) noexcept -> EventKind {
        using Payload = std::decay_t<decltype(value)>;
        if constexpr (std::is_same_v<Payload, BookSnapshot>) {
          return EventKind::BookSnapshot;
        } else if constexpr (std::is_same_v<Payload, DepthUpdate>) {
          return EventKind::DepthUpdate;
        } else if constexpr (std::is_same_v<Payload, Trade>) {
          return EventKind::Trade;
        } else if constexpr (std::is_same_v<Payload, Decision>) {
          return EventKind::Decision;
        } else if constexpr (std::is_same_v<Payload, OrderSubmit>) {
          return EventKind::OrderSubmit;
        } else if constexpr (std::is_same_v<Payload, OrderAcknowledged>) {
          return EventKind::OrderAcknowledged;
        } else if constexpr (std::is_same_v<Payload, OrderRejected>) {
          return EventKind::OrderRejected;
        } else if constexpr (std::is_same_v<Payload, CancelRequest>) {
          return EventKind::CancelRequest;
        } else if constexpr (std::is_same_v<Payload, CancelAcknowledged>) {
          return EventKind::CancelAcknowledged;
        } else if constexpr (std::is_same_v<Payload, CancelRejected>) {
          return EventKind::CancelRejected;
        } else if constexpr (std::is_same_v<Payload, ReplaceRequest>) {
          return EventKind::ReplaceRequest;
        } else if constexpr (std::is_same_v<Payload, ReplaceAcknowledged>) {
          return EventKind::ReplaceAcknowledged;
        } else if constexpr (std::is_same_v<Payload, ReplaceRejected>) {
          return EventKind::ReplaceRejected;
        } else if constexpr (std::is_same_v<Payload, Fill>) {
          return EventKind::Fill;
        } else if constexpr (std::is_same_v<Payload, Fee>) {
          return EventKind::Fee;
        } else if constexpr (std::is_same_v<Payload, TerminalCompletion>) {
          return EventKind::TerminalCompletion;
        } else {
          static_assert(std::is_same_v<Payload, Timer>);
          return EventKind::Timer;
        }
      },
      payload
  );
}

EventOrderKey event_order_key(const Event& event) noexcept {
  return EventOrderKey{event.header.event_time, event.header.ordering, event.header.event_id};
}

}  // namespace robust_execution::model
