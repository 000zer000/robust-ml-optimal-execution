#include "robust_execution/synthetic/types.hpp"

#include "robust_execution/util/sha256.hpp"

#include <algorithm>
#include <cstdint>
#include <limits>
#include <sstream>
#include <string>
#include <unordered_set>

namespace robust_execution::synthetic {
namespace {

void add_issue(
    std::vector<ValidationIssue>& issues,
    std::string code,
    std::string detail
) {
  issues.push_back(ValidationIssue{std::move(code), std::move(detail)});
}

bool valid_probability(std::uint32_t value) noexcept {
  return value <= kProbabilityScalePpm;
}

std::string escape_json(std::string_view input) {
  std::ostringstream output;
  for (const char character : input) {
    switch (character) {
      case '\\':
        output << "\\\\";
        break;
      case '"':
        output << "\\\"";
        break;
      case '\n':
        output << "\\n";
        break;
      case '\r':
        output << "\\r";
        break;
      case '\t':
        output << "\\t";
        break;
      default:
        output << character;
        break;
    }
  }
  return output.str();
}

void validate_regime(
    const RegimeConfig& regime,
    std::vector<ValidationIssue>& issues
) {
  if (regime.regime_id.empty()) {
    add_issue(issues, "regime_id", "regime_id must be non-empty");
  }
  if (regime.steps == 0U) {
    add_issue(issues, "regime_steps", "every regime must contain at least one step");
  }
  const std::pair<std::string_view, std::uint32_t> probabilities[] = {
      {"limit_add_probability_ppm", regime.limit_add_probability_ppm},
      {"market_order_probability_ppm", regime.market_order_probability_ppm},
      {"cancel_probability_ppm", regime.cancel_probability_ppm},
      {"reference_move_probability_ppm", regime.reference_move_probability_ppm},
      {"buy_probability_ppm", regime.buy_probability_ppm},
      {"excitation_increment_ppm", regime.excitation_increment_ppm},
      {"excitation_decay_ppm", regime.excitation_decay_ppm},
      {"excitation_cap_ppm", regime.excitation_cap_ppm},
      {"resilience_boost_cap_ppm", regime.resilience_boost_cap_ppm},
      {"impact_decay_ppm", regime.impact_decay_ppm},
  };
  for (const auto& [name, value] : probabilities) {
    if (!valid_probability(value)) {
      add_issue(issues, std::string{name}, std::string{name} + " must be in [0, 1,000,000]");
    }
  }
  if (regime.half_spread_ticks == 0U) {
    add_issue(issues, "half_spread_ticks", "half_spread_ticks must be positive");
  }
  if (regime.visible_levels_per_side == 0U || regime.visible_levels_per_side > 1'000U) {
    add_issue(
        issues,
        "visible_levels_per_side",
        "visible_levels_per_side must be in [1, 1000]"
    );
  }
  if (regime.target_lots_per_level == 0U) {
    add_issue(issues, "target_lots_per_level", "target_lots_per_level must be positive");
  }
  if (regime.minimum_order_lots == 0U ||
      regime.maximum_order_lots < regime.minimum_order_lots) {
    add_issue(
        issues,
        "order_lot_range",
        "synthetic order-lot range must be positive and ordered"
    );
  }
  if (regime.maximum_reference_jump_ticks == 0U) {
    add_issue(
        issues,
        "maximum_reference_jump_ticks",
        "maximum_reference_jump_ticks must be positive"
    );
  }
}

void validate_shock(
    const ShockConfig& shock,
    std::vector<ValidationIssue>& issues
) {
  if (shock.shock_id.empty()) {
    add_issue(issues, "shock_id", "shock_id must be non-empty");
  }
  if (shock.duration_steps == 0U) {
    add_issue(issues, "shock_duration", "shock duration must be positive");
  }
  const std::pair<std::string_view, std::uint32_t> multipliers[] = {
      {"liquidity_multiplier_ppm", shock.liquidity_multiplier_ppm},
      {"spread_multiplier_ppm", shock.spread_multiplier_ppm},
      {"volatility_multiplier_ppm", shock.volatility_multiplier_ppm},
      {"market_order_multiplier_ppm", shock.market_order_multiplier_ppm},
      {"cancel_multiplier_ppm", shock.cancel_multiplier_ppm},
  };
  for (const auto& [name, value] : multipliers) {
    if (value > 10U * kProbabilityScalePpm) {
      add_issue(
          issues,
          std::string{name},
          std::string{name} + " must not exceed 10x"
      );
    }
  }
  const auto shifted = static_cast<std::int64_t>(500'000) + shock.buy_probability_shift_ppm;
  if (shifted < -500'000 || shifted > 1'500'000) {
    add_issue(
        issues,
        "buy_probability_shift_ppm",
        "buy-probability shift is outside the supported range"
    );
  }
}

}  // namespace

std::vector<ValidationIssue> validate(const SyntheticMarketConfig& config) {
  std::vector<ValidationIssue> issues;
  if (config.schema_id != "synthetic-market-config-v1") {
    add_issue(issues, "schema_id", "unsupported synthetic-market schema_id");
  }
  if (config.scenario_id.empty()) {
    add_issue(issues, "scenario_id", "scenario_id must be non-empty");
  }
  if (!config.run_id.valid()) {
    add_issue(issues, "run_id", "run_id must be non-empty");
  }
  if (!config.instrument.venue.valid() || !config.instrument.instrument.valid()) {
    add_issue(issues, "instrument", "instrument venue and identifier must be non-empty");
  }
  if (!config.instrument.tick_size.valid() || !config.instrument.lot_size.valid() ||
      !config.instrument.quote_atom_size.valid()) {
    add_issue(issues, "instrument_increment", "instrument increments must be valid");
  }
  if (config.instrument.minimum_order_quantity.is_zero()) {
    add_issue(issues, "minimum_order_quantity", "instrument minimum order must be positive");
  }
  if (config.grid_step_ns <= 0) {
    add_issue(issues, "grid_step_ns", "grid_step_ns must be positive");
  }
  if (config.start_time.domain() != model::ClockDomain::Simulation) {
    add_issue(issues, "clock_domain", "synthetic generator requires simulation clock domain");
  }
  if (config.initial_reference_price.value() <= 0) {
    add_issue(issues, "initial_reference_price", "initial reference price must be positive");
  }
  if (config.regimes.empty()) {
    add_issue(issues, "regimes", "at least one regime is required");
  }
  if (!config.fees.fee_schedule_id.valid()) {
    add_issue(issues, "fee_schedule_id", "fee schedule identifier must be non-empty");
  }
  if (config.first_client_order_id == 0U || config.first_decision_id == 0U) {
    add_issue(issues, "identifier_start", "generated numeric identifiers must start above zero");
  }

  std::unordered_set<std::string> regime_ids;
  std::uint64_t total_steps = 0U;
  bool contains_adversarial_regime = false;
  for (const auto& regime : config.regimes) {
    validate_regime(regime, issues);
    contains_adversarial_regime = contains_adversarial_regime ||
                                  regime.scenario_class == ScenarioClass::AdversarialStress;
    if (regime.minimum_order_lots < config.instrument.minimum_order_quantity.value()) {
      add_issue(issues, "order_lot_range", "regime minimum is below the instrument minimum");
    }
    if (config.instrument.maximum_order_quantity.has_value() &&
        (regime.maximum_order_lots > config.instrument.maximum_order_quantity->value() ||
         regime.target_lots_per_level > config.instrument.maximum_order_quantity->value())) {
      add_issue(issues, "order_lot_range", "regime quantities exceed the instrument maximum");
    }
    if (regime.impact_microticks_per_lot < -1'000'000'000LL ||
        regime.impact_microticks_per_lot > 1'000'000'000LL) {
      add_issue(issues, "impact_microticks_per_lot", "impact magnitude exceeds the Step 9 safety bound");
    }
    if (!regime_ids.insert(regime.regime_id).second) {
      add_issue(issues, "duplicate_regime_id", "regime identifiers must be unique");
    }
    if (regime.steps > std::numeric_limits<std::uint64_t>::max() - total_steps) {
      add_issue(issues, "total_steps_overflow", "regime step total overflows uint64");
    } else {
      total_steps += regime.steps;
    }
  }

  std::unordered_set<std::string> shock_ids;
  for (const auto& shock : config.shocks) {
    validate_shock(shock, issues);
    if (!shock_ids.insert(shock.shock_id).second) {
      add_issue(issues, "duplicate_shock_id", "shock identifiers must be unique");
    }
    if (shock.start_step >= total_steps) {
      add_issue(issues, "shock_start", "shock start_step is outside the generated horizon");
    }
    if (shock.duration_steps > total_steps - std::min(shock.start_step, total_steps)) {
      add_issue(issues, "shock_horizon", "shock extends beyond the generated horizon");
    }
  }

  if (total_steps > 100'000'000U) {
    add_issue(issues, "total_steps", "Step 9 scenarios are capped at 100 million grid steps");
  }
  if (total_steps > (std::numeric_limits<std::uint64_t>::max() - config.first_client_order_id) / 3U ||
      total_steps > (std::numeric_limits<std::uint64_t>::max() - config.first_decision_id) / 3U) {
    add_issue(issues, "identifier_range", "generated identifiers could overflow the uint64 range");
  }
  if (config.scenario_class == ScenarioClass::DesignedSynthetic) {
    if (contains_adversarial_regime) {
      add_issue(issues, "scenario_class", "adversarial regimes require an adversarial_stress scenario");
    }
    for (const auto& shock : config.shocks) {
      if (shock.scenario_class == ScenarioClass::AdversarialStress) {
        add_issue(
            issues,
            "scenario_class",
            "a scenario containing adversarial shocks must be classified adversarial_stress"
        );
        break;
      }
    }
  }
  return issues;
}


std::vector<ValidationIssue> validate_tape(const SyntheticTape& tape) {
  auto issues = validate(tape.config);
  std::uint64_t expected_action_sequence = 1U;
  std::uint64_t limit_actions = 0U;
  std::uint64_t market_actions = 0U;
  std::uint64_t cancel_actions = 0U;
  std::uint64_t reference_actions = 0U;
  std::uint64_t shock_actions = 0U;
  std::optional<std::int64_t> previous_action_time;
  for (const auto& action : tape.actions) {
    if (action.sequence != expected_action_sequence++) {
      add_issue(issues, "action_sequence", "synthetic action sequence is not contiguous");
      break;
    }
    if (action.time.domain() != model::ClockDomain::Simulation ||
        (previous_action_time.has_value() && action.time.value() < *previous_action_time)) {
      add_issue(issues, "action_time", "synthetic action times must be nondecreasing simulation time");
      break;
    }
    previous_action_time = action.time.value();
    switch (action.kind) {
      case SyntheticActionKind::InitialLiquidity:
      case SyntheticActionKind::LimitAdd:
        ++limit_actions;
        break;
      case SyntheticActionKind::AggressiveMarket:
        ++market_actions;
        break;
      case SyntheticActionKind::Cancel:
        ++cancel_actions;
        break;
      case SyntheticActionKind::ReferenceMove:
        ++reference_actions;
        break;
      case SyntheticActionKind::ShockApplied:
        ++shock_actions;
        break;
    }
  }
  if (limit_actions != tape.summary.limit_submissions ||
      market_actions != tape.summary.market_submissions ||
      cancel_actions != tape.summary.cancellations ||
      reference_actions != tape.summary.reference_moves ||
      shock_actions != tape.summary.shocks_applied) {
    add_issue(issues, "action_summary", "synthetic action counts do not match the summary");
  }

  std::uint64_t expected_trade_sequence = 1U;
  model::QuantityLots executed{};
  model::QuoteAtoms maker_fees{};
  model::QuoteAtoms taker_fees{};
  for (const auto& trade : tape.trades) {
    if (trade.sequence != expected_trade_sequence++) {
      add_issue(issues, "trade_sequence", "synthetic trade sequence is not contiguous");
      break;
    }
    const auto next_executed = model::checked_add(executed, trade.trade.quantity);
    const auto next_maker = model::checked_add(maker_fees, trade.maker_fee);
    const auto next_taker = model::checked_add(taker_fees, trade.taker_fee);
    if (!next_executed.has_value() || !next_maker.has_value() || !next_taker.has_value()) {
      add_issue(issues, "trade_accounting", "synthetic trade aggregation overflowed");
      break;
    }
    executed = *next_executed;
    maker_fees = *next_maker;
    taker_fees = *next_taker;
  }
  if (tape.trades.size() != tape.summary.trades || executed != tape.summary.executed_lots ||
      maker_fees != tape.summary.maker_fees || taker_fees != tape.summary.taker_fees) {
    add_issue(issues, "trade_summary", "synthetic trade or fee summary is inconsistent");
  }

  if (tape.steps.size() != tape.summary.total_steps) {
    add_issue(issues, "step_summary", "synthetic step count does not match the summary");
  }
  for (std::size_t index = 0U; index < tape.steps.size(); ++index) {
    const auto& step = tape.steps[index];
    if (step.global_step != index || step.reference_price.value() <= 0) {
      add_issue(issues, "step_order", "synthetic step index or reference price is invalid");
      break;
    }
    if (step.best_bid.has_value() && step.best_ask.has_value() &&
        step.best_bid->value() >= step.best_ask->value()) {
      add_issue(issues, "crossed_book", "synthetic step contains a crossed book");
      break;
    }
  }

  const auto expected_config_hash = util::sha256_hex(canonical_config(tape.config));
  if (!tape.config_sha256.empty() && tape.config_sha256 != expected_config_hash) {
    add_issue(issues, "config_hash", "synthetic config hash is inconsistent");
  }
  if (!tape.canonical_text.empty() && tape.canonical_text != canonical_tape(tape)) {
    add_issue(issues, "canonical_tape", "stored canonical tape differs from regeneration");
  }
  if (!tape.tape_sha256.empty() && tape.tape_sha256 != util::sha256_hex(tape.canonical_text)) {
    add_issue(issues, "tape_hash", "synthetic tape hash is inconsistent");
  }
  if (!tape.manifest_json.empty() && tape.manifest_json != manifest_json(tape)) {
    add_issue(issues, "manifest", "stored synthetic manifest differs from regeneration");
  }
  if (!tape.manifest_sha256.empty() &&
      tape.manifest_sha256 != util::sha256_hex(tape.manifest_json)) {
    add_issue(issues, "manifest_hash", "synthetic manifest hash is inconsistent");
  }
  return issues;
}

bool has_errors(const std::vector<ValidationIssue>& issues) noexcept {
  return !issues.empty();
}

std::string canonical_config(const SyntheticMarketConfig& config) {
  std::ostringstream output;
  output << "schema=" << config.schema_id << '\n'
         << "scenario=" << config.scenario_id << '\n'
         << "class=" << to_string(config.scenario_class) << '\n'
         << "venue=" << config.instrument.venue.value() << '\n'
         << "instrument=" << config.instrument.instrument.value() << '\n'
         << "run=" << config.run_id.value() << '\n'
         << "seed=" << config.random_seed << '\n'
         << "start_ns=" << config.start_time.value() << '\n'
         << "grid_step_ns=" << config.grid_step_ns << '\n'
         << "initial_reference_ticks=" << config.initial_reference_price.value() << '\n'
         << "fee_schedule=" << config.fees.fee_schedule_id.value() << '\n'
         << "maker_atoms_per_lot=" << config.fees.maker_atoms_per_lot.value() << '\n'
         << "taker_atoms_per_lot=" << config.fees.taker_atoms_per_lot.value() << '\n';
  for (const auto& regime : config.regimes) {
    output << "regime|" << escape_json(regime.regime_id) << '|'
           << to_string(regime.scenario_class) << '|' << regime.steps << '|'
           << regime.limit_add_probability_ppm << '|'
           << regime.market_order_probability_ppm << '|'
           << regime.cancel_probability_ppm << '|'
           << regime.reference_move_probability_ppm << '|'
           << regime.buy_probability_ppm << '|'
           << regime.excitation_increment_ppm << '|'
           << regime.excitation_decay_ppm << '|'
           << regime.excitation_cap_ppm << '|'
           << regime.resilience_boost_cap_ppm << '|'
           << regime.half_spread_ticks << '|'
           << regime.visible_levels_per_side << '|'
           << regime.target_lots_per_level << '|'
           << regime.minimum_order_lots << '|'
           << regime.maximum_order_lots << '|'
           << regime.maximum_reference_jump_ticks << '|'
           << regime.impact_microticks_per_lot << '|'
           << regime.impact_decay_ppm << '\n';
  }
  for (const auto& shock : config.shocks) {
    output << "shock|" << escape_json(shock.shock_id) << '|'
           << to_string(shock.scenario_class) << '|'
           << shock.start_step << '|' << shock.duration_steps << '|'
           << shock.liquidity_multiplier_ppm << '|'
           << shock.spread_multiplier_ppm << '|'
           << shock.volatility_multiplier_ppm << '|'
           << shock.market_order_multiplier_ppm << '|'
           << shock.cancel_multiplier_ppm << '|'
           << shock.buy_probability_shift_ppm << '|'
           << shock.one_time_reference_jump_ticks << '\n';
  }
  return output.str();
}

}  // namespace robust_execution::synthetic
