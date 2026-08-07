#include "robust_execution/historical/historical.hpp"

#include <cstdlib>
#include <optional>

namespace historical = robust_execution::historical;
namespace model = robust_execution::model;

namespace {
model::TimestampNs time(std::int64_t value) {
  return model::TimestampNs{model::ClockDomain::Simulation, value};
}

historical::AggregateL2QueueModel queue(historical::QueueAssumption assumption) {
  return historical::AggregateL2QueueModel{
      historical::QueueModelConfig{assumption, 0U, true, "test-v1"},
      historical::PassiveOrderSpec{
          model::ClientOrderId{1U}, model::Side::Buy, model::PriceTicks{100},
          model::QuantityLots{20U}, model::QuantityLots{100U}, time(0)},
  };
}
}

int main() {
  auto optimistic = queue(historical::QueueAssumption::Optimistic);
  auto central = queue(historical::QueueAssumption::Central);
  auto pessimistic = queue(historical::QueueAssumption::Pessimistic);
  for (auto* model_ptr : {&optimistic, &central, &pessimistic}) {
    model_ptr->on_level_quantity(model::QuantityLots{200U}, time(1));
    model_ptr->on_level_quantity(model::QuantityLots{120U}, time(2));
    const auto fills = model_ptr->on_trade(
        model::Trade{model::TradeId{1U}, std::nullopt, model::PriceTicks{100},
                     model::QuantityLots{70U}, model::AggressorSide::Sell},
        time(3)
    );
    model_ptr->on_level_quantity(model::QuantityLots{50U}, time(4));
    if (fills.size() > 1U) {
      return EXIT_FAILURE;
    }
  }
  const auto optimistic_state = optimistic.snapshot();
  const auto central_state = central.snapshot();
  const auto pessimistic_state = pessimistic.snapshot();
  if (optimistic_state.cumulative_filled.value() != 20U ||
      central_state.cumulative_filled.value() != 10U ||
      !pessimistic_state.cumulative_filled.is_zero() ||
      optimistic_state.cancellation_allocated_ahead.value() != 80U ||
      central_state.cancellation_allocated_ahead.value() != 40U ||
      !pessimistic_state.cancellation_allocated_ahead.is_zero() ||
      optimistic.state_hash().size() != 64U) {
    return EXIT_FAILURE;
  }

  auto through = queue(historical::QueueAssumption::Pessimistic);
  const auto through_fills = through.on_trade(
      model::Trade{model::TradeId{2U}, std::nullopt, model::PriceTicks{99},
                   model::QuantityLots{1U}, model::AggressorSide::Sell},
      time(1)
  );
  if (through_fills.size() != 1U || through_fills[0].quantity.value() != 20U ||
      through_fills[0].reason != historical::QueueFillReason::TradeThrough ||
      through.snapshot().status != historical::QueueOrderStatus::Filled) {
    return EXIT_FAILURE;
  }
  historical::AggregateL2QueueModel sell_model{
      historical::QueueModelConfig{historical::QueueAssumption::Central, 0U, true, "test-v1"},
      historical::PassiveOrderSpec{
          model::ClientOrderId{9U}, model::Side::Sell, model::PriceTicks{101},
          model::QuantityLots{20U}, model::QuantityLots{100U}, time(0)},
  };
  const auto irrelevant = sell_model.on_trade(
      model::Trade{model::TradeId{3U}, std::nullopt, model::PriceTicks{101},
                   model::QuantityLots{200U}, model::AggressorSide::Sell},
      time(1)
  );
  const auto sell_at_price = sell_model.on_trade(
      model::Trade{model::TradeId{4U}, std::nullopt, model::PriceTicks{101},
                   model::QuantityLots{110U}, model::AggressorSide::Buy},
      time(2)
  );
  const auto sell_through = sell_model.on_trade(
      model::Trade{model::TradeId{5U}, std::nullopt, model::PriceTicks{102},
                   model::QuantityLots{1U}, model::AggressorSide::Buy},
      time(3)
  );
  if (!irrelevant.empty() || sell_at_price.size() != 1U ||
      sell_at_price[0].quantity.value() != 10U || sell_through.size() != 1U ||
      sell_through[0].quantity.value() != 10U ||
      sell_model.snapshot().status != historical::QueueOrderStatus::Filled) {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
