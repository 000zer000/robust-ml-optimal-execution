#include "internal.hpp"

#include "robust_execution/exchange/exchange.hpp"
#include "robust_execution/simulation/simulation.hpp"
#include "robust_execution/util/sha256.hpp"

#include <optional>
#include <string>
#include <vector>

namespace robust_execution::validation::detail {
namespace exchange = robust_execution::exchange;
namespace model = robust_execution::model;
namespace simulation = robust_execution::simulation;
namespace synthetic = robust_execution::synthetic;

namespace {
model::InstrumentDefinition instrument() {
  return base_config(1U).instrument;
}

model::TimestampNs time(std::int64_t value) {
  return model::TimestampNs{model::ClockDomain::Simulation, value};
}

model::OrderSubmit limit(
    std::uint64_t client,
    model::Side side,
    std::uint64_t quantity,
    std::int64_t price
) {
  return model::OrderSubmit{
      model::ParentOrderId{1U}, model::ClientOrderId{client}, model::DecisionId{client}, side,
      model::OrderType::Limit, model::TimeInForce::GoodTilCancelled,
      model::QuantityLots{quantity}, model::PriceTicks{price}, false,
      time(0), time(0), time(0),
  };
}

model::OrderSubmit market(std::uint64_t client, model::Side side, std::uint64_t quantity) {
  return model::OrderSubmit{
      model::ParentOrderId{1U}, model::ClientOrderId{client}, model::DecisionId{client}, side,
      model::OrderType::Market, model::TimeInForce::ImmediateOrCancel,
      model::QuantityLots{quantity}, std::nullopt, false,
      time(0), time(0), time(0),
  };
}

ValidationCheck hand_matching_check() {
  exchange::MatchingEngine engine{exchange::MatchingEngineConfig{instrument()}};
  const auto first = engine.submit(limit(1U, model::Side::Sell, 3U, 101));
  const auto second = engine.submit(limit(2U, model::Side::Sell, 4U, 101));
  const auto third = engine.submit(limit(3U, model::Side::Sell, 5U, 102));
  const auto aggressive = engine.submit(market(10U, model::Side::Buy, 8U));
  const bool passed = first.accepted() && second.accepted() && third.accepted() &&
                      aggressive.accepted() && aggressive.matches.size() == 3U &&
                      aggressive.matches[0].maker_fill.client_order_id == model::ClientOrderId{1U} &&
                      aggressive.matches[0].trade.quantity == model::QuantityLots{3U} &&
                      aggressive.matches[1].maker_fill.client_order_id == model::ClientOrderId{2U} &&
                      aggressive.matches[1].trade.quantity == model::QuantityLots{4U} &&
                      aggressive.matches[2].maker_fill.client_order_id == model::ClientOrderId{3U} &&
                      aggressive.matches[2].trade.quantity == model::QuantityLots{1U} &&
                      engine.quantity_at(model::Side::Sell, model::PriceTicks{102}) ==
                          model::QuantityLots{4U} && engine.validate_invariants().empty();
  return ValidationCheck{
      "HAND-MATCH-001", "hand_oracle",
      "Three-level FIFO and partial-fill tape matches a manually calculated oracle.", passed,
      "Expected fills: 3@101 from order 1, 4@101 from order 2, 1@102 from order 3; 4 lots remain at 102.",
      "Visible-book, price-time-priority mechanics only; hidden liquidity is outside this mode.",
  };
}

ValidationCheck latency_check() {
  simulation::LatencyModelConfig config;
  config.model_id = "step10-fixed-latency";
  config.market_data_network = {11, 11, 1U};
  config.observation_processing = {13, 13, 2U};
  config.decision_processing = {17, 17, 3U};
  config.outbound_network = {19, 19, 4U};
  config.exchange_processing = {23, 23, 5U};
  config.acknowledgement_network = {29, 29, 6U};
  config.acknowledgement_processing = {31, 31, 7U};
  const simulation::LatencyModel model{7U, config};
  const auto observation = model.observation_timing(time(100), 1U);
  const auto action = model.action_timing(time(200), 2U);
  const bool passed = observation.receive_time.value() == 111 &&
                      observation.available_time.value() == 124 &&
                      action.decision_end.value() == 217 &&
                      action.exchange_receive.value() == 236 &&
                      action.exchange_process.value() == 259 &&
                      action.acknowledgement_receive.value() == 288 &&
                      action.acknowledgement_available.value() == 319;
  return ValidationCheck{
      "HAND-LATENCY-001", "hand_oracle",
      "Fixed seven-stage latency path equals manual nanosecond addition.", passed,
      "Observation: 100+11+13=124. Action: 200+17+19+23+29+31=319.",
      "This validates composition and causal timestamps, not empirical latency calibration.",
  };
}

ValidationCheck deterministic_check() {
  const auto first = synthetic::SyntheticMarketGenerator{base_config(42U)}.generate();
  const auto second = synthetic::SyntheticMarketGenerator{base_config(42U)}.generate();
  const auto third = synthetic::SyntheticMarketGenerator{base_config(43U)}.generate();
  const bool passed = first.canonical_text == second.canonical_text &&
                      first.tape_sha256 == second.tape_sha256 &&
                      first.manifest_json == second.manifest_json &&
                      first.tape_sha256 != third.tape_sha256;
  return ValidationCheck{
      "REPRO-001", "reproducibility",
      "Identical seed/config is byte deterministic and a changed seed changes the tape.", passed,
      "Repeated SHA-256 equality for seed 42 and inequality against seed 43.",
      "Determinism is conditional on the documented software/configuration contract.",
  };
}

ValidationCheck failure_injection_check() {
  auto invalid = base_config(99U);
  invalid.grid_step_ns = 0;
  const bool invalid_detected = synthetic::has_errors(synthetic::validate(invalid));
  auto tape = synthetic::SyntheticMarketGenerator{base_config(99U)}.generate();
  tape.actions.front().detail = "failure-injection-tamper";
  const bool tamper_detected = synthetic::has_errors(synthetic::validate_tape(tape));
  const bool passed = invalid_detected && tamper_detected;
  return ValidationCheck{
      "FAIL-INJECT-001", "failure_injection",
      "Invalid configuration and post-generation tape mutation are rejected.", passed,
      "Zero grid interval rejected; canonical action mutation invalidates tape verification.",
      "Failure injection is deterministic mutation testing, not exhaustive adversarial fuzzing.",
  };
}

ValidationCheck structured_mutation_check() {
  constexpr std::uint64_t kCases = 2'048U;
  auto mutation_config = base_config(777U);
  mutation_config.regimes.front().steps = 32U;
  mutation_config.regimes.front().limit_add_probability_ppm = 700'000U;
  mutation_config.regimes.front().market_order_probability_ppm = 700'000U;
  mutation_config.regimes.front().cancel_probability_ppm = 200'000U;
  const auto original = synthetic::SyntheticMarketGenerator{mutation_config}.generate();
  if (original.actions.empty() || original.trades.empty() || original.steps.empty()) {
    return ValidationCheck{
        "MUT-FUZZ-001", "structured_mutation",
        "Structured mutation campaign detects corrupted configuration and tape fields.", false,
        "Baseline tape lacked required mutation targets.",
        "Deterministic structure-aware mutation is not coverage-guided libFuzzer execution.",
    };
  }
  std::uint64_t detected = 0U;
  for (std::uint64_t index = 0U; index < kCases; ++index) {
    auto mutated = original;
    switch (index % 10U) {
      case 0U: mutated.actions.front().sequence += 1U; break;
      case 1U: mutated.actions.front().global_step += 1U; break;
      case 2U: mutated.summary.total_steps += 1U; break;
      case 3U: mutated.summary.trades += 1U; break;
      case 4U: mutated.config.random_seed += 1U; break;
      case 5U: mutated.tape_sha256[0] = mutated.tape_sha256[0] == '0' ? '1' : '0'; break;
      case 6U: mutated.config_sha256[0] = mutated.config_sha256[0] == '0' ? '1' : '0'; break;
      case 7U: mutated.manifest_json.push_back(' '); break;
      case 8U:
        mutated.trades.front().maker_fee = model::QuoteAtoms{
            mutated.trades.front().maker_fee.value() + 1
        };
        break;
      case 9U:
        mutated.steps.front().best_bid = model::PriceTicks{20'000};
        mutated.steps.front().best_ask = model::PriceTicks{10'000};
        break;
      default: break;
    }
    if (synthetic::has_errors(synthetic::validate_tape(mutated))) ++detected;
  }
  return ValidationCheck{
      "MUT-FUZZ-001", "structured_mutation",
      "Structured mutation campaign detects corrupted configuration, sequence, accounting, hash and book fields.",
      detected == kCases,
      std::to_string(detected) + "/" + std::to_string(kCases) + " deterministic mutations rejected.",
      "Deterministic structure-aware mutation is not coverage-guided libFuzzer execution.",
  };
}

ValidationCheck randomized_generator_check() {
  constexpr std::uint64_t kSeedCount = 64U;
  const auto aggregate = run_batch(base_config(10'000U), 10'000U, kSeedCount);
  const bool passed = aggregate.valid && aggregate.total_steps == 256U * kSeedCount &&
                      aggregate.mean_market_submissions > 0.0 &&
                      aggregate.mean_limit_submissions > 0.0 &&
                      aggregate.mean_trades > 0.0;
  return ValidationCheck{
      "PROP-GEN-001", "randomized_property",
      "Sixty-four generated seeds preserve tape accounting and non-crossed-book invariants.", passed,
      "16,384 generated grid steps; each tape passed independent validate_tape checks.",
      "Designed synthetic distributions are not evidence of historical goodness of fit.",
  };
}
}  // namespace

std::vector<ValidationCheck> run_hand_and_failure_checks() {
  return {
      hand_matching_check(),
      latency_check(),
      deterministic_check(),
      failure_injection_check(),
      randomized_generator_check(),
      structured_mutation_check(),
  };
}

}  // namespace robust_execution::validation::detail
