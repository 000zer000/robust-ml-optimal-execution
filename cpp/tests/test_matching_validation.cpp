#include "matching_test_support.hpp"

#include <cstdlib>
#include <stdexcept>

namespace {

robust_execution::model::EventHeader header(std::uint64_t event_id) {
  namespace model = robust_execution::model;
  return model::EventHeader{
      model::kEventSchemaVersion,
      model::EventId{event_id},
      model::RunId{"step6-test"},
      model::VenueId{"synthetic"},
      model::InstrumentId{"TEST-USD"},
      model::SourceChannelId{"matching-engine"},
      model::EventOrigin::SyntheticExchange,
      matching_test::time(100),
      matching_test::time(100),
      matching_test::time(100),
      model::EventOrdering{false, 0U, 0U, event_id, event_id},
      std::nullopt,
  };
}

bool valid_payload(
    std::uint64_t event_id,
    robust_execution::model::EventPayload payload
) {
  namespace model = robust_execution::model;
  return !model::has_errors(model::validate_event(model::Event{header(event_id), std::move(payload)}));
}

}  // namespace

int main() {
  namespace exchange = robust_execution::exchange;
  namespace model = robust_execution::model;

  auto invalid_instrument = matching_test::instrument();
  invalid_instrument.minimum_order_quantity = model::QuantityLots{0U};
  try {
    exchange::MatchingEngine invalid{exchange::MatchingEngineConfig{invalid_instrument}};
    static_cast<void>(invalid);
    return EXIT_FAILURE;
  } catch (const std::invalid_argument&) {
  }

  auto config = exchange::MatchingEngineConfig{matching_test::instrument()};
  config.allow_market_orders = false;
  config.allow_immediate_or_cancel = false;
  config.allow_fill_or_kill = false;
  config.allow_post_only = false;
  exchange::MatchingEngine restricted{config};

  if (restricted.submit(matching_test::market(1U, model::Side::Buy, 1U)).failure->code !=
          exchange::EngineFailureCode::UnsupportedCombination ||
      restricted.submit(matching_test::limit(
          2U,
          model::Side::Buy,
          1U,
          100,
          model::TimeInForce::ImmediateOrCancel
      )).failure->code != exchange::EngineFailureCode::UnsupportedCombination ||
      restricted.submit(matching_test::limit(
          3U,
          model::Side::Buy,
          1U,
          100,
          model::TimeInForce::FillOrKill
      )).failure->code != exchange::EngineFailureCode::UnsupportedCombination ||
      restricted.submit(matching_test::limit(
          4U,
          model::Side::Buy,
          1U,
          100,
          model::TimeInForce::GoodTilCancelled,
          true
      )).failure->code != exchange::EngineFailureCode::UnsupportedCombination) {
    return EXIT_FAILURE;
  }

  auto engine = matching_test::engine();
  const auto accepted = engine.submit(matching_test::limit(10U, model::Side::Sell, 2U, 101));
  if (!accepted.accepted() || !valid_payload(1U, *accepted.acknowledgement)) {
    return EXIT_FAILURE;
  }
  const auto duplicate = engine.submit(matching_test::limit(10U, model::Side::Sell, 2U, 102));
  if (duplicate.accepted() || duplicate.failure->code !=
                                  exchange::EngineFailureCode::DuplicateClientOrderId ||
      !valid_payload(2U, *duplicate.rejection)) {
    return EXIT_FAILURE;
  }

  auto invalid_time = matching_test::limit(11U, model::Side::Buy, 1U, 100);
  invalid_time.outbound_send_time = matching_test::time(9);
  const auto invalid_command = engine.submit(invalid_time);
  if (invalid_command.accepted() || invalid_command.failure->code !=
                                      exchange::EngineFailureCode::InvalidCommand) {
    return EXIT_FAILURE;
  }

  const auto market_fok = engine.submit(matching_test::market(
      11U,
      model::Side::Buy,
      2U,
      model::TimeInForce::FillOrKill
  ));
  if (!market_fok.accepted() || market_fok.matches.size() != 1U ||
      !valid_payload(3U, market_fok.matches[0].trade) ||
      !valid_payload(4U, market_fok.matches[0].maker_fill) ||
      !valid_payload(5U, market_fok.matches[0].taker_fill)) {
    return EXIT_FAILURE;
  }

  const auto unknown_cancel = engine.cancel(matching_test::cancel_request(999U, 999U));
  if (unknown_cancel.accepted() || unknown_cancel.failure->code !=
                                       exchange::EngineFailureCode::UnknownOrder ||
      unknown_cancel.failure->current_state.has_value()) {
    return EXIT_FAILURE;
  }

  if (!engine.validate_invariants().empty()) {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
