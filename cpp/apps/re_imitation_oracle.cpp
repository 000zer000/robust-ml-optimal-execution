#include "robust_execution/strategies/adaptive.hpp"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace robust_execution;

namespace {
model::TimestampNs t(std::int64_t value) {
  return {model::ClockDomain::Simulation, value};
}

model::InstrumentDefinition instrument() {
  return {model::kEventSchemaVersion,
          model::VenueId{"synthetic"},
          model::InstrumentId{"IMIT-USD"},
          "IMIT",
          "USD",
          model::RationalIncrement{1U, 1U},
          model::RationalIncrement{1U, 1U},
          model::RationalIncrement{1U, 1U},
          model::QuantityLots{1U},
          model::QuantityLots{1'000'000U},
          "step26-v1"};
}

policy::PolicyEnvironment environment() {
  return {instrument(),
          model::StrategyId{"step26-teacher-mpc"},
          model::FeeScheduleId{"synthetic-zero-fees"},
          model::LatencyModelId{"zero-latency"},
          250,
          5U,
          16U,
          1U,
          1U,
          {policy::QuantityFraction{1U, 4U},
           policy::QuantityFraction{1U, 2U},
           policy::QuantityFraction{1U, 1U}},
          {model::TickOffset{0}},
          policy::LotRoundingPolicy::Floor,
          true,
          true,
          true};
}

strategies::MpcParameters teacher_parameters() {
  strategies::NonMlCalibration calibration{
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
  return {calibration,
          4U,
          {{1U, 4U}, {1U, 2U}, {1U, 1U}},
          model::TickOffset{0},
          {1U, 2U},
          1.0L,
          200.0L,
          10.0L,
          "step20-non-ml-mpc-v1"};
}

struct Row {
  std::string episode_id;
  std::uint64_t step{};
  std::int64_t now{};
  std::int64_t start{};
  std::int64_t deadline{};
  std::int64_t arrival{};
  std::int64_t bid{};
  std::int64_t ask{};
  std::uint64_t bid_quantity{};
  std::uint64_t ask_quantity{};
  bool favorable_passive_flow{};
  std::uint64_t filled{};
  std::uint64_t total{};
  std::uint64_t decision_id{};
  long double prediction_probability{0.5L};
};

std::vector<std::string> split(const std::string& line) {
  std::vector<std::string> fields;
  std::string field;
  std::istringstream input(line);
  while (std::getline(input, field, ',')) {
    fields.push_back(field);
  }
  return fields;
}

Row parse_row(const std::string& line) {
  const auto fields = split(line);
  if (fields.size() != 15U) {
    throw std::runtime_error("Step 26 oracle row must contain 15 fields");
  }
  Row row;
  row.episode_id = fields[0];
  row.step = std::stoull(fields[1]);
  row.now = std::stoll(fields[2]);
  row.start = std::stoll(fields[3]);
  row.deadline = std::stoll(fields[4]);
  row.arrival = std::stoll(fields[5]);
  row.bid = std::stoll(fields[6]);
  row.ask = std::stoll(fields[7]);
  row.bid_quantity = std::stoull(fields[8]);
  row.ask_quantity = std::stoull(fields[9]);
  row.favorable_passive_flow = std::stoull(fields[10]) != 0U;
  row.filled = std::stoull(fields[11]);
  row.total = std::stoull(fields[12]);
  row.decision_id = std::stoull(fields[13]);
  row.prediction_probability = std::stold(fields[14]);
  if (row.total == 0U || row.filled > row.total || row.start >= row.deadline ||
      row.prediction_probability < 0.0L || row.prediction_probability > 1.0L) {
    throw std::runtime_error("invalid Step 26 oracle state");
  }
  return row;
}

policy::PolicyObservation observation(const Row& row) {
  const auto env = environment();
  policy::ParentOrderSnapshot snap{
      model::ParentOrderId{26U},
      model::Side::Buy,
      t(row.start),
      t(row.deadline),
      model::PriceTicks{row.arrival},
      "hard-completion-v1",
      model::QuantityLots{row.total},
      model::QuantityLots{row.filled},
      model::QuantityLots{row.total - row.filled},
      model::QuoteAtoms{0},
      model::QuoteAtoms{0},
      model::QuoteAtoms{0},
      row.decision_id > 0U ? row.decision_id - 1U : 0U,
      policy::ParentOrderStatus::Active,
      false,
  };
  const auto first = row.favorable_passive_flow ? model::AggressorSide::Sell
                                                 : model::AggressorSide::Buy;
  const auto second = row.favorable_passive_flow ? model::AggressorSide::Buy
                                                  : model::AggressorSide::Sell;
  std::vector<policy::ObservedTrade> trades{
      {model::Trade{model::TradeId{row.decision_id * 2U - 1U},
                    std::nullopt,
                    model::PriceTicks{row.arrival},
                    model::QuantityLots{80U},
                    first},
       t(row.now - 2),
       t(row.now - 1)},
      {model::Trade{model::TradeId{row.decision_id * 2U},
                    std::nullopt,
                    model::PriceTicks{row.arrival},
                    model::QuantityLots{20U},
                    second},
       t(row.now - 2),
       t(row.now - 1)},
  };
  return {model::DecisionId{row.decision_id},
          t(row.now),
          t(row.now),
          env,
          snap,
          {{model::PriceTicks{row.bid}, model::QuantityLots{row.bid_quantity}, std::nullopt}},
          {{model::PriceTicks{row.ask}, model::QuantityLots{row.ask_quantity}, std::nullopt}},
          std::move(trades),
          {},
          0U,
          {}};
}

std::string action_label(const strategies::MpcDecision& decision) {
  if (decision.mode == strategies::AdaptiveActionMode::NoAction) {
    return "no_action";
  }
  if (decision.mode == strategies::AdaptiveActionMode::Cancel) {
    return "cancel";
  }
  if (!decision.fraction.has_value()) {
    throw std::runtime_error("teacher action is missing a quantity fraction");
  }
  const auto fraction = *decision.fraction;
  const std::string prefix = decision.mode == strategies::AdaptiveActionMode::Passive
                                 ? "passive_"
                                 : "aggressive_";
  if (fraction.numerator == 1U && fraction.denominator == 4U) {
    return prefix + "25";
  }
  if (fraction.numerator == 1U && fraction.denominator == 2U) {
    return prefix + "50";
  }
  if (fraction.numerator == 1U && fraction.denominator == 1U) {
    return prefix + "100";
  }
  throw std::runtime_error("unexpected teacher quantity fraction");
}

void emit_header() {
  std::cout
      << "episode_id,step,decision_id,action_label,teacher_latency_ns,midpoint_ticks,"
         "spread_ticks,same_side_best_lots,opposite_side_best_lots,same_side_queue_share,"
         "passive_fill_pressure,passive_fill_probability,elapsed_fraction,filled_fraction,"
         "remaining_fraction,progress_lag,time_remaining_fraction,"
         "prediction_probability,objective_bps\n";
}

void emit_row(const Row& row) {
  const auto obs = observation(row);
  const auto params = teacher_parameters();
  strategies::MpcPredictionInput prediction{
      model::DecisionId{row.decision_id},
      t(row.now),
      t(row.now),
      t(row.now),
      row.prediction_probability,
      0.5L,
      "step26-engineering",
      "step26-synthetic-risk-input",
      "step26-causal-synthetic-risk-v1",
      strategies::MpcPredictionKind::CalibratedModel,
      std::nullopt,
  };
  strategies::MlMpcParameters ml_parameters{
      params,
      10'000.0L,
      "step26-engineering-prediction-contract-v1",
      "step26-imitation-teacher-ml-mpc-v1",
  };
  const auto begin = std::chrono::steady_clock::now();
  const auto decision = strategies::solve_ml_mpc(obs, ml_parameters, prediction);
  const auto end = std::chrono::steady_clock::now();
  const auto latency = std::chrono::duration_cast<std::chrono::nanoseconds>(end - begin).count();
  const auto& s = decision.signals;
  std::cout << std::setprecision(17) << row.episode_id << ',' << row.step << ','
            << row.decision_id << ',' << action_label(decision) << ',' << latency << ','
            << static_cast<double>(s.midpoint_ticks) << ','
            << static_cast<double>(s.spread_ticks) << ','
            << static_cast<double>(s.same_side_best_lots) << ','
            << static_cast<double>(s.opposite_side_best_lots) << ','
            << static_cast<double>(s.same_side_queue_share) << ','
            << static_cast<double>(s.passive_fill_pressure) << ','
            << static_cast<double>(s.passive_fill_probability) << ','
            << static_cast<double>(s.elapsed_fraction) << ','
            << static_cast<double>(s.filled_fraction) << ','
            << static_cast<double>(s.remaining_fraction) << ','
            << static_cast<double>(s.progress_lag) << ','
            << static_cast<double>(s.time_remaining_fraction) << ','
            << static_cast<double>(row.prediction_probability) << ','
            << static_cast<double>(decision.objective_bps) << '\n';
}
}  // namespace

int main(int argc, char** argv) {
  try {
    std::istream* input = &std::cin;
    std::ifstream file;
    if (argc == 2) {
      file.open(argv[1]);
      if (!file) {
        throw std::runtime_error("unable to open Step 26 oracle input");
      }
      input = &file;
    } else if (argc != 1) {
      throw std::runtime_error("usage: robust_execution_imitation_oracle [input.csv]");
    }
    std::string line;
    bool first = true;
    emit_header();
    while (std::getline(*input, line)) {
      if (line.empty()) {
        continue;
      }
      if (first && line.rfind("episode_id,", 0U) == 0U) {
        first = false;
        continue;
      }
      first = false;
      emit_row(parse_row(line));
    }
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "Step 26 imitation oracle error: " << error.what() << '\n';
    return 2;
  }
}
