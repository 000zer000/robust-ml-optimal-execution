#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include "robust_execution/model/model.hpp"

namespace robust_execution::policy {

namespace model = robust_execution::model;

enum class ParentOrderStatus : std::uint8_t {
  Pending,
  Active,
  TerminalCompletionPending,
  Completed,
};

enum class PolicyActionKind : std::uint8_t {
  NoAction,
  Submit,
  Cancel,
  Replace,
};

enum class LimitReference : std::uint8_t {
  SameSideBest,
  OppositeSideBest,
};

enum class LotRoundingPolicy : std::uint8_t {
  Floor,
  Nearest,
  Ceiling,
};

enum class ActionValidationCode : std::uint8_t {
  InvalidDecision,
  ParentNotActive,
  ParentAlreadyComplete,
  InvalidClientOrderId,
  DuplicateClientOrderId,
  InvalidQuantityFraction,
  QuantityFractionNotAllowed,
  QuantityRoundsToZero,
  QuantityExceedsRemaining,
  MissingReferencePrice,
  InvalidLimitPlacement,
  TickOffsetNotAllowed,
  MarketOrderDisabled,
  MarketableLimitDisabled,
  PostOnlyRequiresLimit,
  UnsupportedTimeInForce,
  TooManyLiveChildren,
  UnknownChildOrder,
  ChildOrderNotActive,
  PendingCommandConflict,
  MixedClockDomain,
};

enum class TerminalPlanKind : std::uint8_t {
  None,
  AwaitPendingCommands,
  CancelActiveChildren,
  SubmitAggressiveResidual,
  RequiresExplicitFallback,
  Complete,
};

[[nodiscard]] constexpr std::string_view to_string(ParentOrderStatus value) noexcept {
  switch (value) {
    case ParentOrderStatus::Pending:
      return "pending";
    case ParentOrderStatus::Active:
      return "active";
    case ParentOrderStatus::TerminalCompletionPending:
      return "terminal_completion_pending";
    case ParentOrderStatus::Completed:
      return "completed";
  }
  return "unknown";
}

[[nodiscard]] constexpr std::string_view to_string(PolicyActionKind value) noexcept {
  switch (value) {
    case PolicyActionKind::NoAction:
      return "no_action";
    case PolicyActionKind::Submit:
      return "submit";
    case PolicyActionKind::Cancel:
      return "cancel";
    case PolicyActionKind::Replace:
      return "replace";
  }
  return "unknown";
}

[[nodiscard]] constexpr std::string_view to_string(ActionValidationCode value) noexcept {
  switch (value) {
    case ActionValidationCode::InvalidDecision:
      return "invalid_decision";
    case ActionValidationCode::ParentNotActive:
      return "parent_not_active";
    case ActionValidationCode::ParentAlreadyComplete:
      return "parent_already_complete";
    case ActionValidationCode::InvalidClientOrderId:
      return "invalid_client_order_id";
    case ActionValidationCode::DuplicateClientOrderId:
      return "duplicate_client_order_id";
    case ActionValidationCode::InvalidQuantityFraction:
      return "invalid_quantity_fraction";
    case ActionValidationCode::QuantityFractionNotAllowed:
      return "quantity_fraction_not_allowed";
    case ActionValidationCode::QuantityRoundsToZero:
      return "quantity_rounds_to_zero";
    case ActionValidationCode::QuantityExceedsRemaining:
      return "quantity_exceeds_remaining";
    case ActionValidationCode::MissingReferencePrice:
      return "missing_reference_price";
    case ActionValidationCode::InvalidLimitPlacement:
      return "invalid_limit_placement";
    case ActionValidationCode::TickOffsetNotAllowed:
      return "tick_offset_not_allowed";
    case ActionValidationCode::MarketOrderDisabled:
      return "market_order_disabled";
    case ActionValidationCode::MarketableLimitDisabled:
      return "marketable_limit_disabled";
    case ActionValidationCode::PostOnlyRequiresLimit:
      return "post_only_requires_limit";
    case ActionValidationCode::UnsupportedTimeInForce:
      return "unsupported_time_in_force";
    case ActionValidationCode::TooManyLiveChildren:
      return "too_many_live_children";
    case ActionValidationCode::UnknownChildOrder:
      return "unknown_child_order";
    case ActionValidationCode::ChildOrderNotActive:
      return "child_order_not_active";
    case ActionValidationCode::PendingCommandConflict:
      return "pending_command_conflict";
    case ActionValidationCode::MixedClockDomain:
      return "mixed_clock_domain";
  }
  return "unknown";
}

[[nodiscard]] constexpr std::string_view to_string(TerminalPlanKind value) noexcept {
  switch (value) {
    case TerminalPlanKind::None:
      return "none";
    case TerminalPlanKind::AwaitPendingCommands:
      return "await_pending_commands";
    case TerminalPlanKind::CancelActiveChildren:
      return "cancel_active_children";
    case TerminalPlanKind::SubmitAggressiveResidual:
      return "submit_aggressive_residual";
    case TerminalPlanKind::RequiresExplicitFallback:
      return "requires_explicit_fallback";
    case TerminalPlanKind::Complete:
      return "complete";
  }
  return "unknown";
}

struct QuantityFraction {
  std::uint64_t numerator{1U};
  std::uint64_t denominator{1U};

  [[nodiscard]] constexpr bool valid() const noexcept {
    return numerator > 0U && denominator > 0U && numerator <= denominator;
  }

  [[nodiscard]] friend constexpr auto operator<=>(
      const QuantityFraction&,
      const QuantityFraction&
  ) = default;
};

struct LimitPlacement {
  LimitReference reference{LimitReference::SameSideBest};
  model::TickOffset offset{};

  [[nodiscard]] friend constexpr auto operator<=>(
      const LimitPlacement&,
      const LimitPlacement&
  ) = default;
};

struct ParentOrderDefinition {
  model::ParentOrderId parent_order_id{};
  model::Side side{model::Side::Buy};
  model::QuantityLots total_quantity{};
  model::TimestampNs start_time{};
  model::TimestampNs end_time{};
  model::PriceTicks arrival_price{};
  std::string terminal_rule_id;
};

struct PolicyEnvironment {
  model::InstrumentDefinition instrument;
  model::StrategyId strategy_id;
  model::FeeScheduleId fee_schedule_id;
  model::LatencyModelId latency_model_id;
  std::int64_t decision_interval_ns{100'000'000};
  std::size_t top_levels{5U};
  std::size_t maximum_recent_trades{64U};
  std::size_t maximum_live_children{1U};
  std::size_t maximum_commands_per_decision{1U};
  std::vector<QuantityFraction> allowed_quantity_fractions;
  std::vector<model::TickOffset> allowed_tick_offsets;
  LotRoundingPolicy lot_rounding{LotRoundingPolicy::Floor};
  bool allow_market_orders{true};
  bool allow_marketable_limits{true};
  bool allow_post_only{true};
};

struct TerminalRuleConfig {
  std::string rule_id;
  std::size_t maximum_aggressive_attempts{1U};
  bool allow_explicit_fallback{true};
};

[[nodiscard]] inline bool same_instrument_definition(
    const model::InstrumentDefinition& lhs,
    const model::InstrumentDefinition& rhs
) {
  return lhs.schema == rhs.schema && lhs.venue == rhs.venue &&
         lhs.instrument == rhs.instrument && lhs.base_asset == rhs.base_asset &&
         lhs.quote_asset == rhs.quote_asset && lhs.tick_size == rhs.tick_size &&
         lhs.lot_size == rhs.lot_size && lhs.quote_atom_size == rhs.quote_atom_size &&
         lhs.minimum_order_quantity == rhs.minimum_order_quantity &&
         lhs.maximum_order_quantity == rhs.maximum_order_quantity &&
         lhs.metadata_version == rhs.metadata_version;
}

[[nodiscard]] inline bool same_policy_environment(
    const PolicyEnvironment& lhs,
    const PolicyEnvironment& rhs
) {
  return same_instrument_definition(lhs.instrument, rhs.instrument) &&
         lhs.strategy_id == rhs.strategy_id && lhs.fee_schedule_id == rhs.fee_schedule_id &&
         lhs.latency_model_id == rhs.latency_model_id &&
         lhs.decision_interval_ns == rhs.decision_interval_ns &&
         lhs.top_levels == rhs.top_levels &&
         lhs.maximum_recent_trades == rhs.maximum_recent_trades &&
         lhs.maximum_live_children == rhs.maximum_live_children &&
         lhs.maximum_commands_per_decision == rhs.maximum_commands_per_decision &&
         lhs.allowed_quantity_fractions == rhs.allowed_quantity_fractions &&
         lhs.allowed_tick_offsets == rhs.allowed_tick_offsets &&
         lhs.lot_rounding == rhs.lot_rounding &&
         lhs.allow_market_orders == rhs.allow_market_orders &&
         lhs.allow_marketable_limits == rhs.allow_marketable_limits &&
         lhs.allow_post_only == rhs.allow_post_only;
}

}  // namespace robust_execution::policy
