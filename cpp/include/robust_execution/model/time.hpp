#pragma once

#include <compare>
#include <cstdint>
#include <optional>
#include <tuple>

#include "robust_execution/model/identifiers.hpp"

namespace robust_execution::model {

enum class ClockDomain : std::uint8_t {
  UnixUtc,
  Simulation,
};

class TimestampNs {
 public:
  constexpr TimestampNs() noexcept = default;
  constexpr TimestampNs(ClockDomain domain, std::int64_t value) noexcept
      : domain_(domain), value_(value) {}

  [[nodiscard]] constexpr ClockDomain domain() const noexcept { return domain_; }
  [[nodiscard]] constexpr std::int64_t value() const noexcept { return value_; }
  [[nodiscard]] friend constexpr bool operator==(const TimestampNs&, const TimestampNs&) = default;

 private:
  ClockDomain domain_{ClockDomain::Simulation};
  std::int64_t value_{0};
};

[[nodiscard]] constexpr std::optional<std::strong_ordering> compare_same_clock(
    TimestampNs lhs,
    TimestampNs rhs
) noexcept {
  if (lhs.domain() != rhs.domain()) {
    return std::nullopt;
  }
  return lhs.value() <=> rhs.value();
}

struct EventOrdering {
  bool has_source_sequence{false};
  std::uint64_t source_sequence{0U};
  std::uint32_t source_subsequence{0U};
  std::uint64_t ingest_sequence{0U};
  std::uint64_t canonical_sequence{0U};

  [[nodiscard]] friend constexpr auto operator<=>(const EventOrdering&, const EventOrdering&) =
      default;
};

struct EventOrderKey {
  TimestampNs event_time{};
  EventOrdering ordering{};
  EventId event_id{};
};

[[nodiscard]] constexpr bool event_order_less(
    const EventOrderKey& lhs,
    const EventOrderKey& rhs
) noexcept {
  if (lhs.event_time.domain() != rhs.event_time.domain()) {
    return static_cast<std::uint8_t>(lhs.event_time.domain()) <
           static_cast<std::uint8_t>(rhs.event_time.domain());
  }
  if (lhs.event_time.value() != rhs.event_time.value()) {
    return lhs.event_time.value() < rhs.event_time.value();
  }
  if (lhs.ordering.canonical_sequence != rhs.ordering.canonical_sequence) {
    return lhs.ordering.canonical_sequence < rhs.ordering.canonical_sequence;
  }
  if (lhs.ordering.source_subsequence != rhs.ordering.source_subsequence) {
    return lhs.ordering.source_subsequence < rhs.ordering.source_subsequence;
  }
  if (lhs.ordering.ingest_sequence != rhs.ordering.ingest_sequence) {
    return lhs.ordering.ingest_sequence < rhs.ordering.ingest_sequence;
  }
  return lhs.event_id.value() < rhs.event_id.value();
}

struct ObservationTiming {
  TimestampNs exchange_time{};
  TimestampNs receive_time{};
  TimestampNs available_time{};
};

struct ActionTiming {
  TimestampNs decision_start{};
  TimestampNs decision_end{};
  TimestampNs outbound_send{};
  TimestampNs exchange_receive{};
  TimestampNs exchange_process{};
  TimestampNs acknowledgement_send{};
  TimestampNs acknowledgement_receive{};
  TimestampNs acknowledgement_available{};
};

}  // namespace robust_execution::model
