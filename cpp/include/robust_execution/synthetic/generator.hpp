#pragma once

#include "robust_execution/synthetic/types.hpp"

namespace robust_execution::synthetic {

class SyntheticMarketGenerator {
 public:
  explicit SyntheticMarketGenerator(SyntheticMarketConfig config);

  [[nodiscard]] SyntheticTape generate() const;
  [[nodiscard]] const SyntheticMarketConfig& config() const noexcept { return config_; }

 private:
  SyntheticMarketConfig config_;
};

}  // namespace robust_execution::synthetic
