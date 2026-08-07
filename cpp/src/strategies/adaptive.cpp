#include "robust_execution/strategies/adaptive.hpp"

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <limits>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace robust_execution::strategies {
namespace {

constexpr long double kEpsilon = 1.0e-15L;

long double clamp01(long double value) {
  return std::clamp(value, 0.0L, 1.0L);
}

bool finite(long double value) {
  return std::isfinite(value);
}

long double fraction_value(policy::QuantityFraction fraction) {
  if (!fraction.valid()) throw std::invalid_argument("quantity fraction must lie in (0,1]");
  return static_cast<long double>(fraction.numerator) / static_cast<long double>(fraction.denominator);
}

bool canonical_fraction(policy::QuantityFraction fraction) {
  return fraction.valid() && std::gcd(fraction.numerator, fraction.denominator) == 1U;
}

void validate_calibration(const NonMlCalibration& calibration, const policy::ParentOrderDefinition& parent) {
  if (calibration.provenance_id.empty()) throw std::invalid_argument("non-ML calibration provenance must not be empty");
  if (calibration.calibration_cutoff.domain() != parent.start_time.domain()) throw std::invalid_argument("calibration cutoff clock must match parent clock");
  if (calibration.calibration_cutoff.value() >= parent.start_time.value()) throw std::invalid_argument("non-ML calibration cutoff must be strictly before episode start");
  const long double values[]{calibration.maker_fee_bps, calibration.taker_fee_bps, calibration.passive_fill_base,
      calibration.passive_queue_weight, calibration.passive_trade_weight, calibration.passive_adverse_selection_bps,
      calibration.insufficient_depth_penalty_bps};
  for (const auto value : values) if (!finite(value)) throw std::invalid_argument("non-ML calibration values must be finite");
  if (calibration.passive_fill_base < 0.0L || calibration.passive_fill_base > 1.0L ||
      calibration.passive_queue_weight < 0.0L || calibration.passive_trade_weight < 0.0L ||
      calibration.passive_adverse_selection_bps < 0.0L || calibration.insufficient_depth_penalty_bps < 0.0L) {
    throw std::invalid_argument("non-ML calibration contains invalid bounds");
  }
}

void validate_parent(const policy::ParentOrderDefinition& parent) {
  if (parent.total_quantity.is_zero()) throw std::invalid_argument("adaptive parent quantity must be positive");
  if (parent.start_time.domain() != parent.end_time.domain()) throw std::invalid_argument("adaptive parent clocks must match");
  if (parent.end_time.value() <= parent.start_time.value()) throw std::invalid_argument("adaptive parent horizon must be positive");
}

bool contains_fraction(const std::vector<policy::QuantityFraction>& allowed, policy::QuantityFraction value) {
  return std::find(allowed.begin(), allowed.end(), value) != allowed.end();
}

bool contains_offset(const std::vector<model::TickOffset>& allowed, model::TickOffset value) {
  return std::find(allowed.begin(), allowed.end(), value) != allowed.end();
}

void validate_common_environment(
    const policy::PolicyEnvironment& environment,
    model::StrategyId strategy_id,
    model::TickOffset passive_offset
) {
  if (environment.strategy_id != strategy_id) throw std::invalid_argument("strategy id does not match environment");
  if (!environment.allow_market_orders) throw std::invalid_argument("adaptive baselines require market orders");
  if (!environment.allow_post_only) throw std::invalid_argument("adaptive baselines require post-only limit orders");
  if (!contains_offset(environment.allowed_tick_offsets, passive_offset)) throw std::invalid_argument("adaptive passive offset is not predeclared in environment");
  if (!contains_fraction(environment.allowed_quantity_fractions, policy::QuantityFraction{1U, 1U})) {
    throw std::invalid_argument("adaptive environment must permit full residual execution");
  }
}

std::optional<std::uint64_t> fraction_lots(
    std::uint64_t remaining,
    policy::QuantityFraction fraction,
    policy::LotRoundingPolicy rounding
) {
  if (!fraction.valid()) return std::nullopt;
#if defined(__SIZEOF_INT128__)
  __extension__ using Uint128 = unsigned __int128;
  const auto product = static_cast<Uint128>(remaining) * static_cast<Uint128>(fraction.numerator);
  const auto denominator = static_cast<Uint128>(fraction.denominator);
  auto quotient = product / denominator;
  const auto remainder = product % denominator;
  if (rounding == policy::LotRoundingPolicy::Ceiling && remainder != 0U) ++quotient;
  if (rounding == policy::LotRoundingPolicy::Nearest && remainder * 2U >= denominator) ++quotient;
  if (quotient > static_cast<Uint128>(std::numeric_limits<std::uint64_t>::max())) return std::nullopt;
  return static_cast<std::uint64_t>(quotient);
#else
  if (fraction.numerator != 0U && remaining > std::numeric_limits<std::uint64_t>::max() / fraction.numerator) return std::nullopt;
  const auto product = remaining * fraction.numerator;
  auto quotient = product / fraction.denominator;
  const auto remainder = product % fraction.denominator;
  if (rounding == policy::LotRoundingPolicy::Ceiling && remainder != 0U) ++quotient;
  if (rounding == policy::LotRoundingPolicy::Nearest && remainder >= (fraction.denominator + 1U) / 2U) ++quotient;
  return quotient;
#endif
}

policy::QuantityFraction usable_fraction(
    const policy::PolicyEnvironment& environment,
    model::QuantityLots remaining,
    policy::QuantityFraction preferred
) {
  const auto quantity = fraction_lots(remaining.value(), preferred, environment.lot_rounding);
  if (contains_fraction(environment.allowed_quantity_fractions, preferred) && quantity.has_value() && *quantity > 0U) return preferred;
  const policy::QuantityFraction full{1U, 1U};
  if (contains_fraction(environment.allowed_quantity_fractions, full)) return full;
  throw std::invalid_argument("no usable adaptive quantity fraction is permitted");
}

std::optional<model::PriceTicks> same_side_best(const policy::PolicyObservation& observation) {
  return observation.parent().side == model::Side::Buy ? observation.best_bid() : observation.best_ask();
}

long double passive_fill_pressure(const policy::PolicyObservation& observation) {
  long double favorable = 0.0L;
  long double known = 0.0L;
  const auto desired = observation.parent().side == model::Side::Buy ? model::AggressorSide::Sell : model::AggressorSide::Buy;
  for (const auto& observed : observation.recent_trades()) {
    if (observed.trade.aggressor_side == model::AggressorSide::Unknown) continue;
    const auto quantity = static_cast<long double>(observed.trade.quantity.value());
    known += quantity;
    if (observed.trade.aggressor_side == desired) favorable += quantity;
  }
  return known <= 0.0L ? 0.5L : clamp01(favorable / known);
}

long double passive_execution_cost_bps(
    const policy::PolicyObservation& observation,
    const NonMlCalibration& calibration,
    const AdaptiveSignals& signals
) {
  const auto best = same_side_best(observation);
  if (!best.has_value() || signals.midpoint_ticks <= 0.0L) return calibration.insufficient_depth_penalty_bps;
  const long double directional = observation.parent().side == model::Side::Buy
      ? (static_cast<long double>(best->value()) - signals.midpoint_ticks) / signals.midpoint_ticks * 10'000.0L
      : (signals.midpoint_ticks - static_cast<long double>(best->value())) / signals.midpoint_ticks * 10'000.0L;
  return directional + calibration.maker_fee_bps + calibration.passive_adverse_selection_bps * signals.passive_fill_pressure;
}

long double aggressive_execution_cost_bps(
    const policy::PolicyObservation& observation,
    const NonMlCalibration& calibration,
    long double requested_lots,
    long double midpoint_ticks
) {
  if (requested_lots <= 0.0L) return 0.0L;
  if (midpoint_ticks <= 0.0L) return calibration.insufficient_depth_penalty_bps + calibration.taker_fee_bps;
  const auto& levels = observation.parent().side == model::Side::Buy ? observation.asks() : observation.bids();
  long double remaining = requested_lots;
  long double notional_ticks = 0.0L;
  long double executed = 0.0L;
  for (const auto& level : levels) {
    if (remaining <= 0.0L) break;
    const auto available = static_cast<long double>(level.displayed_quantity.value());
    const auto take = std::min(remaining, available);
    notional_ticks += take * static_cast<long double>(level.price.value());
    executed += take;
    remaining -= take;
  }
  long double directional_bps = calibration.insufficient_depth_penalty_bps;
  if (executed > 0.0L) {
    const auto average = notional_ticks / executed;
    directional_bps = observation.parent().side == model::Side::Buy
        ? (average - midpoint_ticks) / midpoint_ticks * 10'000.0L
        : (midpoint_ticks - average) / midpoint_ticks * 10'000.0L;
  }
  const auto missing_fraction = clamp01(remaining / requested_lots);
  return directional_bps + calibration.taker_fee_bps + calibration.insufficient_depth_penalty_bps * missing_fraction;
}

std::string decimal(long double value) {
  std::ostringstream out;
  out << std::fixed << std::setprecision(12) << value;
  return out.str();
}

struct Candidate {
  AdaptiveActionMode mode{AdaptiveActionMode::NoAction};
  std::optional<policy::QuantityFraction> fraction;
};

struct SearchResult {
  long double cost{0.0L};
  Candidate first;
  std::uint64_t nodes{0U};
};

class MpcSearch {
 public:
  MpcSearch(
      const policy::PolicyObservation& observation,
      const MpcParameters& parameters,
      AdaptiveSignals signals,
      std::size_t horizon,
      long double passive_prediction_adjustment_bps
  )
      : observation_(observation), parameters_(parameters), signals_(signals), horizon_(horizon),
        initial_lots_(static_cast<long double>(observation.parent().remaining_quantity.value())),
        passive_cost_bps_(passive_execution_cost_bps(observation, parameters.calibration, signals) +
                          passive_prediction_adjustment_bps) {}

  SearchResult solve() {
    nodes_ = 0U;
    auto result = recurse(0U, initial_lots_);
    result.nodes = nodes_;
    return result;
  }

  long double passive_cost_bps() const noexcept { return passive_cost_bps_; }
  long double full_aggressive_cost_bps() const {
    return aggressive_execution_cost_bps(observation_, parameters_.calibration, initial_lots_, signals_.midpoint_ticks);
  }

 private:
  SearchResult recurse(std::size_t step, long double remaining_lots) {
    ++nodes_;
    if (remaining_lots <= kEpsilon) return {0.0L, Candidate{}, 0U};
    if (step >= horizon_) {
      const auto remaining_fraction = remaining_lots / initial_lots_;
      const auto forced_cost = aggressive_execution_cost_bps(observation_, parameters_.calibration, remaining_lots, signals_.midpoint_ticks);
      return {remaining_fraction * (forced_cost + parameters_.terminal_penalty_bps) +
                  parameters_.terminal_inventory_quadratic_bps * remaining_fraction * remaining_fraction,
              Candidate{}, 0U};
    }

    SearchResult best;
    best.cost = std::numeric_limits<long double>::infinity();
    bool have_best = false;
    auto consider = [&](Candidate candidate, long double immediate_cost, long double next_remaining) {
      const auto next_fraction = initial_lots_ <= 0.0L ? 0.0L : next_remaining / initial_lots_;
      const auto risk_cost = parameters_.inventory_risk_bps * next_fraction * next_fraction;
      const auto tail = recurse(step + 1U, next_remaining);
      const auto total = immediate_cost + risk_cost + tail.cost;
      if (!have_best || total < best.cost - 1.0e-12L) {
        have_best = true;
        best.cost = total;
        best.first = step == 0U ? candidate : tail.first;
      }
    };

    consider(Candidate{AdaptiveActionMode::NoAction, std::nullopt}, 0.0L, remaining_lots);
    for (const auto fraction : parameters_.action_fractions) {
      const auto f = fraction_value(fraction);
      const auto attempt = remaining_lots * f;
      if (attempt <= kEpsilon) continue;
      const auto aggressive_cost = aggressive_execution_cost_bps(observation_, parameters_.calibration, attempt, signals_.midpoint_ticks);
      consider(Candidate{AdaptiveActionMode::Aggressive, fraction}, (attempt / initial_lots_) * aggressive_cost, remaining_lots - attempt);

      if (f > fraction_value(parameters_.maximum_passive_fraction) + kEpsilon) continue;
      const auto expected_fill = attempt * signals_.passive_fill_probability;
      if (expected_fill > kEpsilon) {
        consider(Candidate{AdaptiveActionMode::Passive, fraction}, (expected_fill / initial_lots_) * passive_cost_bps_, remaining_lots - expected_fill);
      }
    }
    if (!have_best) throw std::logic_error("MPC search produced no candidate");
    return best;
  }

  const policy::PolicyObservation& observation_;
  const MpcParameters& parameters_;
  AdaptiveSignals signals_;
  std::size_t horizon_{1U};
  long double initial_lots_{0.0L};
  long double passive_cost_bps_{0.0L};
  std::uint64_t nodes_{0U};
};

void validate_mpc_parameters(const MpcParameters& parameters) {
  if (parameters.configuration_id.empty()) {
    throw std::invalid_argument("MPC configuration_id must not be empty");
  }
  if (parameters.planning_horizon_steps == 0U || parameters.planning_horizon_steps > 4U) {
    throw std::invalid_argument("MPC planning horizon must lie in [1,4]");
  }
  if (parameters.action_fractions.empty() || parameters.action_fractions.size() > 4U) {
    throw std::invalid_argument("MPC action fraction set must contain 1..4 values");
  }
  if (!finite(parameters.inventory_risk_bps) || !finite(parameters.terminal_penalty_bps) ||
      !finite(parameters.terminal_inventory_quadratic_bps) ||
      parameters.inventory_risk_bps < 0.0L || parameters.terminal_penalty_bps < 0.0L ||
      parameters.terminal_inventory_quadratic_bps < 0.0L) {
    throw std::invalid_argument("MPC cost parameters must be finite and non-negative");
  }
  for (const auto fraction : parameters.action_fractions) {
    if (!canonical_fraction(fraction)) {
      throw std::invalid_argument("MPC action fractions must be canonical reduced fractions");
    }
  }
  if (!canonical_fraction(parameters.maximum_passive_fraction)) {
    throw std::invalid_argument("MPC maximum passive fraction must be canonical");
  }
}

void validate_prediction(
    const policy::PolicyObservation& observation,
    const MpcPredictionInput& prediction
) {
  if (prediction.decision_id != observation.decision_id()) {
    throw std::invalid_argument("prediction decision id must match observation endpoint");
  }
  const auto domain = observation.decision_time().domain();
  if (prediction.endpoint_time.domain() != domain ||
      prediction.feature_cutoff_time.domain() != domain ||
      prediction.available_time.domain() != domain) {
    throw std::invalid_argument("prediction clocks must match observation clock domain");
  }
  if (prediction.endpoint_time != observation.decision_time()) {
    throw std::invalid_argument("prediction endpoint time must equal decision time");
  }
  if (prediction.feature_cutoff_time.value() > observation.observation_cutoff().value()) {
    throw std::invalid_argument("prediction feature cutoff exceeds causal observation cutoff");
  }
  if (prediction.available_time.value() > observation.decision_time().value()) {
    throw std::invalid_argument("prediction is not causally available at decision time");
  }
  if (!finite(prediction.probability) || prediction.probability < 0.0L ||
      prediction.probability > 1.0L || !finite(prediction.training_base_rate) ||
      prediction.training_base_rate < 0.0L ||
      prediction.training_base_rate > 1.0L) {
    throw std::invalid_argument("prediction probabilities must lie in [0,1]");
  }
  if (prediction.horizon_id.empty() || prediction.model_id.empty() ||
      prediction.provenance_id.empty()) {
    throw std::invalid_argument("prediction provenance, model and horizon must not be empty");
  }
  if (prediction.kind == MpcPredictionKind::Stale) {
    if (!prediction.source_prediction_decision_id.has_value() ||
        prediction.source_prediction_decision_id->value() >= prediction.decision_id.value()) {
      throw std::invalid_argument("stale ablation must identify an earlier source prediction");
    }
  }
}

std::size_t mpc_available_steps(
    const policy::PolicyObservation& observation,
    const MpcParameters& parameters
) {
  const auto interval = observation.environment().decision_interval_ns;
  if (interval <= 0) throw std::invalid_argument("MPC decision interval must be positive");
  const auto remaining_ns = std::max<std::int64_t>(0, observation.time_remaining_ns());
  std::size_t available_steps = 1U;
  if (remaining_ns > 0) {
    const auto raw = static_cast<std::uint64_t>(remaining_ns / interval) +
                     static_cast<std::uint64_t>(remaining_ns % interval != 0);
    available_steps = static_cast<std::size_t>(std::min<std::uint64_t>(
        raw, static_cast<std::uint64_t>(parameters.planning_horizon_steps)));
    available_steps = std::max<std::size_t>(1U, available_steps);
  }
  return available_steps;
}

MpcDecision solve_mpc_common(
    const policy::PolicyObservation& observation,
    const MpcParameters& parameters,
    const MpcPredictionInput* prediction,
    long double prediction_risk_weight_bps,
    std::string_view outer_configuration_id
) {
  validate_mpc_parameters(parameters);
  long double prediction_adjustment_bps = 0.0L;
  if (prediction != nullptr) {
    validate_prediction(observation, *prediction);
    if (!finite(prediction_risk_weight_bps) || prediction_risk_weight_bps < 0.0L) {
      throw std::invalid_argument("prediction risk weight must be finite and non-negative");
    }
    prediction_adjustment_bps =
        prediction_risk_weight_bps * (prediction->probability - prediction->training_base_rate);
  }

  const auto signals = calculate_adaptive_signals(observation, parameters.calibration);
  const auto available_steps = mpc_available_steps(observation, parameters);
  MpcSearch search{observation, parameters, signals, available_steps, prediction_adjustment_bps};
  const auto solved = search.solve();

  MpcDecision decision;
  decision.mode = solved.first.mode;
  decision.fraction = solved.first.fraction;
  decision.objective_bps = solved.cost;
  decision.aggressive_cost_bps = search.full_aggressive_cost_bps();
  decision.passive_cost_bps = search.passive_cost_bps();
  decision.planning_horizon_steps_used = available_steps;
  decision.evaluated_plan_nodes = solved.nodes;
  decision.signals = signals;
  decision.prediction_used = prediction != nullptr;
  if (prediction != nullptr) {
    decision.prediction_probability = prediction->probability;
    decision.prediction_training_base_rate = prediction->training_base_rate;
    decision.prediction_adjustment_bps = prediction_adjustment_bps;
    decision.prediction_kind = std::string(to_string(prediction->kind));
    decision.prediction_provenance_id = prediction->provenance_id;
    decision.prediction_horizon_id = prediction->horizon_id;
  }
  std::ostringstream out;
  out << to_string(decision.mode) << '|';
  if (decision.fraction.has_value()) {
    out << decision.fraction->numerator << '/' << decision.fraction->denominator;
  } else {
    out << '-';
  }
  out << '|' << decimal(decision.objective_bps) << '|' << decimal(decision.aggressive_cost_bps) << '|'
      << decimal(decision.passive_cost_bps) << '|' << decimal(decision.signals.passive_fill_probability) << '|'
      << decision.planning_horizon_steps_used << '|' << decision.evaluated_plan_nodes << '|'
      << outer_configuration_id << '|' << parameters.calibration.provenance_id;
  if (prediction != nullptr) {
    out << "|prediction=" << to_string(prediction->kind) << '|'
        << decimal(prediction->probability) << '|' << decimal(prediction->training_base_rate) << '|'
        << decimal(prediction_adjustment_bps) << '|' << prediction->horizon_id << '|'
        << prediction->model_id << '|' << prediction->provenance_id;
  }
  decision.canonical = out.str();
  return decision;
}

policy::PolicyAction no_action(const policy::PolicyObservation& observation) {
  return {observation.decision_id(), observation.decision_time(), policy::NoAction{}};
}

policy::PolicyAction cancel_active(const policy::PolicyObservation& observation) {
  policy::CancelChildAction cancel;
  for (const auto& child : observation.active_orders()) cancel.client_order_ids.push_back(child.client_order_id);
  return {observation.decision_id(), observation.decision_time(), std::move(cancel)};
}

policy::PolicyAction submit_action(
    const policy::PolicyObservation& observation,
    const policy::PolicyEnvironment& environment,
    AdaptiveActionMode mode,
    policy::QuantityFraction preferred_fraction,
    model::TickOffset passive_offset,
    std::uint64_t client_order_id
) {
  const auto fraction = usable_fraction(environment, observation.parent().remaining_quantity, preferred_fraction);
  policy::SubmitChildAction submit;
  submit.client_order_id = model::ClientOrderId{client_order_id};
  submit.quantity_fraction = fraction;
  if (mode == AdaptiveActionMode::Aggressive) {
    submit.order_type = model::OrderType::Market;
    submit.time_in_force = model::TimeInForce::ImmediateOrCancel;
  } else if (mode == AdaptiveActionMode::Passive) {
    submit.order_type = model::OrderType::Limit;
    submit.time_in_force = model::TimeInForce::GoodTilCancelled;
    submit.placement = policy::LimitPlacement{policy::LimitReference::SameSideBest, passive_offset};
    submit.post_only = true;
  } else {
    throw std::invalid_argument("submit_action requires passive or aggressive mode");
  }
  return {observation.decision_id(), observation.decision_time(), submit};
}

bool active_order_is_current(const policy::PolicyObservation& observation, const model::TickOffset offset) {
  const auto best = same_side_best(observation);
  if (!best.has_value()) return false;
  const auto desired = model::checked_add(*best, offset);
  if (!desired.has_value()) return false;
  for (const auto& child : observation.active_orders()) {
    if (!child.limit_price.has_value() || child.limit_price != desired) return false;
  }
  return true;
}

}  // namespace

std::string_view to_string(AdaptiveActionMode value) noexcept {
  switch (value) {
    case AdaptiveActionMode::NoAction: return "no_action";
    case AdaptiveActionMode::Passive: return "passive";
    case AdaptiveActionMode::Aggressive: return "aggressive";
    case AdaptiveActionMode::Cancel: return "cancel";
  }
  return "unknown";
}

std::string_view to_string(MpcPredictionKind value) noexcept {
  switch (value) {
    case MpcPredictionKind::CalibratedModel: return "calibrated_model";
    case MpcPredictionKind::TrainingBaseRate: return "training_base_rate";
    case MpcPredictionKind::ShuffledWithinDayInstrument: return "shuffled_within_day_instrument";
    case MpcPredictionKind::Stale: return "stale";
    case MpcPredictionKind::UncalibratedModel: return "uncalibrated_model";
    case MpcPredictionKind::PerfectEventOracle: return "perfect_event_oracle";
  }
  return "unknown";
}

AdaptiveSignals calculate_adaptive_signals(
    const policy::PolicyObservation& observation,
    const NonMlCalibration& calibration
) {
  policy::ParentOrderDefinition calibration_parent{observation.parent().parent_order_id, observation.parent().side, observation.parent().total_quantity,
      observation.parent().start_time, observation.parent().end_time, observation.parent().arrival_price, observation.parent().terminal_rule_id};
  validate_calibration(calibration, calibration_parent);
  const auto bid = observation.best_bid();
  const auto ask = observation.best_ask();
  if (!bid.has_value() || !ask.has_value() || ask->value() <= bid->value()) throw std::invalid_argument("adaptive controller requires a valid two-sided uncrossed book");
  const auto& parent = observation.parent();
  if (parent.total_quantity.is_zero()) throw std::invalid_argument("adaptive controller requires positive parent quantity");
  if (parent.start_time.domain() != parent.end_time.domain() || parent.start_time.domain() != observation.decision_time().domain()) throw std::invalid_argument("adaptive controller clocks must match");
  const auto horizon = parent.end_time.value() - parent.start_time.value();
  if (horizon <= 0) throw std::invalid_argument("adaptive parent horizon must be positive");

  AdaptiveSignals signals;
  signals.midpoint_ticks = (static_cast<long double>(bid->value()) + static_cast<long double>(ask->value())) / 2.0L;
  signals.spread_ticks = static_cast<long double>(ask->value()) - static_cast<long double>(bid->value());
  const auto same = parent.side == model::Side::Buy ? observation.bids().front().displayed_quantity.value() : observation.asks().front().displayed_quantity.value();
  const auto opposite = parent.side == model::Side::Buy ? observation.asks().front().displayed_quantity.value() : observation.bids().front().displayed_quantity.value();
  signals.same_side_best_lots = static_cast<long double>(same);
  signals.opposite_side_best_lots = static_cast<long double>(opposite);
  const auto combined = signals.same_side_best_lots + signals.opposite_side_best_lots;
  signals.same_side_queue_share = combined <= 0.0L ? 0.5L : clamp01(signals.same_side_best_lots / combined);
  signals.passive_fill_pressure = passive_fill_pressure(observation);
  signals.passive_fill_probability = clamp01(
      calibration.passive_fill_base +
      calibration.passive_queue_weight * (0.5L - signals.same_side_queue_share) +
      calibration.passive_trade_weight * (signals.passive_fill_pressure - 0.5L)
  );
  const auto elapsed = observation.decision_time().value() - parent.start_time.value();
  const auto remaining_time = parent.end_time.value() - observation.decision_time().value();
  signals.elapsed_fraction = clamp01(static_cast<long double>(std::max<std::int64_t>(0, elapsed)) / static_cast<long double>(horizon));
  signals.time_remaining_fraction = clamp01(static_cast<long double>(std::max<std::int64_t>(0, remaining_time)) / static_cast<long double>(horizon));
  signals.filled_fraction = clamp01(static_cast<long double>(parent.cumulative_filled.value()) / static_cast<long double>(parent.total_quantity.value()));
  signals.remaining_fraction = clamp01(static_cast<long double>(parent.remaining_quantity.value()) / static_cast<long double>(parent.total_quantity.value()));
  signals.progress_lag = signals.elapsed_fraction - signals.filled_fraction;
  return signals;
}

MpcDecision solve_non_ml_mpc(
    const policy::PolicyObservation& observation,
    const MpcParameters& parameters
) {
  return solve_mpc_common(
      observation, parameters, nullptr, 0.0L, parameters.configuration_id
  );
}

MpcDecision solve_ml_mpc(
    const policy::PolicyObservation& observation,
    const MlMpcParameters& parameters,
    const MpcPredictionInput& prediction
) {
  if (parameters.prediction_contract_id.empty() || parameters.configuration_id.empty()) {
    throw std::invalid_argument("ML-MPC prediction contract/configuration ids must not be empty");
  }
  return solve_mpc_common(
      observation,
      parameters.base,
      &prediction,
      parameters.prediction_risk_weight_bps,
      parameters.configuration_id
  );
}

QueueAwareHeuristicPolicy::QueueAwareHeuristicPolicy(model::StrategyId strategy_id, QueueAwareHeuristicParameters parameters)
    : strategy_id_(std::move(strategy_id)), parameters_(std::move(parameters)) {}

model::StrategyId QueueAwareHeuristicPolicy::strategy_id() const { return strategy_id_; }

void QueueAwareHeuristicPolicy::reset(const policy::ParentOrderDefinition& parent, const policy::PolicyEnvironment& environment) {
  validate_parent(parent);
  validate_calibration(parameters_.calibration, parent);
  validate_common_environment(environment, strategy_id_, parameters_.passive_tick_offset);
  if (parameters_.configuration_id.empty()) throw std::invalid_argument("heuristic configuration_id must not be empty");
  if (!canonical_fraction(parameters_.passive_fraction) || !canonical_fraction(parameters_.aggressive_fraction)) throw std::invalid_argument("heuristic fractions must be canonical reduced fractions");
  if (!contains_fraction(environment.allowed_quantity_fractions, parameters_.passive_fraction) || !contains_fraction(environment.allowed_quantity_fractions, parameters_.aggressive_fraction)) throw std::invalid_argument("heuristic fractions must be predeclared in environment");
  if (!finite(parameters_.aggressive_lag_threshold) || !finite(parameters_.minimum_passive_fill_probability) ||
      parameters_.aggressive_lag_threshold < 0.0L || parameters_.aggressive_lag_threshold > 1.0L ||
      parameters_.minimum_passive_fill_probability < 0.0L || parameters_.minimum_passive_fill_probability > 1.0L ||
      parameters_.terminal_aggressive_window_ns < 0) throw std::invalid_argument("heuristic thresholds are invalid");
  parent_ = parent;
  environment_ = environment;
  last_signals_.reset();
  next_client_order_id_ = 1U;
}

policy::PolicyAction QueueAwareHeuristicPolicy::on_observation(const policy::PolicyObservation& observation) {
  if (!parent_.has_value() || !environment_.has_value()) throw std::logic_error("heuristic policy must be reset before use");
  if (!policy::same_policy_environment(observation.environment(), *environment_)) throw std::invalid_argument("heuristic observation environment mismatch");
  if (observation.parent().remaining_quantity.is_zero() || observation.parent().status == policy::ParentOrderStatus::TerminalCompletionPending || observation.decision_time().value() < parent_->start_time.value()) return no_action(observation);
  if (observation.pending_command_count() != 0U) return no_action(observation);
  last_signals_ = calculate_adaptive_signals(observation, parameters_.calibration);
  const bool force_aggressive = observation.time_remaining_ns() <= parameters_.terminal_aggressive_window_ns ||
                                last_signals_->progress_lag >= parameters_.aggressive_lag_threshold;
  if (!observation.active_orders().empty()) {
    if (force_aggressive || !active_order_is_current(observation, parameters_.passive_tick_offset)) return cancel_active(observation);
    return no_action(observation);
  }
  if (force_aggressive) return submit_action(observation, *environment_, AdaptiveActionMode::Aggressive, parameters_.aggressive_fraction, parameters_.passive_tick_offset, next_client_order_id_++);
  if (last_signals_->passive_fill_probability >= parameters_.minimum_passive_fill_probability) {
    return submit_action(observation, *environment_, AdaptiveActionMode::Passive, parameters_.passive_fraction, parameters_.passive_tick_offset, next_client_order_id_++);
  }
  if (last_signals_->progress_lag > 0.0L) return submit_action(observation, *environment_, AdaptiveActionMode::Aggressive, parameters_.aggressive_fraction, parameters_.passive_tick_offset, next_client_order_id_++);
  return no_action(observation);
}

const std::optional<AdaptiveSignals>& QueueAwareHeuristicPolicy::last_signals() const noexcept { return last_signals_; }

NonMlMpcPolicy::NonMlMpcPolicy(model::StrategyId strategy_id, MpcParameters parameters)
    : strategy_id_(std::move(strategy_id)), parameters_(std::move(parameters)) {}

model::StrategyId NonMlMpcPolicy::strategy_id() const { return strategy_id_; }

void NonMlMpcPolicy::reset(const policy::ParentOrderDefinition& parent, const policy::PolicyEnvironment& environment) {
  validate_parent(parent);
  validate_calibration(parameters_.calibration, parent);
  validate_common_environment(environment, strategy_id_, parameters_.passive_tick_offset);
  if (parameters_.configuration_id.empty()) throw std::invalid_argument("MPC configuration_id must not be empty");
  if (parameters_.planning_horizon_steps == 0U || parameters_.planning_horizon_steps > 4U) throw std::invalid_argument("MPC planning horizon must lie in [1,4]");
  if (parameters_.action_fractions.empty() || parameters_.action_fractions.size() > 4U) throw std::invalid_argument("MPC action fractions must contain 1..4 values");
  if (!canonical_fraction(parameters_.maximum_passive_fraction) || !contains_fraction(environment.allowed_quantity_fractions, parameters_.maximum_passive_fraction)) throw std::invalid_argument("MPC maximum passive fraction must be predeclared and canonical");
  for (const auto fraction : parameters_.action_fractions) {
    if (!canonical_fraction(fraction)) throw std::invalid_argument("MPC action fractions must be canonical reduced fractions");
    if (!contains_fraction(environment.allowed_quantity_fractions, fraction)) throw std::invalid_argument("MPC action fraction is not predeclared in environment");
  }
  if (!contains_fraction(parameters_.action_fractions, policy::QuantityFraction{1U, 1U})) throw std::invalid_argument("MPC action set must include full residual fraction");
  if (!finite(parameters_.inventory_risk_bps) || !finite(parameters_.terminal_penalty_bps) || !finite(parameters_.terminal_inventory_quadratic_bps) ||
      parameters_.inventory_risk_bps < 0.0L || parameters_.terminal_penalty_bps < 0.0L || parameters_.terminal_inventory_quadratic_bps < 0.0L) throw std::invalid_argument("MPC cost parameters are invalid");
  parent_ = parent;
  environment_ = environment;
  last_decision_.reset();
  next_client_order_id_ = 1U;
}

policy::PolicyAction NonMlMpcPolicy::on_observation(const policy::PolicyObservation& observation) {
  if (!parent_.has_value() || !environment_.has_value()) throw std::logic_error("MPC policy must be reset before use");
  if (!policy::same_policy_environment(observation.environment(), *environment_)) throw std::invalid_argument("MPC observation environment mismatch");
  if (observation.parent().remaining_quantity.is_zero() || observation.parent().status == policy::ParentOrderStatus::TerminalCompletionPending || observation.decision_time().value() < parent_->start_time.value()) return no_action(observation);
  if (observation.pending_command_count() != 0U) return no_action(observation);
  last_decision_ = solve_non_ml_mpc(observation, parameters_);
  if (!observation.active_orders().empty()) {
    if (last_decision_->mode != AdaptiveActionMode::Passive || !active_order_is_current(observation, parameters_.passive_tick_offset)) return cancel_active(observation);
    return no_action(observation);
  }
  if (last_decision_->mode == AdaptiveActionMode::NoAction || !last_decision_->fraction.has_value()) return no_action(observation);
  if (last_decision_->mode == AdaptiveActionMode::Passive || last_decision_->mode == AdaptiveActionMode::Aggressive) {
    return submit_action(observation, *environment_, last_decision_->mode, *last_decision_->fraction, parameters_.passive_tick_offset, next_client_order_id_++);
  }
  return no_action(observation);
}

const std::optional<MpcDecision>& NonMlMpcPolicy::last_decision() const noexcept { return last_decision_; }

MlMpcPolicy::MlMpcPolicy(
    model::StrategyId strategy_id,
    MlMpcParameters parameters,
    std::vector<MpcPredictionInput> prediction_tape
)
    : strategy_id_(std::move(strategy_id)),
      parameters_(std::move(parameters)),
      prediction_tape_(std::move(prediction_tape)) {
  std::sort(
      prediction_tape_.begin(),
      prediction_tape_.end(),
      [](const auto& lhs, const auto& rhs) {
        return lhs.decision_id.value() < rhs.decision_id.value();
      }
  );
  for (std::size_t i = 1U; i < prediction_tape_.size(); ++i) {
    if (prediction_tape_[i - 1U].decision_id == prediction_tape_[i].decision_id) {
      throw std::invalid_argument("ML-MPC prediction tape contains duplicate decision ids");
    }
  }
}

model::StrategyId MlMpcPolicy::strategy_id() const { return strategy_id_; }

void MlMpcPolicy::reset(
    const policy::ParentOrderDefinition& parent,
    const policy::PolicyEnvironment& environment
) {
  validate_parent(parent);
  validate_calibration(parameters_.base.calibration, parent);
  validate_common_environment(environment, strategy_id_, parameters_.base.passive_tick_offset);
  validate_mpc_parameters(parameters_.base);
  if (parameters_.prediction_contract_id.empty() || parameters_.configuration_id.empty()) {
    throw std::invalid_argument("ML-MPC prediction contract/configuration ids must not be empty");
  }
  if (!finite(parameters_.prediction_risk_weight_bps) ||
      parameters_.prediction_risk_weight_bps < 0.0L) {
    throw std::invalid_argument("ML-MPC prediction risk weight must be finite and non-negative");
  }
  if (!contains_fraction(
          environment.allowed_quantity_fractions, parameters_.base.maximum_passive_fraction)) {
    throw std::invalid_argument("ML-MPC maximum passive fraction must be predeclared");
  }
  for (const auto fraction : parameters_.base.action_fractions) {
    if (!contains_fraction(environment.allowed_quantity_fractions, fraction)) {
      throw std::invalid_argument("ML-MPC action fraction is not predeclared in environment");
    }
  }
  if (!contains_fraction(parameters_.base.action_fractions, policy::QuantityFraction{1U, 1U})) {
    throw std::invalid_argument("ML-MPC action set must include full residual fraction");
  }
  parent_ = parent;
  environment_ = environment;
  last_decision_.reset();
  next_client_order_id_ = 1U;
}

const MpcPredictionInput& MlMpcPolicy::prediction_for(model::DecisionId decision_id) const {
  const auto it = std::lower_bound(
      prediction_tape_.begin(),
      prediction_tape_.end(),
      decision_id.value(),
      [](const auto& prediction, std::uint64_t value) {
        return prediction.decision_id.value() < value;
      }
  );
  if (it == prediction_tape_.end() || it->decision_id != decision_id) {
    throw std::logic_error("ML-MPC has no precomputed prediction for decision id");
  }
  return *it;
}

policy::PolicyAction MlMpcPolicy::on_observation(const policy::PolicyObservation& observation) {
  if (!parent_.has_value() || !environment_.has_value()) {
    throw std::logic_error("ML-MPC policy must be reset before use");
  }
  if (!policy::same_policy_environment(observation.environment(), *environment_)) {
    throw std::invalid_argument("ML-MPC observation environment mismatch");
  }
  if (observation.parent().remaining_quantity.is_zero() ||
      observation.parent().status == policy::ParentOrderStatus::TerminalCompletionPending ||
      observation.decision_time().value() < parent_->start_time.value()) {
    return no_action(observation);
  }
  if (observation.pending_command_count() != 0U) return no_action(observation);
  const auto& prediction = prediction_for(observation.decision_id());
  last_decision_ = solve_ml_mpc(observation, parameters_, prediction);
  if (!observation.active_orders().empty()) {
    if (last_decision_->mode != AdaptiveActionMode::Passive ||
        !active_order_is_current(observation, parameters_.base.passive_tick_offset)) {
      return cancel_active(observation);
    }
    return no_action(observation);
  }
  if (last_decision_->mode == AdaptiveActionMode::NoAction ||
      !last_decision_->fraction.has_value()) {
    return no_action(observation);
  }
  if (last_decision_->mode == AdaptiveActionMode::Passive ||
      last_decision_->mode == AdaptiveActionMode::Aggressive) {
    return submit_action(
        observation,
        *environment_,
        last_decision_->mode,
        *last_decision_->fraction,
        parameters_.base.passive_tick_offset,
        next_client_order_id_++
    );
  }
  return no_action(observation);
}

const std::optional<MpcDecision>& MlMpcPolicy::last_decision() const noexcept {
  return last_decision_;
}

}  // namespace robust_execution::strategies
