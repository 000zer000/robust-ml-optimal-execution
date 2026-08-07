#include "synthetic_test_support.hpp"

#include <cstdlib>

int main() {
  using namespace synthetic_test;
  const auto tape = synthetic::SyntheticMarketGenerator{config()}.generate();
  if (tape.summary.total_steps != 120U || tape.steps.size() != 120U ||
      tape.summary.limit_submissions <= 10U || tape.summary.market_submissions == 0U ||
      tape.summary.cancellations == 0U || tape.summary.trades == 0U ||
      tape.summary.executed_lots.is_zero()) {
    return EXIT_FAILURE;
  }
  if (!tape.summary.final_best_bid.has_value() || !tape.summary.final_best_ask.has_value() ||
      tape.summary.final_best_bid->value() >= tape.summary.final_best_ask->value()) {
    return EXIT_FAILURE;
  }
  for (const auto& step : tape.steps) {
    if (step.reference_price.value() <= 0 ||
        (step.best_bid.has_value() && step.best_ask.has_value() &&
         step.best_bid->value() >= step.best_ask->value())) {
      return EXIT_FAILURE;
    }
  }
  if (tape.summary.maker_fees.value() >= 0 || tape.summary.taker_fees.value() <= 0) {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
