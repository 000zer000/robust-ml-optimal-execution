#include "robust_execution/diagnostic_sequence.hpp"

#include <cstdlib>
#include <cstdint>
#include <vector>

int main() {
  const auto first = robust_execution::diagnostic_sequence(UINT64_C(42), 4U);
  const auto second = robust_execution::diagnostic_sequence(UINT64_C(42), 4U);
  const auto other = robust_execution::diagnostic_sequence(UINT64_C(43), 4U);

  if (first != second || first == other || first.size() != 4U) {
    return EXIT_FAILURE;
  }
  if (!robust_execution::diagnostic_sequence(UINT64_C(0), 0U).empty()) {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
