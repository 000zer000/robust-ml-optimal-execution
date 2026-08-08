#include "robust_execution/historical/queue_model.hpp"

#include "robust_execution/exchange/exchange.hpp"
#include "robust_execution/util/sha256.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <limits>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace robust_execution::historical {
namespace {

[[nodiscard]] std::uint64_t checked_add_value(std::uint64_t lhs, std::uint64_t rhs) {
  if (rhs > std::numeric_limits<std::uint64_t>::max() - lhs) {
    throw std::overflow_error("queue quantity addition overflow");
  }
  return lhs + rhs;
}

[[nodiscard]] std::uint64_t checked_multiply(std::uint64_t lhs, std::uint64_t rhs) {
  if (lhs != 0U && rhs > std::numeric_limits<std::uint64_t>::max() / lhs) {
    throw std::overflow_error("queue quantity multiplication overflow");
  }
  return lhs * rhs;
}

[[nodiscard]] std::uint64_t central_cancellation_ahead(
    std::uint64_t unexplained_reduction,
    std::uint64_t estimated_ahead,
    std::uint64_t displayed_before
) {
  if (unexplained_reduction == 0U || estimated_ahead == 0U || displayed_before == 0U) {
    return 0U;
  }
  const auto bounded_ahead = std::min(estimated_ahead, displayed_before);
  const auto numerator = checked_multiply(unexplained_reduction, bounded_ahead);
  return numerator / displayed_before;
}

[[nodiscard]] bool consumes_side(model::Side resting_side, model::AggressorSide aggressor) {
  return (resting_side == model::Side::Buy && aggressor == model::AggressorSide::Sell) ||
         (resting_side == model::Side::Sell && aggressor == model::AggressorSide::Buy);
}

[[nodiscard]] bool is_trade_through(
    model::Side resting_side,
    model::PriceTicks trade_price,
    model::PriceTicks order_price
) {
  if (resting_side == model::Side::Buy) {
    return trade_price.value() < order_price.value();
  }
  return trade_price.value() > order_price.value();
}

[[nodiscard]] model::InstrumentDefinition validation_instrument() {
  return model::InstrumentDefinition{
      model::kEventSchemaVersion,
      model::VenueId{"synthetic_exact"},
      model::InstrumentId{"QUEUE_TEST"},
      "BASE",
      "QUOTE",
      model::RationalIncrement{1U, 1U},
      model::RationalIncrement{1U, 1U},
      model::RationalIncrement{1U, 1U},
      model::QuantityLots{1U},
      model::QuantityLots{1'000'000U},
      "step16-queue-validation-v1",
  };
}

[[nodiscard]] model::TimestampNs time(std::int64_t value) {
  return model::TimestampNs{model::ClockDomain::Simulation, value};
}

[[nodiscard]] model::OrderSubmit limit_order(
    std::uint64_t client_id,
    model::Side side,
    std::uint64_t quantity,
    std::int64_t price,
    std::int64_t event_time
) {
  return model::OrderSubmit{
      model::ParentOrderId{client_id},
      model::ClientOrderId{client_id},
      model::DecisionId{client_id},
      side,
      model::OrderType::Limit,
      model::TimeInForce::GoodTilCancelled,
      model::QuantityLots{quantity},
      model::PriceTicks{price},
      false,
      time(event_time),
      time(event_time),
      time(event_time),
  };
}

[[nodiscard]] model::OrderSubmit market_order(
    std::uint64_t client_id,
    model::Side side,
    std::uint64_t quantity,
    std::int64_t event_time
) {
  return model::OrderSubmit{
      model::ParentOrderId{client_id},
      model::ClientOrderId{client_id},
      model::DecisionId{client_id},
      side,
      model::OrderType::Market,
      model::TimeInForce::ImmediateOrCancel,
      model::QuantityLots{quantity},
      std::nullopt,
      false,
      time(event_time),
      time(event_time),
      time(event_time),
  };
}

struct ScenarioDefinition {
  std::string id;
  std::uint64_t ahead_cancel{0U};
  std::uint64_t ahead_keep{0U};
  std::uint64_t behind_cancel{0U};
  std::uint64_t behind_keep{0U};
  std::uint64_t own_quantity{20U};
  std::uint64_t aggressive_quantity{0U};
};

struct ExactScenarioTape {
  model::QuantityLots exact_fill{};
  model::QuantityLots displayed_at_join{};
  model::QuantityLots displayed_after_additions{};
  model::QuantityLots displayed_after_cancellations{};
  model::QuantityLots displayed_after_trade{};
  std::vector<model::Trade> public_trades;
};

struct SubmittedOrder {
  model::ClientOrderId client_id{};
  model::ExchangeOrderId exchange_id{};
};

[[nodiscard]] SubmittedOrder submit_required(
    exchange::MatchingEngine& engine,
    const model::OrderSubmit& command
) {
  const auto result = engine.submit(command);
  if (!result.accepted() || !result.final_order.has_value()) {
    throw std::logic_error("queue validation failed to submit exact FIFO order");
  }
  return SubmittedOrder{command.client_order_id, result.final_order->exchange_order_id};
}

void cancel_required(
    exchange::MatchingEngine& engine,
    const SubmittedOrder& order,
    std::uint64_t decision_id,
    std::int64_t event_time
) {
  const auto result = engine.cancel(model::CancelRequest{
      order.client_id,
      order.exchange_id,
      model::DecisionId{decision_id},
      time(event_time),
      time(event_time),
      time(event_time),
  });
  if (!result.accepted()) {
    throw std::logic_error("queue validation failed to cancel exact FIFO order");
  }
}

[[nodiscard]] ExactScenarioTape build_exact_scenario(const ScenarioDefinition& definition) {
  exchange::MatchingEngine exact{exchange::MatchingEngineConfig{validation_instrument()}};
  exchange::MatchingEngine ghost{exchange::MatchingEngineConfig{validation_instrument()}};

  std::uint64_t next_id = 10U;
  auto submit_pair = [&](std::uint64_t quantity, bool exact_only = false) {
    if (quantity == 0U) {
      return std::pair<std::optional<SubmittedOrder>, std::optional<SubmittedOrder>>{};
    }
    const auto exact_order = submit_required(
        exact, limit_order(next_id, model::Side::Buy, quantity, 100, static_cast<std::int64_t>(next_id))
    );
    std::optional<SubmittedOrder> ghost_order;
    if (!exact_only) {
      ghost_order = submit_required(
          ghost,
          limit_order(
              next_id,
              model::Side::Buy,
              quantity,
              100,
              static_cast<std::int64_t>(next_id)
          )
      );
    }
    ++next_id;
    return std::pair<std::optional<SubmittedOrder>, std::optional<SubmittedOrder>>{
        exact_order, ghost_order};
  };

  const auto ahead_cancel = submit_pair(definition.ahead_cancel);
  (void)submit_pair(definition.ahead_keep);
  const auto displayed_at_join = checked_add_value(definition.ahead_cancel, definition.ahead_keep);
  const auto own = submit_pair(definition.own_quantity, true);
  if (!own.first.has_value()) {
    throw std::logic_error("queue validation own order is missing");
  }
  const auto behind_cancel = submit_pair(definition.behind_cancel);
  (void)submit_pair(definition.behind_keep);
  const auto displayed_after_additions = checked_add_value(
      displayed_at_join,
      checked_add_value(definition.behind_cancel, definition.behind_keep)
  );

  if (ahead_cancel.first.has_value() && ahead_cancel.second.has_value()) {
    cancel_required(exact, *ahead_cancel.first, 500U, 500);
    cancel_required(ghost, *ahead_cancel.second, 500U, 500);
  }
  if (behind_cancel.first.has_value() && behind_cancel.second.has_value()) {
    cancel_required(exact, *behind_cancel.first, 501U, 501);
    cancel_required(ghost, *behind_cancel.second, 501U, 501);
  }
  const auto displayed_after_cancellations = checked_add_value(
      definition.ahead_keep, definition.behind_keep
  );

  const auto exact_market = exact.submit(
      market_order(900U, model::Side::Sell, definition.aggressive_quantity, 900)
  );
  const auto ghost_market = ghost.submit(
      market_order(900U, model::Side::Sell, definition.aggressive_quantity, 900)
  );
  if (!exact_market.accepted() || !ghost_market.accepted()) {
    throw std::logic_error("queue validation aggressive order was rejected");
  }

  std::uint64_t exact_fill = 0U;
  for (const auto& match : exact_market.matches) {
    if (match.maker_fill.client_order_id == own.first->client_id) {
      exact_fill = checked_add_value(exact_fill, match.maker_fill.quantity.value());
    }
  }
  std::vector<model::Trade> public_trades;
  public_trades.reserve(ghost_market.matches.size());
  for (const auto& match : ghost_market.matches) {
    public_trades.push_back(match.trade);
  }

  return ExactScenarioTape{
      model::QuantityLots{exact_fill},
      model::QuantityLots{displayed_at_join},
      model::QuantityLots{displayed_after_additions},
      model::QuantityLots{displayed_after_cancellations},
      ghost.quantity_at(model::Side::Buy, model::PriceTicks{100}),
      std::move(public_trades),
  };
}

[[nodiscard]] QueueModelSnapshot replay_scenario(
    const ScenarioDefinition& definition,
    const ExactScenarioTape& tape,
    QueueAssumption assumption,
    std::uint32_t additional_ahead_bps
) {
  AggregateL2QueueModel model{
      QueueModelConfig{assumption, additional_ahead_bps, true, "aggregate-l2-queue-v1"},
      PassiveOrderSpec{
          model::ClientOrderId{777U},
          model::Side::Buy,
          model::PriceTicks{100},
          model::QuantityLots{definition.own_quantity},
          tape.displayed_at_join,
          time(100),
      },
  };
  model.on_level_quantity(tape.displayed_after_additions, time(200));
  model.on_level_quantity(tape.displayed_after_cancellations, time(600));
  std::int64_t trade_time = 900;
  for (const auto& trade : tape.public_trades) {
    (void)model.on_trade(trade, time(trade_time++));
  }
  model.on_level_quantity(tape.displayed_after_trade, time(1000));
  return model.snapshot();
}

[[nodiscard]] std::string report_json(
    const std::vector<QueueScenarioResult>& scenarios,
    const std::vector<QueueSensitivityResult>& sensitivity,
    bool trade_through_passed,
    bool cancellation_only_passed,
    bool deterministic
) {
  std::ostringstream output;
  output << '{'
         << "\"schema_version\":\"queue-model-validation-v1\","
         << "\"step\":16,"
         << "\"historical_exact_fifo_reconstructed\":false,"
         << "\"ghost_small_agent_assumption\":true,"
         << "\"trade_through_rule_passed\":" << (trade_through_passed ? "true" : "false")
         << ','
         << "\"no_fill_from_cancellation_only_passed\":"
         << (cancellation_only_passed ? "true" : "false") << ','
         << "\"deterministic\":" << (deterministic ? "true" : "false") << ','
         << "\"scenarios\":[";
  for (std::size_t index = 0U; index < scenarios.size(); ++index) {
    if (index > 0U) {
      output << ',';
    }
    const auto& scenario = scenarios[index];
    output << '{'
           << "\"scenario_id\":\"" << scenario.scenario_id << "\","
           << "\"exact_fifo_fill_lots\":" << scenario.exact_fifo_fill.value() << ','
           << "\"optimistic_fill_lots\":" << scenario.optimistic_fill.value() << ','
           << "\"central_fill_lots\":" << scenario.central_fill.value() << ','
           << "\"pessimistic_fill_lots\":" << scenario.pessimistic_fill.value() << ','
           << "\"exact_within_model_bounds\":"
           << (scenario.exact_within_model_bounds ? "true" : "false") << ','
           << "\"model_ordering_valid\":"
           << (scenario.model_ordering_valid ? "true" : "false") << '}';
  }
  output << "],\"sensitivity\":[";
  for (std::size_t index = 0U; index < sensitivity.size(); ++index) {
    if (index > 0U) {
      output << ',';
    }
    const auto& item = sensitivity[index];
    output << '{'
           << "\"scenario_id\":\"" << item.scenario_id << "\","
           << "\"assumption\":\"" << to_string(item.assumption) << "\","
           << "\"additional_initial_ahead_bps\":" << item.additional_initial_ahead_bps << ','
           << "\"estimated_fill_lots\":" << item.estimated_fill.value() << ','
           << "\"estimated_ahead_after_events_lots\":"
           << item.estimated_ahead_after_events.value() << '}';
  }
  output << "]}";
  return output.str();
}

}  // namespace

AggregateL2QueueModel::AggregateL2QueueModel(QueueModelConfig config, PassiveOrderSpec order)
    : config_(std::move(config)),
      order_(std::move(order)),
      displayed_quantity_(order_.displayed_quantity_at_join),
      leaves_quantity_(order_.quantity),
      last_event_time_(order_.join_time) {
  if (!order_.client_order_id.valid() || order_.quantity.is_zero() || order_.price.value() <= 0 ||
      order_.join_time.value() < 0 || config_.model_version.empty() ||
      config_.additional_initial_ahead_bps > 100'000U) {
    throw std::invalid_argument("aggregate L2 queue model configuration is invalid");
  }
  const auto product = checked_multiply(
      order_.displayed_quantity_at_join.value(), config_.additional_initial_ahead_bps
  );
  const auto additional = product == 0U ? 0U : checked_add_value(product, 9'999U) / 10'000U;
  estimated_ahead_ = model::QuantityLots{checked_add_value(
      order_.displayed_quantity_at_join.value(), additional
  )};
}

void AggregateL2QueueModel::require_event_time(model::TimestampNs event_time) const {
  if (event_time.domain() != order_.join_time.domain()) {
    throw std::invalid_argument("queue model event uses a different clock domain");
  }
  if (event_time.value() < last_event_time_.value()) {
    throw std::invalid_argument("queue model events must be time ordered");
  }
}

QueueFillEstimate AggregateL2QueueModel::apply_fill(
    model::QuantityLots quantity,
    QueueFillReason reason,
    model::TimestampNs event_time
) {
  const auto fill = std::min(quantity.value(), leaves_quantity_.value());
  cumulative_filled_ = model::QuantityLots{
      checked_add_value(cumulative_filled_.value(), fill)};
  leaves_quantity_ = model::QuantityLots{leaves_quantity_.value() - fill};
  status_ = leaves_quantity_.is_zero() ? QueueOrderStatus::Filled : QueueOrderStatus::PartiallyFilled;
  return QueueFillEstimate{
      order_.client_order_id,
      order_.price,
      model::QuantityLots{fill},
      cumulative_filled_,
      leaves_quantity_,
      model::LiquidityRole::Maker,
      reason,
      event_time,
  };
}

std::vector<QueueFillEstimate> AggregateL2QueueModel::on_trade(
    const model::Trade& trade,
    model::TimestampNs event_time
) {
  require_event_time(event_time);
  last_event_time_ = event_time;
  std::vector<QueueFillEstimate> fills;
  if (status_ == QueueOrderStatus::Cancelled || status_ == QueueOrderStatus::Filled ||
      trade.quantity.is_zero() || !consumes_side(order_.side, trade.aggressor_side)) {
    return fills;
  }
  if (is_trade_through(order_.side, trade.price, order_.price)) {
    ++relevant_trade_count_;
    ++trade_through_count_;
    if (config_.fill_on_trade_through && !leaves_quantity_.is_zero()) {
      estimated_ahead_ = model::QuantityLots{0U};
      fills.push_back(apply_fill(leaves_quantity_, QueueFillReason::TradeThrough, event_time));
    }
    return fills;
  }
  if (trade.price != order_.price) {
    return fills;
  }

  ++relevant_trade_count_;
  trade_quantity_at_price_ = model::QuantityLots{checked_add_value(
      trade_quantity_at_price_.value(), trade.quantity.value()
  )};
  const auto reflected = std::min(trade.quantity.value(), displayed_quantity_.value());
  pending_trade_depletion_ = model::QuantityLots{checked_add_value(
      pending_trade_depletion_.value(), reflected
  )};

  const auto ahead_consumed = std::min(trade.quantity.value(), estimated_ahead_.value());
  estimated_ahead_ = model::QuantityLots{estimated_ahead_.value() - ahead_consumed};
  const auto residual = trade.quantity.value() - ahead_consumed;
  if (residual > 0U && !leaves_quantity_.is_zero()) {
    fills.push_back(
        apply_fill(model::QuantityLots{residual}, QueueFillReason::TradeAtPrice, event_time)
    );
  }
  return fills;
}

void AggregateL2QueueModel::on_level_quantity(
    model::QuantityLots quantity_after,
    model::TimestampNs event_time
) {
  require_event_time(event_time);
  last_event_time_ = event_time;
  if (status_ == QueueOrderStatus::Cancelled || status_ == QueueOrderStatus::Filled) {
    displayed_quantity_ = quantity_after;
    pending_trade_depletion_ = model::QuantityLots{0U};
    ++level_update_count_;
    return;
  }
  const auto before = displayed_quantity_.value();
  const auto after = quantity_after.value();
  if (after < before) {
    const auto reduction = before - after;
    const auto trade_attributed = std::min(reduction, pending_trade_depletion_.value());
    const auto unexplained = reduction - trade_attributed;
    unexplained_reduction_ = model::QuantityLots{checked_add_value(
        unexplained_reduction_.value(), unexplained
    )};
    std::uint64_t ahead_reduction = 0U;
    switch (config_.assumption) {
      case QueueAssumption::Optimistic:
        ahead_reduction = std::min(unexplained, estimated_ahead_.value());
        break;
      case QueueAssumption::Central:
        ahead_reduction = std::min(
            central_cancellation_ahead(unexplained, estimated_ahead_.value(), before),
            estimated_ahead_.value()
        );
        break;
      case QueueAssumption::Pessimistic:
        ahead_reduction = 0U;
        break;
    }
    estimated_ahead_ = model::QuantityLots{estimated_ahead_.value() - ahead_reduction};
    cancellation_ahead_ = model::QuantityLots{checked_add_value(
        cancellation_ahead_.value(), ahead_reduction
    )};
    cancellation_behind_ = model::QuantityLots{checked_add_value(
        cancellation_behind_.value(), unexplained - ahead_reduction
    )};
  }
  displayed_quantity_ = quantity_after;
  pending_trade_depletion_ = model::QuantityLots{0U};
  ++level_update_count_;
}

void AggregateL2QueueModel::cancel(model::TimestampNs event_time) {
  require_event_time(event_time);
  last_event_time_ = event_time;
  if (status_ == QueueOrderStatus::Filled) {
    throw std::logic_error("a filled aggregate queue order cannot be cancelled");
  }
  status_ = QueueOrderStatus::Cancelled;
}

QueueModelSnapshot AggregateL2QueueModel::snapshot() const noexcept {
  return QueueModelSnapshot{
      config_.assumption,
      status_,
      displayed_quantity_,
      estimated_ahead_,
      cumulative_filled_,
      leaves_quantity_,
      unexplained_reduction_,
      cancellation_ahead_,
      cancellation_behind_,
      trade_quantity_at_price_,
      level_update_count_,
      relevant_trade_count_,
      trade_through_count_,
  };
}

const QueueModelConfig& AggregateL2QueueModel::config() const noexcept { return config_; }

const PassiveOrderSpec& AggregateL2QueueModel::order() const noexcept { return order_; }

std::string AggregateL2QueueModel::canonical_state() const {
  const auto state = snapshot();
  std::ostringstream output;
  output << "model=" << config_.model_version << '\n'
         << "assumption=" << to_string(config_.assumption) << '\n'
         << "additional_initial_ahead_bps=" << config_.additional_initial_ahead_bps << '\n'
         << "fill_on_trade_through=" << config_.fill_on_trade_through << '\n'
         << "client_order_id=" << order_.client_order_id.value() << '\n'
         << "side=" << model::to_string(order_.side) << '\n'
         << "price_ticks=" << order_.price.value() << '\n'
         << "order_quantity_lots=" << order_.quantity.value() << '\n'
         << "displayed_quantity_lots=" << state.displayed_quantity.value() << '\n'
         << "estimated_ahead_lots=" << state.estimated_quantity_ahead.value() << '\n'
         << "cumulative_filled_lots=" << state.cumulative_filled.value() << '\n'
         << "leaves_quantity_lots=" << state.leaves_quantity.value() << '\n'
         << "unexplained_reduction_lots=" << state.unexplained_reduction.value() << '\n'
         << "cancellation_ahead_lots=" << state.cancellation_allocated_ahead.value() << '\n'
         << "cancellation_behind_lots=" << state.cancellation_allocated_behind.value() << '\n'
         << "trade_quantity_at_price_lots=" << state.trade_quantity_at_price.value() << '\n'
         << "level_updates=" << state.level_update_count << '\n'
         << "relevant_trades=" << state.relevant_trade_count << '\n'
         << "trade_throughs=" << state.trade_through_count << '\n'
         << "status=" << to_string(state.status) << '\n';
  return output.str();
}

std::string AggregateL2QueueModel::state_hash() const {
  return util::sha256_hex(canonical_state());
}

QueueValidationReport run_queue_model_validation() {
  const std::array<ScenarioDefinition, 5U> definitions{{
      ScenarioDefinition{"no_cancellation", 0U, 100U, 0U, 100U, 20U, 110U},
      ScenarioDefinition{"cancellation_ahead", 80U, 20U, 0U, 100U, 20U, 50U},
      ScenarioDefinition{"cancellation_behind", 0U, 100U, 80U, 20U, 20U, 50U},
      ScenarioDefinition{"mixed_cancellation", 40U, 60U, 40U, 60U, 20U, 70U},
      ScenarioDefinition{"addition_only", 0U, 100U, 0U, 200U, 20U, 50U},
  }};

  std::vector<QueueScenarioResult> scenarios;
  scenarios.reserve(definitions.size());
  std::vector<QueueSensitivityResult> sensitivity;
  sensitivity.reserve(9U);
  for (const auto& definition : definitions) {
    const auto tape = build_exact_scenario(definition);
    const auto optimistic = replay_scenario(definition, tape, QueueAssumption::Optimistic, 0U);
    const auto central = replay_scenario(definition, tape, QueueAssumption::Central, 0U);
    const auto pessimistic = replay_scenario(definition, tape, QueueAssumption::Pessimistic, 0U);
    const bool ordering = optimistic.cumulative_filled.value() >= central.cumulative_filled.value() &&
                          central.cumulative_filled.value() >=
                              pessimistic.cumulative_filled.value();
    const bool bracketed = optimistic.cumulative_filled.value() >= tape.exact_fill.value() &&
                           tape.exact_fill.value() >=
                               pessimistic.cumulative_filled.value();
    scenarios.push_back(QueueScenarioResult{
        definition.id,
        tape.exact_fill,
        optimistic.cumulative_filled,
        central.cumulative_filled,
        pessimistic.cumulative_filled,
        bracketed,
        ordering,
    });
    if (definition.id == "mixed_cancellation") {
      for (const auto assumption : {
               QueueAssumption::Optimistic,
               QueueAssumption::Central,
               QueueAssumption::Pessimistic,
           }) {
        for (const auto buffer : {0U, 2'500U, 5'000U}) {
          const auto estimate = replay_scenario(definition, tape, assumption, buffer);
          sensitivity.push_back(QueueSensitivityResult{
              definition.id,
              assumption,
              buffer,
              estimate.cumulative_filled,
              estimate.estimated_quantity_ahead,
          });
        }
      }
    }
  }

  AggregateL2QueueModel through_model{
      QueueModelConfig{QueueAssumption::Pessimistic, 0U, true, "aggregate-l2-queue-v1"},
      PassiveOrderSpec{
          model::ClientOrderId{888U},
          model::Side::Buy,
          model::PriceTicks{100},
          model::QuantityLots{20U},
          model::QuantityLots{500U},
          time(0),
      },
  };
  const auto through_fills = through_model.on_trade(
      model::Trade{
          model::TradeId{1U},
          std::nullopt,
          model::PriceTicks{99},
          model::QuantityLots{1U},
          model::AggressorSide::Sell,
      },
      time(1)
  );
  const bool trade_through_passed = through_fills.size() == 1U &&
                                    through_fills.front().quantity.value() == 20U &&
                                    through_fills.front().reason == QueueFillReason::TradeThrough;

  AggregateL2QueueModel cancellation_only{
      QueueModelConfig{QueueAssumption::Optimistic, 0U, true, "aggregate-l2-queue-v1"},
      PassiveOrderSpec{
          model::ClientOrderId{889U},
          model::Side::Sell,
          model::PriceTicks{101},
          model::QuantityLots{20U},
          model::QuantityLots{100U},
          time(0),
      },
  };
  cancellation_only.on_level_quantity(model::QuantityLots{0U}, time(1));
  const auto cancellation_state = cancellation_only.snapshot();
  const bool cancellation_only_passed = cancellation_state.cumulative_filled.is_zero() &&
                                        cancellation_state.leaves_quantity.value() == 20U &&
                                        cancellation_state.estimated_quantity_ahead.is_zero();

  const auto first_json = report_json(
      scenarios, sensitivity, trade_through_passed, cancellation_only_passed, true
  );
  const auto second_json = report_json(
      scenarios, sensitivity, trade_through_passed, cancellation_only_passed, true
  );
  const bool deterministic = first_json == second_json;
  const auto canonical = report_json(
      scenarios, sensitivity, trade_through_passed, cancellation_only_passed, deterministic
  );

  QueueValidationReport report{};
  report.scenarios = scenarios;
  report.sensitivity = sensitivity;
  report.exact_comparison_count = static_cast<std::uint64_t>(scenarios.size());
  report.bracketed_comparison_count = static_cast<std::uint64_t>(std::count_if(
      scenarios.begin(), scenarios.end(), [](const auto& item) { return item.exact_within_model_bounds; }
  ));
  report.monotonic_comparison_count = static_cast<std::uint64_t>(std::count_if(
      scenarios.begin(), scenarios.end(), [](const auto& item) { return item.model_ordering_valid; }
  ));
  report.trade_through_rule_passed = trade_through_passed;
  report.no_fill_from_cancellation_only_passed = cancellation_only_passed;
  report.deterministic = deterministic;
  report.exact_fifo_reconstructed_historically = false;
  report.canonical_json = canonical;
  report.sha256 = util::sha256_hex(canonical);
  return report;
}

}  // namespace robust_execution::historical
