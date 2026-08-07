#include "robust_execution/build_info.hpp"
#include "robust_execution/diagnostic_sequence.hpp"

#include <cstddef>
#include <cstdint>
#include <iostream>

int main() {
  const auto sequence = robust_execution::diagnostic_sequence(UINT64_C(20260806), 3U);
  std::cout << "{\"build\":" << robust_execution::build_info_json()
            << ",\"diagnostic\":[" << sequence.at(0) << ',' << sequence.at(1) << ','
            << sequence.at(2) << "]}\n";
  return 0;
}
