#include "robust_execution/metrics/metrics.hpp"
#include "policy_test_support.hpp"

#include <cstdlib>

int main() {
  namespace metrics = robust_execution::metrics;
  namespace model = robust_execution::model;
  metrics::EpisodeMetricInput input;
  input.episode_id = "audit";
  input.instrument = policy_test::instrument();
  input.parent = policy_test::parent(model::Side::Sell, 10U);
  input.fills = {{model::ExecutionId{1U}, model::Side::Sell, model::PriceTicks{100},
                  model::QuantityLots{10U}, policy_test::time(100),
                  model::LiquidityRole::Maker, model::QuoteAtoms{1},
                  metrics::FillSource::Continuous}};
  const auto calculated = metrics::calculate_episode_metrics(input);
  if (!calculated.ok() || !metrics::audit_episode_metrics(input, *calculated.metrics).passed) {
    return EXIT_FAILURE;
  }
  auto tampered = *calculated.metrics;
  tampered.net_cash_flow = model::QuoteAtoms{998};
  return metrics::audit_episode_metrics(input, tampered).passed ? EXIT_FAILURE : EXIT_SUCCESS;
}
