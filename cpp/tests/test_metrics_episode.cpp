#include "robust_execution/metrics/metrics.hpp"
#include "policy_test_support.hpp"

#include <cmath>
#include <cstdlib>
#include <string>

int main() {
  namespace metrics = robust_execution::metrics;
  namespace model = robust_execution::model;
  auto input = metrics::EpisodeMetricInput{};
  input.episode_id = "episode";
  input.instrument = policy_test::instrument();
  input.parent = policy_test::parent(model::Side::Buy, 100U);
  input.fills = {
      {model::ExecutionId{1U}, model::Side::Buy, model::PriceTicks{99},
       model::QuantityLots{40U}, policy_test::time(100), model::LiquidityRole::Maker,
       model::QuoteAtoms{-4}, metrics::FillSource::Continuous},
      {model::ExecutionId{2U}, model::Side::Buy, model::PriceTicks{101},
       model::QuantityLots{50U}, policy_test::time(500), model::LiquidityRole::Taker,
       model::QuoteAtoms{5}, metrics::FillSource::Continuous},
      {model::ExecutionId{3U}, model::Side::Buy, model::PriceTicks{105},
       model::QuantityLots{10U}, policy_test::time(1'100), model::LiquidityRole::Taker,
       model::QuoteAtoms{2}, metrics::FillSource::TerminalCompletion},
  };
  input.actions = {2U, 2U, 1U, 0U, 0U, 0U};
  input.performance = {1'000U, 2'000'000, 1'024U};
  const auto result = metrics::calculate_episode_metrics(input);
  if (!result.ok()) {
    return EXIT_FAILURE;
  }
  const auto& value = *result.metrics;
  if (!value.complete || value.filled_quantity.value() != 100U ||
      value.remaining_quantity.value() != 0U ||
      value.gross_execution_notional.value() != 10'060 ||
      value.explicit_fees.value() != 3 || value.net_cash_flow.value() != -10'063 ||
      !value.implementation_shortfall.has_value() ||
      value.implementation_shortfall->value() != -37 ||
      value.terminal_completion_cost.value() != 42 ||
      std::abs(value.passive_fraction - 0.4) > 1e-12 ||
      std::abs(*value.events_per_second - 500'000.0) > 1e-9 ||
      value.canonical_json.find("\"action_dispatch_latency\"") == std::string::npos) {
    return EXIT_FAILURE;
  }
  const auto audit = metrics::audit_episode_metrics(input, value);
  if (!audit.passed) {
    return EXIT_FAILURE;
  }

  metrics::EpisodeMetricInput rational;
  rational.episode_id = "rational-increments";
  rational.instrument = model::InstrumentDefinition{
      model::kEventSchemaVersion,
      model::VenueId{"synthetic"},
      model::InstrumentId{"RATIONAL-USD"},
      "RATIONAL",
      "USD",
      model::RationalIncrement{1U, 100U},
      model::RationalIncrement{1U, 1'000U},
      model::RationalIncrement{1U, 1'000'000U},
      model::QuantityLots{1U},
      model::QuantityLots{1'000'000U},
      "rational-metrics-v1",
  };
  rational.parent = policy_test::parent(model::Side::Buy, 2'000U);
  rational.parent.arrival_price = model::PriceTicks{12'345};
  rational.fills = {{
      model::ExecutionId{1U}, model::Side::Buy, model::PriceTicks{12'345},
      model::QuantityLots{2'000U}, policy_test::time(100),
      model::LiquidityRole::Maker, model::QuoteAtoms{0},
      metrics::FillSource::Continuous,
  }};
  const auto rational_result = metrics::calculate_episode_metrics(rational);
  if (!rational_result.ok() ||
      rational_result.metrics->gross_execution_notional.value() != 246'900'000 ||
      !rational_result.metrics->average_execution_price_ticks.has_value() ||
      std::abs(*rational_result.metrics->average_execution_price_ticks - 12'345.0) > 1e-9 ||
      !rational_result.metrics->average_execution_price_quote.has_value() ||
      std::abs(*rational_result.metrics->average_execution_price_quote - 123.45) > 1e-12 ||
      !metrics::audit_episode_metrics(rational, *rational_result.metrics).passed) {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
