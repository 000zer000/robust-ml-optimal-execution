#include "robust_execution/simulation/simulation.hpp"

#include <cstdint>
#include <iostream>
#include <optional>

namespace {

namespace exchange = robust_execution::exchange;
namespace model = robust_execution::model;
namespace simulation = robust_execution::simulation;

model::TimestampNs time(std::int64_t value) {
  return model::TimestampNs{model::ClockDomain::Simulation, value};
}

model::InstrumentDefinition instrument() {
  return model::InstrumentDefinition{
      model::kEventSchemaVersion,
      model::VenueId{"synthetic"},
      model::InstrumentId{"DEMO-USD"},
      "DEMO",
      "USD",
      model::RationalIncrement{1U, 100U},
      model::RationalIncrement{1U, 1000U},
      model::RationalIncrement{1U, 100U},
      model::QuantityLots{1U},
      model::QuantityLots{1000U},
      "step7-demo-v1",
  };
}

simulation::SimulationKernelConfig config() {
  return simulation::SimulationKernelConfig{
      exchange::MatchingEngineConfig{instrument()},
      model::RunId{"step7-demo-run"},
      20260806U,
      simulation::LatencyModelConfig{
          "step7-demo-latency-v1",
          simulation::LatencyRangeNs{7, 7, 1U},
          simulation::LatencyRangeNs{3, 3, 2U},
          simulation::LatencyRangeNs{2, 2, 3U},
          simulation::LatencyRangeNs{5, 5, 4U},
          simulation::LatencyRangeNs{4, 4, 5U},
          simulation::LatencyRangeNs{6, 6, 6U},
          simulation::LatencyRangeNs{3, 3, 7U},
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

model::OrderSubmit limit_sell() {
  return model::OrderSubmit{
      model::ParentOrderId{1U},
      model::ClientOrderId{1U},
      model::DecisionId{1U},
      model::Side::Sell,
      model::OrderType::Limit,
      model::TimeInForce::GoodTilCancelled,
      model::QuantityLots{4U},
      model::PriceTicks{101},
      false,
      time(0),
      time(0),
      time(0),
  };
}

model::OrderSubmit market_buy() {
  return model::OrderSubmit{
      model::ParentOrderId{1U},
      model::ClientOrderId{2U},
      model::DecisionId{2U},
      model::Side::Buy,
      model::OrderType::Market,
      model::TimeInForce::ImmediateOrCancel,
      model::QuantityLots{3U},
      std::nullopt,
      false,
      time(0),
      time(0),
      time(0),
  };
}

}  // namespace

int main() {
  simulation::SimulationKernel kernel{config()};
  const auto maker = kernel.schedule_submit(limit_sell(), time(1000), 1U);
  const auto taker = kernel.schedule_submit(market_buy(), time(2000), 2U);
  (void)kernel.schedule_timer(model::Timer{"deadline-check", 1U}, time(3000));
  kernel.run();

  std::cout << "step=7\n"
            << "maker_exchange_receive_ns=" << maker.timing.exchange_receive.value() << '\n'
            << "maker_ack_available_ns=" << maker.timing.acknowledgement_available.value() << '\n'
            << "taker_exchange_receive_ns=" << taker.timing.exchange_receive.value() << '\n'
            << "taker_ack_available_ns=" << taker.timing.acknowledgement_available.value() << '\n'
            << "exchange_received_events=" << kernel.exchange_received_events().size() << '\n'
            << "delivered_events=" << kernel.delivered_events().size() << '\n'
            << "failures=" << kernel.failures().size() << '\n'
            << "trace_records=" << kernel.trace().size() << '\n'
            << "active_orders=" << kernel.matching_engine().active_order_count() << '\n'
            << "replay_sha256=" << kernel.replay_hash() << '\n'
            << "state_sha256=" << kernel.state_hash() << '\n';
  return 0;
}
