#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <variant>
#include <vector>

#include "robust_execution/model/model.hpp"

namespace robust_execution::synthetic {

namespace model = robust_execution::model;

inline constexpr std::uint32_t kProbabilityScalePpm = 1'000'000U;

/** Evidence category for a synthetic scenario. Step 9 deliberately does not claim calibration. */
enum class ScenarioClass : std::uint8_t {
  DesignedSynthetic,
  AdversarialStress,
};

[[nodiscard]] constexpr std::string_view to_string(ScenarioClass value) noexcept {
  switch (value) {
    case ScenarioClass::DesignedSynthetic:
      return "designed_synthetic";
    case ScenarioClass::AdversarialStress:
      return "adversarial_stress";
  }
  return "unknown";
}

enum class SyntheticActionKind : std::uint8_t {
  InitialLiquidity,
  LimitAdd,
  AggressiveMarket,
  Cancel,
  ReferenceMove,
  ShockApplied,
};

[[nodiscard]] constexpr std::string_view to_string(SyntheticActionKind value) noexcept {
  switch (value) {
    case SyntheticActionKind::InitialLiquidity:
      return "initial_liquidity";
    case SyntheticActionKind::LimitAdd:
      return "limit_add";
    case SyntheticActionKind::AggressiveMarket:
      return "aggressive_market";
    case SyntheticActionKind::Cancel:
      return "cancel";
    case SyntheticActionKind::ReferenceMove:
      return "reference_move";
    case SyntheticActionKind::ShockApplied:
      return "shock_applied";
  }
  return "unknown";
}

struct FeeScheduleConfig {
  model::FeeScheduleId fee_schedule_id{"synthetic-fees-v1"};
  model::QuoteAtoms maker_atoms_per_lot{};
  model::QuoteAtoms taker_atoms_per_lot{};

  [[nodiscard]] friend bool operator==(const FeeScheduleConfig&, const FeeScheduleConfig&) =
      default;
};

/**
 * A regime uses a discrete-time, self-exciting Bernoulli process. Probabilities are per grid step
 * and expressed in parts per million. Excitation is deterministic integer state, not a claim that
 * the process is a calibrated Hawkes model.
 */
struct RegimeConfig {
  std::string regime_id;
  ScenarioClass scenario_class{ScenarioClass::DesignedSynthetic};
  std::uint64_t steps{0U};
  std::uint32_t limit_add_probability_ppm{0U};
  std::uint32_t market_order_probability_ppm{0U};
  std::uint32_t cancel_probability_ppm{0U};
  std::uint32_t reference_move_probability_ppm{0U};
  std::uint32_t buy_probability_ppm{500'000U};
  std::uint32_t excitation_increment_ppm{0U};
  std::uint32_t excitation_decay_ppm{kProbabilityScalePpm};
  std::uint32_t excitation_cap_ppm{0U};
  std::uint32_t resilience_boost_cap_ppm{0U};
  std::uint32_t half_spread_ticks{1U};
  std::uint32_t visible_levels_per_side{5U};
  std::uint64_t target_lots_per_level{10U};
  std::uint64_t minimum_order_lots{1U};
  std::uint64_t maximum_order_lots{5U};
  std::uint32_t maximum_reference_jump_ticks{1U};
  std::int64_t impact_microticks_per_lot{0};
  std::uint32_t impact_decay_ppm{kProbabilityScalePpm};

  [[nodiscard]] friend bool operator==(const RegimeConfig&, const RegimeConfig&) = default;
};

/** Multipliers are ppm and are active on [start_step, start_step + duration_steps). */
struct ShockConfig {
  std::string shock_id;
  ScenarioClass scenario_class{ScenarioClass::AdversarialStress};
  std::uint64_t start_step{0U};
  std::uint64_t duration_steps{0U};
  std::uint32_t liquidity_multiplier_ppm{kProbabilityScalePpm};
  std::uint32_t spread_multiplier_ppm{kProbabilityScalePpm};
  std::uint32_t volatility_multiplier_ppm{kProbabilityScalePpm};
  std::uint32_t market_order_multiplier_ppm{kProbabilityScalePpm};
  std::uint32_t cancel_multiplier_ppm{kProbabilityScalePpm};
  std::int32_t buy_probability_shift_ppm{0};
  std::int64_t one_time_reference_jump_ticks{0};

  [[nodiscard]] friend bool operator==(const ShockConfig&, const ShockConfig&) = default;
};

struct SyntheticMarketConfig {
  std::string schema_id{"synthetic-market-config-v1"};
  std::string scenario_id;
  ScenarioClass scenario_class{ScenarioClass::DesignedSynthetic};
  model::InstrumentDefinition instrument;
  model::RunId run_id{"synthetic-run"};
  std::uint64_t random_seed{0U};
  model::TimestampNs start_time{model::ClockDomain::Simulation, 0};
  std::int64_t grid_step_ns{100'000};
  model::PriceTicks initial_reference_price{};
  std::vector<RegimeConfig> regimes;
  std::vector<ShockConfig> shocks;
  FeeScheduleConfig fees;
  std::uint64_t first_client_order_id{1U};
  std::uint64_t first_decision_id{1U};

};

struct SyntheticAction {
  std::uint64_t sequence{0U};
  std::uint64_t global_step{0U};
  model::TimestampNs time{};
  std::string regime_id;
  SyntheticActionKind kind{SyntheticActionKind::LimitAdd};
  std::optional<model::Side> side;
  model::QuantityLots quantity{};
  std::optional<model::PriceTicks> price;
  std::optional<model::ClientOrderId> client_order_id;
  std::optional<model::ExchangeOrderId> exchange_order_id;
  std::optional<std::string> shock_id;
  std::string detail;
};

struct SyntheticTradeRecord {
  std::uint64_t sequence{0U};
  std::uint64_t global_step{0U};
  model::TimestampNs time{};
  std::string regime_id;
  model::Trade trade;
  model::QuantityLots maker_quantity{};
  model::QuantityLots taker_quantity{};
  model::QuoteAtoms maker_fee{};
  model::QuoteAtoms taker_fee{};
};

struct SyntheticStepSummary {
  std::uint64_t global_step{0U};
  model::TimestampNs time{};
  std::string regime_id;
  model::PriceTicks reference_price{};
  std::optional<model::PriceTicks> best_bid;
  std::optional<model::PriceTicks> best_ask;
  model::QuantityLots visible_bid_lots{};
  model::QuantityLots visible_ask_lots{};
  std::uint64_t active_orders{0U};
  std::int64_t impact_microticks{0};
  std::uint32_t limit_excitation_ppm{0U};
  std::uint32_t market_excitation_ppm{0U};
  std::uint32_t cancel_excitation_ppm{0U};
};

struct SyntheticSummary {
  std::uint64_t total_steps{0U};
  std::uint64_t limit_submissions{0U};
  std::uint64_t market_submissions{0U};
  std::uint64_t cancellations{0U};
  std::uint64_t reference_moves{0U};
  std::uint64_t shocks_applied{0U};
  std::uint64_t trades{0U};
  std::uint64_t rejected_commands{0U};
  model::QuantityLots executed_lots{};
  model::QuoteAtoms maker_fees{};
  model::QuoteAtoms taker_fees{};
  model::PriceTicks final_reference_price{};
  std::optional<model::PriceTicks> final_best_bid;
  std::optional<model::PriceTicks> final_best_ask;
};

struct SyntheticTape {
  SyntheticMarketConfig config;
  std::vector<SyntheticAction> actions;
  std::vector<SyntheticTradeRecord> trades;
  std::vector<SyntheticStepSummary> steps;
  SyntheticSummary summary;
  std::string config_sha256;
  std::string canonical_text;
  std::string tape_sha256;
  std::string manifest_json;
  std::string manifest_sha256;
};

struct ValidationIssue {
  std::string code;
  std::string detail;
};

[[nodiscard]] std::vector<ValidationIssue> validate(const SyntheticMarketConfig& config);
[[nodiscard]] std::vector<ValidationIssue> validate_tape(const SyntheticTape& tape);
[[nodiscard]] bool has_errors(const std::vector<ValidationIssue>& issues) noexcept;
[[nodiscard]] std::string canonical_config(const SyntheticMarketConfig& config);
[[nodiscard]] std::string canonical_tape(const SyntheticTape& tape);
[[nodiscard]] std::string manifest_json(const SyntheticTape& tape);

}  // namespace robust_execution::synthetic
