#include "matching_test_support.hpp"

#include <cstdlib>
#include <cstdint>
#include <string>

namespace {

std::string run_sequence(std::size_t expected_order_count) {
  namespace exchange = robust_execution::exchange;
  namespace model = robust_execution::model;
  auto config = exchange::MatchingEngineConfig{matching_test::instrument()};
  config.expected_order_count = expected_order_count;
  exchange::MatchingEngine engine{std::move(config)};

  for (std::uint64_t index = 0U; index < 250U; ++index) {
    const auto side = index % 2U == 0U ? model::Side::Buy : model::Side::Sell;
    const auto price = side == model::Side::Buy ? 99 : 101;
    const auto submitted = engine.submit(matching_test::limit(
        index + 1U,
        side,
        1U + (index % 3U),
        price,
        model::TimeInForce::GoodTilCancelled,
        false,
        index + 1U
    ));
    if (!submitted.accepted()) return "submit failure";
  }

  const auto aggressive = engine.submit(matching_test::market(
      10'000U,
      model::Side::Buy,
      20U,
      model::TimeInForce::ImmediateOrCancel,
      500U
  ));
  if (!aggressive.accepted()) return "market failure";
  if (!engine.validate_invariants().empty()) return "invariant failure";
  return engine.canonical_state();
}

}  // namespace

int main() {
  const auto baseline = run_sequence(0U);
  const auto reserved = run_sequence(1024U);
  if (baseline != reserved || baseline == "submit failure" || baseline == "market failure" ||
      baseline == "invariant failure") {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
