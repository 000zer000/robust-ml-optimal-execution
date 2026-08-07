#include "internal.hpp"

#include "robust_execution/exchange/exchange.hpp"

#include <algorithm>
#include <cstdint>
#include <deque>
#include <functional>
#include <map>
#include <optional>
#include <random>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

namespace robust_execution::validation::detail {
namespace exchange = robust_execution::exchange;
namespace model = robust_execution::model;

namespace {
struct RefOrder {
  std::uint64_t client_id{0U};
  model::Side side{model::Side::Buy};
  std::uint64_t leaves{0U};
  std::int64_t price{0};
};

struct RefFill {
  std::uint64_t maker_id{0U};
  std::uint64_t quantity{0U};
  std::int64_t price{0};
};

class ReferenceBook {
 public:
  std::vector<RefFill> submit_limit(
      std::uint64_t client_id,
      model::Side side,
      std::uint64_t quantity,
      std::int64_t price
  ) {
    auto fills = match(side, quantity, price);
    std::uint64_t executed = 0U;
    for (const auto& fill : fills) executed += fill.quantity;
    const auto leaves = quantity - executed;
    if (leaves != 0U) add(RefOrder{client_id, side, leaves, price});
    return fills;
  }

  std::vector<RefFill> submit_market(
      model::Side side,
      std::uint64_t quantity
  ) {
    return match(side, quantity, std::nullopt);
  }

  bool cancel(std::uint64_t client_id) {
    const auto found = orders_.find(client_id);
    if (found == orders_.end()) return false;
    if (found->second.side == model::Side::Buy) {
      const auto level = bids_.find(found->second.price);
      if (level == bids_.end()) return false;
      auto& queue = level->second;
      queue.erase(std::remove(queue.begin(), queue.end(), client_id), queue.end());
      if (queue.empty()) bids_.erase(level);
    } else {
      const auto level = asks_.find(found->second.price);
      if (level == asks_.end()) return false;
      auto& queue = level->second;
      queue.erase(std::remove(queue.begin(), queue.end(), client_id), queue.end());
      if (queue.empty()) asks_.erase(level);
    }
    orders_.erase(found);
    return true;
  }

  [[nodiscard]] std::vector<std::uint64_t> active_ids() const {
    std::vector<std::uint64_t> ids;
    ids.reserve(orders_.size());
    for (const auto& [id, order] : orders_) {
      (void)order;
      ids.push_back(id);
    }
    std::sort(ids.begin(), ids.end());
    return ids;
  }

  [[nodiscard]] std::size_t active_count() const noexcept { return orders_.size(); }
  [[nodiscard]] std::optional<std::int64_t> best_bid() const {
    if (bids_.empty()) return std::nullopt;
    return bids_.begin()->first;
  }
  [[nodiscard]] std::optional<std::int64_t> best_ask() const {
    if (asks_.empty()) return std::nullopt;
    return asks_.begin()->first;
  }

  [[nodiscard]] std::vector<std::pair<std::int64_t, std::uint64_t>> bid_levels() const {
    return levels(bids_);
  }
  [[nodiscard]] std::vector<std::pair<std::int64_t, std::uint64_t>> ask_levels() const {
    return levels(asks_);
  }

 private:
  using BidLevels = std::map<std::int64_t, std::deque<std::uint64_t>, std::greater<>>;
  using AskLevels = std::map<std::int64_t, std::deque<std::uint64_t>>;

  template <class Levels>
  [[nodiscard]] std::vector<std::pair<std::int64_t, std::uint64_t>> levels(
      const Levels& levels_map
  ) const {
    std::vector<std::pair<std::int64_t, std::uint64_t>> result;
    for (const auto& [price, queue] : levels_map) {
      std::uint64_t quantity = 0U;
      for (const auto id : queue) quantity += orders_.at(id).leaves;
      result.emplace_back(price, quantity);
    }
    return result;
  }

  void add(RefOrder order) {
    const auto id = order.client_id;
    if (order.side == model::Side::Buy) bids_[order.price].push_back(id);
    else asks_[order.price].push_back(id);
    orders_.emplace(id, order);
  }

  std::vector<RefFill> match(
      model::Side side,
      std::uint64_t quantity,
      std::optional<std::int64_t> limit_price
  ) {
    std::vector<RefFill> fills;
    while (quantity != 0U) {
      if (side == model::Side::Buy) {
        if (asks_.empty()) break;
        auto level = asks_.begin();
        if (limit_price.has_value() && level->first > *limit_price) break;
        consume_level(asks_, level, quantity, fills);
      } else {
        if (bids_.empty()) break;
        auto level = bids_.begin();
        if (limit_price.has_value() && level->first < *limit_price) break;
        consume_level(bids_, level, quantity, fills);
      }
    }
    return fills;
  }

  template <class Levels, class Iterator>
  void consume_level(
      Levels& levels,
      Iterator level,
      std::uint64_t& quantity,
      std::vector<RefFill>& fills
  ) {
    while (quantity != 0U && !level->second.empty()) {
      const auto maker_id = level->second.front();
      auto found = orders_.find(maker_id);
      if (found == orders_.end()) {
        throw std::logic_error("reference book queue points to an unknown order");
      }
      const auto maker_leaves = found->second.leaves;
      const auto fill_price = level->first;
      const auto fill_quantity = quantity < maker_leaves ? quantity : maker_leaves;
      fills.push_back(RefFill{maker_id, fill_quantity, fill_price});
      quantity -= fill_quantity;
      found->second.leaves = maker_leaves - fill_quantity;
      if (found->second.leaves == 0U) {
        level->second.pop_front();
        orders_.erase(found);
      }
    }
    if (level->second.empty()) {
      levels.erase(level);
    }
  }

  BidLevels bids_;
  AskLevels asks_;
  std::unordered_map<std::uint64_t, RefOrder> orders_;
};

model::TimestampNs time(std::int64_t value) {
  return model::TimestampNs{model::ClockDomain::Simulation, value};
}

model::OrderSubmit limit(
    std::uint64_t client,
    model::Side side,
    std::uint64_t quantity,
    std::int64_t price
) {
  return model::OrderSubmit{
      model::ParentOrderId{1U}, model::ClientOrderId{client}, model::DecisionId{client}, side,
      model::OrderType::Limit, model::TimeInForce::GoodTilCancelled,
      model::QuantityLots{quantity}, model::PriceTicks{price}, false,
      time(static_cast<std::int64_t>(client)), time(static_cast<std::int64_t>(client)),
      time(static_cast<std::int64_t>(client)),
  };
}

model::OrderSubmit market(
    std::uint64_t client,
    model::Side side,
    std::uint64_t quantity
) {
  return model::OrderSubmit{
      model::ParentOrderId{1U}, model::ClientOrderId{client}, model::DecisionId{client}, side,
      model::OrderType::Market, model::TimeInForce::ImmediateOrCancel,
      model::QuantityLots{quantity}, std::nullopt, false,
      time(static_cast<std::int64_t>(client)), time(static_cast<std::int64_t>(client)),
      time(static_cast<std::int64_t>(client)),
  };
}

bool same_fills(
    const std::vector<exchange::MatchExecution>& engine_fills,
    const std::vector<RefFill>& reference_fills
) {
  if (engine_fills.size() != reference_fills.size()) return false;
  for (std::size_t index = 0U; index < engine_fills.size(); ++index) {
    if (engine_fills[index].maker_fill.client_order_id.value() !=
            reference_fills[index].maker_id ||
        engine_fills[index].trade.quantity.value() != reference_fills[index].quantity ||
        engine_fills[index].trade.price.value() != reference_fills[index].price) {
      return false;
    }
  }
  return true;
}

bool same_book(const exchange::MatchingEngine& engine, const ReferenceBook& reference) {
  if (engine.active_order_count() != reference.active_count()) return false;
  const auto engine_bid = engine.best_bid();
  const auto engine_ask = engine.best_ask();
  const auto reference_bid = reference.best_bid();
  const auto reference_ask = reference.best_ask();
  if (engine_bid.has_value() != reference_bid.has_value() ||
      engine_ask.has_value() != reference_ask.has_value()) return false;
  if (engine_bid.has_value() && engine_bid->value() != *reference_bid) return false;
  if (engine_ask.has_value() && engine_ask->value() != *reference_ask) return false;
  const auto book = engine.book();
  const auto bids = reference.bid_levels();
  const auto asks = reference.ask_levels();
  if (book.bids.size() != bids.size() || book.asks.size() != asks.size()) return false;
  for (std::size_t index = 0U; index < bids.size(); ++index) {
    if (book.bids[index].price.value() != bids[index].first ||
        book.bids[index].displayed_quantity.value() != bids[index].second) return false;
  }
  for (std::size_t index = 0U; index < asks.size(); ++index) {
    if (book.asks[index].price.value() != asks[index].first ||
        book.asks[index].displayed_quantity.value() != asks[index].second) return false;
  }
  return engine.validate_invariants().empty();
}
}  // namespace

ValidationCheck run_differential_check() {
  constexpr std::uint64_t kSeeds = 32U;
  constexpr std::uint64_t kCommandsPerSeed = 2'000U;
  bool passed = true;
  std::string failure;
  for (std::uint64_t seed = 0U; seed < kSeeds && passed; ++seed) {
    exchange::MatchingEngine engine{exchange::MatchingEngineConfig{base_config(seed).instrument}};
    ReferenceBook reference;
    std::mt19937_64 random{0x9e3779b97f4a7c15ULL ^ seed};
    std::uint64_t next_client = 1U;
    for (std::uint64_t command = 0U; command < kCommandsPerSeed; ++command) {
      const auto action = random() % 100U;
      if (action < 55U) {
        const auto side = (random() & 1U) == 0U ? model::Side::Buy : model::Side::Sell;
        const auto quantity = 1U + random() % 12U;
        const auto price = static_cast<std::int64_t>(9'970U + random() % 61U);
        const auto result = engine.submit(limit(next_client, side, quantity, price));
        const auto expected = reference.submit_limit(next_client, side, quantity, price);
        if (!result.accepted() || !same_fills(result.matches, expected)) {
          passed = false;
          failure = "limit differential mismatch at seed " + std::to_string(seed) +
                    ", command " + std::to_string(command);
        }
        ++next_client;
      } else if (action < 82U) {
        const auto side = (random() & 1U) == 0U ? model::Side::Buy : model::Side::Sell;
        const auto quantity = 1U + random() % 15U;
        const auto result = engine.submit(market(next_client, side, quantity));
        const auto expected = reference.submit_market(side, quantity);
        if (!result.accepted() || !same_fills(result.matches, expected)) {
          passed = false;
          failure = "market differential mismatch at seed " + std::to_string(seed) +
                    ", command " + std::to_string(command);
        }
        ++next_client;
      } else {
        const auto ids = reference.active_ids();
        if (!ids.empty()) {
          const auto id = ids[random() % ids.size()];
          const auto view = engine.order(model::ClientOrderId{id});
          if (!view.has_value()) {
            passed = false;
            failure = "reference active order missing in engine";
          } else {
            const model::CancelRequest request{
                model::ClientOrderId{id}, view->exchange_order_id,
                model::DecisionId{next_client++}, time(static_cast<std::int64_t>(command)),
                time(static_cast<std::int64_t>(command)), time(static_cast<std::int64_t>(command)),
            };
            const auto result = engine.cancel(request);
            if (!result.accepted() || !reference.cancel(id)) {
              passed = false;
              failure = "cancel differential mismatch";
            }
          }
        }
      }
      if (passed && !same_book(engine, reference)) {
        passed = false;
        failure = "book differential mismatch at seed " + std::to_string(seed) +
                  ", command " + std::to_string(command);
      }
    }
  }
  return ValidationCheck{
      "DIFF-BOOK-001", "differential_reference",
      "Independent deque/map reference book agrees with the production engine over 64,000 commands.",
      passed,
      passed ? "32 seeds x 2,000 valid limit, market and cancel commands matched after every command."
             : failure,
      "Reference covers visible FIFO limit/market/cancel semantics; replacement and exchange-specific rules retain dedicated tests.",
  };
}

}  // namespace robust_execution::validation::detail
