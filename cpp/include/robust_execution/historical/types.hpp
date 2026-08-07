#pragma once

#include <cstdint>
#include <string>
#include <variant>
#include <vector>

#include "robust_execution/model/model.hpp"

namespace robust_execution::historical {

struct ReplaySnapshot {
  std::string connection_id;
  std::uint64_t last_update_id{0U};
  model::TimestampNs event_time_proxy{};
  model::TimestampNs synchronization_receive_time{};
  std::vector<model::BookLevel> bids;
  std::vector<model::BookLevel> asks;
  std::uint64_t canonical_message_sequence{0U};
};

struct ReplayDepthBatch {
  std::uint64_t canonical_message_sequence{0U};
  std::uint64_t first_update_id{0U};
  std::uint64_t final_update_id{0U};
  model::TimestampNs event_time{};
  model::TimestampNs receive_time{};
  std::vector<model::DepthUpdate> updates;
};

struct ReplayTrade {
  std::uint64_t canonical_message_sequence{0U};
  model::TimestampNs event_time{};
  model::TimestampNs receive_time{};
  model::Trade trade;
};

using ReplayMessage = std::variant<ReplayDepthBatch, ReplayTrade>;

struct ReplayConnection {
  ReplaySnapshot snapshot;
  std::vector<ReplayMessage> messages;
};

struct ReplayCheckpoint {
  model::DecisionId decision_id{};
  model::TimestampNs decision_time{};
};

struct ReplayIntegrity {
  std::uint64_t connection_count{0U};
  std::uint64_t snapshot_count{0U};
  std::uint64_t depth_batch_count{0U};
  std::uint64_t depth_update_count{0U};
  std::uint64_t trade_count{0U};
  std::uint64_t delivered_event_count{0U};
  std::uint64_t synchronized_connection_count{0U};
  std::uint64_t suppressed_checkpoint_count{0U};
  std::uint64_t sequence_gap_count{0U};
  bool exact_fifo_reconstructed{false};
  bool endogenous_impact_modelled{false};
};

}  // namespace robust_execution::historical
