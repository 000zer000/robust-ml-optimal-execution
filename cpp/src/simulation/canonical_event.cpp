#include "robust_execution/simulation/canonical_event.hpp"

#include <optional>
#include <sstream>
#include <string>
#include <type_traits>

namespace robust_execution::simulation {
namespace {

void text(std::ostringstream& output, const std::string& value) {
  output << value.size() << ':' << value << '|';
}

void timestamp(std::ostringstream& output, model::TimestampNs value) {
  output << static_cast<unsigned>(value.domain()) << ':' << value.value() << '|';
}

void optional_timestamp(
    std::ostringstream& output,
    const std::optional<model::TimestampNs>& value
) {
  output << (value.has_value() ? '1' : '0') << '|';
  if (value.has_value()) {
    timestamp(output, *value);
  }
}

void optional_price(
    std::ostringstream& output,
    const std::optional<model::PriceTicks>& value
) {
  output << (value.has_value() ? '1' : '0') << '|';
  if (value.has_value()) {
    output << value->value() << '|';
  }
}

void optional_string(
    std::ostringstream& output,
    const std::optional<std::string>& value
) {
  output << (value.has_value() ? '1' : '0') << '|';
  if (value.has_value()) {
    text(output, *value);
  }
}

template <typename Tag>
void optional_text_id(
    std::ostringstream& output,
    const std::optional<model::TextId<Tag>>& value
) {
  output << (value.has_value() ? '1' : '0') << '|';
  if (value.has_value()) {
    text(output, value->value());
  }
}

void book_levels(std::ostringstream& output, const std::vector<model::BookLevel>& levels) {
  output << levels.size() << '|';
  for (const auto& level : levels) {
    output << level.price.value() << '|' << level.displayed_quantity.value() << '|'
           << (level.order_count.has_value() ? '1' : '0') << '|';
    if (level.order_count.has_value()) {
      output << *level.order_count << '|';
    }
  }
}

void payload(std::ostringstream& output, const model::EventPayload& event_payload) {
  output << static_cast<unsigned>(model::event_kind(event_payload)) << '|';
  std::visit(
      [&output](const auto& value) {
        using Payload = std::decay_t<decltype(value)>;
        if constexpr (std::is_same_v<Payload, model::BookSnapshot>) {
          book_levels(output, value.bids);
          book_levels(output, value.asks);
        } else if constexpr (std::is_same_v<Payload, model::DepthUpdate>) {
          output << static_cast<unsigned>(value.side) << '|' << value.price.value() << '|'
                 << value.quantity_after.value() << '|' << static_cast<unsigned>(value.action)
                 << '|' << (value.order_count_after.has_value() ? '1' : '0') << '|';
          if (value.order_count_after.has_value()) {
            output << *value.order_count_after << '|';
          }
        } else if constexpr (std::is_same_v<Payload, model::Trade>) {
          output << value.trade_id.value() << '|';
          optional_text_id(output, value.external_trade_id);
          output << value.price.value() << '|' << value.quantity.value() << '|'
                 << static_cast<unsigned>(value.aggressor_side) << '|';
        } else if constexpr (std::is_same_v<Payload, model::Decision>) {
          output << value.decision_id.value() << '|';
          text(output, value.strategy_id.value());
          timestamp(output, value.observation_cutoff);
          timestamp(output, value.decision_start);
          timestamp(output, value.decision_end);
          output << value.remaining_inventory.value() << '|';
          text(output, value.action_name);
          optional_string(output, value.model_artifact_id);
        } else if constexpr (std::is_same_v<Payload, model::OrderSubmit>) {
          output << value.parent_order_id.value() << '|' << value.client_order_id.value() << '|'
                 << value.decision_id.value() << '|' << static_cast<unsigned>(value.side) << '|'
                 << static_cast<unsigned>(value.order_type) << '|'
                 << static_cast<unsigned>(value.time_in_force) << '|' << value.quantity.value()
                 << '|';
          optional_price(output, value.limit_price);
          output << value.post_only << '|';
          timestamp(output, value.decision_time);
          timestamp(output, value.outbound_send_time);
          timestamp(output, value.exchange_receive_time);
        } else if constexpr (std::is_same_v<Payload, model::OrderAcknowledged>) {
          output << value.client_order_id.value() << '|' << value.exchange_order_id.value() << '|';
          optional_text_id(output, value.external_order_id);
          output << value.accepted_quantity.value() << '|' << value.cumulative_filled.value() << '|'
                 << value.leaves_quantity.value() << '|' << static_cast<unsigned>(value.state) << '|';
        } else if constexpr (std::is_same_v<Payload, model::OrderRejected>) {
          output << value.client_order_id.value() << '|' << static_cast<unsigned>(value.reason) << '|';
          text(output, value.detail);
        } else if constexpr (std::is_same_v<Payload, model::CancelRequest>) {
          output << value.client_order_id.value() << '|' << value.exchange_order_id.value() << '|'
                 << value.decision_id.value() << '|';
          timestamp(output, value.decision_time);
          timestamp(output, value.outbound_send_time);
          timestamp(output, value.exchange_receive_time);
        } else if constexpr (std::is_same_v<Payload, model::CancelAcknowledged>) {
          output << value.client_order_id.value() << '|' << value.exchange_order_id.value() << '|'
                 << value.cumulative_filled.value() << '|' << value.cancelled_quantity.value() << '|'
                 << value.leaves_quantity.value() << '|' << static_cast<unsigned>(value.state) << '|';
        } else if constexpr (std::is_same_v<Payload, model::CancelRejected>) {
          output << value.client_order_id.value() << '|' << value.exchange_order_id.value() << '|'
                 << static_cast<unsigned>(value.reason) << '|'
                 << static_cast<unsigned>(value.resulting_state) << '|';
          text(output, value.detail);
        } else if constexpr (std::is_same_v<Payload, model::ReplaceRequest>) {
          output << value.client_order_id.value() << '|' << value.exchange_order_id.value() << '|'
                 << value.replacement_client_order_id.value() << '|' << value.decision_id.value() << '|'
                 << value.new_quantity.value() << '|';
          optional_price(output, value.new_limit_price);
          timestamp(output, value.decision_time);
          timestamp(output, value.outbound_send_time);
          timestamp(output, value.exchange_receive_time);
        } else if constexpr (std::is_same_v<Payload, model::ReplaceAcknowledged>) {
          output << value.original_client_order_id.value() << '|'
                 << value.original_exchange_order_id.value() << '|'
                 << value.replacement_client_order_id.value() << '|'
                 << value.replacement_exchange_order_id.value() << '|'
                 << value.accepted_quantity.value() << '|' << value.leaves_quantity.value() << '|';
        } else if constexpr (std::is_same_v<Payload, model::ReplaceRejected>) {
          output << value.client_order_id.value() << '|' << value.exchange_order_id.value() << '|'
                 << value.replacement_client_order_id.value() << '|'
                 << static_cast<unsigned>(value.reason) << '|'
                 << static_cast<unsigned>(value.resulting_state) << '|';
          text(output, value.detail);
        } else if constexpr (std::is_same_v<Payload, model::Fill>) {
          output << value.execution_id.value() << '|' << value.client_order_id.value() << '|'
                 << value.exchange_order_id.value() << '|';
          optional_string(output, value.external_match_id);
          output << static_cast<unsigned>(value.side) << '|' << value.price.value() << '|'
                 << value.quantity.value() << '|' << value.cumulative_filled.value() << '|'
                 << value.leaves_quantity.value() << '|'
                 << static_cast<unsigned>(value.liquidity_role) << '|';
        } else if constexpr (std::is_same_v<Payload, model::Fee>) {
          output << value.execution_id.value() << '|';
          text(output, value.fee_schedule_id.value());
          output << value.amount.value() << '|' << static_cast<unsigned>(value.liquidity_role) << '|';
        } else if constexpr (std::is_same_v<Payload, model::TerminalCompletion>) {
          output << value.parent_order_id.value() << '|' << static_cast<unsigned>(value.side) << '|'
                 << value.quantity.value() << '|' << value.price.value() << '|'
                 << value.explicit_fee.value() << '|';
          text(output, value.rule_id);
        } else {
          static_assert(std::is_same_v<Payload, model::Timer>);
          text(output, value.timer_name);
          output << value.occurrence << '|';
        }
      },
      event_payload
  );
}

}  // namespace

std::string canonical_event(const model::Event& event) {
  std::ostringstream output;
  const auto& header = event.header;
  output << header.schema.major << '|' << header.schema.minor << '|'
         << header.event_id.value() << '|';
  text(output, header.run_id.value());
  text(output, header.venue.value());
  text(output, header.instrument.value());
  text(output, header.source_channel.value());
  output << static_cast<unsigned>(header.origin) << '|';
  timestamp(output, header.event_time);
  optional_timestamp(output, header.receive_time);
  optional_timestamp(output, header.available_time);
  output << header.ordering.has_source_sequence << '|' << header.ordering.source_sequence << '|'
         << header.ordering.source_subsequence << '|' << header.ordering.ingest_sequence << '|'
         << header.ordering.canonical_sequence << '|';
  optional_string(output, header.original_timestamp);
  payload(output, event.payload);
  return output.str();
}

}  // namespace robust_execution::simulation
