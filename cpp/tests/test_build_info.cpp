#include "robust_execution/build_info.hpp"

#include <cstdlib>
#include <string>

int main() {
  const auto info = robust_execution::build_info();
  if (info.version != "0.14.0") {
    return EXIT_FAILURE;
  }
  if (info.cpp_standard != "C++20" || info.compiler.empty()) {
    return EXIT_FAILURE;
  }
  const std::string json = robust_execution::build_info_json();
  if (json.find("\"version\":\"0.14.0\"") == std::string::npos) {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
