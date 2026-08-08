#pragma once

#include "robust_execution/policy/policy.hpp"

#include <cstdint>
#include <optional>
#include <utility>
#include <vector>

namespace policy_test {

namespace model = robust_execution::model;
namespace policy = robust_execution::policy;

inline model::TimestampNs time(std::int64_t value) {
  return model::TimestampNs{model::ClockDomain::Simulation, value};
}

inline model::InstrumentDefinition instrument() {
  return model::InstrumentDefinition{
      model::kEventSchemaVersion,
      model::VenueId{"synthetic"},
      model::InstrumentId{"POLICY-USD"},
      "POLICY",
      "USD",
      model::RationalIncrement{1U, 1U},
      model::RationalIncrement{1U, 1U},
      model::RationalIncrement{1U, 1U},
      model::QuantityLots{1U},
      model::QuantityLots{10'000U},
      "policy-test-v1",
  };
}

inline policy::ParentOrderDefinition parent(
    model::Side side = model::Side::Buy,
    std::uint64_t quantity = 100U
) {
  return policy::ParentOrderDefinition{
      model::ParentOrderId{1U},
      side,
      model::QuantityLots{quantity},
      time(0),
      time(1'000),
      model::PriceTicks{101},
      "hard-completion-v1",
  };
}

inline policy::PolicyEnvironment environment() {
  return policy::PolicyEnvironment{
      instrument(),
      model::StrategyId{"test-policy"},
      model::FeeScheduleId{"fee-v1"},
      model::LatencyModelId{"latency-v1"},
      100,
      2U,
      4U,
      1U,
      1U,
      {
          policy::QuantityFraction{1U, 4U},
          policy::QuantityFraction{1U, 2U},
          policy::QuantityFraction{1U, 1U},
      },
      {model::TickOffset{-1}, model::TickOffset{0}, model::TickOffset{1}},
      policy::LotRoundingPolicy::Floor,
      true,
      true,
      true,
  };
}

inline model::Event event(
    std::uint64_t event_id,
    std::int64_t event_time,
    std::int64_t available_time,
    model::EventPayload payload,
    model::EventOrigin origin = model::EventOrigin::SyntheticExchange
) {
  return model::Event{
      model::EventHeader{
          model::kEventSchemaVersion,
          model::EventId{event_id},
          model::RunId{"policy-test-run"},
          model::VenueId{"synthetic"},
          model::InstrumentId{"POLICY-USD"},
          model::SourceChannelId{"policy-test"},
          origin,
          time(event_time),
          time(available_time),
          time(available_time),
          model::EventOrdering{true, event_id, 0U, event_id, event_id},
          std::nullopt,
      },
      std::move(payload),
  };
}

inline model::Event snapshot(
    std::uint64_t event_id = 1U,
    std::int64_t event_time = 100,
    std::int64_t available_time = 110
) {
  return event(
      event_id,
      event_time,
      available_time,
      model::BookSnapshot{
          {
              model::BookLevel{model::PriceTicks{100}, model::QuantityLots{20U}, 2U},
              model::BookLevel{model::PriceTicks{99}, model::QuantityLots{30U}, 3U},
              model::BookLevel{model::PriceTicks{98}, model::QuantityLots{40U}, 4U},
          },
          {
              model::BookLevel{model::PriceTicks{102}, model::QuantityLots{25U}, 2U},
              model::BookLevel{model::PriceTicks{103}, model::QuantityLots{35U}, 3U},
              model::BookLevel{model::PriceTicks{104}, model::QuantityLots{45U}, 4U},
          },
      }
  );
}

inline policy::PolicyObservation observation(
    policy::ExecutionState& state,
    model::DecisionId decision_id = model::DecisionId{1U},
    std::int64_t decision_time = 120
) {
  policy::ObservationBuilder builder{environment()};
  builder.ingest_delivered_event(snapshot(), time(110));
  return builder.build(decision_id, time(decision_time), state);
}

inline policy::ValidatedPolicyAction validated_submit(
    std::uint64_t client_id,
    std::uint64_t quantity,
    model::OrderType type = model::OrderType::Limit,
    std::optional<model::PriceTicks> price = model::PriceTicks{100}
) {
  return policy::ValidatedPolicyAction{
      model::DecisionId{1U},
      time(120),
      policy::PolicyActionKind::Submit,
      "submit",
      {
          model::OrderSubmit{
              model::ParentOrderId{1U},
              model::ClientOrderId{client_id},
              model::DecisionId{1U},
              model::Side::Buy,
              type,
              type == model::OrderType::Market ? model::TimeInForce::ImmediateOrCancel
                                                : model::TimeInForce::GoodTilCancelled,
              model::QuantityLots{quantity},
              price,
              false,
              time(120),
              time(120),
              time(120),
          },
      },
      model::QuantityLots{quantity},
  };
}

}  // namespace policy_test
