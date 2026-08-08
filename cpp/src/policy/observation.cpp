#include "robust_execution/policy/observation.hpp"

#include "robust_execution/model/validation.hpp"
#include "robust_execution/simulation/canonical_event.hpp"
#include "robust_execution/util/sha256.hpp"

#include <algorithm>
#include <deque>
#include <limits>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <utility>

namespace robust_execution::policy {
namespace {

void require_environment(const PolicyEnvironment& environment) {
  if (!environment.instrument.venue.valid() || !environment.instrument.instrument.valid() ||
      !environment.strategy_id.valid() || !environment.fee_schedule_id.valid() ||
      !environment.latency_model_id.valid() || environment.decision_interval_ns <= 0 ||
      environment.top_levels == 0U || environment.maximum_live_children == 0U ||
      environment.maximum_commands_per_decision == 0U) {
    throw std::invalid_argument("policy environment identifiers and positive limits are required");
  }
}

void require_same_clock(model::TimestampNs lhs, model::TimestampNs rhs, const char* context) {
  if (lhs.domain() != rhs.domain()) {
    throw std::invalid_argument(std::string{context} + " uses mixed clock domains");
  }
}

std::vector<model::BookLevel> top_levels(
    const std::map<std::int64_t, model::BookLevel>& levels,
    std::size_t maximum,
    bool descending
) {
  std::vector<model::BookLevel> output;
  output.reserve(std::min(maximum, levels.size()));
  if (descending) {
    for (auto iterator = levels.rbegin(); iterator != levels.rend() && output.size() < maximum;
         ++iterator) {
      output.push_back(iterator->second);
    }
  } else {
    for (auto iterator = levels.begin(); iterator != levels.end() && output.size() < maximum;
         ++iterator) {
      output.push_back(iterator->second);
    }
  }
  return output;
}

model::QuantityLots sum_quantity(const std::vector<model::BookLevel>& levels) {
  model::QuantityLots total{0U};
  for (const auto& level : levels) {
    const auto next = model::checked_add(total, level.displayed_quantity);
    if (!next.has_value()) {
      throw std::overflow_error("visible book quantity overflow");
    }
    total = *next;
  }
  return total;
}

}  // namespace

PolicyObservation::PolicyObservation(
    model::DecisionId decision_id,
    model::TimestampNs decision_time,
    model::TimestampNs observation_cutoff,
    PolicyEnvironment environment,
    ParentOrderSnapshot parent,
    std::vector<model::BookLevel> bids,
    std::vector<model::BookLevel> asks,
    std::vector<ObservedTrade> recent_trades,
    std::vector<ChildOrderView> active_orders,
    std::size_t pending_command_count,
    ObservationLineage lineage
)
    : decision_id_(decision_id),
      decision_time_(decision_time),
      observation_cutoff_(observation_cutoff),
      environment_(std::move(environment)),
      parent_(std::move(parent)),
      bids_(std::move(bids)),
      asks_(std::move(asks)),
      recent_trades_(std::move(recent_trades)),
      active_orders_(std::move(active_orders)),
      pending_command_count_(pending_command_count),
      lineage_(std::move(lineage)) {
  if (!decision_id_.valid()) {
    throw std::invalid_argument("policy observation requires a valid decision identifier");
  }
  require_environment(environment_);
  require_same_clock(decision_time_, observation_cutoff_, "policy observation");
  if (observation_cutoff_.value() > decision_time_.value()) {
    throw std::invalid_argument("observation cutoff cannot exceed decision time");
  }
  if (lineage_.maximum_available_time.has_value()) {
    require_same_clock(decision_time_, *lineage_.maximum_available_time, "observation lineage");
    if (lineage_.maximum_available_time->value() > decision_time_.value()) {
      throw std::invalid_argument("observation includes an event unavailable at decision time");
    }
  }
  const auto validate_levels = [](const std::vector<model::BookLevel>& levels, bool descending) {
    for (std::size_t index = 0U; index < levels.size(); ++index) {
      if (levels[index].price.value() <= 0 || levels[index].displayed_quantity.is_zero()) {
        throw std::invalid_argument("policy observation contains a non-positive book level");
      }
      if (index > 0U) {
        const auto previous = levels[index - 1U].price.value();
        const auto current = levels[index].price.value();
        if ((descending && current >= previous) || (!descending && current <= previous)) {
          throw std::invalid_argument("policy observation book levels are unsorted or duplicated");
        }
      }
    }
  };
  validate_levels(bids_, true);
  validate_levels(asks_, false);
  if (!bids_.empty() && !asks_.empty() &&
      bids_.front().price.value() >= asks_.front().price.value()) {
    throw std::invalid_argument("policy observation cannot contain a crossed or locked book");
  }
}

model::DecisionId PolicyObservation::decision_id() const noexcept { return decision_id_; }
model::TimestampNs PolicyObservation::decision_time() const noexcept { return decision_time_; }
model::TimestampNs PolicyObservation::observation_cutoff() const noexcept {
  return observation_cutoff_;
}
const PolicyEnvironment& PolicyObservation::environment() const noexcept { return environment_; }
const ParentOrderSnapshot& PolicyObservation::parent() const noexcept { return parent_; }
const std::vector<model::BookLevel>& PolicyObservation::bids() const noexcept { return bids_; }
const std::vector<model::BookLevel>& PolicyObservation::asks() const noexcept { return asks_; }
const std::vector<ObservedTrade>& PolicyObservation::recent_trades() const noexcept {
  return recent_trades_;
}
const std::vector<ChildOrderView>& PolicyObservation::active_orders() const noexcept {
  return active_orders_;
}
std::size_t PolicyObservation::pending_command_count() const noexcept {
  return pending_command_count_;
}
const ObservationLineage& PolicyObservation::lineage() const noexcept { return lineage_; }

std::optional<model::PriceTicks> PolicyObservation::best_bid() const noexcept {
  return bids_.empty() ? std::nullopt : std::optional{bids_.front().price};
}

std::optional<model::PriceTicks> PolicyObservation::best_ask() const noexcept {
  return asks_.empty() ? std::nullopt : std::optional{asks_.front().price};
}

std::optional<std::int64_t> PolicyObservation::spread_ticks() const noexcept {
  if (bids_.empty() || asks_.empty()) {
    return std::nullopt;
  }
  return asks_.front().price.value() - bids_.front().price.value();
}

std::optional<std::int64_t> PolicyObservation::midpoint_twice_ticks() const noexcept {
  if (bids_.empty() || asks_.empty()) {
    return std::nullopt;
  }
  const auto bid = bids_.front().price.value();
  const auto ask = asks_.front().price.value();
  if ((ask > 0 && bid > std::numeric_limits<std::int64_t>::max() - ask) ||
      (ask < 0 && bid < std::numeric_limits<std::int64_t>::min() - ask)) {
    return std::nullopt;
  }
  return bid + ask;
}

std::int64_t PolicyObservation::elapsed_time_ns() const {
  require_same_clock(decision_time_, parent_.start_time, "policy elapsed time");
  return decision_time_.value() <= parent_.start_time.value()
             ? 0
             : decision_time_.value() - parent_.start_time.value();
}

std::int64_t PolicyObservation::time_remaining_ns() const {
  require_same_clock(decision_time_, parent_.end_time, "policy time remaining");
  return decision_time_.value() >= parent_.end_time.value()
             ? 0
             : parent_.end_time.value() - decision_time_.value();
}

model::QuantityLots PolicyObservation::visible_bid_quantity() const {
  return sum_quantity(bids_);
}

model::QuantityLots PolicyObservation::visible_ask_quantity() const {
  return sum_quantity(asks_);
}

std::string PolicyObservation::canonical() const {
  std::ostringstream output;
  output << decision_id_.value() << '|' << static_cast<unsigned>(decision_time_.domain()) << '|'
         << decision_time_.value() << '|' << observation_cutoff_.value() << '|'
         << environment_.instrument.venue.value().size() << ':'
         << environment_.instrument.venue.value() << '|'
         << environment_.instrument.instrument.value().size() << ':'
         << environment_.instrument.instrument.value() << '|'
         << environment_.strategy_id.value().size() << ':' << environment_.strategy_id.value() << '|'
         << environment_.fee_schedule_id.value().size() << ':'
         << environment_.fee_schedule_id.value() << '|'
         << environment_.latency_model_id.value().size() << ':'
         << environment_.latency_model_id.value() << '|'
         << environment_.decision_interval_ns << '|' << environment_.top_levels << '|'
         << environment_.maximum_recent_trades << '|' << environment_.maximum_live_children << '|'
         << environment_.maximum_commands_per_decision << '|'
         << static_cast<unsigned>(environment_.lot_rounding) << '|'
         << environment_.allow_market_orders << '|' << environment_.allow_marketable_limits << '|'
         << environment_.allow_post_only << '|' << environment_.allowed_quantity_fractions.size() << '|';
  for (const auto& fraction : environment_.allowed_quantity_fractions) {
    output << fraction.numerator << '|' << fraction.denominator << '|';
  }
  output << environment_.allowed_tick_offsets.size() << '|';
  for (const auto offset : environment_.allowed_tick_offsets) {
    output << offset.value() << '|';
  }
  output << parent_.parent_order_id.value() << '|' << static_cast<unsigned>(parent_.side) << '|'
         << parent_.start_time.value() << '|' << parent_.end_time.value() << '|'
         << parent_.arrival_price.value() << '|' << parent_.terminal_rule_id.size() << ':'
         << parent_.terminal_rule_id << '|' << parent_.total_quantity.value() << '|'
         << parent_.cumulative_filled.value() << '|' << parent_.remaining_quantity.value() << '|'
         << parent_.gross_cash_flow.value() << '|' << parent_.explicit_fees.value() << '|'
         << parent_.net_cash_flow.value() << '|' << parent_.fill_count << '|'
         << to_string(parent_.status) << '|' << parent_.terminal_completion_applied << '|'
         << pending_command_count_ << '|';
  const auto write_levels = [&output](const std::vector<model::BookLevel>& levels) {
    output << levels.size() << '|';
    for (const auto& level : levels) {
      output << level.price.value() << '|' << level.displayed_quantity.value() << '|';
      if (level.order_count.has_value()) {
        output << *level.order_count;
      }
      output << '|';
    }
  };
  write_levels(bids_);
  write_levels(asks_);
  output << recent_trades_.size() << '|';
  for (const auto& trade : recent_trades_) {
    output << trade.trade.trade_id.value() << '|';
    if (trade.trade.external_trade_id.has_value()) {
      output << trade.trade.external_trade_id->value().size() << ':'
             << trade.trade.external_trade_id->value();
    }
    output << '|' << trade.trade.price.value() << '|' << trade.trade.quantity.value() << '|'
           << static_cast<unsigned>(trade.trade.aggressor_side) << '|'
           << trade.event_time.value() << '|' << trade.available_time.value() << '|';
  }
  output << active_orders_.size() << '|';
  for (const auto& child : active_orders_) {
    output << child.client_order_id.value() << '|';
    if (child.exchange_order_id.has_value()) {
      output << child.exchange_order_id->value();
    }
    output << '|' << child.decision_id.value() << '|' << static_cast<unsigned>(child.side) << '|'
           << static_cast<unsigned>(child.order_type) << '|'
           << static_cast<unsigned>(child.time_in_force) << '|'
           << child.requested_quantity.value() << '|' << child.cumulative_filled.value() << '|'
           << child.leaves_quantity.value() << '|';
    if (child.limit_price.has_value()) {
      output << child.limit_price->value();
    }
    output << '|' << child.post_only << '|' << static_cast<unsigned>(child.state) << '|'
           << child.cancel_pending << '|' << child.replace_pending << '|';
  }
  output << lineage_.delivered_event_count << '|';
  if (lineage_.last_event_id.has_value()) {
    output << lineage_.last_event_id->value();
  }
  output << '|';
  if (lineage_.maximum_event_time.has_value()) {
    output << lineage_.maximum_event_time->value();
  }
  output << '|';
  if (lineage_.maximum_available_time.has_value()) {
    output << lineage_.maximum_available_time->value();
  }
  output << '|' << lineage_.rolling_sha256;
  return output.str();
}

std::string PolicyObservation::hash() const { return util::sha256_hex(canonical()); }

class ObservationBuilder::Impl {
 public:
  explicit Impl(PolicyEnvironment environment) : environment_(std::move(environment)) {
    require_environment(environment_);
  }

  PolicyEnvironment environment_;
  std::map<std::int64_t, model::BookLevel> bids_;
  std::map<std::int64_t, model::BookLevel> asks_;
  std::deque<ObservedTrade> recent_trades_;
  std::optional<model::TimestampNs> delivery_watermark_;
  ObservationLineage lineage_;

  void update_maximum(std::optional<model::TimestampNs>& target, model::TimestampNs value) {
    if (!target.has_value()) {
      target = value;
      return;
    }
    require_same_clock(*target, value, "observation event stream");
    if (value.value() > target->value()) {
      target = value;
    }
  }

  void apply_snapshot(const model::BookSnapshot& snapshot) {
    bids_.clear();
    asks_.clear();
    for (const auto& level : snapshot.bids) {
      if (level.price.value() <= 0 || level.displayed_quantity.is_zero()) {
        throw std::invalid_argument("book snapshot contains a non-positive bid level");
      }
      bids_[level.price.value()] = level;
    }
    for (const auto& level : snapshot.asks) {
      if (level.price.value() <= 0 || level.displayed_quantity.is_zero()) {
        throw std::invalid_argument("book snapshot contains a non-positive ask level");
      }
      asks_[level.price.value()] = level;
    }
  }

  void apply_depth(const model::DepthUpdate& update) {
    auto& side = update.side == model::Side::Buy ? bids_ : asks_;
    if (update.action == model::BookUpdateAction::Delete || update.quantity_after.is_zero()) {
      side.erase(update.price.value());
      return;
    }
    if (update.price.value() <= 0) {
      throw std::invalid_argument("depth update contains a non-positive price");
    }
    side[update.price.value()] = model::BookLevel{
        update.price,
        update.quantity_after,
        update.order_count_after,
    };
  }

  void ensure_uncrossed() const {
    if (!bids_.empty() && !asks_.empty() && bids_.rbegin()->first >= asks_.begin()->first) {
      throw std::invalid_argument("delivered market event produced a crossed or locked visible book");
    }
  }
};

ObservationBuilder::ObservationBuilder(PolicyEnvironment environment)
    : impl_(new Impl(std::move(environment))) {}

ObservationBuilder::~ObservationBuilder() { delete impl_; }

ObservationBuilder::ObservationBuilder(ObservationBuilder&& other) noexcept : impl_(other.impl_) {
  other.impl_ = nullptr;
}

ObservationBuilder& ObservationBuilder::operator=(ObservationBuilder&& other) noexcept {
  if (this != &other) {
    delete impl_;
    impl_ = other.impl_;
    other.impl_ = nullptr;
  }
  return *this;
}

void ObservationBuilder::ingest_delivered_event(
    const model::Event& event,
    model::TimestampNs delivery_time
) {
  const auto validation_issues = model::validate_event(event);
  if (model::has_errors(validation_issues)) {
    throw std::invalid_argument("observation builder received an invalid canonical event");
  }
  if (event.header.venue != impl_->environment_.instrument.venue ||
      event.header.instrument != impl_->environment_.instrument.instrument) {
    throw std::invalid_argument("observation builder received another venue or instrument");
  }
  if (!event.header.available_time.has_value()) {
    throw std::invalid_argument("delivered observation event lacks available_time");
  }
  require_same_clock(delivery_time, *event.header.available_time, "delivered observation event");
  if (event.header.available_time->value() > delivery_time.value()) {
    throw std::invalid_argument("event cannot be ingested before its availability time");
  }
  if (impl_->delivery_watermark_.has_value()) {
    require_same_clock(*impl_->delivery_watermark_, delivery_time, "observation delivery stream");
    if (delivery_time.value() < impl_->delivery_watermark_->value()) {
      throw std::invalid_argument("delivered observation events must be ingested monotonically");
    }
  }

  const auto bids_before = impl_->bids_;
  const auto asks_before = impl_->asks_;
  const auto trades_before = impl_->recent_trades_;
  try {
    std::visit(
        [this, &event](const auto& value) {
          using Payload = std::decay_t<decltype(value)>;
          if constexpr (std::is_same_v<Payload, model::BookSnapshot>) {
            impl_->apply_snapshot(value);
          } else if constexpr (std::is_same_v<Payload, model::DepthUpdate>) {
            impl_->apply_depth(value);
          } else if constexpr (std::is_same_v<Payload, model::Trade>) {
            impl_->recent_trades_.push_back(ObservedTrade{
                value,
                event.header.event_time,
                *event.header.available_time,
            });
            while (impl_->recent_trades_.size() > impl_->environment_.maximum_recent_trades) {
              impl_->recent_trades_.pop_front();
            }
          }
        },
        event.payload
    );
    impl_->ensure_uncrossed();
  } catch (...) {
    impl_->bids_ = bids_before;
    impl_->asks_ = asks_before;
    impl_->recent_trades_ = trades_before;
    throw;
  }
  impl_->delivery_watermark_ = delivery_time;
  ++impl_->lineage_.delivered_event_count;
  impl_->lineage_.last_event_id = event.header.event_id;
  impl_->update_maximum(impl_->lineage_.maximum_event_time, event.header.event_time);
  impl_->update_maximum(impl_->lineage_.maximum_available_time, *event.header.available_time);
  impl_->lineage_.rolling_sha256 = util::sha256_hex(
      impl_->lineage_.rolling_sha256 + simulation::canonical_event(event)
  );
}

PolicyObservation ObservationBuilder::build(
    model::DecisionId decision_id,
    model::TimestampNs decision_time,
    const ExecutionState& state
) const {
  if (!same_policy_environment(state.environment(), impl_->environment_)) {
    throw std::invalid_argument("execution state and observation builder environments differ");
  }
  if (impl_->delivery_watermark_.has_value()) {
    require_same_clock(decision_time, *impl_->delivery_watermark_, "policy decision");
    if (decision_time.value() < impl_->delivery_watermark_->value()) {
      throw std::invalid_argument("cannot build an observation before the ingestion watermark");
    }
  }
  const auto cutoff = impl_->lineage_.maximum_event_time.value_or(decision_time);
  std::vector<ObservedTrade> trades(impl_->recent_trades_.begin(), impl_->recent_trades_.end());
  return PolicyObservation{
      decision_id,
      decision_time,
      cutoff,
      impl_->environment_,
      state.parent_snapshot(decision_time),
      top_levels(impl_->bids_, impl_->environment_.top_levels, true),
      top_levels(impl_->asks_, impl_->environment_.top_levels, false),
      std::move(trades),
      state.acknowledged_active_orders(),
      state.pending_command_count(),
      impl_->lineage_,
  };
}

const PolicyEnvironment& ObservationBuilder::environment() const noexcept {
  return impl_->environment_;
}

std::optional<model::TimestampNs> ObservationBuilder::delivery_watermark() const noexcept {
  return impl_->delivery_watermark_;
}

}  // namespace robust_execution::policy
