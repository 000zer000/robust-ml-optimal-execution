#pragma once

#include <string>
#include <vector>

#include "robust_execution/model/enums.hpp"
#include "robust_execution/model/events.hpp"

namespace robust_execution::model {

struct ValidationIssue {
  Severity severity{Severity::Error};
  std::string code;
  std::string message;

  [[nodiscard]] friend bool operator==(const ValidationIssue&, const ValidationIssue&) = default;
};

using ValidationIssues = std::vector<ValidationIssue>;

[[nodiscard]] ValidationIssues validate_instrument(const InstrumentDefinition& instrument);
[[nodiscard]] ValidationIssues validate_event(const Event& event);
[[nodiscard]] bool has_errors(const ValidationIssues& issues) noexcept;

}  // namespace robust_execution::model
