#include "robust_execution/simulation/latency.hpp"

#include <limits>
#include <stdexcept>
#include <utility>

namespace robust_execution::simulation {
namespace {

void validate_range(const LatencyRangeNs& range, const char* name) {
  if (range.minimum < 0 || range.maximum < 0 || range.minimum > range.maximum) {
    throw std::invalid_argument(std::string{name} + " latency range must satisfy 0 <= min <= max");
  }
  const auto width = static_cast<std::uint64_t>(range.maximum - range.minimum);
  if (width >= static_cast<std::uint64_t>(std::numeric_limits<std::uint32_t>::max())) {
    throw std::invalid_argument(std::string{name} + " latency range width must fit in uint32");
  }
}

}  // namespace

model::TimestampNs checked_add_duration(
    model::TimestampNs timestamp,
    std::int64_t duration_ns
) {
  if (duration_ns < 0) {
    throw std::invalid_argument("latency duration cannot be negative");
  }
  if (timestamp.value() > std::numeric_limits<std::int64_t>::max() - duration_ns) {
    throw std::overflow_error("timestamp plus latency overflows int64 nanoseconds");
  }
  return model::TimestampNs{timestamp.domain(), timestamp.value() + duration_ns};
}

LatencyModel::LatencyModel(std::uint64_t seed, LatencyModelConfig config)
    : random_(seed), config_(std::move(config)) {
  if (config_.model_id.empty()) {
    throw std::invalid_argument("latency model_id cannot be empty");
  }
  validate_range(config_.market_data_network, "market_data_network");
  validate_range(config_.observation_processing, "observation_processing");
  validate_range(config_.decision_processing, "decision_processing");
  validate_range(config_.outbound_network, "outbound_network");
  validate_range(config_.exchange_processing, "exchange_processing");
  validate_range(config_.acknowledgement_network, "acknowledgement_network");
  validate_range(config_.acknowledgement_processing, "acknowledgement_processing");
}

std::int64_t LatencyModel::draw(
    const LatencyRangeNs& range,
    std::uint64_t logical_index
) const {
  if (range.minimum == range.maximum) {
    return range.minimum;
  }
  const auto width = static_cast<std::uint32_t>(range.maximum - range.minimum + 1);
  return range.minimum + static_cast<std::int64_t>(random_.bounded_u32(
                             LogicalRandomAddress{range.stream_id, logical_index},
                             width
                         ));
}

ObservationLatencySample LatencyModel::sample_observation(
    std::uint64_t logical_index
) const {
  return ObservationLatencySample{
      draw(config_.market_data_network, logical_index),
      draw(config_.observation_processing, logical_index),
  };
}

ActionLatencySample LatencyModel::sample_action(std::uint64_t logical_index) const {
  return ActionLatencySample{
      draw(config_.decision_processing, logical_index),
      draw(config_.outbound_network, logical_index),
      draw(config_.exchange_processing, logical_index),
      draw(config_.acknowledgement_network, logical_index),
      draw(config_.acknowledgement_processing, logical_index),
  };
}

model::ObservationTiming LatencyModel::observation_timing(
    model::TimestampNs event_time,
    std::uint64_t logical_index
) const {
  const auto sample = sample_observation(logical_index);
  const auto receive = checked_add_duration(event_time, sample.network_ns);
  const auto available = checked_add_duration(receive, sample.processing_ns);
  return model::ObservationTiming{event_time, receive, available};
}

model::ActionTiming LatencyModel::action_timing(
    model::TimestampNs decision_start,
    std::uint64_t logical_index
) const {
  const auto sample = sample_action(logical_index);
  const auto decision_end = checked_add_duration(decision_start, sample.decision_processing_ns);
  const auto outbound_send = decision_end;
  const auto exchange_receive = checked_add_duration(outbound_send, sample.outbound_network_ns);
  const auto exchange_process = checked_add_duration(exchange_receive, sample.exchange_processing_ns);
  const auto acknowledgement_send = exchange_process;
  const auto acknowledgement_receive =
      checked_add_duration(acknowledgement_send, sample.acknowledgement_network_ns);
  const auto acknowledgement_available =
      checked_add_duration(acknowledgement_receive, sample.acknowledgement_processing_ns);
  return model::ActionTiming{
      decision_start,
      decision_end,
      outbound_send,
      exchange_receive,
      exchange_process,
      acknowledgement_send,
      acknowledgement_receive,
      acknowledgement_available,
  };
}

}  // namespace robust_execution::simulation
