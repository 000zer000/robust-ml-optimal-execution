#include "robust_execution/model/validation.hpp"

#include <algorithm>
#include <cstddef>
#include <string>
#include <type_traits>

namespace robust_execution::model {
namespace {

void add_error(ValidationIssues& issues, std::string code, std::string message) {
  issues.push_back(ValidationIssue{Severity::Error, std::move(code), std::move(message)});
}

void add_warning(ValidationIssues& issues, std::string code, std::string message) {
  issues.push_back(ValidationIssue{Severity::Warning, std::move(code), std::move(message)});
}

bool same_clock(TimestampNs lhs, TimestampNs rhs) noexcept {
  return lhs.domain() == rhs.domain();
}

void validate_non_decreasing(
    ValidationIssues& issues,
    TimestampNs first,
    TimestampNs second,
    const std::string& code,
    const std::string& message
) {
  if (!same_clock(first, second)) {
    add_error(issues, code + ".clock_domain", "timestamps use different clock domains");
  } else if (second.value() < first.value()) {
    add_error(issues, code, message);
  }
}

void require_numeric_id(ValidationIssues& issues, bool valid, const std::string& field) {
  if (!valid) {
    add_error(issues, "id.invalid", field + " must be non-zero");
  }
}

void require_text_id(ValidationIssues& issues, bool valid, const std::string& field) {
  if (!valid) {
    add_error(issues, "id.empty", field + " must be non-empty");
  }
}

void require_positive_price(ValidationIssues& issues, PriceTicks price, const std::string& field) {
  if (price.value() <= 0) {
    add_error(issues, "price.non_positive", field + " must be positive integer ticks");
  }
}

void require_positive_quantity(
    ValidationIssues& issues,
    QuantityLots quantity,
    const std::string& field
) {
  if (quantity.is_zero()) {
    add_error(issues, "quantity.zero", field + " must be positive integer lots");
  }
}

void validate_order_action_times(
    ValidationIssues& issues,
    TimestampNs decision,
    TimestampNs send,
    TimestampNs exchange_receive
) {
  validate_non_decreasing(
      issues,
      decision,
      send,
      "time.send_before_decision",
      "outbound send time precedes decision time"
  );
  validate_non_decreasing(
      issues,
      send,
      exchange_receive,
      "time.exchange_before_send",
      "exchange receive time precedes outbound send time"
  );
}

void validate_book_side(
    ValidationIssues& issues,
    const std::vector<BookLevel>& levels,
    bool descending,
    const std::string& side_name
) {
  for (std::size_t index = 0U; index < levels.size(); ++index) {
    const auto& level = levels[index];
    require_positive_price(issues, level.price, side_name + " price");
    require_positive_quantity(issues, level.displayed_quantity, side_name + " displayed quantity");
    if (index == 0U) {
      continue;
    }
    const auto previous = levels[index - 1U].price.value();
    const auto current = level.price.value();
    const bool ordered = descending ? current < previous : current > previous;
    if (!ordered) {
      add_error(
          issues,
          "book.unsorted_or_duplicate",
          side_name + " levels must be strictly price ordered without duplicates"
      );
    }
  }
}

void validate_payload(ValidationIssues& issues, const EventPayload& payload) {
  std::visit(
      [&issues](const auto& value) {
        using Payload = std::decay_t<decltype(value)>;
        if constexpr (std::is_same_v<Payload, BookSnapshot>) {
          validate_book_side(issues, value.bids, true, "bid");
          validate_book_side(issues, value.asks, false, "ask");
          if (!value.bids.empty() && !value.asks.empty() &&
              value.bids.front().price.value() >= value.asks.front().price.value()) {
            add_error(issues, "book.crossed", "best bid must be below best ask");
          }
        } else if constexpr (std::is_same_v<Payload, DepthUpdate>) {
          require_positive_price(issues, value.price, "depth update price");
          if (value.action == BookUpdateAction::Set) {
            require_positive_quantity(issues, value.quantity_after, "depth update quantity_after");
          } else if (!value.quantity_after.is_zero()) {
            add_error(
                issues,
                "depth.delete_nonzero",
                "delete depth update must set quantity_after to zero"
            );
          }
        } else if constexpr (std::is_same_v<Payload, Trade>) {
          require_numeric_id(issues, value.trade_id.valid(), "trade_id");
          require_positive_price(issues, value.price, "trade price");
          require_positive_quantity(issues, value.quantity, "trade quantity");
          if (value.external_trade_id.has_value()) {
            require_text_id(issues, value.external_trade_id->valid(), "external_trade_id");
          }
        } else if constexpr (std::is_same_v<Payload, Decision>) {
          require_numeric_id(issues, value.decision_id.valid(), "decision_id");
          require_text_id(issues, value.strategy_id.valid(), "strategy_id");
          if (value.action_name.empty()) {
            add_error(issues, "decision.action_empty", "decision action_name must be non-empty");
          }
          validate_non_decreasing(
              issues,
              value.observation_cutoff,
              value.decision_start,
              "time.decision_before_observation_cutoff",
              "decision start precedes causal observation cutoff"
          );
          validate_non_decreasing(
              issues,
              value.decision_start,
              value.decision_end,
              "time.decision_end_before_start",
              "decision end precedes decision start"
          );
        } else if constexpr (std::is_same_v<Payload, OrderSubmit>) {
          require_numeric_id(issues, value.parent_order_id.valid(), "parent_order_id");
          require_numeric_id(issues, value.client_order_id.valid(), "client_order_id");
          require_numeric_id(issues, value.decision_id.valid(), "decision_id");
          require_positive_quantity(issues, value.quantity, "order quantity");
          if (value.order_type == OrderType::Limit) {
            if (!value.limit_price.has_value()) {
              add_error(issues, "order.limit_price_missing", "limit order requires limit_price");
            } else {
              require_positive_price(issues, *value.limit_price, "limit_price");
            }
          } else {
            if (value.limit_price.has_value()) {
              add_error(issues, "order.market_has_price", "market order must not carry limit_price");
            }
            if (value.post_only) {
              add_error(issues, "order.market_post_only", "market order cannot be post-only");
            }
          }
          validate_order_action_times(
              issues,
              value.decision_time,
              value.outbound_send_time,
              value.exchange_receive_time
          );
        } else if constexpr (std::is_same_v<Payload, OrderAcknowledged>) {
          require_numeric_id(issues, value.client_order_id.valid(), "client_order_id");
          require_numeric_id(issues, value.exchange_order_id.valid(), "exchange_order_id");
          require_positive_quantity(issues, value.accepted_quantity, "accepted_quantity");
          const auto total = checked_add(value.cumulative_filled, value.leaves_quantity);
          if (!total.has_value() || *total != value.accepted_quantity) {
            add_error(
                issues,
                "order.ack_quantity_conservation",
                "cumulative_filled plus leaves_quantity must equal accepted_quantity"
            );
          }
          if (value.state != OrderState::Live && value.state != OrderState::PartiallyFilled &&
              value.state != OrderState::Filled) {
            add_error(issues, "order.ack_state", "acknowledgement has invalid order state");
          }
        } else if constexpr (std::is_same_v<Payload, OrderRejected>) {
          require_numeric_id(issues, value.client_order_id.valid(), "client_order_id");
        } else if constexpr (std::is_same_v<Payload, CancelRequest>) {
          require_numeric_id(issues, value.client_order_id.valid(), "client_order_id");
          require_numeric_id(issues, value.exchange_order_id.valid(), "exchange_order_id");
          require_numeric_id(issues, value.decision_id.valid(), "decision_id");
          validate_order_action_times(
              issues,
              value.decision_time,
              value.outbound_send_time,
              value.exchange_receive_time
          );
        } else if constexpr (std::is_same_v<Payload, CancelAcknowledged>) {
          require_numeric_id(issues, value.client_order_id.valid(), "client_order_id");
          require_numeric_id(issues, value.exchange_order_id.valid(), "exchange_order_id");
          if (value.state != OrderState::Cancelled) {
            add_error(issues, "order.cancel_ack_state", "cancel acknowledgement must be cancelled");
          }
          if (!value.leaves_quantity.is_zero()) {
            add_error(issues, "order.cancel_leaves", "cancelled order must have zero leaves_quantity");
          }
        } else if constexpr (std::is_same_v<Payload, CancelRejected>) {
          require_numeric_id(issues, value.client_order_id.valid(), "client_order_id");
          require_numeric_id(issues, value.exchange_order_id.valid(), "exchange_order_id");
          if (is_terminal(value.resulting_state)) {
            add_error(
                issues,
                "order.cancel_reject_terminal",
                "cancel rejection cannot report a terminal resulting state"
            );
          }
        } else if constexpr (std::is_same_v<Payload, ReplaceRequest>) {
          require_numeric_id(issues, value.client_order_id.valid(), "client_order_id");
          require_numeric_id(issues, value.exchange_order_id.valid(), "exchange_order_id");
          require_numeric_id(
              issues,
              value.replacement_client_order_id.valid(),
              "replacement_client_order_id"
          );
          require_numeric_id(issues, value.decision_id.valid(), "decision_id");
          require_positive_quantity(issues, value.new_quantity, "replacement quantity");
          if (value.new_limit_price.has_value()) {
            require_positive_price(issues, *value.new_limit_price, "replacement limit price");
          }
          validate_order_action_times(
              issues,
              value.decision_time,
              value.outbound_send_time,
              value.exchange_receive_time
          );
        } else if constexpr (std::is_same_v<Payload, ReplaceAcknowledged>) {
          require_numeric_id(
              issues,
              value.original_client_order_id.valid(),
              "original_client_order_id"
          );
          require_numeric_id(
              issues,
              value.original_exchange_order_id.valid(),
              "original_exchange_order_id"
          );
          require_numeric_id(
              issues,
              value.replacement_client_order_id.valid(),
              "replacement_client_order_id"
          );
          require_numeric_id(
              issues,
              value.replacement_exchange_order_id.valid(),
              "replacement_exchange_order_id"
          );
          require_positive_quantity(issues, value.accepted_quantity, "accepted_quantity");
          if (value.leaves_quantity != value.accepted_quantity) {
            add_error(
                issues,
                "order.replace_ack_quantity",
                "new replacement order must start with leaves equal to accepted quantity"
            );
          }
        } else if constexpr (std::is_same_v<Payload, ReplaceRejected>) {
          require_numeric_id(issues, value.client_order_id.valid(), "client_order_id");
          require_numeric_id(issues, value.exchange_order_id.valid(), "exchange_order_id");
          require_numeric_id(
              issues,
              value.replacement_client_order_id.valid(),
              "replacement_client_order_id"
          );
          if (is_terminal(value.resulting_state)) {
            add_error(
                issues,
                "order.replace_reject_terminal",
                "replace rejection cannot report a terminal resulting state"
            );
          }
        } else if constexpr (std::is_same_v<Payload, Fill>) {
          require_numeric_id(issues, value.execution_id.valid(), "execution_id");
          require_numeric_id(issues, value.client_order_id.valid(), "client_order_id");
          require_numeric_id(issues, value.exchange_order_id.valid(), "exchange_order_id");
          require_positive_price(issues, value.price, "fill price");
          require_positive_quantity(issues, value.quantity, "fill quantity");
          require_positive_quantity(issues, value.cumulative_filled, "cumulative_filled");
          if (value.quantity.value() > value.cumulative_filled.value()) {
            add_error(
                issues,
                "fill.increment_exceeds_cumulative",
                "fill quantity cannot exceed cumulative_filled"
            );
          }
        } else if constexpr (std::is_same_v<Payload, Fee>) {
          require_numeric_id(issues, value.execution_id.valid(), "execution_id");
          require_text_id(issues, value.fee_schedule_id.valid(), "fee_schedule_id");
        } else if constexpr (std::is_same_v<Payload, TerminalCompletion>) {
          require_numeric_id(issues, value.parent_order_id.valid(), "parent_order_id");
          require_positive_quantity(issues, value.quantity, "terminal quantity");
          require_positive_price(issues, value.price, "terminal price");
          if (value.rule_id.empty()) {
            add_error(
                issues,
                "terminal.rule_empty",
                "terminal completion rule_id must be non-empty"
            );
          }
        } else {
          static_assert(std::is_same_v<Payload, Timer>);
          if (value.timer_name.empty()) {
            add_error(issues, "timer.name_empty", "timer_name must be non-empty");
          }
        }
      },
      payload
  );
}

}  // namespace

ValidationIssues validate_instrument(const InstrumentDefinition& instrument) {
  ValidationIssues issues;
  if (instrument.schema.major != kEventSchemaVersion.major) {
    add_error(issues, "schema.major", "unsupported instrument schema major version");
  }
  require_text_id(issues, instrument.venue.valid(), "venue");
  require_text_id(issues, instrument.instrument.valid(), "instrument");
  if (instrument.base_asset.empty() || instrument.quote_asset.empty()) {
    add_error(issues, "instrument.assets_empty", "base_asset and quote_asset are required");
  }
  if (!instrument.tick_size.valid() || !instrument.lot_size.valid() ||
      !instrument.quote_atom_size.valid()) {
    add_error(issues, "instrument.increment_invalid", "all rational increments must be positive");
  }
  require_positive_quantity(
      issues,
      instrument.minimum_order_quantity,
      "minimum_order_quantity"
  );
  if (instrument.maximum_order_quantity.has_value() &&
      *instrument.maximum_order_quantity < instrument.minimum_order_quantity) {
    add_error(
        issues,
        "instrument.maximum_below_minimum",
        "maximum_order_quantity must not be below minimum_order_quantity"
    );
  }
  if (instrument.metadata_version.empty()) {
    add_error(issues, "instrument.metadata_version_empty", "metadata_version is required");
  }
  return issues;
}

ValidationIssues validate_event(const Event& event) {
  ValidationIssues issues;
  const auto& header = event.header;
  if (header.schema.major != kEventSchemaVersion.major) {
    add_error(issues, "schema.major", "unsupported event schema major version");
  }
  require_numeric_id(issues, header.event_id.valid(), "event_id");
  require_text_id(issues, header.run_id.valid(), "run_id");
  require_text_id(issues, header.venue.valid(), "venue");
  require_text_id(issues, header.instrument.valid(), "instrument");
  require_text_id(issues, header.source_channel.valid(), "source_channel");
  if (header.ordering.ingest_sequence == 0U) {
    add_error(issues, "ordering.ingest_zero", "ingest_sequence must be non-zero");
  }
  if (header.ordering.canonical_sequence == 0U) {
    add_error(issues, "ordering.canonical_zero", "canonical_sequence must be non-zero");
  }
  if (!header.ordering.has_source_sequence && header.ordering.source_sequence != 0U) {
    add_error(
        issues,
        "ordering.source_sequence_without_flag",
        "source_sequence must be zero when has_source_sequence is false"
    );
  }
  if (header.receive_time.has_value()) {
    if (!same_clock(header.event_time, *header.receive_time)) {
      add_error(
          issues,
          "time.receive_clock_domain",
          "exchange and receive timestamps use different clock domains"
      );
    } else if (header.receive_time->value() < header.event_time.value()) {
      if (header.origin == EventOrigin::HistoricalFeed) {
        add_warning(
            issues,
            "time.receive_before_exchange_historical",
            "historical receive time precedes exchange time; retain clock-quality metadata"
        );
      } else {
        add_error(
            issues,
            "time.receive_before_exchange",
            "receive time precedes exchange time"
        );
      }
    }
  }
  if (header.available_time.has_value()) {
    if (!header.receive_time.has_value()) {
      add_error(
          issues,
          "time.available_without_receive",
          "available_time requires receive_time"
      );
    } else {
      validate_non_decreasing(
          issues,
          *header.receive_time,
          *header.available_time,
          "time.available_before_receive",
          "available time precedes receive time"
      );
    }
  }
  validate_payload(issues, event.payload);
  return issues;
}

bool has_errors(const ValidationIssues& issues) noexcept {
  return std::any_of(issues.begin(), issues.end(), [](const ValidationIssue& issue) {
    return issue.severity == Severity::Error;
  });
}

}  // namespace robust_execution::model
