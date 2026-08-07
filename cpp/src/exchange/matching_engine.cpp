#include "matching_engine_internal.hpp"

#include <stdexcept>
#include <utility>

namespace robust_execution::exchange {

MatchingEngine::Impl::Impl(MatchingEngineConfig input_config) : config_(std::move(input_config)) {
  const auto issues = model::validate_instrument(config_.instrument);
  if (model::has_errors(issues)) {
    throw std::invalid_argument("matching engine requires a valid instrument definition");
  }
  if (config_.expected_order_count > 0U) {
    active_by_exchange_.reserve(config_.expected_order_count);
    active_by_client_.reserve(config_.expected_order_count);
    exchange_by_client_.reserve(config_.expected_order_count);
    orders_by_exchange_.reserve(config_.expected_order_count);
    all_client_ids_.reserve(config_.expected_order_count);
  }
}

const MatchingEngineConfig& MatchingEngine::Impl::config() const noexcept { return config_; }

MatchingEngine::MatchingEngine(MatchingEngineConfig config)
    : impl_(new Impl(std::move(config))) {}

MatchingEngine::~MatchingEngine() { delete impl_; }

MatchingEngine::MatchingEngine(MatchingEngine&& other) noexcept : impl_(other.impl_) {
  other.impl_ = nullptr;
}

MatchingEngine& MatchingEngine::operator=(MatchingEngine&& other) noexcept {
  if (this != &other) {
    delete impl_;
    impl_ = other.impl_;
    other.impl_ = nullptr;
  }
  return *this;
}

SubmitResult MatchingEngine::submit(const model::OrderSubmit& command) {
  return impl_->submit(command);
}

CancelResult MatchingEngine::cancel(const model::CancelRequest& command) {
  return impl_->cancel(command);
}

ReplaceResult MatchingEngine::replace(const model::ReplaceRequest& command) {
  return impl_->replace(command);
}

std::optional<OrderView> MatchingEngine::order(model::ClientOrderId client_order_id) const {
  return impl_->order(client_order_id);
}

std::optional<model::PriceTicks> MatchingEngine::best_bid() const noexcept {
  return impl_->best_bid();
}

std::optional<model::PriceTicks> MatchingEngine::best_ask() const noexcept {
  return impl_->best_ask();
}

model::QuantityLots MatchingEngine::quantity_at(
    model::Side side,
    model::PriceTicks price
) const {
  return impl_->quantity_at(side, price);
}

std::size_t MatchingEngine::active_order_count() const noexcept {
  return impl_->active_order_count();
}

BookView MatchingEngine::book(std::size_t maximum_levels_per_side) const {
  return impl_->book(maximum_levels_per_side);
}

bool MatchingEngine::would_cross(
    model::Side side,
    std::optional<model::PriceTicks> limit_price
) const noexcept {
  return impl_->would_cross(side, limit_price);
}

bool MatchingEngine::can_fully_execute(
    model::Side side,
    model::QuantityLots quantity,
    std::optional<model::PriceTicks> limit_price
) const noexcept {
  return impl_->can_fully_execute(side, quantity, limit_price);
}

std::vector<InvariantViolation> MatchingEngine::validate_invariants() const {
  return impl_->validate_invariants();
}

std::string MatchingEngine::canonical_state() const { return impl_->canonical_state(); }

const MatchingEngineConfig& MatchingEngine::config() const noexcept { return impl_->config(); }

}  // namespace robust_execution::exchange
