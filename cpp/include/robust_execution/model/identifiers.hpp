#pragma once

#include <compare>
#include <cstdint>
#include <string>
#include <utility>

namespace robust_execution::model {

template <typename Tag>
class NumericId {
 public:
  constexpr NumericId() noexcept = default;
  constexpr explicit NumericId(std::uint64_t value) noexcept : value_(value) {}

  [[nodiscard]] constexpr std::uint64_t value() const noexcept { return value_; }
  [[nodiscard]] constexpr bool valid() const noexcept { return value_ != 0U; }
  [[nodiscard]] friend constexpr auto operator<=>(const NumericId&, const NumericId&) = default;

 private:
  std::uint64_t value_{0U};
};

struct EventIdTag;
struct ParentOrderIdTag;
struct ClientOrderIdTag;
struct ExchangeOrderIdTag;
struct ExecutionIdTag;
struct DecisionIdTag;
struct TradeIdTag;

using EventId = NumericId<EventIdTag>;
using ParentOrderId = NumericId<ParentOrderIdTag>;
using ClientOrderId = NumericId<ClientOrderIdTag>;
using ExchangeOrderId = NumericId<ExchangeOrderIdTag>;
using ExecutionId = NumericId<ExecutionIdTag>;
using DecisionId = NumericId<DecisionIdTag>;
using TradeId = NumericId<TradeIdTag>;

template <typename Tag>
class TextId {
 public:
  TextId() = default;
  explicit TextId(std::string value) : value_(std::move(value)) {}

  [[nodiscard]] const std::string& value() const noexcept { return value_; }
  [[nodiscard]] bool valid() const noexcept { return !value_.empty(); }
  [[nodiscard]] friend bool operator==(const TextId&, const TextId&) = default;
  [[nodiscard]] friend auto operator<=>(const TextId&, const TextId&) = default;

 private:
  std::string value_;
};

struct RunIdTag;
struct VenueIdTag;
struct InstrumentIdTag;
struct SourceChannelIdTag;
struct ExternalOrderIdTag;
struct ExternalTradeIdTag;
struct FeeScheduleIdTag;
struct StrategyIdTag;
struct QueueModelIdTag;
struct LatencyModelIdTag;

using RunId = TextId<RunIdTag>;
using VenueId = TextId<VenueIdTag>;
using InstrumentId = TextId<InstrumentIdTag>;
using SourceChannelId = TextId<SourceChannelIdTag>;
using ExternalOrderId = TextId<ExternalOrderIdTag>;
using ExternalTradeId = TextId<ExternalTradeIdTag>;
using FeeScheduleId = TextId<FeeScheduleIdTag>;
using StrategyId = TextId<StrategyIdTag>;
using QueueModelId = TextId<QueueModelIdTag>;
using LatencyModelId = TextId<LatencyModelIdTag>;

}  // namespace robust_execution::model
