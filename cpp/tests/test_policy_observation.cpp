#include "policy_test_support.hpp"

#include <cstdlib>
#include <stdexcept>

int main() {
  namespace model = robust_execution::model;
  namespace policy = robust_execution::policy;

  policy::ExecutionState state{policy_test::parent(), policy_test::environment()};
  policy::ObservationBuilder builder{policy_test::environment()};
  builder.ingest_delivered_event(policy_test::snapshot(), policy_test::time(110));
  builder.ingest_delivered_event(
      policy_test::event(
          2U,
          105,
          115,
          model::Trade{
              model::TradeId{2U},
              std::nullopt,
              model::PriceTicks{102},
              model::QuantityLots{3U},
              model::AggressorSide::Buy,
          }
      ),
      policy_test::time(115)
  );
  builder.ingest_delivered_event(
      policy_test::event(
          3U,
          108,
          118,
          model::DepthUpdate{
              model::Side::Buy,
              model::PriceTicks{100},
              model::QuantityLots{15U},
              model::BookUpdateAction::Set,
              1U,
          }
      ),
      policy_test::time(118)
  );
  const auto observation = builder.build(model::DecisionId{9U}, policy_test::time(120), state);
  if (observation.best_bid()->value() != 100 || observation.best_ask()->value() != 102 ||
      observation.spread_ticks() != 2 || observation.midpoint_twice_ticks() != 202 ||
      observation.bids().size() != 2U || observation.asks().size() != 2U ||
      observation.visible_bid_quantity().value() != 45U ||
      observation.visible_ask_quantity().value() != 60U ||
      observation.recent_trades().size() != 1U ||
      observation.lineage().delivered_event_count != 3U ||
      observation.observation_cutoff().value() != 108 || observation.hash().size() != 64U) {
    return EXIT_FAILURE;
  }
  const auto repeated = builder.build(model::DecisionId{9U}, policy_test::time(120), state);
  if (observation.canonical() != repeated.canonical() || observation.hash() != repeated.hash()) {
    return EXIT_FAILURE;
  }

  bool future_rejected = false;
  try {
    builder.ingest_delivered_event(policy_test::snapshot(4U, 130, 140), policy_test::time(139));
  } catch (const std::invalid_argument&) {
    future_rejected = true;
  }
  if (!future_rejected) {
    return EXIT_FAILURE;
  }

  bool time_travel_rejected = false;
  try {
    static_cast<void>(builder.build(model::DecisionId{10U}, policy_test::time(117), state));
  } catch (const std::invalid_argument&) {
    time_travel_rejected = true;
  }
  if (!time_travel_rejected) {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
