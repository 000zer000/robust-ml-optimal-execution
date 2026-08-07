#include "robust_execution/model/time.hpp"

#include <cstdlib>

int main() {
  using robust_execution::model::ClockDomain;
  using robust_execution::model::EventId;
  using robust_execution::model::EventOrderKey;
  using robust_execution::model::EventOrdering;
  using robust_execution::model::TimestampNs;
  using robust_execution::model::compare_same_clock;
  using robust_execution::model::event_order_less;

  const TimestampNs first{ClockDomain::Simulation, 10};
  const TimestampNs second{ClockDomain::Simulation, 20};
  const auto comparison = compare_same_clock(first, second);
  if (!comparison.has_value() || *comparison != std::strong_ordering::less) {
    return EXIT_FAILURE;
  }
  if (compare_same_clock(first, TimestampNs{ClockDomain::UnixUtc, 20}).has_value()) {
    return EXIT_FAILURE;
  }

  const EventOrderKey source_sequenced{
      first,
      EventOrdering{true, 4U, 0U, 9U, 1U},
      EventId{2U},
  };
  const EventOrderKey ingest_only{
      first,
      EventOrdering{false, 0U, 0U, 1U, 2U},
      EventId{1U},
  };
  if (!event_order_less(source_sequenced, ingest_only)) {
    return EXIT_FAILURE;
  }

  const EventOrderKey later_subsequence{
      first,
      EventOrdering{true, 4U, 1U, 9U, 1U},
      EventId{1U},
  };
  if (!event_order_less(source_sequenced, later_subsequence)) {
    return EXIT_FAILURE;
  }
  if (!event_order_less(
          source_sequenced,
          EventOrderKey{second, EventOrdering{true, 1U, 0U, 1U, 1U}, EventId{1U}}
      )) {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
