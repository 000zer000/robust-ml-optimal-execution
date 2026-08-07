#include "robust_execution/model/model.hpp"

#include <algorithm>
#include <cstdlib>
#include <string>

namespace model = robust_execution::model;

model::EventHeader valid_header(model::EventId event_id) {
  return model::EventHeader{
      model::kEventSchemaVersion,
      event_id,
      model::RunId{"run-1"},
      model::VenueId{"synthetic"},
      model::InstrumentId{"TEST-USD"},
      model::SourceChannelId{"book"},
      model::EventOrigin::SyntheticExchange,
      model::TimestampNs{model::ClockDomain::Simulation, 100},
      model::TimestampNs{model::ClockDomain::Simulation, 110},
      model::TimestampNs{model::ClockDomain::Simulation, 120},
      model::EventOrdering{true, event_id.value(), 0U, event_id.value(), event_id.value()},
      std::nullopt,
  };
}

bool has_code(const model::ValidationIssues& issues, const std::string& code) {
  return std::any_of(issues.begin(), issues.end(), [&code](const model::ValidationIssue& issue) {
    return issue.code == code;
  });
}

int main() {
  const model::InstrumentDefinition instrument{
      model::kEventSchemaVersion,
      model::VenueId{"synthetic"},
      model::InstrumentId{"TEST-USD"},
      "TEST",
      "USD",
      model::RationalIncrement{1U, 100U},
      model::RationalIncrement{1U, 1000U},
      model::RationalIncrement{1U, 100U},
      model::QuantityLots{1U},
      model::QuantityLots{1000000U},
      "synthetic-v1",
  };
  if (model::has_errors(model::validate_instrument(instrument))) {
    return EXIT_FAILURE;
  }

  const model::Event snapshot{
      valid_header(model::EventId{1U}),
      model::BookSnapshot{
          {{model::PriceTicks{100}, model::QuantityLots{5U}, 1U}},
          {{model::PriceTicks{101}, model::QuantityLots{4U}, 1U}},
      },
  };
  if (model::event_kind(snapshot.payload) != model::EventKind::BookSnapshot ||
      model::has_errors(model::validate_event(snapshot))) {
    return EXIT_FAILURE;
  }

  const model::Event bad_snapshot{
      valid_header(model::EventId{2U}),
      model::BookSnapshot{
          {{model::PriceTicks{101}, model::QuantityLots{5U}, std::nullopt}},
          {{model::PriceTicks{101}, model::QuantityLots{4U}, std::nullopt}},
      },
  };
  const auto bad_book_issues = model::validate_event(bad_snapshot);
  if (!model::has_errors(bad_book_issues) || !has_code(bad_book_issues, "book.crossed")) {
    return EXIT_FAILURE;
  }

  const model::Event submit{
      valid_header(model::EventId{3U}),
      model::OrderSubmit{
          model::ParentOrderId{1U},
          model::ClientOrderId{10U},
          model::DecisionId{20U},
          model::Side::Buy,
          model::OrderType::Limit,
          model::TimeInForce::GoodTilCancelled,
          model::QuantityLots{3U},
          model::PriceTicks{100},
          true,
          model::TimestampNs{model::ClockDomain::Simulation, 80},
          model::TimestampNs{model::ClockDomain::Simulation, 90},
          model::TimestampNs{model::ClockDomain::Simulation, 100},
      },
  };
  if (model::has_errors(model::validate_event(submit))) {
    return EXIT_FAILURE;
  }

  auto bad_submit = submit;
  bad_submit.payload = model::OrderSubmit{
      model::ParentOrderId{1U},
      model::ClientOrderId{11U},
      model::DecisionId{21U},
      model::Side::Buy,
      model::OrderType::Market,
      model::TimeInForce::ImmediateOrCancel,
      model::QuantityLots{3U},
      model::PriceTicks{100},
      true,
      model::TimestampNs{model::ClockDomain::Simulation, 100},
      model::TimestampNs{model::ClockDomain::Simulation, 90},
      model::TimestampNs{model::ClockDomain::Simulation, 80},
  };
  const auto bad_submit_issues = model::validate_event(bad_submit);
  if (!has_code(bad_submit_issues, "order.market_has_price") ||
      !has_code(bad_submit_issues, "order.market_post_only") ||
      !has_code(bad_submit_issues, "time.send_before_decision")) {
    return EXIT_FAILURE;
  }

  const model::Event fill{
      valid_header(model::EventId{4U}),
      model::Fill{
          model::ExecutionId{30U},
          model::ClientOrderId{10U},
          model::ExchangeOrderId{40U},
          std::string{"match-1"},
          model::Side::Buy,
          model::PriceTicks{100},
          model::QuantityLots{1U},
          model::QuantityLots{1U},
          model::QuantityLots{2U},
          model::LiquidityRole::Maker,
      },
  };
  if (model::has_errors(model::validate_event(fill))) {
    return EXIT_FAILURE;
  }

  auto historical_header = valid_header(model::EventId{5U});
  historical_header.origin = model::EventOrigin::HistoricalFeed;
  historical_header.receive_time = model::TimestampNs{model::ClockDomain::Simulation, 90};
  const model::Event historical{
      historical_header,
      model::Timer{"historical-clock-quality", 1U},
  };
  const auto historical_issues = model::validate_event(historical);
  if (model::has_errors(historical_issues) ||
      !has_code(historical_issues, "time.receive_before_exchange_historical")) {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
