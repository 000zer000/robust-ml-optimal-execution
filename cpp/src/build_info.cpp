#include "robust_execution/build_info.hpp"

#include <sstream>

namespace robust_execution {
namespace {

[[nodiscard]] std::string compiler_name() {
#if defined(__clang__)
  return "Clang " + std::to_string(__clang_major__) + "." +
         std::to_string(__clang_minor__) + "." + std::to_string(__clang_patchlevel__);
#elif defined(__GNUC__)
  return "GCC " + std::to_string(__GNUC__) + "." +
         std::to_string(__GNUC_MINOR__) + "." + std::to_string(__GNUC_PATCHLEVEL__);
#elif defined(_MSC_VER)
  return "MSVC " + std::to_string(_MSC_VER);
#else
  return "unknown";
#endif
}

}  // namespace

BuildInfo build_info() {
  return BuildInfo{
      .version = ROBUST_EXECUTION_VERSION,
      .compiler = compiler_name(),
      .cpp_standard = "C++20",
  };
}

std::string build_info_json() {
  const auto info = build_info();
  std::ostringstream stream;
  stream << "{\"version\":\"" << info.version << "\","
         << "\"compiler\":\"" << info.compiler << "\","
         << "\"cpp_standard\":\"" << info.cpp_standard << "\"}";
  return stream.str();
}

}  // namespace robust_execution
