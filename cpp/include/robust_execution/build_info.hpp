#pragma once

#include <string>

namespace robust_execution {

struct BuildInfo {
  std::string version;
  std::string compiler;
  std::string cpp_standard;
};

[[nodiscard]] BuildInfo build_info();
[[nodiscard]] std::string build_info_json();

}  // namespace robust_execution
