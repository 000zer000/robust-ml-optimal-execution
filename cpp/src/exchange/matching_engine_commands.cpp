#include "matching_engine_internal.hpp"

#include <limits>
#include <optional>
#include <string>
#include <utility>

namespace robust_execution::exchange {

namespace {

[[nodiscard]] bool valid_action_times(
    model::TimestampNs decision_time,
    model::TimestampNs send_time,
    model::TimestampNs receive_time
) noexcept {
  if (decision_time.domain() != send_time.domain() ||
      send_time.domain() != receive_time.domain()) {
    return false;
  }
  return decision_time.value() <= send_time.value() &&
         send_time.value() <= receive_time.value();
}

[[nodiscard]] model::RejectReason event_reason(EngineFailureCode code) noexcept {
  switch (code) {
    case EngineFailureCode::DuplicateClientOrderId:
      return model::RejectReason::DuplicateClientOrderId;
    case EngineFailureCode::UnknownOrder:
    case EngineFailureCode::OrderIdentifierMismatch:
      return model::RejectReason::UnknownOrder;
    case EngineFailureCode::AlreadyTerminal:
      return model::RejectReason::AlreadyTerminal;
    case EngineFailureCode::PostOnlyWouldCross:
      return model::RejectReason::PostOnlyWouldCross;
    case EngineFailureCode::QuantityBelowMinimum:
    case EngineFailureCode::QuantityAboveMaximum:
      return model::RejectReason::InvalidQuantity;
    case EngineFailureCode::MissingLimitPrice:
    case EngineFailureCode::UnexpectedLimitPrice:
      return model::RejectReason::InvalidPrice;
    case EngineFailureCode::UnsupportedCombination:
      return model::RejectReason::UnsupportedOrderType;
    case EngineFailureCode::InvalidCommand:
    case EngineFailureCode::InsufficientLiquidity:
      return model::RejectReason::InvalidState;
    case EngineFailureCode::InternalSequenceExhausted:
      return model::RejectReason::InternalError;
  }
  return model::RejectReason::InternalError;
}

[[nodiscard]] EngineFailure make_failure(
    EngineFailureCode code,
    model::ClientOrderId client_order_id,
    std::string detail,
    std::optional<model::ExchangeOrderId> exchange_order_id = std::nullopt,
    std::optional<model::OrderState> current_state = std::nullopt
) {
  return EngineFailure{
      code,
      event_reason(code),
      client_order_id,
      exchange_order_id,
      current_state,
      std::move(detail),
  };
}

[[nodiscard]] bool has_capacity(
    std::uint64_t next_value,
    std::uint64_t required_count
) noexcept {
  if (required_count == 0U) {
    return true;
  }
  if (next_value == 0U) {
    return false;
  }
  return required_count - 1U <=
         std::numeric_limits<std::uint64_t>::max() - next_value;
}

}  // namespace

SubmitResult MatchingEngine::Impl::submit(const model::OrderSubmit& command) {
  if (const auto failure = validate_submit(command); failure.has_value()) {
    return rejected_submit(command.client_order_id, *failure);
  }

  const auto maximum_matches = static_cast<std::uint64_t>(active_by_exchange_.size());
  const auto execution_capacity_valid =
      maximum_matches <= std::numeric_limits<std::uint64_t>::max() / 2U;
  const auto maximum_executions = execution_capacity_valid ? maximum_matches * 2U : 0U;
  if (!execution_capacity_valid || !has_capacity(next_exchange_order_id_, 1U) ||
      !has_capacity(next_priority_sequence_, 1U) ||
      !has_capacity(next_match_sequence_, maximum_matches) ||
      !has_capacity(next_execution_id_, maximum_executions)) {
    return rejected_submit(
        command.client_order_id,
        make_failure(
            EngineFailureCode::InternalSequenceExhausted,
            command.client_order_id,
            "matching-engine identifier sequence is exhausted"
        )
    );
  }

  if (command.time_in_force == model::TimeInForce::FillOrKill &&
      !can_fully_execute(command.side, command.quantity, command.limit_price)) {
    return rejected_submit(
        command.client_order_id,
        make_failure(
            EngineFailureCode::InsufficientLiquidity,
            command.client_order_id,
            "fill-or-kill order cannot be fully executed at eligible resting prices"
        )
    );
  }

  if (command.post_only && would_cross(command.side, command.limit_price)) {
    return rejected_submit(
        command.client_order_id,
        make_failure(
            EngineFailureCode::PostOnlyWouldCross,
            command.client_order_id,
            "post-only order would execute immediately"
        )
    );
  }

  if (command.order_type == model::OrderType::Limit &&
      command.time_in_force == model::TimeInForce::GoodTilCancelled &&
      !can_add_to_level(command.side, *command.limit_price, command.quantity)) {
    return rejected_submit(
        command.client_order_id,
        make_failure(
            EngineFailureCode::InternalSequenceExhausted,
            command.client_order_id,
            "price-level quantity or order-count capacity would be exceeded"
        )
    );
  }

  const model::ExchangeOrderId exchange_order_id{allocate(next_exchange_order_id_)};
  const auto priority_sequence = allocate(next_priority_sequence_);

  OrderView incoming{
      command.parent_order_id,
      command.client_order_id,
      exchange_order_id,
      command.decision_id,
      command.side,
      command.order_type,
      command.time_in_force,
      command.quantity,
      model::QuantityLots{0U},
      command.quantity,
      command.limit_price,
      command.post_only,
      model::OrderState::Live,
      priority_sequence,
  };

  all_client_ids_.insert(command.client_order_id.value());
  exchange_by_client_.emplace(command.client_order_id.value(), exchange_order_id.value());
  orders_by_exchange_.emplace(exchange_order_id.value(), incoming);

  SubmitResult result;
  result.acknowledgement = model::OrderAcknowledged{
      command.client_order_id,
      exchange_order_id,
      std::nullopt,
      command.quantity,
      model::QuantityLots{0U},
      command.quantity,
      model::OrderState::Live,
  };

  match(incoming, result.matches);

  if (incoming.leaves_quantity.is_zero()) {
    incoming.state = model::OrderState::Filled;
  } else if (command.order_type == model::OrderType::Limit &&
             command.time_in_force == model::TimeInForce::GoodTilCancelled) {
    incoming.state = incoming.cumulative_filled.is_zero()
                         ? model::OrderState::Live
                         : model::OrderState::PartiallyFilled;
    rest(incoming);
  } else {
    const auto cancelled = incoming.leaves_quantity;
    incoming.leaves_quantity = model::QuantityLots{0U};
    incoming.state = model::OrderState::Cancelled;
    result.automatic_cancellation = model::CancelAcknowledged{
        incoming.client_order_id,
        incoming.exchange_order_id,
        incoming.cumulative_filled,
        cancelled,
        model::QuantityLots{0U},
        model::OrderState::Cancelled,
    };
  }

  orders_by_exchange_[exchange_order_id.value()] = incoming;
  result.final_order = incoming;
  return result;
}

CancelResult MatchingEngine::Impl::cancel(const model::CancelRequest& command) {
  if (!command.client_order_id.valid() || !command.exchange_order_id.valid() ||
      !command.decision_id.valid() ||
      !valid_action_times(
          command.decision_time,
          command.outbound_send_time,
          command.exchange_receive_time
      )) {
    return CancelResult{
        std::nullopt,
        make_failure(
            EngineFailureCode::InvalidCommand,
            command.client_order_id,
            "cancel command has invalid identifiers or non-causal timestamps",
            command.exchange_order_id
        ),
    };
  }

  const auto located = locate_active(command.client_order_id, command.exchange_order_id);
  if (located.failure.has_value()) {
    return CancelResult{std::nullopt, located.failure};
  }

  auto& locator = active_by_exchange_.at(command.exchange_order_id.value());
  auto& node = *locator.iterator;
  const auto cumulative_filled = node.view.cumulative_filled;
  const auto cancelled_quantity = node.view.leaves_quantity;

  remove_active(locator, model::OrderState::Cancelled);

  return CancelResult{
      model::CancelAcknowledged{
          command.client_order_id,
          command.exchange_order_id,
          cumulative_filled,
          cancelled_quantity,
          model::QuantityLots{0U},
          model::OrderState::Cancelled,
      },
      std::nullopt,
  };
}

ReplaceResult MatchingEngine::Impl::replace(const model::ReplaceRequest& command) {
  if (!command.client_order_id.valid() || !command.exchange_order_id.valid() ||
      !command.replacement_client_order_id.valid() || !command.decision_id.valid() ||
      command.replacement_client_order_id == command.client_order_id ||
      !valid_action_times(
          command.decision_time,
          command.outbound_send_time,
          command.exchange_receive_time
      )) {
    return ReplaceResult{
        std::nullopt,
        make_failure(
            EngineFailureCode::InvalidCommand,
            command.client_order_id,
            "replace command has invalid identifiers or non-causal timestamps",
            command.exchange_order_id
        ),
        {},
        std::nullopt,
    };
  }

  const auto located = locate_active(command.client_order_id, command.exchange_order_id);
  if (located.failure.has_value()) {
    return ReplaceResult{std::nullopt, located.failure, {}, std::nullopt};
  }

  if (all_client_ids_.contains(command.replacement_client_order_id.value())) {
    return ReplaceResult{
        std::nullopt,
        make_failure(
            EngineFailureCode::DuplicateClientOrderId,
            command.replacement_client_order_id,
            "replacement client order identifier has already been used"
        ),
        {},
        std::nullopt,
    };
  }

  if (const auto failure = validate_quantity(
          command.replacement_client_order_id,
          command.new_quantity
      ); failure.has_value()) {
    return ReplaceResult{std::nullopt, failure, {}, std::nullopt};
  }
  if (!command.new_limit_price.has_value() || command.new_limit_price->value() <= 0) {
    return ReplaceResult{
        std::nullopt,
        make_failure(
            EngineFailureCode::MissingLimitPrice,
            command.replacement_client_order_id,
            "replacement of a resting limit order requires a positive limit price"
        ),
        {},
        std::nullopt,
    };
  }

  const auto maximum_matches = static_cast<std::uint64_t>(active_by_exchange_.size());
  const auto execution_capacity_valid =
      maximum_matches <= std::numeric_limits<std::uint64_t>::max() / 2U;
  const auto maximum_executions = execution_capacity_valid ? maximum_matches * 2U : 0U;
  if (!execution_capacity_valid || !has_capacity(next_exchange_order_id_, 1U) ||
      !has_capacity(next_priority_sequence_, 1U) ||
      !has_capacity(next_match_sequence_, maximum_matches) ||
      !has_capacity(next_execution_id_, maximum_executions)) {
    return ReplaceResult{
        std::nullopt,
        make_failure(
            EngineFailureCode::InternalSequenceExhausted,
            command.replacement_client_order_id,
            "matching-engine identifier sequence is exhausted"
        ),
        {},
        std::nullopt,
    };
  }

  const auto& old_locator = active_by_exchange_.at(command.exchange_order_id.value());
  const auto old_view = old_locator.iterator->view;
  if (!can_add_to_level(old_view.side, *command.new_limit_price, command.new_quantity)) {
    return ReplaceResult{
        std::nullopt,
        make_failure(
            EngineFailureCode::InternalSequenceExhausted,
            command.replacement_client_order_id,
            "replacement price-level capacity would be exceeded"
        ),
        {},
        std::nullopt,
    };
  }

  remove_active(active_by_exchange_.at(command.exchange_order_id.value()), model::OrderState::Replaced);

  const model::ExchangeOrderId replacement_exchange_order_id{
      allocate(next_exchange_order_id_)
  };
  const auto replacement_priority = allocate(next_priority_sequence_);
  OrderView replacement{
      old_view.parent_order_id,
      command.replacement_client_order_id,
      replacement_exchange_order_id,
      command.decision_id,
      old_view.side,
      model::OrderType::Limit,
      model::TimeInForce::GoodTilCancelled,
      command.new_quantity,
      model::QuantityLots{0U},
      command.new_quantity,
      command.new_limit_price,
      false,
      model::OrderState::Live,
      replacement_priority,
  };

  all_client_ids_.insert(command.replacement_client_order_id.value());
  exchange_by_client_.emplace(
      command.replacement_client_order_id.value(),
      replacement_exchange_order_id.value()
  );
  orders_by_exchange_.emplace(replacement_exchange_order_id.value(), replacement);

  ReplaceResult result;
  result.acknowledgement = model::ReplaceAcknowledged{
      command.client_order_id,
      command.exchange_order_id,
      command.replacement_client_order_id,
      replacement_exchange_order_id,
      command.new_quantity,
      command.new_quantity,
  };

  match(replacement, result.matches);
  if (replacement.leaves_quantity.is_zero()) {
    replacement.state = model::OrderState::Filled;
  } else {
    replacement.state = replacement.cumulative_filled.is_zero()
                            ? model::OrderState::Live
                            : model::OrderState::PartiallyFilled;
    rest(replacement);
  }
  orders_by_exchange_[replacement_exchange_order_id.value()] = replacement;
  result.replacement_order = replacement;
  return result;
}

std::optional<EngineFailure> MatchingEngine::Impl::validate_submit(
    const model::OrderSubmit& command
) const {
  if (!command.parent_order_id.valid() || !command.client_order_id.valid() ||
      !command.decision_id.valid() ||
      !valid_action_times(
          command.decision_time,
          command.outbound_send_time,
          command.exchange_receive_time
      )) {
    return make_failure(
        EngineFailureCode::InvalidCommand,
        command.client_order_id,
        "submit command has invalid identifiers or non-causal timestamps"
    );
  }
  if (all_client_ids_.contains(command.client_order_id.value())) {
    return make_failure(
        EngineFailureCode::DuplicateClientOrderId,
        command.client_order_id,
        "client order identifier has already been used"
    );
  }
  if (const auto failure = validate_quantity(command.client_order_id, command.quantity);
      failure.has_value()) {
    return failure;
  }
  if (command.order_type == model::OrderType::Limit) {
    if (!command.limit_price.has_value() || command.limit_price->value() <= 0) {
      return make_failure(
          EngineFailureCode::MissingLimitPrice,
          command.client_order_id,
          "limit order requires a positive limit price"
      );
    }
  } else {
    if (!config_.allow_market_orders) {
      return make_failure(
          EngineFailureCode::UnsupportedCombination,
          command.client_order_id,
          "market orders are disabled by the synthetic venue configuration"
      );
    }
    if (command.limit_price.has_value()) {
      return make_failure(
          EngineFailureCode::UnexpectedLimitPrice,
          command.client_order_id,
          "market order must not carry a limit price"
      );
    }
    if (command.time_in_force == model::TimeInForce::GoodTilCancelled) {
      return make_failure(
          EngineFailureCode::UnsupportedCombination,
          command.client_order_id,
          "market order cannot be good-til-cancelled"
      );
    }
  }
  if (command.time_in_force == model::TimeInForce::ImmediateOrCancel &&
      !config_.allow_immediate_or_cancel) {
    return make_failure(
        EngineFailureCode::UnsupportedCombination,
        command.client_order_id,
        "immediate-or-cancel orders are disabled"
    );
  }
  if (command.time_in_force == model::TimeInForce::FillOrKill &&
      !config_.allow_fill_or_kill) {
    return make_failure(
        EngineFailureCode::UnsupportedCombination,
        command.client_order_id,
        "fill-or-kill orders are disabled"
    );
  }
  if (command.post_only) {
    if (!config_.allow_post_only) {
      return make_failure(
          EngineFailureCode::UnsupportedCombination,
          command.client_order_id,
          "post-only orders are disabled"
      );
    }
    if (command.order_type != model::OrderType::Limit ||
        command.time_in_force != model::TimeInForce::GoodTilCancelled) {
      return make_failure(
          EngineFailureCode::UnsupportedCombination,
          command.client_order_id,
          "post-only requires a good-til-cancelled limit order"
      );
    }
  }
  return std::nullopt;
}

std::optional<EngineFailure> MatchingEngine::Impl::validate_quantity(
    model::ClientOrderId client_order_id,
    model::QuantityLots quantity
) const {
  if (quantity < config_.instrument.minimum_order_quantity) {
    return make_failure(
        EngineFailureCode::QuantityBelowMinimum,
        client_order_id,
        "order quantity is below the instrument minimum"
    );
  }
  if (config_.instrument.maximum_order_quantity.has_value() &&
      quantity > *config_.instrument.maximum_order_quantity) {
    return make_failure(
        EngineFailureCode::QuantityAboveMaximum,
        client_order_id,
        "order quantity exceeds the instrument maximum"
    );
  }
  return std::nullopt;
}

SubmitResult MatchingEngine::Impl::rejected_submit(
    model::ClientOrderId client_order_id,
    EngineFailure failure
) const {
  return SubmitResult{
      std::nullopt,
      model::OrderRejected{client_order_id, failure.event_model_reason, failure.detail},
      std::move(failure),
      {},
      std::nullopt,
      std::nullopt,
  };
}

MatchingEngine::Impl::LocateResult MatchingEngine::Impl::locate_active(
    model::ClientOrderId client_order_id,
    model::ExchangeOrderId exchange_order_id
) const {
  const auto known = exchange_by_client_.find(client_order_id.value());
  if (known == exchange_by_client_.end()) {
    return LocateResult{make_failure(
        EngineFailureCode::UnknownOrder,
        client_order_id,
        "client order identifier is unknown",
        exchange_order_id
    )};
  }
  if (known->second != exchange_order_id.value()) {
    return LocateResult{make_failure(
        EngineFailureCode::OrderIdentifierMismatch,
        client_order_id,
        "client and exchange order identifiers do not refer to the same order",
        exchange_order_id
    )};
  }
  const auto active = active_by_exchange_.find(exchange_order_id.value());
  if (active == active_by_exchange_.end()) {
    const auto history = orders_by_exchange_.find(exchange_order_id.value());
    if (history == orders_by_exchange_.end()) {
      return LocateResult{make_failure(
          EngineFailureCode::AlreadyTerminal,
          client_order_id,
          "order is no longer active",
          exchange_order_id,
          std::nullopt
      )};
    }
    return LocateResult{make_failure(
        EngineFailureCode::AlreadyTerminal,
        client_order_id,
        "order is no longer active",
        exchange_order_id,
        history->second.state
    )};
  }
  return LocateResult{std::nullopt};
}

}  // namespace robust_execution::exchange
