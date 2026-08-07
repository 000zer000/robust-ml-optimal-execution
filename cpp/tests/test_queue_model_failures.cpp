#include "robust_execution/historical/historical.hpp"

#include <cstdlib>
#include <optional>
#include <stdexcept>

namespace historical = robust_execution::historical;
namespace model = robust_execution::model;

namespace {
model::TimestampNs time(std::int64_t value) {
  return model::TimestampNs{model::ClockDomain::Simulation, value};
}

bool rejected(const historical::QueueModelConfig& config, const historical::PassiveOrderSpec& spec) {
  try {
    const historical::AggregateL2QueueModel model{config, spec};
    (void)model;
  } catch (const std::invalid_argument&) {
    return true;
  }
  return false;
}
}

int main() {
  const historical::QueueModelConfig valid{
      historical::QueueAssumption::Central, 0U, true, "test-v1"};
  const historical::PassiveOrderSpec spec{
      model::ClientOrderId{1U}, model::Side::Buy, model::PriceTicks{100},
      model::QuantityLots{20U}, model::QuantityLots{100U}, time(10)};
  if (!rejected(valid, historical::PassiveOrderSpec{}) ||
      !rejected(historical::QueueModelConfig{historical::QueueAssumption::Central, 100'001U,
                                             true, "test-v1"}, spec) ||
      !rejected(historical::QueueModelConfig{historical::QueueAssumption::Central, 0U,
                                             true, ""}, spec)) {
    return EXIT_FAILURE;
  }

  historical::AggregateL2QueueModel model_instance{valid, spec};
  try {
    model_instance.on_level_quantity(model::QuantityLots{50U}, time(9));
    return EXIT_FAILURE;
  } catch (const std::invalid_argument&) {
  }
  try {
    (void)model_instance.on_trade(
        model::Trade{model::TradeId{1U}, std::nullopt, model::PriceTicks{100},
                     model::QuantityLots{1U}, model::AggressorSide::Sell},
        model::TimestampNs{model::ClockDomain::UnixUtc, 11}
    );
    return EXIT_FAILURE;
  } catch (const std::invalid_argument&) {
  }
  model_instance.cancel(time(11));
  const auto ignored = model_instance.on_trade(
      model::Trade{model::TradeId{2U}, std::nullopt, model::PriceTicks{100},
                   model::QuantityLots{100U}, model::AggressorSide::Sell},
      time(12)
  );
  if (!ignored.empty() || model_instance.snapshot().status != historical::QueueOrderStatus::Cancelled) {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
