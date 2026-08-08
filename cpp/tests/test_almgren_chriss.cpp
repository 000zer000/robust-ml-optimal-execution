#include "robust_execution/strategies/almgren_chriss.hpp"

#include <cmath>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <vector>

using namespace robust_execution;

namespace {
void require(bool condition, const char* message) { if (!condition) { std::cerr << message << '\n'; std::exit(1); } }
model::TimestampNs t(std::int64_t value) { return {model::ClockDomain::Simulation, value}; }
policy::ParentOrderDefinition parent(std::uint64_t quantity = 100U) {
  return {model::ParentOrderId{19U}, model::Side::Buy, model::QuantityLots{quantity}, t(1'000), t(2'000), model::PriceTicks{100}, "hard-completion-v1"};
}
strategies::AlmgrenChrissParameters params(long double lambda) {
  return {4U, lambda, 1.0L, 1.0L, 0.0L, 0.0L, 250.0L, strategies::ExecutionStyle::Aggressive, t(999), "ac-unit-parameters-v1"};
}
std::vector<std::uint64_t> quantities(const strategies::AlmgrenChrissSchedule& schedule) {
  std::vector<std::uint64_t> out;
  for (const auto& slice : schedule.slices) out.push_back(slice.quantity.value());
  return out;
}
}

int main() {
  const auto neutral = strategies::build_almgren_chriss_schedule(parent(), params(0.0L));
  require((quantities(neutral) == std::vector<std::uint64_t>{25U,25U,25U,25U}), "risk-neutral AC must collapse to TWAP");
  require(std::abs(neutral.diagnostics.kappa) < 1e-18L, "risk-neutral kappa must be zero");
  require(std::abs(neutral.diagnostics.expected_cost_model_units - 2500.0L) < 1e-12L, "risk-neutral expected cost oracle failed");
  require(std::abs(neutral.diagnostics.variance_model_units - 8750.0L) < 1e-12L, "risk-neutral variance oracle failed");

  const auto moderate = strategies::build_almgren_chriss_schedule(parent(), params(0.5L));
  require((quantities(moderate) == std::vector<std::uint64_t>{51U,26U,14U,9U}), "moderate-risk integer apportionment oracle failed");
  require(std::abs(moderate.diagnostics.kappa - std::log(2.0L)) < 1e-14L, "closed-form kappa=ln(2) oracle failed");
  require(std::abs(moderate.normalized_inventory_path[1] - 0.4941176470588235294L) < 1e-14L, "inventory recurrence oracle failed");
  require(std::abs(moderate.diagnostics.expected_cost_model_units - 3554.0L) < 1e-12L, "moderate expected cost oracle failed");
  require(std::abs(moderate.diagnostics.variance_model_units - 3011.0L) < 1e-12L, "moderate variance oracle failed");
  require(std::abs(moderate.diagnostics.objective_model_units - 5059.5L) < 1e-12L, "moderate objective oracle failed");
  const long double closed_form_kappa = std::log(2.0L);
  for (std::size_t j = 0U; j <= 4U; ++j) {
    const auto closed_form = j == 4U ? 0.0L : std::sinh(closed_form_kappa * static_cast<long double>(4U - j)) / std::sinh(4.0L * closed_form_kappa);
    require(std::abs(moderate.normalized_inventory_path[j] - closed_form) < 1e-14L, "tridiagonal solution must match closed-form hyperbolic trajectory");
  }
  const long double moderate_twap_objective = 2500.0L + 0.5L * 8750.0L;
  require(moderate.diagnostics.objective_model_units < moderate_twap_objective, "AC optimum must improve the AC objective relative to TWAP at the same lambda");

  const auto high = strategies::build_almgren_chriss_schedule(parent(), params(2.0L));
  require((quantities(high) == std::vector<std::uint64_t>{73U,20U,5U,2U}), "high-risk integer apportionment oracle failed");
  require(high.slices.front().quantity.value() > moderate.slices.front().quantity.value(), "higher risk aversion must front-load more");
  require(moderate.slices.front().quantity.value() > neutral.slices.front().quantity.value(), "positive risk aversion must front-load relative to TWAP");
  require(high.total_quantity().value() == 100U, "AC schedule must conserve parent quantity");

  const auto zero_sigma = strategies::build_almgren_chriss_schedule(parent(), {4U, 100.0L, 0.0L, 1.0L, 0.0L, 0.0L, 250.0L, strategies::ExecutionStyle::Aggressive, t(999), "zero-sigma"});
  require((quantities(zero_sigma) == std::vector<std::uint64_t>{25U,25U,25U,25U}), "zero volatility must remove variance penalty");

  const auto one_slice = strategies::build_almgren_chriss_schedule(parent(), {1U, 2.0L, 1.0L, 1.0L, 0.0L, 0.0L, 250.0L, strategies::ExecutionStyle::Aggressive, t(999), "one-slice"});
  require((quantities(one_slice) == std::vector<std::uint64_t>{100U}), "single interval must execute full quantity");

  const auto extreme = strategies::build_almgren_chriss_schedule(parent(), {64U, 1.0e12L, 1.0L, 1.0L, 0.0L, 0.0L, 1'000.0L, strategies::ExecutionStyle::Aggressive, t(999), "extreme-stability"});
  require(extreme.total_quantity().value() == 100U, "extreme-risk schedule must conserve quantity");
  require(std::isfinite(extreme.diagnostics.kappa), "extreme-risk kappa must remain finite");
  require(extreme.slices.front().quantity.value() >= 99U, "extreme risk should approach immediate execution without hyperbolic overflow");

  const auto gamma_case = strategies::build_almgren_chriss_schedule(parent(), {4U, 0.5L, 1.0L, 1.0L, 0.2L, 0.0L, 250.0L, strategies::ExecutionStyle::Aggressive, t(999), "gamma-case"});
  require(std::abs(gamma_case.diagnostics.eta_tilde - 0.9L) < 1e-15L, "eta_tilde calculation failed");

  bool rejected_bad_eta = false;
  try {
    (void)strategies::build_almgren_chriss_schedule(parent(), {4U, 0.5L, 1.0L, 1.0L, 2.0L, 0.0L, 250.0L, strategies::ExecutionStyle::Aggressive, t(999), "invalid-eta-tilde"});
  } catch (const std::invalid_argument&) { rejected_bad_eta = true; }
  require(rejected_bad_eta, "eta_tilde <= 0 must be rejected");

  bool rejected_nan = false;
  try {
    auto invalid = params(0.5L);
    invalid.volatility_sigma = std::numeric_limits<long double>::quiet_NaN();
    (void)strategies::build_almgren_chriss_schedule(parent(), invalid);
  } catch (const std::invalid_argument&) { rejected_nan = true; }
  require(rejected_nan, "non-finite parameter must be rejected");
  bool rejected_leaked_calibration = false;
  try {
    auto leaked = params(0.5L);
    leaked.calibration_cutoff = t(1'000);
    (void)strategies::build_almgren_chriss_schedule(parent(), leaked);
  } catch (const std::invalid_argument&) { rejected_leaked_calibration = true; }
  require(rejected_leaked_calibration, "AC calibration cutoff must be strictly before episode start");

  {
    auto inst = model::InstrumentDefinition{model::kEventSchemaVersion, model::VenueId{"synthetic"}, model::InstrumentId{"AC-USD"}, "AC", "USD",
        model::RationalIncrement{1U,1U}, model::RationalIncrement{1U,1U}, model::RationalIncrement{1U,1U}, model::QuantityLots{1U}, model::QuantityLots{1'000U}, "v1"};
    policy::PolicyEnvironment env{inst, model::StrategyId{"ac-policy"}, model::FeeScheduleId{"fees"}, model::LatencyModelId{"lat"}, 250, 5U, 8U, 1U, 1U,
        {policy::QuantityFraction{51U,100U}, policy::QuantityFraction{1U,1U}}, {model::TickOffset{0}}, policy::LotRoundingPolicy::Floor, true, true, true};
    strategies::AlmgrenChrissPolicy strategy{model::StrategyId{"ac-policy"}, params(0.5L)};
    strategy.reset(parent(), env);
    policy::ParentOrderSnapshot snap{model::ParentOrderId{19U}, model::Side::Buy, t(1'000), t(2'000), model::PriceTicks{100}, "hard-completion-v1",
        model::QuantityLots{100U}, model::QuantityLots{0U}, model::QuantityLots{100U}, model::QuoteAtoms{0}, model::QuoteAtoms{0}, model::QuoteAtoms{0}, 0U, policy::ParentOrderStatus::Active, false};
    policy::PolicyObservation obs{model::DecisionId{1U}, t(1'000), t(1'000), env, snap,
        {{model::PriceTicks{99}, model::QuantityLots{100U}, std::nullopt}}, {{model::PriceTicks{101}, model::QuantityLots{100U}, std::nullopt}}, {}, {}, 0U, {}};
    const auto action = strategy.on_observation(obs);
    const auto* submit = std::get_if<policy::SubmitChildAction>(&action.payload);
    require(submit != nullptr, "AC policy must submit first due slice");
    require(submit->order_type == model::OrderType::Market, "aggressive AC policy must use market orders");
    require((submit->quantity_fraction == policy::QuantityFraction{51U,100U}), "AC policy quantity fraction mismatch");
  }

  return 0;
}
