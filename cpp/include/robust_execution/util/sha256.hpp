#pragma once

#include <string>
#include <string_view>

namespace robust_execution::util {

[[nodiscard]] std::string sha256_hex(std::string_view input);

}  // namespace robust_execution::util
