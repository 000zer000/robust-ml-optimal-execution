#include "robust_execution/synthetic/generator.hpp"

#include "robust_execution/exchange/matching_engine.hpp"
#include "robust_execution/simulation/logical_rng.hpp"
#include "robust_execution/util/sha256.hpp"

#include <algorithm>
#include <cstdlib>
#include <cstdint>
#include <limits>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace robust_execution::synthetic {
namespace {

namespace exchange = robust_execution::exchange;
namespace simulation = robust_execution::simulation;

constexpr std::uint64_t kStreamLimitOccurrence = 101U;
constexpr std::uint64_t kStreamMarketOccurrence = 102U;
constexpr std::uint64_t kStreamCancelOccurrence = 103U;
constexpr std::uint64_t kStreamReferenceOccurrence = 104U;
constexpr std::uint64_t kStreamLimitSide = 111U;
constexpr std::uint64_t kStreamMarketSide = 112U;
constexpr std::uint64_t kStreamReferenceSide = 113U;
constexpr std::uint64_t kStreamLimitLevel = 121U;
constexpr std::uint64_t kStreamLimitQuantity = 122U;
constexpr std::uint64_t kStreamMarketQuantity = 123U;
constexpr std::uint64_t kStreamCancelSelection = 124U;
constexpr std::uint64_t kStreamReferenceJump = 125U;
constexpr std::int64_t kMicroticksPerTick = 1'000'000;
constexpr std::uint32_t kMaximumRuntimeMultiplierPpm = 10U * kProbabilityScalePpm;

struct ActiveOrder {
  model::ClientOrderId client_order_id{};
  model::ExchangeOrderId exchange_order_id{};
  model::Side side{model::Side::Buy};
};

struct RuntimeParameters {
  std::uint32_t liquidity_multiplier_ppm{kProbabilityScalePpm};
  std::uint32_t spread_multiplier_ppm{kProbabilityScalePpm};
  std::uint32_t volatility_multiplier_ppm{kProbabilityScalePpm};
  std::uint32_t market_multiplier_ppm{kProbabilityScalePpm};
  std::uint32_t cancel_multiplier_ppm{kProbabilityScalePpm};
  std::int64_t buy_probability_ppm{500'000};
};

struct ExcitationState {
  std::uint32_t limit_ppm{0U};
  std::uint32_t market_ppm{0U};
  std::uint32_t cancel_ppm{0U};
};

[[nodiscard]] std::uint32_t multiply_ppm(
    std::uint32_t lhs,
    std::uint32_t rhs,
    std::uint32_t cap = kMaximumRuntimeMultiplierPpm
) noexcept {
  const auto product = static_cast<std::uint64_t>(lhs) * static_cast<std::uint64_t>(rhs);
  return static_cast<std::uint32_t>(
      std::min<std::uint64_t>(cap, product / kProbabilityScalePpm)
  );
}

[[nodiscard]] std::uint32_t scaled_probability(
    std::uint32_t base,
    std::uint32_t multiplier,
    std::uint32_t excitation = 0U
) noexcept {
  const auto scaled = static_cast<std::uint64_t>(base) * multiplier / kProbabilityScalePpm;
  return static_cast<std::uint32_t>(
      std::min<std::uint64_t>(kProbabilityScalePpm, scaled + excitation)
  );
}

[[nodiscard]] bool occurs(
    const simulation::LogicalRandom& random,
    std::uint64_t stream,
    std::uint64_t logical_index,
    std::uint32_t probability_ppm
) {
  if (probability_ppm == 0U) {
    return false;
  }
  if (probability_ppm >= kProbabilityScalePpm) {
    return true;
  }
  return random.bounded_u32({stream, logical_index}, kProbabilityScalePpm) < probability_ppm;
}

[[nodiscard]] model::Side draw_side(
    const simulation::LogicalRandom& random,
    std::uint64_t stream,
    std::uint64_t logical_index,
    std::int64_t buy_probability_ppm
) {
  const auto clamped = std::clamp<std::int64_t>(buy_probability_ppm, 0, kProbabilityScalePpm);
  const auto draw = random.bounded_u32({stream, logical_index}, kProbabilityScalePpm);
  return static_cast<std::int64_t>(draw) < clamped ? model::Side::Buy : model::Side::Sell;
}

[[nodiscard]] std::uint64_t draw_quantity(
    const simulation::LogicalRandom& random,
    std::uint64_t stream,
    std::uint64_t logical_index,
    std::uint64_t minimum,
    std::uint64_t maximum
) {
  const auto span = maximum - minimum + 1U;
  if (span > std::numeric_limits<std::uint32_t>::max()) {
    throw std::overflow_error("synthetic quantity range exceeds bounded RNG support");
  }
  return minimum + random.bounded_u32(
                       {stream, logical_index},
                       static_cast<std::uint32_t>(span)
                   );
}

[[nodiscard]] model::TimestampNs step_time(
    const SyntheticMarketConfig& config,
    std::uint64_t global_step
) {
  if (global_step > static_cast<std::uint64_t>(
                        (std::numeric_limits<std::int64_t>::max() -
                         config.start_time.value()) /
                        config.grid_step_ns
                    )) {
    throw std::overflow_error("synthetic timestamp exceeds int64 nanosecond range");
  }
  return model::TimestampNs{
      model::ClockDomain::Simulation,
      config.start_time.value() + static_cast<std::int64_t>(global_step) * config.grid_step_ns,
  };
}

[[nodiscard]] model::QuoteAtoms fee_for(
    model::QuoteAtoms atoms_per_lot,
    model::QuantityLots quantity
) {
  const auto rate = atoms_per_lot.value();
  const auto lots = quantity.value();
  if (rate != 0) {
    const auto absolute_rate = rate < 0 ? static_cast<std::uint64_t>(-(rate + 1)) + 1U
                                        : static_cast<std::uint64_t>(rate);
    if (lots > static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max()) /
                   absolute_rate) {
      throw std::overflow_error("synthetic fee multiplication overflow");
    }
  }
  return model::QuoteAtoms{rate * static_cast<std::int64_t>(lots)};
}

[[nodiscard]] std::int64_t safe_add_price(std::int64_t base, std::int64_t offset) {
  if ((offset > 0 && base > std::numeric_limits<std::int64_t>::max() - offset) ||
      (offset < 0 && base < std::numeric_limits<std::int64_t>::min() - offset)) {
    throw std::overflow_error("synthetic reference-price arithmetic overflow");
  }
  const auto result = base + offset;
  if (result <= 0) {
    throw std::runtime_error("synthetic reference price became non-positive");
  }
  return result;
}

[[nodiscard]] std::int64_t effective_reference(
    std::int64_t fundamental_ticks,
    std::int64_t impact_microticks
) {
  return safe_add_price(fundamental_ticks, impact_microticks / kMicroticksPerTick);
}

[[nodiscard]] std::uint64_t book_side_quantity(
    const exchange::BookView& book,
    model::Side side
) {
  const auto& levels = side == model::Side::Buy ? book.bids : book.asks;
  std::uint64_t total = 0U;
  for (const auto& level : levels) {
    if (level.displayed_quantity.value() > std::numeric_limits<std::uint64_t>::max() - total) {
      throw std::overflow_error("visible synthetic book quantity overflow");
    }
    total += level.displayed_quantity.value();
  }
  return total;
}

[[nodiscard]] std::uint32_t resilience_boost(
    const RegimeConfig& regime,
    const RuntimeParameters& runtime,
    const exchange::BookView& book
) {
  const auto target_per_level =
      regime.target_lots_per_level * static_cast<std::uint64_t>(runtime.liquidity_multiplier_ppm) /
      kProbabilityScalePpm;
  const auto target = std::max<std::uint64_t>(1U, target_per_level) *
                      static_cast<std::uint64_t>(regime.visible_levels_per_side) * 2U;
  const auto visible = book_side_quantity(book, model::Side::Buy) +
                       book_side_quantity(book, model::Side::Sell);
  if (visible >= target) {
    return 0U;
  }
  const auto deficit = target - visible;
  return static_cast<std::uint32_t>(std::min<std::uint64_t>(
      regime.resilience_boost_cap_ppm,
      deficit * regime.resilience_boost_cap_ppm / target
  ));
}

void decay_excitation(ExcitationState& state, const RegimeConfig& regime) noexcept {
  state.limit_ppm = multiply_ppm(state.limit_ppm, regime.excitation_decay_ppm, regime.excitation_cap_ppm);
  state.market_ppm = multiply_ppm(state.market_ppm, regime.excitation_decay_ppm, regime.excitation_cap_ppm);
  state.cancel_ppm = multiply_ppm(state.cancel_ppm, regime.excitation_decay_ppm, regime.excitation_cap_ppm);
}

void excite(std::uint32_t& value, const RegimeConfig& regime) noexcept {
  value = static_cast<std::uint32_t>(std::min<std::uint64_t>(
      regime.excitation_cap_ppm,
      static_cast<std::uint64_t>(value) + regime.excitation_increment_ppm
  ));
}

[[nodiscard]] RuntimeParameters runtime_parameters(
    const RegimeConfig& regime,
    const std::vector<ShockConfig>& shocks,
    std::uint64_t global_step
) {
  RuntimeParameters runtime;
  runtime.buy_probability_ppm = regime.buy_probability_ppm;
  for (const auto& shock : shocks) {
    const auto end = shock.start_step + shock.duration_steps;
    if (global_step < shock.start_step || global_step >= end) {
      continue;
    }
    runtime.liquidity_multiplier_ppm = multiply_ppm(
        runtime.liquidity_multiplier_ppm,
        shock.liquidity_multiplier_ppm
    );
    runtime.spread_multiplier_ppm = multiply_ppm(
        runtime.spread_multiplier_ppm,
        shock.spread_multiplier_ppm
    );
    runtime.volatility_multiplier_ppm = multiply_ppm(
        runtime.volatility_multiplier_ppm,
        shock.volatility_multiplier_ppm
    );
    runtime.market_multiplier_ppm = multiply_ppm(
        runtime.market_multiplier_ppm,
        shock.market_order_multiplier_ppm
    );
    runtime.cancel_multiplier_ppm = multiply_ppm(
        runtime.cancel_multiplier_ppm,
        shock.cancel_multiplier_ppm
    );
    runtime.buy_probability_ppm += shock.buy_probability_shift_ppm;
  }
  runtime.buy_probability_ppm = std::clamp<std::int64_t>(
      runtime.buy_probability_ppm,
      0,
      kProbabilityScalePpm
  );
  return runtime;
}

[[nodiscard]] std::uint32_t half_spread(
    const RegimeConfig& regime,
    const RuntimeParameters& runtime
) noexcept {
  const auto scaled = static_cast<std::uint64_t>(regime.half_spread_ticks) *
                      runtime.spread_multiplier_ppm / kProbabilityScalePpm;
  return static_cast<std::uint32_t>(std::max<std::uint64_t>(1U, scaled));
}

void clean_active_orders(
    std::vector<ActiveOrder>& active_orders,
    const exchange::MatchingEngine& engine
) {
  active_orders.erase(
      std::remove_if(
          active_orders.begin(),
          active_orders.end(),
          [&engine](const ActiveOrder& active) {
            const auto order = engine.order(active.client_order_id);
            return !order.has_value() || model::is_terminal(order->state);
          }
      ),
      active_orders.end()
  );
}

[[nodiscard]] model::OrderSubmit make_limit_order(
    std::uint64_t client_id,
    std::uint64_t decision_id,
    model::Side side,
    std::uint64_t quantity,
    std::int64_t price,
    model::TimestampNs time
) {
  return model::OrderSubmit{
      model::ParentOrderId{9'001U},
      model::ClientOrderId{client_id},
      model::DecisionId{decision_id},
      side,
      model::OrderType::Limit,
      model::TimeInForce::GoodTilCancelled,
      model::QuantityLots{quantity},
      model::PriceTicks{price},
      true,
      time,
      time,
      time,
  };
}

[[nodiscard]] model::OrderSubmit make_market_order(
    std::uint64_t client_id,
    std::uint64_t decision_id,
    model::Side side,
    std::uint64_t quantity,
    model::TimestampNs time
) {
  return model::OrderSubmit{
      model::ParentOrderId{9'001U},
      model::ClientOrderId{client_id},
      model::DecisionId{decision_id},
      side,
      model::OrderType::Market,
      model::TimeInForce::ImmediateOrCancel,
      model::QuantityLots{quantity},
      std::nullopt,
      false,
      time,
      time,
      time,
  };
}

[[nodiscard]] std::int64_t passive_price(
    const exchange::MatchingEngine& engine,
    model::Side side,
    std::int64_t reference,
    std::uint32_t half_spread_ticks,
    std::uint32_t level
) {
  std::int64_t price = side == model::Side::Buy
                           ? reference - static_cast<std::int64_t>(half_spread_ticks + level)
                           : reference + static_cast<std::int64_t>(half_spread_ticks + level);
  if (side == model::Side::Buy) {
    if (const auto ask = engine.best_ask(); ask.has_value() && price >= ask->value()) {
      price = ask->value() - 1;
    }
  } else if (const auto bid = engine.best_bid(); bid.has_value() && price <= bid->value()) {
    price = bid->value() + 1;
  }
  if (price <= 0) {
    throw std::runtime_error("synthetic passive order price became non-positive");
  }
  return price;
}

void add_action(
    SyntheticTape& tape,
    std::uint64_t& action_sequence,
    std::uint64_t global_step,
    model::TimestampNs time,
    std::string regime_id,
    SyntheticActionKind kind,
    std::optional<model::Side> side,
    model::QuantityLots quantity,
    std::optional<model::PriceTicks> price,
    std::optional<model::ClientOrderId> client_order_id,
    std::optional<model::ExchangeOrderId> exchange_order_id,
    std::optional<std::string> shock_id,
    std::string detail
) {
  tape.actions.push_back(SyntheticAction{
      ++action_sequence,
      global_step,
      time,
      std::move(regime_id),
      kind,
      side,
      quantity,
      price,
      client_order_id,
      exchange_order_id,
      std::move(shock_id),
      std::move(detail),
  });
}

void add_matches(
    SyntheticTape& tape,
    const std::vector<exchange::MatchExecution>& matches,
    std::uint64_t global_step,
    model::TimestampNs time,
    const std::string& regime_id,
    const FeeScheduleConfig& fees,
    std::uint64_t& trade_sequence,
    std::int64_t& impact_microticks,
    const RegimeConfig& regime
) {
  for (const auto& match : matches) {
    const auto maker_fee = fee_for(fees.maker_atoms_per_lot, match.maker_fill.quantity);
    const auto taker_fee = fee_for(fees.taker_atoms_per_lot, match.taker_fill.quantity);
    tape.trades.push_back(SyntheticTradeRecord{
        ++trade_sequence,
        global_step,
        time,
        regime_id,
        match.trade,
        match.maker_fill.quantity,
        match.taker_fill.quantity,
        maker_fee,
        taker_fee,
    });
    ++tape.summary.trades;
    const auto executed = model::checked_add(tape.summary.executed_lots, match.trade.quantity);
    const auto maker_total = model::checked_add(tape.summary.maker_fees, maker_fee);
    const auto taker_total = model::checked_add(tape.summary.taker_fees, taker_fee);
    if (!executed.has_value() || !maker_total.has_value() || !taker_total.has_value()) {
      throw std::overflow_error("synthetic summary accounting overflow");
    }
    tape.summary.executed_lots = *executed;
    tape.summary.maker_fees = *maker_total;
    tape.summary.taker_fees = *taker_total;

    const auto signed_quantity = static_cast<std::int64_t>(match.trade.quantity.value());
    const auto direction = match.trade.aggressor_side == model::AggressorSide::Buy ? 1 : -1;
    if (regime.impact_microticks_per_lot != 0 &&
        signed_quantity > std::numeric_limits<std::int64_t>::max() /
                              std::max<std::int64_t>(1, std::abs(regime.impact_microticks_per_lot))) {
      throw std::overflow_error("synthetic impact multiplication overflow");
    }
    const auto delta = direction * signed_quantity * regime.impact_microticks_per_lot;
    if ((delta > 0 && impact_microticks > std::numeric_limits<std::int64_t>::max() - delta) ||
        (delta < 0 && impact_microticks < std::numeric_limits<std::int64_t>::min() - delta)) {
      throw std::overflow_error("synthetic impact accumulation overflow");
    }
    impact_microticks += delta;
  }
}

void ensure_invariants(const exchange::MatchingEngine& engine) {
  const auto violations = engine.validate_invariants();
  if (!violations.empty()) {
    throw std::logic_error("matching-engine invariant failed during synthetic generation");
  }
  const auto bid = engine.best_bid();
  const auto ask = engine.best_ask();
  if (bid.has_value() && ask.has_value() && bid->value() >= ask->value()) {
    throw std::logic_error("synthetic generator produced a crossed book");
  }
}

}  // namespace

SyntheticMarketGenerator::SyntheticMarketGenerator(SyntheticMarketConfig config)
    : config_(std::move(config)) {
  const auto issues = validate(config_);
  if (has_errors(issues)) {
    std::ostringstream message;
    message << "invalid synthetic-market configuration";
    for (const auto& issue : issues) {
      message << "\n- " << issue.code << ": " << issue.detail;
    }
    throw std::invalid_argument(message.str());
  }
}

SyntheticTape SyntheticMarketGenerator::generate() const {
  SyntheticTape tape;
  tape.config = config_;
  exchange::MatchingEngine engine{exchange::MatchingEngineConfig{config_.instrument}};
  simulation::LogicalRandom random{config_.random_seed};
  std::vector<ActiveOrder> active_orders;
  std::uint64_t next_client_id = config_.first_client_order_id;
  std::uint64_t next_decision_id = config_.first_decision_id;
  std::uint64_t action_sequence = 0U;
  std::uint64_t trade_sequence = 0U;
  std::uint64_t global_step = 0U;
  std::int64_t fundamental_ticks = config_.initial_reference_price.value();
  std::int64_t impact_microticks = 0;
  ExcitationState excitation;

  const auto initial_time = config_.start_time;
  const auto& initial_regime = config_.regimes.front();
  for (const auto side : {model::Side::Buy, model::Side::Sell}) {
    for (std::uint32_t level = 0U; level < initial_regime.visible_levels_per_side; ++level) {
      const auto price = passive_price(
          engine,
          side,
          fundamental_ticks,
          initial_regime.half_spread_ticks,
          level
      );
      const auto command = make_limit_order(
          next_client_id++,
          next_decision_id++,
          side,
          initial_regime.target_lots_per_level,
          price,
          initial_time
      );
      const auto result = engine.submit(command);
      if (!result.accepted() || !result.final_order.has_value()) {
        throw std::logic_error("initial synthetic liquidity was rejected");
      }
      active_orders.push_back(ActiveOrder{
          command.client_order_id,
          result.final_order->exchange_order_id,
          side,
      });
      add_action(
          tape,
          action_sequence,
          0U,
          initial_time,
          initial_regime.regime_id,
          SyntheticActionKind::InitialLiquidity,
          side,
          command.quantity,
          command.limit_price,
          command.client_order_id,
          result.final_order->exchange_order_id,
          std::nullopt,
          "accepted"
      );
      ++tape.summary.limit_submissions;
    }
  }
  ensure_invariants(engine);

  for (const auto& regime : config_.regimes) {
    excitation = ExcitationState{};
    for (std::uint64_t local_step = 0U; local_step < regime.steps; ++local_step) {
      const auto time = step_time(config_, global_step);
      const auto runtime = runtime_parameters(regime, config_.shocks, global_step);

      for (const auto& shock : config_.shocks) {
        if (shock.start_step == global_step) {
          fundamental_ticks = safe_add_price(
              fundamental_ticks,
              shock.one_time_reference_jump_ticks
          );
          add_action(
              tape,
              action_sequence,
              global_step,
              time,
              regime.regime_id,
              SyntheticActionKind::ShockApplied,
              std::nullopt,
              model::QuantityLots{},
              model::PriceTicks{fundamental_ticks},
              std::nullopt,
              std::nullopt,
              shock.shock_id,
              "shock_start"
          );
          ++tape.summary.shocks_applied;
        }
      }

      impact_microticks = static_cast<std::int64_t>(
          impact_microticks * static_cast<std::int64_t>(regime.impact_decay_ppm) /
          static_cast<std::int64_t>(kProbabilityScalePpm)
      );
      decay_excitation(excitation, regime);

      const auto reference_probability = scaled_probability(
          regime.reference_move_probability_ppm,
          runtime.volatility_multiplier_ppm
      );
      if (occurs(random, kStreamReferenceOccurrence, global_step, reference_probability)) {
        const auto direction = draw_side(
            random,
            kStreamReferenceSide,
            global_step,
            runtime.buy_probability_ppm
        );
        const auto jump = 1U + random.bounded_u32(
                                   {kStreamReferenceJump, global_step},
                                   regime.maximum_reference_jump_ticks
                               );
        const auto signed_jump = direction == model::Side::Buy
                                     ? static_cast<std::int64_t>(jump)
                                     : -static_cast<std::int64_t>(jump);
        fundamental_ticks = safe_add_price(fundamental_ticks, signed_jump);
        add_action(
            tape,
            action_sequence,
            global_step,
            time,
            regime.regime_id,
            SyntheticActionKind::ReferenceMove,
            direction,
            model::QuantityLots{},
            model::PriceTicks{fundamental_ticks},
            std::nullopt,
            std::nullopt,
            std::nullopt,
            "exogenous_discrete_reference_move"
        );
        ++tape.summary.reference_moves;
      }

      clean_active_orders(active_orders, engine);
      const auto book_before = engine.book(regime.visible_levels_per_side);
      const auto limit_probability = scaled_probability(
          regime.limit_add_probability_ppm,
          runtime.liquidity_multiplier_ppm,
          std::min<std::uint32_t>(
              kProbabilityScalePpm,
              excitation.limit_ppm + resilience_boost(regime, runtime, book_before)
          )
      );
      if (occurs(random, kStreamLimitOccurrence, global_step, limit_probability)) {
        const auto side = draw_side(
            random,
            kStreamLimitSide,
            global_step,
            runtime.buy_probability_ppm
        );
        const auto level = random.bounded_u32(
            {kStreamLimitLevel, global_step},
            regime.visible_levels_per_side
        );
        const auto quantity = draw_quantity(
            random,
            kStreamLimitQuantity,
            global_step,
            regime.minimum_order_lots,
            regime.maximum_order_lots
        );
        const auto reference = effective_reference(fundamental_ticks, impact_microticks);
        const auto price = passive_price(
            engine,
            side,
            reference,
            half_spread(regime, runtime),
            level
        );
        const auto command = make_limit_order(
            next_client_id++,
            next_decision_id++,
            side,
            quantity,
            price,
            time
        );
        const auto result = engine.submit(command);
        ++tape.summary.limit_submissions;
        if (result.accepted() && result.final_order.has_value() &&
            !model::is_terminal(result.final_order->state)) {
          active_orders.push_back(ActiveOrder{
              command.client_order_id,
              result.final_order->exchange_order_id,
              side,
          });
          add_action(
              tape,
              action_sequence,
              global_step,
              time,
              regime.regime_id,
              SyntheticActionKind::LimitAdd,
              side,
              command.quantity,
              command.limit_price,
              command.client_order_id,
              result.final_order->exchange_order_id,
              std::nullopt,
              "accepted"
          );
        } else {
          ++tape.summary.rejected_commands;
          add_action(
              tape,
              action_sequence,
              global_step,
              time,
              regime.regime_id,
              SyntheticActionKind::LimitAdd,
              side,
              command.quantity,
              command.limit_price,
              command.client_order_id,
              std::nullopt,
              std::nullopt,
              "rejected"
          );
        }
        add_matches(
            tape,
            result.matches,
            global_step,
            time,
            regime.regime_id,
            config_.fees,
            trade_sequence,
            impact_microticks,
            regime
        );
        excite(excitation.limit_ppm, regime);
      }

      const auto market_probability = scaled_probability(
          regime.market_order_probability_ppm,
          runtime.market_multiplier_ppm,
          excitation.market_ppm
      );
      if (occurs(random, kStreamMarketOccurrence, global_step, market_probability)) {
        const auto side = draw_side(
            random,
            kStreamMarketSide,
            global_step,
            runtime.buy_probability_ppm
        );
        const auto quantity = draw_quantity(
            random,
            kStreamMarketQuantity,
            global_step,
            regime.minimum_order_lots,
            regime.maximum_order_lots
        );
        const auto command = make_market_order(
            next_client_id++,
            next_decision_id++,
            side,
            quantity,
            time
        );
        const auto result = engine.submit(command);
        ++tape.summary.market_submissions;
        if (!result.accepted()) {
          ++tape.summary.rejected_commands;
        }
        add_action(
            tape,
            action_sequence,
            global_step,
            time,
            regime.regime_id,
            SyntheticActionKind::AggressiveMarket,
            side,
            command.quantity,
            std::nullopt,
            command.client_order_id,
            result.final_order.has_value()
                ? std::optional<model::ExchangeOrderId>{result.final_order->exchange_order_id}
                : std::nullopt,
            std::nullopt,
            result.accepted() ? "accepted_ioc" : "rejected"
        );
        add_matches(
            tape,
            result.matches,
            global_step,
            time,
            regime.regime_id,
            config_.fees,
            trade_sequence,
            impact_microticks,
            regime
        );
        excite(excitation.market_ppm, regime);
      }

      clean_active_orders(active_orders, engine);
      const auto cancel_probability = scaled_probability(
          regime.cancel_probability_ppm,
          runtime.cancel_multiplier_ppm,
          excitation.cancel_ppm
      );
      if (!active_orders.empty() &&
          occurs(random, kStreamCancelOccurrence, global_step, cancel_probability)) {
        const auto selected = random.bounded_u32(
            {kStreamCancelSelection, global_step},
            static_cast<std::uint32_t>(active_orders.size())
        );
        const auto active = active_orders.at(selected);
        const model::CancelRequest command{
            active.client_order_id,
            active.exchange_order_id,
            model::DecisionId{next_decision_id++},
            time,
            time,
            time,
        };
        const auto result = engine.cancel(command);
        if (result.accepted()) {
          active_orders.erase(active_orders.begin() + selected);
          ++tape.summary.cancellations;
        } else {
          ++tape.summary.rejected_commands;
        }
        add_action(
            tape,
            action_sequence,
            global_step,
            time,
            regime.regime_id,
            SyntheticActionKind::Cancel,
            active.side,
            result.acknowledgement.has_value()
                ? result.acknowledgement->cancelled_quantity
                : model::QuantityLots{},
            std::nullopt,
            active.client_order_id,
            active.exchange_order_id,
            std::nullopt,
            result.accepted() ? "accepted" : "rejected"
        );
        excite(excitation.cancel_ppm, regime);
      }

      clean_active_orders(active_orders, engine);
      ensure_invariants(engine);
      const auto visible_book = engine.book(regime.visible_levels_per_side);
      tape.steps.push_back(SyntheticStepSummary{
          global_step,
          time,
          regime.regime_id,
          model::PriceTicks{effective_reference(fundamental_ticks, impact_microticks)},
          engine.best_bid(),
          engine.best_ask(),
          model::QuantityLots{book_side_quantity(visible_book, model::Side::Buy)},
          model::QuantityLots{book_side_quantity(visible_book, model::Side::Sell)},
          static_cast<std::uint64_t>(engine.active_order_count()),
          impact_microticks,
          excitation.limit_ppm,
          excitation.market_ppm,
          excitation.cancel_ppm,
      });
      ++global_step;
    }
  }

  tape.summary.total_steps = global_step;
  tape.summary.final_reference_price = model::PriceTicks{
      effective_reference(fundamental_ticks, impact_microticks)
  };
  tape.summary.final_best_bid = engine.best_bid();
  tape.summary.final_best_ask = engine.best_ask();
  tape.config_sha256 = util::sha256_hex(canonical_config(config_));
  tape.canonical_text = canonical_tape(tape);
  tape.tape_sha256 = util::sha256_hex(tape.canonical_text);
  tape.manifest_json = manifest_json(tape);
  tape.manifest_sha256 = util::sha256_hex(tape.manifest_json);
  return tape;
}

}  // namespace robust_execution::synthetic
