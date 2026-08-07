#include "robust_execution/strategies/baselines.hpp"

#include <algorithm>
#include <limits>
#include <numeric>
#include <sstream>
#include <stdexcept>

namespace robust_execution::strategies {
namespace {

std::vector<std::uint64_t> allocate_lots(std::uint64_t total, const std::vector<std::uint64_t>& weights) {
  if (weights.empty()) throw std::invalid_argument("schedule weights must not be empty");
  std::uint64_t weight_sum = 0U;
  for (const auto weight : weights) {
    if (weight > std::numeric_limits<std::uint64_t>::max() - weight_sum) throw std::overflow_error("schedule weight sum overflow");
    weight_sum += weight;
  }
  if (weight_sum == 0U) throw std::invalid_argument("schedule weights must sum to a positive value");
  std::vector<std::uint64_t> quantities(weights.size(), 0U);
  struct Remainder { std::size_t index; std::uint64_t remainder; };
  std::vector<Remainder> remainders;
  remainders.reserve(weights.size());
  std::uint64_t assigned = 0U;
  for (std::size_t i = 0; i < weights.size(); ++i) {
    if (total != 0U && weights[i] > std::numeric_limits<std::uint64_t>::max() / total) {
      throw std::overflow_error("schedule allocation product overflow");
    }
    const auto product = total * weights[i];
    const auto quotient = product / weight_sum;
    quantities[i] = quotient;
    assigned += quotient;
    remainders.push_back({i, product % weight_sum});
  }
  std::sort(remainders.begin(), remainders.end(), [](const auto& a, const auto& b) {
    if (a.remainder != b.remainder) return a.remainder > b.remainder;
    return a.index < b.index;
  });
  for (std::uint64_t extra = 0U; extra < total - assigned; ++extra) quantities[remainders[extra].index] += 1U;
  return quantities;
}

std::vector<model::TimestampNs> release_times(const policy::ParentOrderDefinition& parent, std::size_t count) {
  if (count == 0U) throw std::invalid_argument("slice_count must be positive");
  if (parent.start_time.domain() != parent.end_time.domain()) throw std::invalid_argument("parent clocks must match");
  if (parent.end_time.value() <= parent.start_time.value()) throw std::invalid_argument("parent horizon must be positive");
  std::vector<model::TimestampNs> out;
  out.reserve(count);
  const auto duration = parent.end_time.value() - parent.start_time.value();
  for (std::size_t i = 0; i < count; ++i) {
    const auto count64 = static_cast<std::int64_t>(count);
    const auto index64 = static_cast<std::int64_t>(i);
    const auto quotient = duration / count64;
    const auto remainder = duration % count64;
    if (quotient != 0 && index64 > std::numeric_limits<std::int64_t>::max() / quotient) {
      throw std::overflow_error("schedule release-time overflow");
    }
    const auto offset = quotient * index64 + (remainder * index64) / count64;
    if (parent.start_time.value() > std::numeric_limits<std::int64_t>::max() - offset) {
      throw std::overflow_error("schedule timestamp overflow");
    }
    out.emplace_back(parent.start_time.domain(), parent.start_time.value() + offset);
  }
  return out;
}

}  // namespace

std::string_view to_string(BaselineKind value) noexcept {
  switch (value) {
    case BaselineKind::ImmediateAggressive: return "immediate_aggressive";
    case BaselineKind::Twap: return "twap";
    case BaselineKind::PastVolumeInformed: return "past_volume_informed";
  }
  return "unknown";
}
std::string_view to_string(ExecutionStyle value) noexcept { return value == ExecutionStyle::Aggressive ? "aggressive" : "passive"; }

model::QuantityLots BaselineSchedule::total_quantity() const {
  std::uint64_t total = 0U;
  for (const auto& slice : slices) total += slice.quantity.value();
  return model::QuantityLots{total};
}

std::string BaselineSchedule::canonical() const {
  std::ostringstream out;
  out << to_string(kind) << '|' << to_string(style) << '|' << provenance_id;
  for (const auto& slice : slices) out << '|' << slice.release_time.value() << ':' << slice.quantity.value();
  return out.str();
}

VolumeProfile build_past_volume_profile(
    std::size_t bucket_count,
    const std::vector<VolumeObservation>& observations,
    model::TimestampNs training_cutoff,
    std::string provenance_id
) {
  if (bucket_count == 0U) throw std::invalid_argument("volume profile bucket_count must be positive");
  if (provenance_id.empty()) throw std::invalid_argument("volume profile provenance_id must not be empty");
  std::vector<std::uint64_t> weights(bucket_count, 0U);
  for (const auto& observation : observations) {
    if (observation.event_time.domain() != training_cutoff.domain()) throw std::invalid_argument("volume observation clock must match cutoff clock");
    if (observation.event_time.value() > training_cutoff.value()) throw std::invalid_argument("volume observation occurs after training cutoff");
    if (observation.bucket_index >= bucket_count) throw std::invalid_argument("volume observation bucket index out of range");
    const auto quantity = observation.executed_quantity.value();
    if (quantity > std::numeric_limits<std::uint64_t>::max() - weights[observation.bucket_index]) throw std::overflow_error("volume bucket sum overflow");
    weights[observation.bucket_index] += quantity;
  }
  if (std::all_of(weights.begin(), weights.end(), [](std::uint64_t value) { return value == 0U; })) {
    throw std::invalid_argument("volume profile has no positive past volume");
  }
  return VolumeProfile{std::move(weights), training_cutoff, std::move(provenance_id)};
}

BaselineSchedule build_baseline_schedule(const policy::ParentOrderDefinition& parent, const BaselineConfig& config) {
  if (parent.total_quantity.value() == 0U) throw std::invalid_argument("parent quantity must be positive");
  if (config.kind == BaselineKind::ImmediateAggressive && config.style != ExecutionStyle::Aggressive) {
    throw std::invalid_argument("immediate baseline is defined as aggressive");
  }
  std::vector<std::uint64_t> weights;
  std::string provenance = "predeclared_schedule";
  std::size_t count = config.slice_count;
  if (config.kind == BaselineKind::ImmediateAggressive) {
    count = 1U;
    weights = {1U};
  } else if (config.kind == BaselineKind::Twap) {
    if (count == 0U) throw std::invalid_argument("TWAP slice_count must be positive");
    weights.assign(count, 1U);
  } else {
    if (!config.volume_profile.has_value()) throw std::invalid_argument("volume-informed schedule requires a past-only profile");
    const auto& profile = *config.volume_profile;
    if (profile.provenance_id.empty()) throw std::invalid_argument("volume profile provenance_id must not be empty");
    if (profile.training_cutoff.domain() != parent.start_time.domain()) throw std::invalid_argument("volume profile cutoff clock must match parent clock");
    if (profile.training_cutoff.value() >= parent.start_time.value()) throw std::invalid_argument("volume profile must be frozen strictly before episode start");
    if (profile.bucket_weights.empty()) throw std::invalid_argument("volume profile must contain weights");
    count = profile.bucket_weights.size();
    weights.assign(profile.bucket_weights.cbegin(), profile.bucket_weights.cend());
    provenance = profile.provenance_id;
  }
  const auto quantities = allocate_lots(parent.total_quantity.value(), weights);
  const auto times = release_times(parent, count);
  BaselineSchedule schedule{config.kind, config.style, {}, provenance};
  for (std::size_t i = 0; i < count; ++i) {
    if (quantities[i] > 0U) schedule.slices.push_back({times[i], model::QuantityLots{quantities[i]}});
  }
  if (schedule.total_quantity() != parent.total_quantity) throw std::logic_error("schedule does not conserve parent quantity");
  return schedule;
}

ScheduledBaselinePolicy::ScheduledBaselinePolicy(model::StrategyId strategy_id, BaselineConfig config)
    : strategy_id_(std::move(strategy_id)), config_(std::move(config)) {}
model::StrategyId ScheduledBaselinePolicy::strategy_id() const { return strategy_id_; }
void ScheduledBaselinePolicy::reset(const policy::ParentOrderDefinition& parent, const policy::PolicyEnvironment& environment) {
  if (environment.strategy_id != strategy_id_) throw std::invalid_argument("strategy id does not match environment");
  parent_ = parent;
  environment_ = environment;
  schedule_ = build_baseline_schedule(parent, config_);
  next_client_order_id_ = 1U;
}

policy::PolicyAction ScheduledBaselinePolicy::on_observation(const policy::PolicyObservation& observation) {
  if (!schedule_.has_value() || !parent_.has_value() || !environment_.has_value()) throw std::logic_error("policy must be reset before use");
  if (!policy::same_policy_environment(observation.environment(), *environment_)) throw std::invalid_argument("observation environment mismatch");
  const auto remaining = observation.parent().remaining_quantity.value();
  if (remaining == 0U || observation.decision_time().value() < parent_->start_time.value()) return {observation.decision_id(), observation.decision_time(), policy::NoAction{}};
  std::uint64_t cumulative_target = 0U;
  for (const auto& slice : schedule_->slices) if (slice.release_time.value() <= observation.decision_time().value()) cumulative_target += slice.quantity.value();
  const auto already_filled = observation.parent().cumulative_filled.value();
  if (cumulative_target <= already_filled || observation.pending_command_count() != 0U || !observation.active_orders().empty()) {
    return {observation.decision_id(), observation.decision_time(), policy::NoAction{}};
  }
  const auto due = std::min<std::uint64_t>(remaining, cumulative_target - already_filled);
  const auto divisor = std::gcd(due, remaining);
  const policy::QuantityFraction fraction{due / divisor, remaining / divisor};
  if (std::find(environment_->allowed_quantity_fractions.begin(), environment_->allowed_quantity_fractions.end(), fraction) == environment_->allowed_quantity_fractions.end()) {
    throw std::invalid_argument("exact scheduled quantity fraction is not permitted by policy environment");
  }
  policy::SubmitChildAction submit;
  submit.client_order_id = model::ClientOrderId{next_client_order_id_++};
  submit.quantity_fraction = fraction;
  if (config_.style == ExecutionStyle::Aggressive) {
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

const BaselineSchedule& ScheduledBaselinePolicy::schedule() const {
  if (!schedule_.has_value()) throw std::logic_error("policy has not been reset");
  return *schedule_;
}

}  // namespace robust_execution::strategies
