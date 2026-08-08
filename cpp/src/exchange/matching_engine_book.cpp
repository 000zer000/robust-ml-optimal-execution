#include "matching_engine_internal.hpp"

#include <algorithm>
#include <iterator>
#include <limits>
#include <stdexcept>
#include <string>
#include <utility>

namespace robust_execution::exchange {

std::optional<OrderView> MatchingEngine::Impl::order(model::ClientOrderId client_order_id) const {
  const auto exchange = exchange_by_client_.find(client_order_id.value());
  if (exchange == exchange_by_client_.end()) {
    return std::nullopt;
  }
  const auto found = orders_by_exchange_.find(exchange->second);
  if (found == orders_by_exchange_.end()) {
    return std::nullopt;
  }
  return found->second;
}

std::optional<model::PriceTicks> MatchingEngine::Impl::best_bid() const noexcept {
  if (bids_.empty()) {
    return std::nullopt;
  }
  return model::PriceTicks{bids_.begin()->first};
}

std::optional<model::PriceTicks> MatchingEngine::Impl::best_ask() const noexcept {
  if (asks_.empty()) {
    return std::nullopt;
  }
  return model::PriceTicks{asks_.begin()->first};
}

model::QuantityLots MatchingEngine::Impl::quantity_at(
    model::Side side,
    model::PriceTicks price
) const {
  if (side == model::Side::Buy) {
    const auto found = bids_.find(price.value());
    return found == bids_.end() ? model::QuantityLots{0U} : found->second.total_quantity;
  }
  const auto found = asks_.find(price.value());
  return found == asks_.end() ? model::QuantityLots{0U} : found->second.total_quantity;
}

std::size_t MatchingEngine::Impl::active_order_count() const noexcept {
  return active_by_exchange_.size();
}

BookView MatchingEngine::Impl::book(std::size_t maximum_levels_per_side) const {
  BookView result;
  append_levels(bids_, maximum_levels_per_side, result.bids);
  append_levels(asks_, maximum_levels_per_side, result.asks);
  return result;
}

bool MatchingEngine::Impl::would_cross(
    model::Side side,
    std::optional<model::PriceTicks> limit_price
) const noexcept {
  if (!limit_price.has_value()) {
    return side == model::Side::Buy ? !asks_.empty() : !bids_.empty();
  }
  if (side == model::Side::Buy) {
    return !asks_.empty() && asks_.begin()->first <= limit_price->value();
  }
  return !bids_.empty() && bids_.begin()->first >= limit_price->value();
}

bool MatchingEngine::Impl::can_fully_execute(
    model::Side side,
    model::QuantityLots quantity,
    std::optional<model::PriceTicks> limit_price
) const noexcept {
  std::uint64_t accumulated = 0U;
  if (side == model::Side::Buy) {
    for (const auto& [price, level] : asks_) {
      if (limit_price.has_value() && price > limit_price->value()) {
        break;
      }
      if (level.total_quantity.value() >= quantity.value() - accumulated) {
        return true;
      }
      accumulated += level.total_quantity.value();
    }
    return accumulated >= quantity.value();
  }
  for (const auto& [price, level] : bids_) {
    if (limit_price.has_value() && price < limit_price->value()) {
      break;
    }
    if (level.total_quantity.value() >= quantity.value() - accumulated) {
      return true;
    }
    accumulated += level.total_quantity.value();
  }
  return accumulated >= quantity.value();
}

std::vector<InvariantViolation> MatchingEngine::Impl::validate_invariants() const {
  std::vector<InvariantViolation> violations;
  if (!bids_.empty() && !asks_.empty() && bids_.begin()->first >= asks_.begin()->first) {
    violations.push_back({"book.crossed", "best bid must be strictly below best ask"});
  }

  std::size_t observed_active = 0U;
  validate_side(bids_, model::Side::Buy, violations, observed_active);
  validate_side(asks_, model::Side::Sell, violations, observed_active);

  if (observed_active != active_by_exchange_.size()) {
    violations.push_back({
        "index.active_count",
        "price-level active order count differs from exchange-order index",
    });
  }
  if (active_by_client_.size() != active_by_exchange_.size()) {
    violations.push_back({
        "index.client_count",
        "active client and exchange order indices have different sizes",
    });
  }
  if (exchange_by_client_.size() != all_client_ids_.size()) {
    violations.push_back({
        "index.used_client_count",
        "all-client identifier set differs from client-to-exchange history",
    });
  }

  for (const auto& [exchange_id, locator] : active_by_exchange_) {
    const auto& view = locator.iterator->view;
    if (view.exchange_order_id.value() != exchange_id || view.side != locator.side ||
        !view.limit_price.has_value() || view.limit_price->value() != locator.price) {
      violations.push_back({
          "index.locator_mismatch",
          "active exchange-order locator disagrees with the stored order",
      });
    }
    const auto client = active_by_client_.find(view.client_order_id.value());
    if (client == active_by_client_.end() || client->second != exchange_id) {
      violations.push_back({
          "index.active_client_missing",
          "active client-order index is missing or inconsistent",
      });
    }
    const auto history = orders_by_exchange_.find(exchange_id);
    if (history == orders_by_exchange_.end() || history->second != view) {
      violations.push_back({
          "index.history_mismatch",
          "active order differs from its history record",
      });
    }
  }
  return violations;
}

std::string MatchingEngine::Impl::canonical_state() const {
  std::ostringstream stream;
  stream << "matching-engine-state-v1\n";
  stream << "next_exchange=" << next_exchange_order_id_ << "\n";
  stream << "next_execution=" << next_execution_id_ << "\n";
  stream << "next_match=" << next_match_sequence_ << "\n";
  stream << "next_priority=" << next_priority_sequence_ << "\n";
  append_canonical_side(stream, "bids", bids_);
  append_canonical_side(stream, "asks", asks_);

  std::vector<std::uint64_t> exchange_ids;
  exchange_ids.reserve(orders_by_exchange_.size());
  for (const auto& [exchange_id, unused] : orders_by_exchange_) {
    static_cast<void>(unused);
    exchange_ids.push_back(exchange_id);
  }
  std::sort(exchange_ids.begin(), exchange_ids.end());
  stream << "orders\n";
  for (const auto exchange_id : exchange_ids) {
    const auto& view = orders_by_exchange_.at(exchange_id);
    stream << view.client_order_id.value() << '|' << view.exchange_order_id.value() << '|'
           << model::to_string(view.side) << '|'
           << (view.limit_price.has_value() ? view.limit_price->value() : 0) << '|'
           << view.original_quantity.value() << '|' << view.cumulative_filled.value() << '|'
           << view.leaves_quantity.value() << '|' << model::to_string(view.state) << '|'
           << view.priority_sequence << '\n';
  }
  return stream.str();
}

bool MatchingEngine::Impl::can_add_to_level(
    model::Side side,
    model::PriceTicks price,
    model::QuantityLots quantity
) const noexcept {
  if (side == model::Side::Buy) {
    return can_add_to_level_map(bids_, price, quantity);
  }
  return can_add_to_level_map(asks_, price, quantity);
}

template <typename Book>
bool MatchingEngine::Impl::can_add_to_level_map(
    const Book& book,
    model::PriceTicks price,
    model::QuantityLots quantity
) noexcept {
  const auto found = book.find(price.value());
  if (found == book.end()) {
    return true;
  }
  if (found->second.orders.size() >=
      static_cast<std::size_t>(std::numeric_limits<std::uint32_t>::max())) {
    return false;
  }
  return model::checked_add(found->second.total_quantity, quantity).has_value();
}

void MatchingEngine::Impl::match(OrderView& incoming, std::vector<MatchExecution>& matches) {
  if (incoming.side == model::Side::Buy) {
    match_buy(incoming, matches);
  } else {
    match_sell(incoming, matches);
  }
}

void MatchingEngine::Impl::match_buy(OrderView& incoming, std::vector<MatchExecution>& matches) {
  while (!incoming.leaves_quantity.is_zero() && !asks_.empty()) {
    auto level_it = asks_.begin();
    if (incoming.limit_price.has_value() &&
        level_it->first > incoming.limit_price->value()) {
      break;
    }
    match_level(incoming, level_it->second, matches);
    if (level_it->second.orders.empty()) {
      asks_.erase(level_it);
    }
  }
}

void MatchingEngine::Impl::match_sell(OrderView& incoming, std::vector<MatchExecution>& matches) {
  while (!incoming.leaves_quantity.is_zero() && !bids_.empty()) {
    auto level_it = bids_.begin();
    if (incoming.limit_price.has_value() &&
        level_it->first < incoming.limit_price->value()) {
      break;
    }
    match_level(incoming, level_it->second, matches);
    if (level_it->second.orders.empty()) {
      bids_.erase(level_it);
    }
  }
}

void MatchingEngine::Impl::match_level(
    OrderView& incoming,
    PriceLevel& level,
    std::vector<MatchExecution>& matches
) {
  while (!incoming.leaves_quantity.is_zero() && !level.orders.empty()) {
    auto maker_it = level.orders.begin();
    auto& maker = maker_it->view;
    const auto quantity_value =
        std::min(incoming.leaves_quantity.value(), maker.leaves_quantity.value());
    const model::QuantityLots matched_quantity{quantity_value};
    const auto price = *maker.limit_price;

    maker.leaves_quantity = *model::checked_subtract(maker.leaves_quantity, matched_quantity);
    maker.cumulative_filled =
        *model::checked_add(maker.cumulative_filled, matched_quantity);
    incoming.leaves_quantity =
        *model::checked_subtract(incoming.leaves_quantity, matched_quantity);
    incoming.cumulative_filled =
        *model::checked_add(incoming.cumulative_filled, matched_quantity);
    level.total_quantity = *model::checked_subtract(level.total_quantity, matched_quantity);

    maker.state = maker.leaves_quantity.is_zero() ? model::OrderState::Filled
                                                  : model::OrderState::PartiallyFilled;
    incoming.state = incoming.leaves_quantity.is_zero() ? model::OrderState::Filled
                                                        : model::OrderState::PartiallyFilled;

    const auto match_sequence = allocate(next_match_sequence_);
    const auto match_text = std::string{"synthetic-match-"} +
                            std::to_string(match_sequence);
    const auto maker_execution = model::ExecutionId{allocate(next_execution_id_)};
    const auto taker_execution = model::ExecutionId{allocate(next_execution_id_)};

    matches.push_back(MatchExecution{
        match_sequence,
        model::Trade{
            model::TradeId{match_sequence},
            model::ExternalTradeId{match_text},
            price,
            matched_quantity,
            incoming.side == model::Side::Buy ? model::AggressorSide::Buy
                                               : model::AggressorSide::Sell,
        },
        model::Fill{
            maker_execution,
            maker.client_order_id,
            maker.exchange_order_id,
            match_text,
            maker.side,
            price,
            matched_quantity,
            maker.cumulative_filled,
            maker.leaves_quantity,
            model::LiquidityRole::Maker,
        },
        model::Fill{
            taker_execution,
            incoming.client_order_id,
            incoming.exchange_order_id,
            match_text,
            incoming.side,
            price,
            matched_quantity,
            incoming.cumulative_filled,
            incoming.leaves_quantity,
            model::LiquidityRole::Taker,
        },
    });

    orders_by_exchange_[maker.exchange_order_id.value()] = maker;
    if (maker.leaves_quantity.is_zero()) {
      active_by_client_.erase(maker.client_order_id.value());
      active_by_exchange_.erase(maker.exchange_order_id.value());
      level.orders.erase(maker_it);
    }
  }
}

void MatchingEngine::Impl::rest(const OrderView& order) {
  if (order.side == model::Side::Buy) {
    rest_in_book(bids_, order);
  } else {
    rest_in_book(asks_, order);
  }
}

template <typename Book>
void MatchingEngine::Impl::rest_in_book(Book& book, const OrderView& order) {
  const auto price = order.limit_price->value();
  auto [level_it, inserted] = book.try_emplace(price);
  static_cast<void>(inserted);
  auto& level = level_it->second;
  level.total_quantity = *model::checked_add(level.total_quantity, order.leaves_quantity);
  level.orders.push_back(OrderNode{order});
  auto order_it = std::prev(level.orders.end());
  active_by_exchange_.emplace(
      order.exchange_order_id.value(),
      Locator{order.side, price, order_it}
  );
  active_by_client_.emplace(order.client_order_id.value(), order.exchange_order_id.value());
  orders_by_exchange_[order.exchange_order_id.value()] = order;
}

void MatchingEngine::Impl::remove_active(Locator locator, model::OrderState terminal_state) {
  const auto view = locator.iterator->view;
  auto terminal = view;
  terminal.leaves_quantity = model::QuantityLots{0U};
  terminal.state = terminal_state;

  if (locator.side == model::Side::Buy) {
    remove_from_book(bids_, locator, view.leaves_quantity);
  } else {
    remove_from_book(asks_, locator, view.leaves_quantity);
  }
  active_by_client_.erase(view.client_order_id.value());
  active_by_exchange_.erase(view.exchange_order_id.value());
  orders_by_exchange_[view.exchange_order_id.value()] = terminal;
}

template <typename Book>
void MatchingEngine::Impl::remove_from_book(
    Book& book,
    const Locator& locator,
    model::QuantityLots leaves_quantity
) {
  auto level_it = book.find(locator.price);
  if (level_it == book.end()) {
    throw std::logic_error("active-order locator points to a missing price level");
  }
  auto& level = level_it->second;
  level.total_quantity = *model::checked_subtract(level.total_quantity, leaves_quantity);
  level.orders.erase(locator.iterator);
  if (level.orders.empty()) {
    book.erase(level_it);
  }
}

template <typename Book>
void MatchingEngine::Impl::append_levels(
    const Book& source,
    std::size_t maximum_levels,
    std::vector<PriceLevelView>& destination
) {
  for (const auto& [price, level] : source) {
    if (maximum_levels != 0U && destination.size() >= maximum_levels) {
      break;
    }
    destination.push_back(PriceLevelView{
        model::PriceTicks{price},
        level.total_quantity,
        static_cast<std::uint32_t>(level.orders.size()),
    });
  }
}

template <typename Book>
void MatchingEngine::Impl::validate_side(
    const Book& book,
    model::Side expected_side,
    std::vector<InvariantViolation>& violations,
    std::size_t& observed_active
) const {
  for (const auto& [price, level] : book) {
    if (price <= 0 || level.orders.empty() || level.total_quantity.is_zero()) {
      violations.push_back({
          "book.invalid_level",
          "price levels must have positive price, quantity, and at least one order",
      });
    }
    model::QuantityLots sum{0U};
    std::uint64_t previous_priority = 0U;
    for (const auto& node : level.orders) {
      ++observed_active;
      const auto& view = node.view;
      if (view.side != expected_side || !view.limit_price.has_value() ||
          view.limit_price->value() != price || view.leaves_quantity.is_zero() ||
          (view.state != model::OrderState::Live &&
           view.state != model::OrderState::PartiallyFilled)) {
        violations.push_back({
            "book.invalid_order",
            "resting order has inconsistent side, price, quantity, or state",
        });
      }
      if (previous_priority != 0U && view.priority_sequence <= previous_priority) {
        violations.push_back({
            "book.fifo_priority",
            "priority sequence must increase strictly within a price level",
        });
      }
      previous_priority = view.priority_sequence;
      const auto added = model::checked_add(sum, view.leaves_quantity);
      if (!added.has_value()) {
        violations.push_back({"book.quantity_overflow", "price-level quantity overflow"});
      } else {
        sum = *added;
      }
    }
    if (sum != level.total_quantity) {
      violations.push_back({
          "book.aggregate_quantity",
          "price-level aggregate differs from the sum of resting leaves quantities",
      });
    }
  }
}

template <typename Book>
void MatchingEngine::Impl::append_canonical_side(
    std::ostringstream& stream,
    std::string_view name,
    const Book& book
) {
  stream << name << '\n';
  for (const auto& [price, level] : book) {
    stream << price << '|' << level.total_quantity.value() << '|' << level.orders.size()
           << '\n';
    for (const auto& node : level.orders) {
      const auto& view = node.view;
      stream << "  " << view.client_order_id.value() << '|'
             << view.exchange_order_id.value() << '|' << view.leaves_quantity.value() << '|'
             << view.priority_sequence << '\n';
    }
  }
}

std::uint64_t MatchingEngine::Impl::allocate(std::uint64_t& next_value) {
  if (next_value == 0U) {
    throw std::overflow_error("matching-engine identifier sequence exhausted");
  }
  const auto result = next_value;
  if (next_value == std::numeric_limits<std::uint64_t>::max()) {
    next_value = 0U;
  } else {
    ++next_value;
  }
  return result;
}

}  // namespace robust_execution::exchange
