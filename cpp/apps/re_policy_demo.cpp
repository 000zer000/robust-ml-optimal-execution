#include "robust_execution/policy/policy.hpp"
#include "robust_execution/simulation/simulation.hpp"

#include <cstdint>
#include <iostream>
#include <optional>
#include <stdexcept>

namespace {

namespace exchange = robust_execution::exchange;
namespace model = robust_execution::model;
namespace policy = robust_execution::policy;
namespace simulation = robust_execution::simulation;

model::TimestampNs sim_time(std::int64_t value) {
  return model::TimestampNs{model::ClockDomain::Simulation, value};
}

model::InstrumentDefinition instrument() {
  return model::InstrumentDefinition{
      model::kEventSchemaVersion,
      model::VenueId{"synthetic"},
      model::InstrumentId{"POLICY-DEMO-USD"},
      "POLICY",
      "USD",
      model::RationalIncrement{1U, 1U},
      model::RationalIncrement{1U, 1U},
      model::RationalIncrement{1U, 1U},
      model::QuantityLots{1U},
      model::QuantityLots{1'000U},
      "step8-demo-v1",
  };
}

simulation::SimulationKernelConfig kernel_config() {
  return simulation::SimulationKernelConfig{
      exchange::MatchingEngineConfig{instrument()},
      model::RunId{"step8-demo-run"},
      20260806U,
      simulation::LatencyModelConfig{
          "zero-latency-v1",
          simulation::LatencyRangeNs{0, 0, 1U},
          simulation::LatencyRangeNs{0, 0, 2U},
          simulation::LatencyRangeNs{0, 0, 3U},
          simulation::LatencyRangeNs{0, 0, 4U},
          simulation::LatencyRangeNs{0, 0, 5U},
          simulation::LatencyRangeNs{0, 0, 6U},
          simulation::LatencyRangeNs{0, 0, 7U},
      },
      model::SourceChannelId{"strategy-orders"},
      model::SourceChannelId{"exchange-orders"},
      model::SourceChannelId{"exchange-fills"},
      model::SourceChannelId{"exchange-trades"},
      model::SourceChannelId{"system"},
      100U,
      100U,
  };
}

policy::PolicyEnvironment environment() {
  return policy::PolicyEnvironment{
      instrument(),
      model::StrategyId{"step8-demo-policy"},
      model::FeeScheduleId{"zero-fee-v1"},
      model::LatencyModelId{"zero-latency-v1"},
      100,
      5U,
      16U,
      1U,
      1U,
      {policy::QuantityFraction{1U, 2U}, policy::QuantityFraction{1U, 1U}},
      {model::TickOffset{-1}, model::TickOffset{0}, model::TickOffset{1}},
      policy::LotRoundingPolicy::Floor,
      true,
      true,
      true,
  };
}

policy::ParentOrderDefinition parent() {
  return policy::ParentOrderDefinition{
      model::ParentOrderId{1U},
      model::Side::Buy,
      model::QuantityLots{10U},
      sim_time(0),
      sim_time(1'000),
      model::PriceTicks{101},
      "hard-completion-v1",
  };
}

model::Event snapshot() {
  return model::Event{
      model::EventHeader{
          model::kEventSchemaVersion,
          model::EventId{1U},
          model::RunId{"step8-demo-run"},
          model::VenueId{"synthetic"},
          model::InstrumentId{"POLICY-DEMO-USD"},
          model::SourceChannelId{"synthetic-market"},
          model::EventOrigin::SyntheticExchange,
          sim_time(0),
          std::nullopt,
          std::nullopt,
          model::EventOrdering{true, 1U, 0U, 1U, 1U},
          std::nullopt,
      },
      model::BookSnapshot{
          {model::BookLevel{model::PriceTicks{100}, model::QuantityLots{10U}, 1U}},
          {model::BookLevel{model::PriceTicks{102}, model::QuantityLots{10U}, 1U}},
      },
  };
}

model::OrderSubmit maker_sell() {
  return model::OrderSubmit{
      model::ParentOrderId{999U},
      model::ClientOrderId{900U},
      model::DecisionId{900U},
      model::Side::Sell,
      model::OrderType::Limit,
      model::TimeInForce::GoodTilCancelled,
      model::QuantityLots{10U},
      model::PriceTicks{102},
      false,
      sim_time(0),
      sim_time(0),
      sim_time(0),
  };
}

void ingest_new(
    const simulation::SimulationKernel& kernel,
    std::size_t& cursor,
    policy::ObservationBuilder& builder,
    policy::ExecutionState& state
) {
  const auto& events = kernel.delivered_events();
  while (cursor < events.size()) {
    const auto& event = events[cursor++];
    const auto delivery = *event.header.available_time;
    builder.ingest_delivered_event(event, delivery);
    const auto issues = state.apply_delivered_event(event, delivery);
    if (!issues.empty()) {
      throw std::runtime_error("policy demo state update failed");
    }
  }
}

}  // namespace

int main() {
  simulation::SimulationKernel kernel{kernel_config()};
  policy::ExecutionState state{parent(), environment()};
  policy::ObservationBuilder builder{environment()};
  policy::ActionValidator validator{environment()};
  policy::TerminalCompletionPlanner terminal{
      policy::TerminalRuleConfig{"hard-completion-v1", 1U, true}
  };

  (void)kernel.schedule_market_event(snapshot(), 1U);
  (void)kernel.schedule_submit(maker_sell(), sim_time(0), 2U);
  kernel.run();
  std::size_t cursor = 0U;
  ingest_new(kernel, cursor, builder, state);

  const auto first_observation = builder.build(model::DecisionId{1U}, sim_time(100), state);
  const auto first_action = policy::PolicyAction{
      model::DecisionId{1U},
      sim_time(100),
      policy::SubmitChildAction{
          model::ClientOrderId{10U},
          policy::QuantityFraction{1U, 2U},
          model::OrderType::Market,
          model::TimeInForce::ImmediateOrCancel,
          std::nullopt,
          false,
      },
  };
  const auto first_validated = validator.validate(first_action, first_observation, state);
  if (!first_validated.valid()) {
    throw std::runtime_error("first demo action failed validation");
  }
  (void)policy::dispatch_validated_action(kernel, state, *first_validated.action, 10U);
  kernel.run();
  ingest_new(kernel, cursor, builder, state);

  const auto terminal_observation = builder.build(model::DecisionId{2U}, sim_time(1'000), state);
  const auto terminal_plan = terminal.plan(
      terminal_observation,
      model::DecisionId{2U},
      model::ClientOrderId{11U}
  );
  if (!terminal_plan.action.has_value()) {
    throw std::runtime_error("terminal demo plan did not produce an action");
  }
  const auto terminal_validated = validator.validate(*terminal_plan.action, terminal_observation, state);
  if (!terminal_validated.valid()) {
    throw std::runtime_error("terminal demo action failed validation");
  }
  (void)policy::dispatch_validated_action(kernel, state, *terminal_validated.action, 20U);
  terminal.record_aggressive_attempt();
  kernel.run();
  ingest_new(kernel, cursor, builder, state);

  const auto final_state = state.parent_snapshot(sim_time(1'001));
  const auto final_observation = builder.build(model::DecisionId{3U}, sim_time(1'001), state);
  std::cout << "step=8\n"
            << "parent_status=" << policy::to_string(final_state.status) << '\n'
            << "total_quantity_lots=" << final_state.total_quantity.value() << '\n'
            << "filled_quantity_lots=" << final_state.cumulative_filled.value() << '\n'
            << "remaining_quantity_lots=" << final_state.remaining_quantity.value() << '\n'
            << "gross_cash_flow_quote_atoms=" << final_state.gross_cash_flow.value() << '\n'
            << "net_cash_flow_quote_atoms=" << final_state.net_cash_flow.value() << '\n'
            << "fill_count=" << final_state.fill_count << '\n'
            << "active_child_orders=" << state.acknowledged_active_order_count() << '\n'
            << "delivered_events=" << kernel.delivered_events().size() << '\n'
            << "terminal_plan=" << policy::to_string(terminal_plan.kind) << '\n'
            << "observation_sha256=" << final_observation.hash() << '\n'
            << "policy_state_sha256=" << state.state_hash(sim_time(1'001)) << '\n'
            << "kernel_replay_sha256=" << kernel.replay_hash() << '\n';
  return 0;
}
