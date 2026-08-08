#include "robust_execution/historical/replay.hpp"

#include "robust_execution/model/validation.hpp"
#include "robust_execution/util/sha256.hpp"

#include <algorithm>
#include <cstdint>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <unordered_map>
#include <utility>

namespace robust_execution::historical {
namespace {

struct DeliveryMarker {
  enum class Kind : std::uint8_t { Snapshot, Depth, Trade };
  Kind kind{Kind::Trade};
  bool sequence_bridge{false};
};

[[nodiscard]] model::TimestampNs checked_available(
    model::TimestampNs receive_time,
    std::int64_t delay_ns
) {
  if (delay_ns < 0) {
    throw std::invalid_argument("historical observation-processing delay cannot be negative");
  }
  if (receive_time.value() > std::numeric_limits<std::int64_t>::max() - delay_ns) {
    throw std::overflow_error("historical event availability timestamp overflow");
  }
  return model::TimestampNs{receive_time.domain(), receive_time.value() + delay_ns};
}

void require_same_clock(model::TimestampNs lhs, model::TimestampNs rhs, const char* context) {
  if (lhs.domain() != rhs.domain()) {
    throw std::invalid_argument(std::string{context} + " uses mixed clock domains");
  }
}

[[nodiscard]] std::uint64_t message_sequence(const ReplayMessage& message) {
  return std::visit(
      [](const auto& value) { return value.canonical_message_sequence; }, message
  );
}

[[nodiscard]] model::TimestampNs receive_time(const ReplayMessage& message) {
  return std::visit([](const auto& value) { return value.receive_time; }, message);
}

[[nodiscard]] model::EventHeader header(
    const HistoricalReplayConfig& config,
    model::EventId event_id,
    model::TimestampNs event_time,
    std::uint64_t source_sequence,
    std::uint32_t source_subsequence,
    std::uint64_t ingest_sequence,
    std::uint64_t canonical_sequence,
    std::string original_timestamp
) {
  return model::EventHeader{
      model::kEventSchemaVersion,
      event_id,
      config.kernel.run_id,
      config.kernel.exchange.instrument.venue,
      config.kernel.exchange.instrument.instrument,
      config.historical_channel,
      model::EventOrigin::HistoricalFeed,
      event_time,
      std::nullopt,
      std::nullopt,
      model::EventOrdering{
          true,
          source_sequence,
          source_subsequence,
          ingest_sequence,
          canonical_sequence,
      },
      std::move(original_timestamp),
  };
}

void validate_config(const HistoricalReplayConfig& config) {
  if (!config.historical_channel.valid() || config.first_event_id == 0U ||
      config.first_canonical_sequence == 0U || config.observation_processing_delay_ns < 0) {
    throw std::invalid_argument("historical replay configuration is incomplete");
  }
  if (config.environment.instrument.venue != config.kernel.exchange.instrument.venue ||
      config.environment.instrument.instrument !=
          config.kernel.exchange.instrument.instrument) {
    throw std::invalid_argument("historical replay policy and kernel instruments differ");
  }
}

void validate_connections(const std::vector<ReplayConnection>& connections) {
  if (connections.empty()) {
    throw std::invalid_argument("historical replay requires at least one connection");
  }
  std::uint64_t prior_message_sequence = 0U;
  bool have_prior_sequence = false;
  std::optional<model::TimestampNs> prior_receive;
  std::optional<model::TimestampNs> prior_connection_start;
  for (const auto& connection : connections) {
    const auto& snapshot = connection.snapshot;
    if (snapshot.connection_id.empty() || snapshot.last_update_id == 0U ||
        snapshot.bids.empty() || snapshot.asks.empty() || connection.messages.empty()) {
      throw std::invalid_argument("historical replay connection is incomplete");
    }
    require_same_clock(
        snapshot.event_time_proxy,
        snapshot.synchronization_receive_time,
        "historical snapshot"
    );
    if (snapshot.event_time_proxy.value() > snapshot.synchronization_receive_time.value()) {
      throw std::invalid_argument("snapshot event-time proxy cannot follow synchronization time");
    }
    if (prior_connection_start.has_value()) {
      require_same_clock(*prior_connection_start, snapshot.event_time_proxy, "historical reconnect");
      if (snapshot.event_time_proxy.value() <= prior_connection_start->value()) {
        throw std::invalid_argument("historical connection starts must strictly increase");
      }
    }
    if (prior_receive.has_value()) {
      require_same_clock(*prior_receive, snapshot.event_time_proxy, "historical reconnect");
      if (snapshot.event_time_proxy.value() < prior_receive->value()) {
        throw std::invalid_argument("historical connections cannot overlap in receive time");
      }
    }
    prior_connection_start = snapshot.event_time_proxy;
    std::uint64_t last_update_id = snapshot.last_update_id;
    bool bridged = false;
    std::uint64_t previous_connection_sequence = 0U;
    bool have_connection_sequence = false;
    for (const auto& message : connection.messages) {
      const auto sequence = message_sequence(message);
      if (sequence == 0U || (have_connection_sequence && sequence <= previous_connection_sequence) ||
          (have_prior_sequence && sequence <= prior_message_sequence)) {
        throw std::invalid_argument("historical canonical message sequences must increase");
      }
      previous_connection_sequence = sequence;
      have_connection_sequence = true;
      prior_message_sequence = sequence;
      have_prior_sequence = true;
      const auto received = receive_time(message);
      require_same_clock(snapshot.event_time_proxy, received, "historical message");
      if (prior_receive.has_value() && received.value() < prior_receive->value()) {
        throw std::invalid_argument("historical receive times must be globally non-decreasing");
      }
      prior_receive = received;
      std::visit(
          [&](const auto& value) {
            using Message = std::decay_t<decltype(value)>;
            require_same_clock(value.event_time, value.receive_time, "historical message");
            if (value.event_time.value() > value.receive_time.value()) {
              throw std::invalid_argument("historical event time cannot follow receive time");
            }
            if constexpr (std::is_same_v<Message, ReplayDepthBatch>) {
              if (value.first_update_id == 0U || value.final_update_id < value.first_update_id ||
                  value.updates.empty()) {
                throw std::invalid_argument("historical depth batch is malformed");
              }
              if (last_update_id == std::numeric_limits<std::uint64_t>::max()) {
                throw std::overflow_error("historical update sequence is exhausted");
              }
              const auto expected = last_update_id + 1U;
              if (value.final_update_id < expected) {
                throw std::invalid_argument("stale historical depth batch is not replayable");
              }
              if (value.first_update_id > expected) {
                throw std::invalid_argument("historical depth sequence gap detected");
              }
              last_update_id = value.final_update_id;
              bridged = true;
            } else {
              if (!value.trade.trade_id.valid() || value.trade.price.value() <= 0 ||
                  value.trade.quantity.is_zero()) {
                throw std::invalid_argument("historical trade is malformed");
              }
            }
          },
          message
      );
    }
    if (!bridged) {
      throw std::invalid_argument("historical connection never bridges its snapshot sequence");
    }
  }
}

}  // namespace

HistoricalReplayEngine::HistoricalReplayEngine(HistoricalReplayConfig config)
    : config_(std::move(config)) {
  validate_config(config_);
}

const HistoricalReplayConfig& HistoricalReplayEngine::config() const noexcept { return config_; }

HistoricalReplayResult HistoricalReplayEngine::run(
    const std::vector<ReplayConnection>& connections,
    const std::vector<ReplayCheckpoint>& checkpoints,
    policy::ExecutionState& execution_state
) const {
  validate_connections(connections);
  if (checkpoints.empty()) {
    throw std::invalid_argument("historical replay requires at least one observation checkpoint");
  }
  for (std::size_t index = 0U; index < checkpoints.size(); ++index) {
    if (!checkpoints[index].decision_id.valid()) {
      throw std::invalid_argument("historical replay checkpoint decision_id must be non-zero");
    }
    if (index > 0U) {
      require_same_clock(
          checkpoints[index - 1U].decision_time,
          checkpoints[index].decision_time,
          "historical checkpoints"
      );
      if (checkpoints[index].decision_time.value() <=
          checkpoints[index - 1U].decision_time.value()) {
        throw std::invalid_argument("historical replay checkpoints must strictly increase");
      }
    }
  }

  simulation::SimulationKernel kernel{config_.kernel};
  policy::ObservationBuilder observation_builder{config_.environment};
  std::unordered_map<std::uint64_t, DeliveryMarker> markers;
  std::vector<model::TimestampNs> connection_reset_times;
  connection_reset_times.reserve(connections.size());
  auto next_event_id = config_.first_event_id;
  auto next_canonical = config_.first_canonical_sequence;
  ReplayIntegrity integrity{};
  integrity.connection_count = static_cast<std::uint64_t>(connections.size());

  auto allocate_event = [&]() {
    if (next_event_id == 0U || next_event_id == std::numeric_limits<std::uint64_t>::max()) {
      throw std::overflow_error("historical replay event identifiers are exhausted");
    }
    return model::EventId{next_event_id++};
  };
  auto allocate_canonical = [&]() {
    if (next_canonical == 0U ||
        next_canonical == std::numeric_limits<std::uint64_t>::max()) {
      throw std::overflow_error("historical replay canonical sequence is exhausted");
    }
    return next_canonical++;
  };

  for (const auto& connection : connections) {
    connection_reset_times.push_back(connection.snapshot.event_time_proxy);
    const auto snapshot_id = allocate_event();
    const auto snapshot_sequence = allocate_canonical();
    auto snapshot_event = model::Event{
        header(
            config_,
            snapshot_id,
            connection.snapshot.event_time_proxy,
            connection.snapshot.last_update_id,
            0U,
            connection.snapshot.canonical_message_sequence,
            snapshot_sequence,
            "bootstrap_connection_start_proxy"
        ),
        model::BookSnapshot{connection.snapshot.bids, connection.snapshot.asks},
    };
    const auto snapshot_available = checked_available(
        connection.snapshot.synchronization_receive_time,
        config_.observation_processing_delay_ns
    );
    (void)kernel.schedule_market_event_with_timing(
        std::move(snapshot_event),
        connection.snapshot.synchronization_receive_time,
        snapshot_available
    );
    markers.emplace(snapshot_id.value(), DeliveryMarker{DeliveryMarker::Kind::Snapshot, false});
    ++integrity.snapshot_count;

    std::uint64_t sequence_cursor = connection.snapshot.last_update_id;
    bool connection_bridged = false;
    for (const auto& message : connection.messages) {
      std::visit(
          [&](const auto& value) {
            using Message = std::decay_t<decltype(value)>;
            const auto available = checked_available(
                value.receive_time, config_.observation_processing_delay_ns
            );
            if constexpr (std::is_same_v<Message, ReplayDepthBatch>) {
              if (sequence_cursor == std::numeric_limits<std::uint64_t>::max()) {
                throw std::overflow_error("historical update sequence is exhausted");
              }
              const auto expected = sequence_cursor + 1U;
              const bool is_bridge = !connection_bridged && value.first_update_id <= expected &&
                                     expected <= value.final_update_id;
              for (std::size_t level = 0U; level < value.updates.size(); ++level) {
                if (level > std::numeric_limits<std::uint32_t>::max()) {
                  throw std::overflow_error("historical depth subsequence exceeds uint32");
                }
                const auto event_id = allocate_event();
                const auto canonical = allocate_canonical();
                auto event = model::Event{
                    header(
                        config_,
                        event_id,
                        value.event_time,
                        value.final_update_id,
                        static_cast<std::uint32_t>(level),
                        value.canonical_message_sequence,
                        canonical,
                        std::to_string(value.event_time.value())
                    ),
                    value.updates[level],
                };
                (void)kernel.schedule_market_event_with_timing(
                    std::move(event), value.receive_time, available
                );
                markers.emplace(
                    event_id.value(),
                    DeliveryMarker{
                        DeliveryMarker::Kind::Depth,
                        is_bridge && level + 1U == value.updates.size(),
                    }
                );
                ++integrity.depth_update_count;
              }
              sequence_cursor = value.final_update_id;
              connection_bridged = true;
              ++integrity.depth_batch_count;
            } else {
              const auto event_id = allocate_event();
              const auto canonical = allocate_canonical();
              auto event = model::Event{
                  header(
                      config_,
                      event_id,
                      value.event_time,
                      value.trade.trade_id.value(),
                      0U,
                      value.canonical_message_sequence,
                      canonical,
                      std::to_string(value.event_time.value())
                  ),
                  value.trade,
              };
              (void)kernel.schedule_market_event_with_timing(
                  std::move(event), value.receive_time, available
              );
              markers.emplace(event_id.value(), DeliveryMarker{DeliveryMarker::Kind::Trade, false});
              ++integrity.trade_count;
            }
          },
          message
      );
    }
  }

  std::vector<policy::PolicyObservation> observations;
  observations.reserve(checkpoints.size());
  std::size_t ingested_events = 0U;
  std::size_t next_connection_reset = 0U;
  bool synchronized = false;

  auto apply_connection_resets = [&](model::TimestampNs inclusive_time) {
    while (next_connection_reset < connection_reset_times.size() &&
           connection_reset_times[next_connection_reset].value() <= inclusive_time.value()) {
      observation_builder = policy::ObservationBuilder{config_.environment};
      synchronized = false;
      ++next_connection_reset;
    }
  };

  auto ingest_delivered = [&](const model::Event& event, const char* error_message) {
    if (!event.header.available_time.has_value()) {
      throw std::logic_error("historical replay delivered an event without availability time");
    }
    apply_connection_resets(*event.header.available_time);
    const auto marker = markers.find(event.header.event_id.value());
    if (marker == markers.end()) {
      throw std::logic_error(error_message);
    }
    if (marker->second.kind == DeliveryMarker::Kind::Snapshot) {
      synchronized = false;
    }
    observation_builder.ingest_delivered_event(event, *event.header.available_time);
    if (marker->second.sequence_bridge) {
      synchronized = true;
      ++integrity.synchronized_connection_count;
    }
  };

  for (const auto& checkpoint : checkpoints) {
    kernel.run_until(checkpoint.decision_time);
    const auto& delivered = kernel.delivered_events();
    while (ingested_events < delivered.size()) {
      ingest_delivered(
          delivered[ingested_events++], "historical replay delivered an unregistered event"
      );
    }
    apply_connection_resets(checkpoint.decision_time);
    if (config_.suppress_observations_until_sequence_bridge && !synchronized) {
      ++integrity.suppressed_checkpoint_count;
      continue;
    }
    observations.push_back(
        observation_builder.build(checkpoint.decision_id, checkpoint.decision_time, execution_state)
    );
  }
  kernel.run();
  const auto& delivered = kernel.delivered_events();
  while (ingested_events < delivered.size()) {
    ingest_delivered(
        delivered[ingested_events++], "historical replay delivered an unregistered final event"
    );
  }
  integrity.delivered_event_count = static_cast<std::uint64_t>(delivered.size());

  HistoricalReplayResult result{};
  result.observations = std::move(observations);
  result.integrity = integrity;
  result.kernel_replay_hash = kernel.replay_hash();
  result.kernel_state_hash = kernel.state_hash();
  result.final_observation_hash = result.observations.empty()
                                      ? std::string{64U, '0'}
                                      : result.observations.back().hash();
  std::ostringstream summary;
  summary << "connections=" << result.integrity.connection_count << '\n'
          << "snapshots=" << result.integrity.snapshot_count << '\n'
          << "depth_batches=" << result.integrity.depth_batch_count << '\n'
          << "depth_updates=" << result.integrity.depth_update_count << '\n'
          << "trades=" << result.integrity.trade_count << '\n'
          << "delivered_events=" << result.integrity.delivered_event_count << '\n'
          << "observations=" << result.observations.size() << '\n'
          << "suppressed_checkpoints=" << result.integrity.suppressed_checkpoint_count << '\n'
          << "exact_fifo_reconstructed=false\n"
          << "endogenous_impact_modelled=false\n"
          << "kernel_replay_hash=" << result.kernel_replay_hash << '\n'
          << "kernel_state_hash=" << result.kernel_state_hash << '\n'
          << "final_observation_hash=" << result.final_observation_hash << '\n';
  result.canonical_summary = summary.str();
  return result;
}

}  // namespace robust_execution::historical
