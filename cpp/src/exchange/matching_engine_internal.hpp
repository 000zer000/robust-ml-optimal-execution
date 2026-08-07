#pragma once

#include "robust_execution/exchange/matching_engine.hpp"

#include <cstdint>
#include <functional>
#include <list>
#include <map>
#include <optional>
#include <sstream>
#include <string_view>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace robust_execution::exchange {

class MatchingEngine::Impl {
 public:
  explicit Impl(MatchingEngineConfig input_config);

  struct OrderNode {
    OrderView view;
  };

  struct PriceLevel {
    model::QuantityLots total_quantity{};
    std::list<OrderNode> orders;
  };

  using BidBook = std::map<std::int64_t, PriceLevel, std::greater<>>;
  using AskBook = std::map<std::int64_t, PriceLevel, std::less<>>;
  using OrderIterator = std::list<OrderNode>::iterator;

  struct Locator {
    model::Side side{model::Side::Buy};
    std::int64_t price{0};
    OrderIterator iterator;
  };

  [[nodiscard]] const MatchingEngineConfig& config() const noexcept;
  [[nodiscard]] SubmitResult submit(const model::OrderSubmit& command);
  [[nodiscard]] CancelResult cancel(const model::CancelRequest& command);
  [[nodiscard]] ReplaceResult replace(const model::ReplaceRequest& command);

  [[nodiscard]] std::optional<OrderView> order(model::ClientOrderId client_order_id) const;
  [[nodiscard]] std::optional<model::PriceTicks> best_bid() const noexcept;
  [[nodiscard]] std::optional<model::PriceTicks> best_ask() const noexcept;
  [[nodiscard]] model::QuantityLots quantity_at(
      model::Side side,
      model::PriceTicks price
  ) const;
  [[nodiscard]] std::size_t active_order_count() const noexcept;
  [[nodiscard]] BookView book(std::size_t maximum_levels_per_side) const;
  [[nodiscard]] bool would_cross(
      model::Side side,
      std::optional<model::PriceTicks> limit_price
  ) const noexcept;
  [[nodiscard]] bool can_fully_execute(
      model::Side side,
      model::QuantityLots quantity,
      std::optional<model::PriceTicks> limit_price
  ) const noexcept;
  [[nodiscard]] std::vector<InvariantViolation> validate_invariants() const;
  [[nodiscard]] std::string canonical_state() const;

 private:
  struct LocateResult {
    std::optional<EngineFailure> failure;
  };

  [[nodiscard]] std::optional<EngineFailure> validate_submit(
      const model::OrderSubmit& command
  ) const;
  [[nodiscard]] std::optional<EngineFailure> validate_quantity(
      model::ClientOrderId client_order_id,
      model::QuantityLots quantity
  ) const;
  [[nodiscard]] SubmitResult rejected_submit(
      model::ClientOrderId client_order_id,
      EngineFailure failure
  ) const;
  [[nodiscard]] LocateResult locate_active(
      model::ClientOrderId client_order_id,
      model::ExchangeOrderId exchange_order_id
  ) const;

  [[nodiscard]] bool can_add_to_level(
      model::Side side,
      model::PriceTicks price,
      model::QuantityLots quantity
  ) const noexcept;

  template <typename Book>
  [[nodiscard]] static bool can_add_to_level_map(
      const Book& book,
      model::PriceTicks price,
      model::QuantityLots quantity
  ) noexcept;

  void match(OrderView& incoming, std::vector<MatchExecution>& matches);
  void match_buy(OrderView& incoming, std::vector<MatchExecution>& matches);
  void match_sell(OrderView& incoming, std::vector<MatchExecution>& matches);
  void match_level(
      OrderView& incoming,
      PriceLevel& level,
      std::vector<MatchExecution>& matches
  );
  void rest(const OrderView& order);

  template <typename Book>
  void rest_in_book(Book& book, const OrderView& order);

  void remove_active(Locator locator, model::OrderState terminal_state);

  template <typename Book>
  static void remove_from_book(
      Book& book,
      const Locator& locator,
      model::QuantityLots leaves_quantity
  );

  template <typename Book>
  static void append_levels(
      const Book& source,
      std::size_t maximum_levels,
      std::vector<PriceLevelView>& destination
  );

  template <typename Book>
  void validate_side(
      const Book& book,
      model::Side expected_side,
      std::vector<InvariantViolation>& violations,
      std::size_t& observed_active
  ) const;

  template <typename Book>
  static void append_canonical_side(
      std::ostringstream& stream,
      std::string_view name,
      const Book& book
  );

  [[nodiscard]] static std::uint64_t allocate(std::uint64_t& next_value);

  MatchingEngineConfig config_;
  BidBook bids_;
  AskBook asks_;
  std::unordered_map<std::uint64_t, Locator> active_by_exchange_;
  std::unordered_map<std::uint64_t, std::uint64_t> active_by_client_;
  std::unordered_map<std::uint64_t, std::uint64_t> exchange_by_client_;
  std::unordered_map<std::uint64_t, OrderView> orders_by_exchange_;
  std::unordered_set<std::uint64_t> all_client_ids_;
  std::uint64_t next_exchange_order_id_{1U};
  std::uint64_t next_execution_id_{1U};
  std::uint64_t next_match_sequence_{1U};
  std::uint64_t next_priority_sequence_{1U};
};

}  // namespace robust_execution::exchange
