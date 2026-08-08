#include "robust_execution/metrics/metrics.hpp"
#include "robust_execution/strategies/adaptive.hpp"
#include "robust_execution/util/sha256.hpp"

#include <algorithm>
#include <array>
#include <cstdlib>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

using namespace robust_execution;

namespace {
model::TimestampNs t(std::int64_t value) {
  return {model::ClockDomain::Simulation, value};
}

model::InstrumentDefinition instrument() {
  return {
      model::kEventSchemaVersion,
      model::VenueId{"synthetic"},
      model::InstrumentId{"MLMPC-USD"},
      "MLMPC",
      "USD",
      model::RationalIncrement{1U, 1U},
      model::RationalIncrement{1U, 1U},
      model::RationalIncrement{1U, 1U},
      model::QuantityLots{1U},
      model::QuantityLots{1'000'000U},
      "step24-v1",
  };
}

policy::ParentOrderDefinition parent() {
  return {
      model::ParentOrderId{24U},
      model::Side::Buy,
      model::QuantityLots{100U},
      t(1'000),
      t(2'000),
      model::PriceTicks{100},
      "hard-completion-v1",
  };
}

policy::PolicyEnvironment environment(const std::string& strategy_id) {
  return {
      instrument(),
      model::StrategyId{strategy_id},
      model::FeeScheduleId{"synthetic-zero-fees"},
      model::LatencyModelId{"zero-latency"},
      250,
      5U,
      16U,
      1U,
      1U,
      {{1U, 4U}, {1U, 2U}, {1U, 1U}},
      {model::TickOffset{0}},
      policy::LotRoundingPolicy::Floor,
      true,
      true,
      true,
  };
}

strategies::NonMlCalibration calibration() {
  return {
      t(999),
      "step20-synthetic-calibration-v1",
      0.0L,
      0.0L,
      0.50L,
      0.45L,
      0.35L,
      1.0L,
      25.0L,
  };
}

strategies::MpcParameters base_parameters() {
  return {
      calibration(),
      4U,
      {{1U, 4U}, {1U, 2U}, {1U, 1U}},
      model::TickOffset{0},
      {1U, 2U},
      1.0L,
      200.0L,
      10.0L,
      "step20-non-ml-mpc-v1",
  };
}

struct MarketStep {
  std::int64_t time;
  std::int64_t bid;
  std::int64_t ask;
  std::uint64_t bid_quantity;
  std::uint64_t ask_quantity;
  bool favorable_passive_flow;
};

constexpr std::array<MarketStep, 4U> kPath{{
    {1'000, 98, 102, 20U, 200U, true},
    {1'250, 99, 101, 50U, 120U, true},
    {1'500, 99, 101, 220U, 20U, false},
    {1'750, 100, 102, 500U, 10U, false},
}};

policy::PolicyObservation make_observation(
    const policy::PolicyEnvironment& env,
    const MarketStep& step,
    std::uint64_t filled,
    std::uint64_t decision_id
) {
  policy::ParentOrderSnapshot snap{
      model::ParentOrderId{24U},
      model::Side::Buy,
      t(1'000),
      t(2'000),
      model::PriceTicks{100},
      "hard-completion-v1",
      model::QuantityLots{100U},
      model::QuantityLots{filled},
      model::QuantityLots{100U - filled},
      model::QuoteAtoms{0},
      model::QuoteAtoms{0},
      model::QuoteAtoms{0},
      decision_id - 1U,
      policy::ParentOrderStatus::Active,
      false,
  };
  const auto first = step.favorable_passive_flow ? model::AggressorSide::Sell
                                                 : model::AggressorSide::Buy;
  const auto second = step.favorable_passive_flow ? model::AggressorSide::Buy
                                                  : model::AggressorSide::Sell;
  std::vector<policy::ObservedTrade> trades{
      {
          model::Trade{
              model::TradeId{decision_id * 2U - 1U},
              std::nullopt,
              model::PriceTicks{100},
              model::QuantityLots{80U},
              first,
          },
          t(step.time - 3),
          t(step.time - 2),
      },
      {
          model::Trade{
              model::TradeId{decision_id * 2U},
              std::nullopt,
              model::PriceTicks{100},
              model::QuantityLots{20U},
              second,
          },
          t(step.time - 3),
          t(step.time - 2),
      },
  };
  return {
      model::DecisionId{decision_id},
      t(step.time),
      t(step.time - 1),
      env,
      snap,
      {{model::PriceTicks{step.bid}, model::QuantityLots{step.bid_quantity}, std::nullopt}},
      {{model::PriceTicks{step.ask}, model::QuantityLots{step.ask_quantity}, std::nullopt}},
      std::move(trades),
      {},
      0U,
      {},
  };
}

std::uint64_t action_quantity(std::uint64_t remaining, policy::QuantityFraction fraction) {
  if (!fraction.valid()) throw std::runtime_error("invalid validation fraction");
  const auto product = remaining * fraction.numerator;
  auto result = product / fraction.denominator;
  if (result == 0U) result = remaining;
  return std::min(result, remaining);
}

struct EpisodeResult {
  metrics::EpisodeMetrics metrics;
  std::vector<std::string> actions;
  std::vector<std::string> diagnostics;
};

EpisodeResult run_policy(policy::ExecutionPolicy& strategy, const policy::PolicyEnvironment& env) {
  const auto p = parent();
  strategy.reset(p, env);
  metrics::EpisodeMetricInput input;
  input.episode_id = env.strategy_id.value();
  input.instrument = instrument();
  input.parent = p;
  std::uint64_t filled = 0U;
  std::uint64_t execution_id = 1U;
  EpisodeResult result;

  for (std::size_t i = 0U; i < kPath.size(); ++i) {
    if (filled >= 100U) break;
    const auto obs = make_observation(env, kPath[i], filled, i + 1U);
    const auto action = strategy.on_observation(obs);
    if (const auto* submit = std::get_if<policy::SubmitChildAction>(&action.payload)) {
      const auto quantity = action_quantity(100U - filled, submit->quantity_fraction);
      const bool passive = submit->order_type == model::OrderType::Limit;
      const auto price = model::PriceTicks{passive ? kPath[i].bid : kPath[i].ask};
      input.fills.push_back({
          model::ExecutionId{execution_id++},
          model::Side::Buy,
          price,
          model::QuantityLots{quantity},
          t(kPath[i].time + 1),
          passive ? model::LiquidityRole::Maker : model::LiquidityRole::Taker,
          model::QuoteAtoms{0},
          metrics::FillSource::Continuous,
      });
      filled += quantity;
      std::ostringstream text;
      text << (passive ? "passive" : "aggressive") << ':' << quantity << '@' << price.value();
      result.actions.push_back(text.str());
    } else if (std::holds_alternative<policy::NoAction>(action.payload)) {
      result.actions.push_back("no_action");
    } else if (std::holds_alternative<policy::CancelChildAction>(action.payload)) {
      result.actions.push_back("cancel");
    } else {
      result.actions.push_back("replace");
    }
    if (const auto* non_ml = dynamic_cast<strategies::NonMlMpcPolicy*>(&strategy);
        non_ml != nullptr && non_ml->last_decision().has_value()) {
      result.diagnostics.push_back(non_ml->last_decision()->canonical);
    }
    if (const auto* ml = dynamic_cast<strategies::MlMpcPolicy*>(&strategy);
        ml != nullptr && ml->last_decision().has_value()) {
      result.diagnostics.push_back(ml->last_decision()->canonical);
    }
  }
  if (filled < 100U) {
    const auto residual = 100U - filled;
    input.fills.push_back({
        model::ExecutionId{execution_id},
        model::Side::Buy,
        model::PriceTicks{103},
        model::QuantityLots{residual},
        t(2'000),
        model::LiquidityRole::Taker,
        model::QuoteAtoms{0},
        metrics::FillSource::TerminalCompletion,
    });
    result.actions.push_back("terminal_aggressive:" + std::to_string(residual) + "@103");
  }
  input.actions.decisions = static_cast<std::uint64_t>(kPath.size());
  input.actions.submits = static_cast<std::uint64_t>(std::count_if(
      result.actions.begin(),
      result.actions.end(),
      [](const auto& action) {
        return action.rfind("passive:", 0U) == 0U || action.rfind("aggressive:", 0U) == 0U ||
               action.rfind("terminal_aggressive:", 0U) == 0U;
      }
  ));
  const auto calculated = metrics::calculate_episode_metrics(input);
  if (!calculated.ok()) throw std::runtime_error("Step 24 validation metric calculation failed");
  const auto audit = metrics::audit_episode_metrics(input, *calculated.metrics);
  if (!audit.passed) throw std::runtime_error("Step 24 validation metric audit failed");
  result.metrics = *calculated.metrics;
  return result;
}

struct HorizonInput {
  std::string_view id;
  long double base_rate;
  std::array<long double, 4U> calibrated;
  std::array<long double, 4U> uncalibrated;
  std::array<int, 4U> target;
  std::string_view prediction_table_sha256;
};

constexpr std::array<HorizonInput, 3U> kHorizons{{
    {
        "250ms",
        0.04500000178813934L,
        {0.08946829999605581L, 0.09336262915729195L, 0.07137070495213149L,
         0.06368392176880149L},
        {0.030320787941102722L, 0.029579627092756067L, 0.03450713374629614L,
         0.036791917305182255L},
        {0, 0, 0, 0},
        "8541a32f8c589635c4d4b5ab066174307d4369faacb0ef531103d86510fe27c7",
    },
    {
        "1s",
        0.17800000309944153L,
        {0.1591999276882306L, 0.17337923911550715L, 0.15788005436913027L,
         0.15935314099002926L},
        {0.14132887440840364L, 0.17487535722168732L, 0.13838818751274923L,
         0.14167229891902702L},
        {0, 1, 0, 1},
        "e50c24fb3946fdaae1a9941670f0a966c2b5716b385f1db63d76fe7f1ea97771",
    },
    {
        "5s",
        0.5889999866485596L,
        {0.662004022445509L, 0.5591634730828186L, 0.3796129130022456L,
         0.6410927914907948L},
        {0.7158858000455388L, 0.5157194730863379L, 0.20067020448779327L,
         0.6773284197768593L},
        {0, 1, 1, 1},
        "36731d3b39e4c31750579ff77ac20cdc2ff81e13bf3fb6b09bf2e5a1feb06a25",
    },
}};

std::vector<strategies::MpcPredictionInput> make_tape(
    const HorizonInput& horizon,
    strategies::MpcPredictionKind kind
) {
  std::vector<strategies::MpcPredictionInput> tape;
  tape.reserve(kPath.size());
  for (std::size_t i = 0U; i < kPath.size(); ++i) {
    long double probability = horizon.calibrated[i];
    std::optional<model::DecisionId> source_id;
    auto effective_kind = kind;
    if (kind == strategies::MpcPredictionKind::TrainingBaseRate) {
      probability = horizon.base_rate;
    } else if (kind == strategies::MpcPredictionKind::UncalibratedModel) {
      probability = horizon.uncalibrated[i];
    } else if (kind == strategies::MpcPredictionKind::PerfectEventOracle) {
      probability = horizon.target[i] == 0 ? 0.0L : 1.0L;
    } else if (kind == strategies::MpcPredictionKind::ShuffledWithinDayInstrument) {
      probability = horizon.calibrated[(i + 1U) % kPath.size()];
    } else if (kind == strategies::MpcPredictionKind::Stale) {
      if (i == 0U) {
        probability = horizon.base_rate;
        effective_kind = strategies::MpcPredictionKind::TrainingBaseRate;
      } else {
        probability = horizon.calibrated[i - 1U];
        source_id = model::DecisionId{static_cast<std::uint64_t>(i)};
      }
    }
    const auto decision_id = static_cast<std::uint64_t>(i + 1U);
    tape.push_back({
        model::DecisionId{decision_id},
        t(kPath[i].time),
        t(kPath[i].time - 1),
        t(kPath[i].time - 1),
        probability,
        horizon.base_rate,
        std::string(horizon.id),
        "causal_conv1d_lstm",
        "step23-engineering-holdout:first-four:" + std::string(horizon.id),
        effective_kind,
        source_id,
    });
  }
  return tape;
}

strategies::MlMpcParameters ml_parameters(long double weight) {
  return {
      base_parameters(),
      weight,
      "step24-precomputed-prediction-v1",
      "step24-ml-mpc-v1",
  };
}

std::string decimal(long double value) {
  std::ostringstream out;
  out << std::fixed << std::setprecision(12) << value;
  return out.str();
}

long double validation_prediction_weight_bps() {
  const auto* raw = std::getenv("RE_ML_MPC_WEIGHT_BPS");
  if (raw == nullptr || std::string_view{raw}.empty()) return 1'000.0L;
  std::size_t consumed = 0U;
  const auto text = std::string{raw};
  const auto value = std::stold(text, &consumed);
  if (consumed != text.size() || !std::isfinite(static_cast<double>(value)) || value < 0.0L) {
    throw std::invalid_argument("RE_ML_MPC_WEIGHT_BPS must be a finite non-negative number");
  }
  return value;
}

std::string compact_weight(long double value) {
  std::ostringstream out;
  out << std::fixed << std::setprecision(1) << value;
  return out.str();
}

void emit_string_array(std::ostringstream& out, const std::vector<std::string>& values) {
  out << '[';
  for (std::size_t i = 0U; i < values.size(); ++i) {
    if (i != 0U) out << ',';
    out << '"' << values[i] << '"';
  }
  out << ']';
}

void emit_episode(std::ostringstream& out, const EpisodeResult& result) {
  out << "{\"actions\":";
  emit_string_array(out, result.actions);
  out << ",\"diagnostics\":";
  emit_string_array(out, result.diagnostics);
  out << ",\"implementation_shortfall_bps\":"
      << *result.metrics.implementation_shortfall_bps;
  out << ",\"complete\":" << (result.metrics.complete ? "true" : "false") << '}';
}

EpisodeResult run_ml(
    const HorizonInput& horizon,
    strategies::MpcPredictionKind kind,
    long double weight,
    std::string_view suffix
) {
  const auto strategy_id = "ml-mpc-" + std::string(horizon.id) + "-" + std::string(suffix);
  auto tape = make_tape(horizon, kind);
  strategies::MlMpcPolicy policy{
      model::StrategyId{strategy_id},
      ml_parameters(weight),
      std::move(tape),
  };
  return run_policy(policy, environment(strategy_id));
}
}  // namespace

int main() {
  const auto prediction_weight_bps = validation_prediction_weight_bps();
  strategies::NonMlMpcPolicy non_ml{model::StrategyId{"non-ml-mpc"}, base_parameters()};
  const auto non_ml_result = run_policy(non_ml, environment("non-ml-mpc"));

  std::ostringstream body;
  body << '{';
  body << "\"evidence_status\":\"synthetic_validation_only_non_research\",";
  body << "\"gate_c_historical_activation\":false,";
  body << "\"final_horizon_selected\":false,";
  body << "\"final_model_family_selected\":false,";
  body << "\"locked_research_test_opened\":false,";
  body << "\"shared_solver\":true,";
  body << "\"same_action_space_constraints_terminal_rules\":true,";
  body << "\"prediction_term\":\"passive_risk_bps=weight*(probability-training_base_rate)\",";
  body << "\"prediction_weight_bps\":" << compact_weight(prediction_weight_bps) << ',';
  body << "\"prediction_weight_status\":\"synthetic_engineering_fixture_not_research_tuned\",";
  body << "\"source_endpoint_row_ids\":[\"BTCUSDT:080:bid:07\",\"BTCUSDT:080:bid:08\","
          "\"BTCUSDT:080:bid:09\",\"BTCUSDT:080:bid:10\"],";
  body << "\"non_ml_mpc\":";
  emit_episode(body, non_ml_result);
  body << ",\"horizons\":{";

  for (std::size_t h = 0U; h < kHorizons.size(); ++h) {
    if (h != 0U) body << ',';
    const auto& horizon = kHorizons[h];
    const auto calibrated = run_ml(
        horizon,
        strategies::MpcPredictionKind::CalibratedModel,
        prediction_weight_bps,
        "calibrated"
    );
    const auto base_rate = run_ml(
        horizon,
        strategies::MpcPredictionKind::TrainingBaseRate,
        prediction_weight_bps,
        "base-rate"
    );
    const auto shuffled = run_ml(
        horizon,
        strategies::MpcPredictionKind::ShuffledWithinDayInstrument,
        prediction_weight_bps,
        "shuffled"
    );
    const auto stale = run_ml(
        horizon,
        strategies::MpcPredictionKind::Stale,
        prediction_weight_bps,
        "stale"
    );
    const auto uncalibrated = run_ml(
        horizon,
        strategies::MpcPredictionKind::UncalibratedModel,
        prediction_weight_bps,
        "uncalibrated"
    );
    const auto oracle = run_ml(
        horizon,
        strategies::MpcPredictionKind::PerfectEventOracle,
        prediction_weight_bps,
        "oracle"
    );
    const auto zero_weight = run_ml(
        horizon,
        strategies::MpcPredictionKind::CalibratedModel,
        0.0L,
        "zero-weight"
    );

    body << '"' << horizon.id << "\":{";
    body << "\"prediction_table_sha256\":\"" << horizon.prediction_table_sha256 << "\",";
    body << "\"training_base_rate\":" << decimal(horizon.base_rate) << ',';
    body << "\"calibrated\":";
    emit_episode(body, calibrated);
    body << ",\"training_base_rate_ablation\":";
    emit_episode(body, base_rate);
    body << ",\"shuffled_within_day_instrument_ablation\":";
    emit_episode(body, shuffled);
    body << ",\"stale_ablation\":";
    emit_episode(body, stale);
    body << ",\"uncalibrated_ablation\":";
    emit_episode(body, uncalibrated);
    body << ",\"perfect_event_oracle_ablation\":";
    emit_episode(body, oracle);
    body << ",\"prediction_weight_zero_ablation\":";
    emit_episode(body, zero_weight);
    body << '}';
  }
  body << "}}";
  const auto canonical = body.str();
  std::cout << "{\"payload\":" << canonical << ",\"sha256\":\""
            << util::sha256_hex(canonical) << "\"}\n";
}
