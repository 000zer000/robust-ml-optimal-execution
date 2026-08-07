#pragma once

#include <cstddef>
#include <optional>
#include <string>
#include <vector>

#include "robust_execution/policy/state.hpp"

namespace robust_execution::policy {

struct ObservedTrade {
  model::Trade trade;
  model::TimestampNs event_time{};
  model::TimestampNs available_time{};
};

struct ObservationLineage {
  std::uint64_t delivered_event_count{0U};
  std::optional<model::EventId> last_event_id;
  std::optional<model::TimestampNs> maximum_event_time;
  std::optional<model::TimestampNs> maximum_available_time;
  std::string rolling_sha256;
};

class PolicyObservation {
 public:
  PolicyObservation(
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
  );

  [[nodiscard]] model::DecisionId decision_id() const noexcept;
  [[nodiscard]] model::TimestampNs decision_time() const noexcept;
  [[nodiscard]] model::TimestampNs observation_cutoff() const noexcept;
  [[nodiscard]] const PolicyEnvironment& environment() const noexcept;
  [[nodiscard]] const ParentOrderSnapshot& parent() const noexcept;
  [[nodiscard]] const std::vector<model::BookLevel>& bids() const noexcept;
  [[nodiscard]] const std::vector<model::BookLevel>& asks() const noexcept;
  [[nodiscard]] const std::vector<ObservedTrade>& recent_trades() const noexcept;
  [[nodiscard]] const std::vector<ChildOrderView>& active_orders() const noexcept;
  [[nodiscard]] std::size_t pending_command_count() const noexcept;
  [[nodiscard]] const ObservationLineage& lineage() const noexcept;
  [[nodiscard]] std::optional<model::PriceTicks> best_bid() const noexcept;
  [[nodiscard]] std::optional<model::PriceTicks> best_ask() const noexcept;
  [[nodiscard]] std::optional<std::int64_t> spread_ticks() const noexcept;
  [[nodiscard]] std::optional<std::int64_t> midpoint_twice_ticks() const noexcept;
  [[nodiscard]] std::int64_t elapsed_time_ns() const;
  [[nodiscard]] std::int64_t time_remaining_ns() const;
  [[nodiscard]] model::QuantityLots visible_bid_quantity() const;
  [[nodiscard]] model::QuantityLots visible_ask_quantity() const;
  [[nodiscard]] std::string canonical() const;
  [[nodiscard]] std::string hash() const;

 private:
  model::DecisionId decision_id_{};
  model::TimestampNs decision_time_{};
  model::TimestampNs observation_cutoff_{};
  PolicyEnvironment environment_;
  ParentOrderSnapshot parent_;
  std::vector<model::BookLevel> bids_;
  std::vector<model::BookLevel> asks_;
  std::vector<ObservedTrade> recent_trades_;
  std::vector<ChildOrderView> active_orders_;
  std::size_t pending_command_count_{0U};
  ObservationLineage lineage_;
};

class ObservationBuilder {
 public:
  explicit ObservationBuilder(PolicyEnvironment environment);
  ~ObservationBuilder();

  ObservationBuilder(const ObservationBuilder&) = delete;
  ObservationBuilder& operator=(const ObservationBuilder&) = delete;
  ObservationBuilder(ObservationBuilder&&) noexcept;
  ObservationBuilder& operator=(ObservationBuilder&&) noexcept;

  void ingest_delivered_event(const model::Event& event, model::TimestampNs delivery_time);
  [[nodiscard]] PolicyObservation build(
      model::DecisionId decision_id,
      model::TimestampNs decision_time,
      const ExecutionState& state
  ) const;

  [[nodiscard]] const PolicyEnvironment& environment() const noexcept;
  [[nodiscard]] std::optional<model::TimestampNs> delivery_watermark() const noexcept;

 private:
  class Impl;
  Impl* impl_;
};

}  // namespace robust_execution::policy
