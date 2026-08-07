#include "robust_execution/strategies/baselines.hpp"

#include <cstdlib>
#include <iostream>
#include <stdexcept>

using namespace robust_execution;

namespace {
void require(bool condition, const char* message) { if (!condition) { std::cerr << message << "\n"; std::exit(1); } }
model::TimestampNs t(std::int64_t v) { return {model::ClockDomain::Simulation, v}; }
policy::ParentOrderDefinition parent(std::uint64_t qty = 100U) {
  return {model::ParentOrderId{1U}, model::Side::Buy, model::QuantityLots{qty}, t(1'000), t(2'000), model::PriceTicks{100}, "hard-completion-v1"};
}
}

int main() {
  {
    const auto schedule = strategies::build_baseline_schedule(parent(), {strategies::BaselineKind::ImmediateAggressive, strategies::ExecutionStyle::Aggressive, 1U, std::nullopt});
    require(bool(schedule.slices.size() == 1U), "baseline requirement failed");
    require(bool(schedule.slices[0].release_time.value() == 1'000), "baseline requirement failed");
    require(bool(schedule.slices[0].quantity.value() == 100U), "baseline requirement failed");
  }
  {
    const auto schedule = strategies::build_baseline_schedule(parent(101U), {strategies::BaselineKind::Twap, strategies::ExecutionStyle::Aggressive, 4U, std::nullopt});
    require(bool(schedule.slices.size() == 4U), "baseline requirement failed");
    require(bool(schedule.slices[0].quantity.value() == 26U), "baseline requirement failed");
    require(bool(schedule.slices[1].quantity.value() == 25U), "baseline requirement failed");
    require(bool(schedule.slices[2].quantity.value() == 25U), "baseline requirement failed");
    require(bool(schedule.slices[3].quantity.value() == 25U), "baseline requirement failed");
    require(bool(schedule.slices[0].release_time.value() == 1'000), "baseline requirement failed");
    require(bool(schedule.slices[1].release_time.value() == 1'250), "baseline requirement failed");
    require(bool(schedule.slices[2].release_time.value() == 1'500), "baseline requirement failed");
    require(bool(schedule.slices[3].release_time.value() == 1'750), "baseline requirement failed");
    require(bool(schedule.total_quantity().value() == 101U), "baseline requirement failed");
  }
  {
    strategies::VolumeProfile profile{{1U, 2U, 3U, 4U}, t(999), "train-days-001-050"};
    const auto schedule = strategies::build_baseline_schedule(parent(), {strategies::BaselineKind::PastVolumeInformed, strategies::ExecutionStyle::Aggressive, 0U, profile});
    require(bool(schedule.slices.size() == 4U), "baseline requirement failed");
    require(bool(schedule.slices[0].quantity.value() == 10U), "baseline requirement failed");
    require(bool(schedule.slices[1].quantity.value() == 20U), "baseline requirement failed");
    require(bool(schedule.slices[2].quantity.value() == 30U), "baseline requirement failed");
    require(bool(schedule.slices[3].quantity.value() == 40U), "baseline requirement failed");
    require(bool(schedule.provenance_id == "train-days-001-050"), "baseline requirement failed");
  }
  {
    bool threw = false;
    try {
      strategies::VolumeProfile leaked{{1U, 1U}, t(1'000), "leaked"};
      (void)strategies::build_baseline_schedule(parent(), {strategies::BaselineKind::PastVolumeInformed, strategies::ExecutionStyle::Aggressive, 0U, leaked});
    } catch (const std::invalid_argument&) { threw = true; }
    require(bool(threw), "baseline requirement failed");
  }
  {
    bool threw = false;
    try {
      (void)strategies::build_baseline_schedule(parent(), {strategies::BaselineKind::ImmediateAggressive, strategies::ExecutionStyle::Passive, 1U, std::nullopt});
    } catch (const std::invalid_argument&) { threw = true; }
    require(bool(threw), "baseline requirement failed");
  }

  {
    auto inst = model::InstrumentDefinition{model::kEventSchemaVersion, model::VenueId{"synthetic"}, model::InstrumentId{"TEST-USD"}, "TEST", "USD",
        model::RationalIncrement{1U,1U}, model::RationalIncrement{1U,1U}, model::RationalIncrement{1U,1U}, model::QuantityLots{1U}, model::QuantityLots{1'000U}, "v1"};
    policy::PolicyEnvironment env{inst, model::StrategyId{"twap-test"}, model::FeeScheduleId{"fees"}, model::LatencyModelId{"lat"},
        250, 5U, 8U, 1U, 1U,
        {policy::QuantityFraction{1U,4U}, policy::QuantityFraction{1U,3U}, policy::QuantityFraction{1U,2U}, policy::QuantityFraction{1U,1U}},
        {model::TickOffset{0}}, policy::LotRoundingPolicy::Floor, true, true, true};
    strategies::ScheduledBaselinePolicy strategy{model::StrategyId{"twap-test"}, {strategies::BaselineKind::Twap, strategies::ExecutionStyle::Aggressive, 4U, std::nullopt}};
    strategy.reset(parent(), env);
    policy::ParentOrderSnapshot snap{model::ParentOrderId{1U}, model::Side::Buy, t(1'000), t(2'000), model::PriceTicks{100}, "hard-completion-v1",
        model::QuantityLots{100U}, model::QuantityLots{0U}, model::QuantityLots{100U}, model::QuoteAtoms{0}, model::QuoteAtoms{0}, model::QuoteAtoms{0}, 0U, policy::ParentOrderStatus::Active, false};
    policy::PolicyObservation obs{model::DecisionId{1U}, t(1'000), t(1'000), env, snap,
        {{model::PriceTicks{99}, model::QuantityLots{100U}, std::nullopt}}, {{model::PriceTicks{101}, model::QuantityLots{100U}, std::nullopt}}, {}, {}, 0U, {}};
    const auto action = strategy.on_observation(obs);
    const auto* submit = std::get_if<policy::SubmitChildAction>(&action.payload);
    require(bool(submit != nullptr), "baseline requirement failed");
    require(bool(submit->order_type == model::OrderType::Market), "baseline requirement failed");
    require(bool(submit->time_in_force == model::TimeInForce::ImmediateOrCancel), "baseline requirement failed");
    require(bool((submit->quantity_fraction == policy::QuantityFraction{1U,4U})), "baseline requirement failed");
  }

  {
    const std::vector<strategies::VolumeObservation> observations{
      {t(900), 0U, model::QuantityLots{10U}}, {t(910), 1U, model::QuantityLots{20U}},
      {t(920), 2U, model::QuantityLots{30U}}, {t(930), 3U, model::QuantityLots{40U}}};
    const auto profile = strategies::build_past_volume_profile(4U, observations, t(999), "past-trades-only");
    require(bool((profile.bucket_weights == std::vector<std::uint64_t>{10U,20U,30U,40U})), "baseline requirement failed");
    bool rejected_future = false;
    try {
      auto future = observations;
      future.push_back({t(1'000), 0U, model::QuantityLots{1U}});
      (void)strategies::build_past_volume_profile(4U, future, t(999), "bad");
    } catch (const std::invalid_argument&) { rejected_future = true; }
    require(bool(rejected_future), "baseline requirement failed");
  }
  return 0;
}
