#include "robust_execution/metrics/metrics.hpp"
#include "policy_test_support.hpp"

#include <cstdlib>
#include <stdexcept>
#include <vector>

int main() {
  namespace metrics = robust_execution::metrics;
  namespace model = robust_execution::model;
  metrics::EpisodeMetricInput input;
  input.episode_id = "bad";
  input.instrument = policy_test::instrument();
  input.parent = policy_test::parent(model::Side::Buy, 10U);
  input.fills = {
      {model::ExecutionId{1U}, model::Side::Buy, model::PriceTicks{100},
       model::QuantityLots{6U}, policy_test::time(100), model::LiquidityRole::Maker,
       model::QuoteAtoms{0}, metrics::FillSource::Continuous},
      {model::ExecutionId{1U}, model::Side::Buy, model::PriceTicks{100},
       model::QuantityLots{6U}, policy_test::time(200), model::LiquidityRole::Maker,
       model::QuoteAtoms{0}, metrics::FillSource::Continuous},
  };
  if (metrics::calculate_episode_metrics(input).ok()) {
    return EXIT_FAILURE;
  }

  metrics::EpisodeMetrics incomplete;
  incomplete.episode_id = "incomplete";
  incomplete.parent_quantity = model::QuantityLots{10U};
  incomplete.filled_quantity = model::QuantityLots{5U};
  incomplete.remaining_quantity = model::QuantityLots{5U};
  incomplete.completion_rate = 0.5;
  metrics::MetricAuditResult audit;
  audit.passed = true;
  try {
    const std::vector episodes{incomplete};
    const std::vector audits{audit};
    static_cast<void>(metrics::summarize_tail_risk(episodes, audits));
  } catch (const std::invalid_argument&) {
    return EXIT_SUCCESS;
  }
  return EXIT_FAILURE;
}
