#include "robust_execution/strategies/almgren_chriss.hpp"

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

void require_finite_nonnegative(long double value, const char* name) {
  if (!std::isfinite(value) || value < 0.0L) throw std::invalid_argument(std::string{name} + " must be finite and non-negative");
}

std::vector<model::TimestampNs> release_times(const policy::ParentOrderDefinition& parent, std::size_t count) {
  if (count == 0U) throw std::invalid_argument("slice_count must be positive");
  if (parent.start_time.domain() != parent.end_time.domain()) throw std::invalid_argument("parent clocks must match");
  if (parent.end_time.value() <= parent.start_time.value()) throw std::invalid_argument("parent horizon must be positive");
  if (count > static_cast<std::size_t>(std::numeric_limits<std::int64_t>::max())) throw std::overflow_error("slice_count exceeds timestamp arithmetic range");
  std::vector<model::TimestampNs> out;
  out.reserve(count);
  const auto duration = parent.end_time.value() - parent.start_time.value();
  const auto count64 = static_cast<std::int64_t>(count);
  for (std::size_t i = 0; i < count; ++i) {
    const auto index64 = static_cast<std::int64_t>(i);
    const auto quotient = duration / count64;
    const auto remainder = duration % count64;
    if (quotient != 0 && index64 > std::numeric_limits<std::int64_t>::max() / quotient) throw std::overflow_error("schedule release-time overflow");
    const auto first = quotient * index64;
    if (remainder != 0 && index64 > std::numeric_limits<std::int64_t>::max() / remainder) throw std::overflow_error("schedule release-time remainder overflow");
    const auto second = (remainder * index64) / count64;
    if (first > std::numeric_limits<std::int64_t>::max() - second) throw std::overflow_error("schedule release-time offset overflow");
    const auto offset = first + second;
    if (parent.start_time.value() > std::numeric_limits<std::int64_t>::max() - offset) throw std::overflow_error("schedule timestamp overflow");
    out.emplace_back(parent.start_time.domain(), parent.start_time.value() + offset);
  }
  return out;
}

std::vector<long double> solve_normalized_inventory(std::size_t slice_count, long double alpha) {
  if (slice_count == 1U) return {1.0L, 0.0L};
  const auto unknown_count = slice_count - 1U;
  const long double diagonal = 2.0L + alpha;
  if (!std::isfinite(diagonal) || diagonal < 2.0L) throw std::overflow_error("invalid Almgren-Chriss recurrence diagonal");

  std::vector<long double> c_prime(unknown_count, 0.0L);
  std::vector<long double> d_prime(unknown_count, 0.0L);
  long double denominator = diagonal;
  c_prime[0] = unknown_count > 1U ? -1.0L / denominator : 0.0L;
  d_prime[0] = 1.0L / denominator;

  for (std::size_t i = 1U; i < unknown_count; ++i) {
    denominator = diagonal + c_prime[i - 1U];
    if (!(denominator > 0.0L) || !std::isfinite(denominator)) throw std::runtime_error("Almgren-Chriss tridiagonal solve became singular");
    c_prime[i] = i + 1U < unknown_count ? -1.0L / denominator : 0.0L;
    d_prime[i] = d_prime[i - 1U] / denominator;
  }

  std::vector<long double> interior(unknown_count, 0.0L);
  interior.back() = d_prime.back();
  for (std::size_t i = unknown_count - 1U; i > 0U; --i) interior[i - 1U] = d_prime[i - 1U] - c_prime[i - 1U] * interior[i];

  std::vector<long double> inventory(slice_count + 1U, 0.0L);
  inventory.front() = 1.0L;
  for (std::size_t i = 0U; i < unknown_count; ++i) inventory[i + 1U] = interior[i];
  inventory.back() = 0.0L;
  for (std::size_t i = 1U; i < inventory.size(); ++i) {
    if (!std::isfinite(inventory[i])) throw std::runtime_error("non-finite Almgren-Chriss inventory target");
    if (inventory[i] < -1e-15L || inventory[i] > inventory[i - 1U] + 1e-15L) throw std::runtime_error("non-monotone Almgren-Chriss inventory target");
    inventory[i] = std::clamp(inventory[i], 0.0L, inventory[i - 1U]);
  }
  return inventory;
}

std::vector<std::uint64_t> apportion_lots(std::uint64_t total, const std::vector<long double>& normalized_inventory) {
  constexpr std::uint64_t kMaxPortableExactQuantity = 9'007'199'254'740'992ULL;  // 2^53
  if (total > kMaxPortableExactQuantity) throw std::overflow_error("parent quantity exceeds portable exact floating apportionment range");
  if (normalized_inventory.size() < 2U) throw std::invalid_argument("inventory path must contain both boundaries");
  const auto count = normalized_inventory.size() - 1U;
  std::vector<long double> weights(count, 0.0L);
  long double weight_sum = 0.0L;
  for (std::size_t i = 0U; i < count; ++i) {
    auto weight = normalized_inventory[i] - normalized_inventory[i + 1U];
    if (weight < 0.0L && weight > -1e-15L) weight = 0.0L;
    if (!(weight >= 0.0L) || !std::isfinite(weight)) throw std::runtime_error("invalid Almgren-Chriss trade weight");
    weights[i] = weight;
    weight_sum += weight;
  }
  if (!(weight_sum > 0.0L) || !std::isfinite(weight_sum)) throw std::runtime_error("Almgren-Chriss weights do not sum to a positive value");

  struct Remainder { std::size_t index; long double value; };
  std::vector<std::uint64_t> quantities(count, 0U);
  std::vector<Remainder> remainders;
  remainders.reserve(count);
  std::uint64_t assigned = 0U;
  for (std::size_t i = 0U; i < count; ++i) {
    const long double raw = static_cast<long double>(total) * (weights[i] / weight_sum);
    if (!std::isfinite(raw) || raw < 0.0L || raw > static_cast<long double>(total)) throw std::runtime_error("invalid Almgren-Chriss lot target");
    const auto floor_value = std::floor(raw);
    const auto quantity = static_cast<std::uint64_t>(floor_value);
    if (quantity > total - assigned) throw std::runtime_error("Almgren-Chriss lot apportionment overflow");
    quantities[i] = quantity;
    assigned += quantity;
    remainders.push_back({i, raw - floor_value});
  }
  if (assigned > total) throw std::runtime_error("Almgren-Chriss lot apportionment exceeded parent quantity");
  auto residual = total - assigned;
  if (residual > count) throw std::runtime_error("Almgren-Chriss floating apportionment residual exceeds slice count");
  std::sort(remainders.begin(), remainders.end(), [](const auto& lhs, const auto& rhs) {
    if (lhs.value != rhs.value) return lhs.value > rhs.value;
    return lhs.index < rhs.index;
  });
  for (std::uint64_t i = 0U; i < residual; ++i) ++quantities[remainders[static_cast<std::size_t>(i)].index];
  return quantities;
}

AlmgrenChrissDiagnostics diagnostics(
    std::uint64_t total_quantity,
    const std::vector<std::uint64_t>& quantities,
    const AlmgrenChrissParameters& p,
    long double tau,
    long double eta_tilde,
    long double kappa_tilde_squared,
    long double kappa
) {
  long double sum_trade_squared = 0.0L;
  long double sum_inventory_squared = 0.0L;
  long double remaining = static_cast<long double>(total_quantity);
  for (const auto quantity : quantities) {
    const auto trade = static_cast<long double>(quantity);
    sum_trade_squared += trade * trade;
    remaining -= trade;
    sum_inventory_squared += remaining * remaining;
  }
  const auto x = static_cast<long double>(total_quantity);
  const auto expected = 0.5L * p.permanent_impact_gamma * x * x + p.fixed_cost_epsilon * x + (eta_tilde / tau) * sum_trade_squared;
  const auto variance = p.volatility_sigma * p.volatility_sigma * tau * sum_inventory_squared;
  const auto objective = expected + p.risk_aversion_lambda * variance;
  if (!std::isfinite(expected) || !std::isfinite(variance) || !std::isfinite(objective)) throw std::overflow_error("Almgren-Chriss diagnostic overflow");
  return {tau, eta_tilde, kappa_tilde_squared, kappa, expected, variance, objective};
}

}  // namespace

model::QuantityLots AlmgrenChrissSchedule::total_quantity() const {
  std::uint64_t total = 0U;
  for (const auto& slice : slices) {
    if (slice.quantity.value() > std::numeric_limits<std::uint64_t>::max() - total) throw std::overflow_error("Almgren-Chriss schedule quantity overflow");
    total += slice.quantity.value();
  }
  return model::QuantityLots{total};
}

std::string AlmgrenChrissSchedule::canonical() const {
  std::ostringstream out;
  out << "almgren_chriss|" << to_string(style) << '|' << parameter_provenance_id;
  for (const auto& slice : slices) out << '|' << slice.release_time.value() << ':' << slice.quantity.value();
  return out.str();
}

AlmgrenChrissSchedule build_almgren_chriss_schedule(
    const policy::ParentOrderDefinition& parent,
    const AlmgrenChrissParameters& parameters
) {
  if (parent.total_quantity.value() == 0U) throw std::invalid_argument("parent quantity must be positive");
  if (parameters.slice_count == 0U) throw std::invalid_argument("Almgren-Chriss slice_count must be positive");
  if (parameters.parameter_provenance_id.empty()) throw std::invalid_argument("Almgren-Chriss parameter provenance must not be empty");
  if (parameters.calibration_cutoff.domain() != parent.start_time.domain()) throw std::invalid_argument("Almgren-Chriss calibration cutoff clock must match parent clock");
  if (parameters.calibration_cutoff.value() >= parent.start_time.value()) throw std::invalid_argument("Almgren-Chriss parameters must be frozen strictly before episode start");
  require_finite_nonnegative(parameters.risk_aversion_lambda, "risk_aversion_lambda");
  require_finite_nonnegative(parameters.volatility_sigma, "volatility_sigma");
  require_finite_nonnegative(parameters.permanent_impact_gamma, "permanent_impact_gamma");
  require_finite_nonnegative(parameters.fixed_cost_epsilon, "fixed_cost_epsilon");
  if (!std::isfinite(parameters.temporary_impact_eta) || parameters.temporary_impact_eta <= 0.0L) throw std::invalid_argument("temporary_impact_eta must be finite and positive");
  if (!std::isfinite(parameters.time_unit_ns) || parameters.time_unit_ns <= 0.0L) throw std::invalid_argument("time_unit_ns must be finite and positive");
  if (parent.start_time.domain() != parent.end_time.domain()) throw std::invalid_argument("parent clocks must match");
  const auto duration_ns = parent.end_time.value() - parent.start_time.value();
  if (duration_ns <= 0) throw std::invalid_argument("parent horizon must be positive");
  const long double horizon = static_cast<long double>(duration_ns) / parameters.time_unit_ns;
  const long double tau = horizon / static_cast<long double>(parameters.slice_count);
  if (!(tau > 0.0L) || !std::isfinite(tau)) throw std::invalid_argument("Almgren-Chriss interval length must be finite and positive");
  const long double eta_tilde = parameters.temporary_impact_eta - 0.5L * parameters.permanent_impact_gamma * tau;
  if (!(eta_tilde > 0.0L) || !std::isfinite(eta_tilde)) throw std::invalid_argument("Almgren-Chriss requires eta_tilde = eta - gamma*tau/2 > 0");
  const long double sigma_squared = parameters.volatility_sigma * parameters.volatility_sigma;
  if (!std::isfinite(sigma_squared)) throw std::overflow_error("volatility square overflow");
  const long double numerator = parameters.risk_aversion_lambda * sigma_squared;
  if (!std::isfinite(numerator)) throw std::overflow_error("risk-volatility product overflow");
  const long double kappa_tilde_squared = numerator / eta_tilde;
  const long double alpha = kappa_tilde_squared * tau * tau;
  if (!std::isfinite(alpha) || alpha < 0.0L) throw std::overflow_error("dimensionless Almgren-Chriss risk parameter overflow");
  const long double kappa = alpha == 0.0L ? 0.0L : std::acosh(1.0L + 0.5L * alpha) / tau;
  if (!std::isfinite(kappa)) throw std::overflow_error("Almgren-Chriss kappa overflow");

  const auto inventory = solve_normalized_inventory(parameters.slice_count, alpha);
  const auto quantities = apportion_lots(parent.total_quantity.value(), inventory);
  const auto times = release_times(parent, parameters.slice_count);
  AlmgrenChrissSchedule schedule;
  schedule.style = parameters.style;
  schedule.parameter_provenance_id = parameters.parameter_provenance_id;
  schedule.normalized_inventory_path = inventory;
  schedule.slices.reserve(parameters.slice_count);
  for (std::size_t i = 0U; i < parameters.slice_count; ++i) schedule.slices.push_back({times[i], model::QuantityLots{quantities[i]}});
  if (schedule.total_quantity() != parent.total_quantity) throw std::logic_error("Almgren-Chriss schedule does not conserve parent quantity");
  schedule.diagnostics = diagnostics(parent.total_quantity.value(), quantities, parameters, tau, eta_tilde, kappa_tilde_squared, kappa);
  return schedule;
}

AlmgrenChrissPolicy::AlmgrenChrissPolicy(model::StrategyId strategy_id, AlmgrenChrissParameters parameters)
    : strategy_id_(std::move(strategy_id)), parameters_(std::move(parameters)) {}

model::StrategyId AlmgrenChrissPolicy::strategy_id() const { return strategy_id_; }

void AlmgrenChrissPolicy::reset(const policy::ParentOrderDefinition& parent, const policy::PolicyEnvironment& environment) {
  if (environment.strategy_id != strategy_id_) throw std::invalid_argument("strategy id does not match environment");
  parent_ = parent;
  environment_ = environment;
  schedule_ = build_almgren_chriss_schedule(parent, parameters_);
  next_client_order_id_ = 1U;
}

policy::PolicyAction AlmgrenChrissPolicy::on_observation(const policy::PolicyObservation& observation) {
  if (!schedule_.has_value() || !parent_.has_value() || !environment_.has_value()) throw std::logic_error("policy must be reset before use");
  if (!policy::same_policy_environment(observation.environment(), *environment_)) throw std::invalid_argument("observation environment mismatch");
  const auto remaining = observation.parent().remaining_quantity.value();
  if (remaining == 0U || observation.decision_time().value() < parent_->start_time.value()) return {observation.decision_id(), observation.decision_time(), policy::NoAction{}};
  std::uint64_t cumulative_target = 0U;
  for (const auto& slice : schedule_->slices) {
    if (slice.release_time.value() <= observation.decision_time().value()) {
      if (slice.quantity.value() > std::numeric_limits<std::uint64_t>::max() - cumulative_target) throw std::overflow_error("Almgren-Chriss cumulative target overflow");
      cumulative_target += slice.quantity.value();
    }
  }
  const auto already_filled = observation.parent().cumulative_filled.value();
  if (cumulative_target <= already_filled || observation.pending_command_count() != 0U || !observation.active_orders().empty()) return {observation.decision_id(), observation.decision_time(), policy::NoAction{}};
  const auto due = std::min<std::uint64_t>(remaining, cumulative_target - already_filled);
  const auto divisor = std::gcd(due, remaining);
  const policy::QuantityFraction fraction{due / divisor, remaining / divisor};
  if (std::find(environment_->allowed_quantity_fractions.begin(), environment_->allowed_quantity_fractions.end(), fraction) == environment_->allowed_quantity_fractions.end()) throw std::invalid_argument("exact Almgren-Chriss quantity fraction is not permitted by policy environment");
  policy::SubmitChildAction submit;
  submit.client_order_id = model::ClientOrderId{next_client_order_id_++};
  submit.quantity_fraction = fraction;
  if (parameters_.style == ExecutionStyle::Aggressive) {
    submit.order_type = model::OrderType::Market;
    submit.time_in_force = model::TimeInForce::ImmediateOrCancel;
  } else {
    submit.order_type = model::OrderType::Limit;
    submit.time_in_force = model::TimeInForce::GoodTilCancelled;
    submit.placement = policy::LimitPlacement{policy::LimitReference::SameSideBest, model::TickOffset{0}};
    submit.post_only = true;
  }
  return {observation.decision_id(), observation.decision_time(), submit};
}

const AlmgrenChrissSchedule& AlmgrenChrissPolicy::schedule() const {
  if (!schedule_.has_value()) throw std::logic_error("policy has not been reset");
  return *schedule_;
}

}  // namespace robust_execution::strategies
