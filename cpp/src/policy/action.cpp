#include "robust_execution/policy/action.hpp"

#include "robust_execution/policy/observation.hpp"
#include "robust_execution/policy/state.hpp"

#include <algorithm>
#include <cstdint>
#include <limits>
#include <numeric>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <utility>

namespace robust_execution::policy {
namespace {

#if defined(__SIZEOF_INT128__)
__extension__ using Uint128 = unsigned __int128;
#endif

void issue(
    ActionValidationResult& result,
    ActionValidationCode code,
    std::string detail
) {
  result.issues.push_back(ActionValidationIssue{code, std::move(detail)});
}

bool contains_fraction(
    const std::vector<QuantityFraction>& allowed,
    const QuantityFraction& value
) {
  return std::find(allowed.begin(), allowed.end(), value) != allowed.end();
}

bool contains_offset(
    const std::vector<model::TickOffset>& allowed,
    model::TickOffset value
) {
  return std::find(allowed.begin(), allowed.end(), value) != allowed.end();
}

std::optional<model::QuantityLots> fraction_quantity(
    model::QuantityLots remaining,
    QuantityFraction fraction,
    LotRoundingPolicy rounding
) {
  if (!fraction.valid()) {
    return std::nullopt;
  }
#if defined(__SIZEOF_INT128__)
  const auto product = static_cast<Uint128>(remaining.value()) *
                       static_cast<Uint128>(fraction.numerator);
  const auto denominator = static_cast<Uint128>(fraction.denominator);
  auto quotient = product / denominator;
  const auto remainder = product % denominator;
  if (rounding == LotRoundingPolicy::Ceiling && remainder != 0U) {
    ++quotient;
  } else if (rounding == LotRoundingPolicy::Nearest && remainder * 2U >= denominator) {
    ++quotient;
  }
  if (quotient > static_cast<Uint128>(std::numeric_limits<std::uint64_t>::max())) {
    return std::nullopt;
  }
  return model::QuantityLots{static_cast<std::uint64_t>(quotient)};
#else
  if (fraction.numerator != 0U &&
      remaining.value() > std::numeric_limits<std::uint64_t>::max() / fraction.numerator) {
    return std::nullopt;
  }
  const auto product = remaining.value() * fraction.numerator;
  auto quotient = product / fraction.denominator;
  const auto remainder = product % fraction.denominator;
  if (rounding == LotRoundingPolicy::Ceiling && remainder != 0U) {
    ++quotient;
  } else if (rounding == LotRoundingPolicy::Nearest &&
             remainder >= (fraction.denominator + 1U) / 2U) {
    ++quotient;
  }
  return model::QuantityLots{quotient};
#endif
}

std::optional<model::PriceTicks> reference_price(
    const PolicyObservation& observation,
    model::Side side,
    LimitReference reference
) {
  if (reference == LimitReference::SameSideBest) {
    return side == model::Side::Buy ? observation.best_bid() : observation.best_ask();
  }
  return side == model::Side::Buy ? observation.best_ask() : observation.best_bid();
}

bool marketable(
    const PolicyObservation& observation,
    model::Side side,
    model::PriceTicks price
) {
  if (side == model::Side::Buy) {
    const auto ask = observation.best_ask();
    return ask.has_value() && price.value() >= ask->value();
  }
  const auto bid = observation.best_bid();
  return bid.has_value() && price.value() <= bid->value();
}

std::optional<model::PriceTicks> validate_placement(
    ActionValidationResult& result,
    const PolicyEnvironment& environment,
    const PolicyObservation& observation,
    model::Side side,
    const std::optional<LimitPlacement>& placement,
    bool post_only
) {
  if (!placement.has_value()) {
    issue(result, ActionValidationCode::InvalidLimitPlacement, "limit action requires a placement");
    return std::nullopt;
  }
  if (!contains_offset(environment.allowed_tick_offsets, placement->offset)) {
    issue(result, ActionValidationCode::TickOffsetNotAllowed, "tick offset is not predeclared");
    return std::nullopt;
  }
  const auto reference = reference_price(observation, side, placement->reference);
  if (!reference.has_value()) {
    issue(result, ActionValidationCode::MissingReferencePrice, "selected quote reference is unavailable");
    return std::nullopt;
  }
  const auto price = model::checked_add(*reference, placement->offset);
  if (!price.has_value() || price->value() <= 0) {
    issue(result, ActionValidationCode::InvalidLimitPlacement, "placement produces an invalid price");
    return std::nullopt;
  }
  const bool crosses = marketable(observation, side, *price);
  if (crosses && !environment.allow_marketable_limits) {
    issue(result, ActionValidationCode::MarketableLimitDisabled, "marketable limit orders are disabled");
    return std::nullopt;
  }
  if (crosses && post_only) {
    issue(result, ActionValidationCode::InvalidLimitPlacement, "post-only placement would cross the book");
    return std::nullopt;
  }
  return price;
}

std::optional<model::QuantityLots> validate_fraction(
    ActionValidationResult& result,
    const PolicyEnvironment& environment,
    const ParentOrderSnapshot& parent,
    QuantityFraction fraction
) {
  if (!fraction.valid()) {
    issue(result, ActionValidationCode::InvalidQuantityFraction, "quantity fraction must lie in (0, 1]");
    return std::nullopt;
  }
  if (!contains_fraction(environment.allowed_quantity_fractions, fraction)) {
    issue(result, ActionValidationCode::QuantityFractionNotAllowed, "quantity fraction is not predeclared");
    return std::nullopt;
  }
  const auto quantity = fraction_quantity(parent.remaining_quantity, fraction, environment.lot_rounding);
  if (!quantity.has_value()) {
    issue(result, ActionValidationCode::InvalidQuantityFraction, "quantity fraction cannot be evaluated safely");
    return std::nullopt;
  }
  if (quantity->is_zero()) {
    issue(result, ActionValidationCode::QuantityRoundsToZero, "quantity fraction rounds to zero lots");
    return std::nullopt;
  }
  if (quantity->value() > parent.remaining_quantity.value()) {
    issue(result, ActionValidationCode::QuantityExceedsRemaining, "child quantity exceeds parent residual");
    return std::nullopt;
  }
  return quantity;
}

void validate_common(
    ActionValidationResult& result,
    const PolicyAction& action,
    const PolicyObservation& observation,
    PolicyActionKind kind
) {
  if (!action.decision_id.valid() || action.decision_id != observation.decision_id()) {
    issue(result, ActionValidationCode::InvalidDecision, "action and observation decision IDs differ");
  }
  if (action.decision_time.domain() != observation.decision_time().domain()) {
    issue(result, ActionValidationCode::MixedClockDomain, "action and observation clocks differ");
  } else if (action.decision_time.value() != observation.decision_time().value()) {
    issue(result, ActionValidationCode::InvalidDecision, "action time differs from observation time");
  }
  if (kind != PolicyActionKind::NoAction) {
    if (observation.parent().status == ParentOrderStatus::Completed ||
        observation.parent().remaining_quantity.is_zero()) {
      issue(result, ActionValidationCode::ParentAlreadyComplete, "parent order has no residual inventory");
    } else if (observation.parent().status == ParentOrderStatus::Pending) {
      issue(result, ActionValidationCode::ParentNotActive, "parent order has not started");
    }
  }
}

}  // namespace

PolicyActionKind action_kind(const PolicyActionPayload& payload) noexcept {
  return std::visit(
      [](const auto& value) {
        using Payload = std::decay_t<decltype(value)>;
        if constexpr (std::is_same_v<Payload, NoAction>) {
          return PolicyActionKind::NoAction;
        } else if constexpr (std::is_same_v<Payload, SubmitChildAction>) {
          return PolicyActionKind::Submit;
        } else if constexpr (std::is_same_v<Payload, CancelChildAction>) {
          return PolicyActionKind::Cancel;
        } else {
          static_assert(std::is_same_v<Payload, ReplaceChildAction>);
          return PolicyActionKind::Replace;
        }
      },
      payload
  );
}

ActionValidator::ActionValidator(PolicyEnvironment environment)
    : environment_(std::move(environment)) {
  if (!environment_.strategy_id.valid() || !environment_.instrument.venue.valid() ||
      !environment_.instrument.instrument.valid() || environment_.maximum_live_children == 0U ||
      environment_.maximum_commands_per_decision == 0U ||
      environment_.allowed_quantity_fractions.empty()) {
    throw std::invalid_argument("action validator requires a complete policy environment");
  }
  for (const auto& fraction : environment_.allowed_quantity_fractions) {
    if (!fraction.valid()) {
      throw std::invalid_argument("allowed quantity fractions must lie in (0, 1]");
    }
  }
}

ActionValidationResult ActionValidator::validate(
    const PolicyAction& action,
    const PolicyObservation& observation,
    const ExecutionState& state
) const {
  ActionValidationResult result;
  const auto kind = action_kind(action.payload);
  validate_common(result, action, observation, kind);
  if (!same_policy_environment(environment_, observation.environment())) {
    issue(result, ActionValidationCode::InvalidDecision, "validator and observation environments differ");
  }

  if (state.parent_definition().parent_order_id != observation.parent().parent_order_id ||
      !same_policy_environment(state.environment(), observation.environment())) {
    issue(result, ActionValidationCode::InvalidDecision, "execution state and observation differ");
  }

  if (kind != PolicyActionKind::NoAction && observation.pending_command_count() != 0U) {
    issue(result, ActionValidationCode::PendingCommandConflict, "another child command is pending");
  }
  if (!result.issues.empty()) {
    return result;
  }

  ValidatedPolicyAction validated{
      action.decision_id,
      action.decision_time,
      kind,
      std::string{to_string(kind)},
      {},
      model::QuantityLots{0U},
  };

  std::visit(
      [&](const auto& value) {
        using Payload = std::decay_t<decltype(value)>;
        if constexpr (std::is_same_v<Payload, NoAction>) {
          return;
        } else if constexpr (std::is_same_v<Payload, SubmitChildAction>) {
          if (!value.client_order_id.valid()) {
            issue(result, ActionValidationCode::InvalidClientOrderId, "submit requires a valid client order ID");
            return;
          }
          if (state.knows_client_order_id(value.client_order_id)) {
            issue(result, ActionValidationCode::DuplicateClientOrderId, "client order ID was already used");
            return;
          }
          if (observation.active_orders().size() >= environment_.maximum_live_children) {
            issue(result, ActionValidationCode::TooManyLiveChildren, "live-child limit would be exceeded");
            return;
          }
          const auto quantity = validate_fraction(
              result,
              environment_,
              observation.parent(),
              value.quantity_fraction
          );
          if (!quantity.has_value()) {
            return;
          }
          std::optional<model::PriceTicks> price;
          if (value.order_type == model::OrderType::Market) {
            if (!environment_.allow_market_orders) {
              issue(result, ActionValidationCode::MarketOrderDisabled, "market orders are disabled");
              return;
            }
            if (value.placement.has_value()) {
              issue(result, ActionValidationCode::InvalidLimitPlacement, "market order cannot contain a limit placement");
              return;
            }
            if (value.post_only) {
              issue(result, ActionValidationCode::PostOnlyRequiresLimit, "post-only requires a limit order");
              return;
            }
            if (value.time_in_force != model::TimeInForce::ImmediateOrCancel) {
              issue(result, ActionValidationCode::UnsupportedTimeInForce, "market order must be immediate-or-cancel");
              return;
            }
          } else {
            price = validate_placement(
                result,
                environment_,
                observation,
                observation.parent().side,
                value.placement,
                value.post_only
            );
            if (!price.has_value()) {
              return;
            }
            if (value.post_only && !environment_.allow_post_only) {
              issue(result, ActionValidationCode::PostOnlyRequiresLimit, "post-only is disabled");
              return;
            }
            if (value.post_only && value.time_in_force != model::TimeInForce::GoodTilCancelled) {
              issue(result, ActionValidationCode::UnsupportedTimeInForce, "post-only order must be GTC");
              return;
            }
          }
          validated.commands.emplace_back(model::OrderSubmit{
              observation.parent().parent_order_id,
              value.client_order_id,
              action.decision_id,
              observation.parent().side,
              value.order_type,
              value.time_in_force,
              *quantity,
              price,
              value.post_only,
              action.decision_time,
              action.decision_time,
              action.decision_time,
          });
          validated.reserved_quantity = *quantity;
        } else if constexpr (std::is_same_v<Payload, CancelChildAction>) {
          if (value.client_order_ids.empty() ||
              value.client_order_ids.size() > environment_.maximum_commands_per_decision) {
            issue(result, ActionValidationCode::UnknownChildOrder, "cancel list is empty or exceeds the command limit");
            return;
          }
          std::set<std::uint64_t> unique;
          for (const auto client_id : value.client_order_ids) {
            if (!unique.insert(client_id.value()).second) {
              issue(result, ActionValidationCode::DuplicateClientOrderId, "cancel list contains a duplicate client ID");
              return;
            }
            const auto child = state.child_order(client_id);
            if (!child.has_value()) {
              issue(result, ActionValidationCode::UnknownChildOrder, "cancel references an unknown child order");
              return;
            }
            if (!child->acknowledged_active() || !child->exchange_order_id.has_value()) {
              issue(result, ActionValidationCode::ChildOrderNotActive, "cancel requires an acknowledged active child");
              return;
            }
            validated.commands.emplace_back(model::CancelRequest{
                child->client_order_id,
                *child->exchange_order_id,
                action.decision_id,
                action.decision_time,
                action.decision_time,
                action.decision_time,
            });
          }
        } else {
          static_assert(std::is_same_v<Payload, ReplaceChildAction>);
          const auto child = state.child_order(value.client_order_id);
          if (!child.has_value()) {
            issue(result, ActionValidationCode::UnknownChildOrder, "replace references an unknown child order");
            return;
          }
          if (!child->acknowledged_active() || !child->exchange_order_id.has_value()) {
            issue(result, ActionValidationCode::ChildOrderNotActive, "replace requires an acknowledged active child");
            return;
          }
          if (!value.replacement_client_order_id.valid()) {
            issue(result, ActionValidationCode::InvalidClientOrderId, "replacement client order ID is invalid");
            return;
          }
          if (state.knows_client_order_id(value.replacement_client_order_id)) {
            issue(result, ActionValidationCode::DuplicateClientOrderId, "replacement client order ID was already used");
            return;
          }
          const auto quantity = validate_fraction(
              result,
              environment_,
              observation.parent(),
              value.quantity_fraction
          );
          if (!quantity.has_value()) {
            return;
          }
          const auto price = validate_placement(
              result,
              environment_,
              observation,
              observation.parent().side,
              value.placement,
              child->post_only
          );
          if (!price.has_value()) {
            return;
          }
          validated.commands.emplace_back(model::ReplaceRequest{
              child->client_order_id,
              *child->exchange_order_id,
              value.replacement_client_order_id,
              action.decision_id,
              *quantity,
              price,
              action.decision_time,
              action.decision_time,
              action.decision_time,
          });
          validated.reserved_quantity = *quantity;
        }
      },
      action.payload
  );

  if (!result.issues.empty()) {
    return result;
  }
  if (validated.commands.size() > environment_.maximum_commands_per_decision) {
    issue(result, ActionValidationCode::PendingCommandConflict, "validated action exceeds command limit");
    return result;
  }
  result.action = std::move(validated);
  return result;
}

const PolicyEnvironment& ActionValidator::environment() const noexcept { return environment_; }

std::string canonical_action(const ValidatedPolicyAction& action) {
  std::ostringstream output;
  output << action.decision_id.value() << '|' << static_cast<unsigned>(action.decision_time.domain())
         << '|' << action.decision_time.value() << '|' << to_string(action.kind) << '|'
         << action.action_name.size() << ':' << action.action_name << '|' << action.commands.size()
         << '|' << action.reserved_quantity.value() << '|';
  for (const auto& command : action.commands) {
    std::visit(
        [&output](const auto& value) {
          using Command = std::decay_t<decltype(value)>;
          if constexpr (std::is_same_v<Command, model::OrderSubmit>) {
            output << "submit|" << value.parent_order_id.value() << '|'
                   << value.client_order_id.value() << '|' << static_cast<unsigned>(value.side) << '|'
                   << static_cast<unsigned>(value.order_type) << '|'
                   << static_cast<unsigned>(value.time_in_force) << '|' << value.quantity.value()
                   << '|';
            if (value.limit_price.has_value()) {
              output << value.limit_price->value();
            }
            output << '|' << value.post_only << '|';
          } else if constexpr (std::is_same_v<Command, model::CancelRequest>) {
            output << "cancel|" << value.client_order_id.value() << '|'
                   << value.exchange_order_id.value() << '|';
          } else {
            static_assert(std::is_same_v<Command, model::ReplaceRequest>);
            output << "replace|" << value.client_order_id.value() << '|'
                   << value.exchange_order_id.value() << '|'
                   << value.replacement_client_order_id.value() << '|'
                   << value.new_quantity.value() << '|';
            if (value.new_limit_price.has_value()) {
              output << value.new_limit_price->value();
            }
            output << '|';
          }
        },
        command
    );
  }
  return output.str();
}

}  // namespace robust_execution::policy
