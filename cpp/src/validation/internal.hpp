#pragma once

#include "robust_execution/synthetic/synthetic.hpp"
#include "robust_execution/validation/types.hpp"

#include <cstdint>
#include <string>
#include <vector>

namespace robust_execution::validation::detail {

struct BatchAggregate {
  double mean_market_submissions{0.0};
  double mean_limit_submissions{0.0};
  double mean_cancellations{0.0};
  double mean_trades{0.0};
  double mean_executed_lots{0.0};
  double mean_minimum_visible_depth{0.0};
  double mean_average_visible_depth{0.0};
  double mean_absolute_reference_move{0.0};
  std::uint64_t total_steps{0U};
  bool valid{true};
  std::string failure;
};

[[nodiscard]] synthetic::SyntheticMarketConfig base_config(std::uint64_t seed);
[[nodiscard]] BatchAggregate run_batch(
    const synthetic::SyntheticMarketConfig& prototype,
    std::uint64_t first_seed,
    std::uint64_t seed_count
);
[[nodiscard]] std::vector<ValidationCheck> run_hand_and_failure_checks();
[[nodiscard]] ValidationCheck run_differential_check();
[[nodiscard]] std::vector<DirectionalSensitivity> run_sensitivity_checks();
[[nodiscard]] std::string json_escape(std::string_view value);

}  // namespace robust_execution::validation::detail
