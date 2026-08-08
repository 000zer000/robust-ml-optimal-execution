#include "synthetic_test_support.hpp"

#include <cstdlib>

int main() {
  using namespace synthetic_test;
  const auto first = synthetic::SyntheticMarketGenerator{config(77U)}.generate();
  const auto second = synthetic::SyntheticMarketGenerator{config(77U)}.generate();
  const auto different = synthetic::SyntheticMarketGenerator{config(78U)}.generate();

  if (synthetic::has_errors(synthetic::validate_tape(first))) {
    return EXIT_FAILURE;
  }
  if (first.canonical_text != second.canonical_text ||
      first.tape_sha256 != second.tape_sha256 ||
      first.manifest_json != second.manifest_json ||
      first.manifest_sha256 != second.manifest_sha256) {
    return EXIT_FAILURE;
  }
  if (first.tape_sha256 == different.tape_sha256 || first.tape_sha256.size() != 64U ||
      first.manifest_sha256.size() != 64U) {
    return EXIT_FAILURE;
  }
  auto tampered = first;
  tampered.actions.front().detail = "tampered";
  if (!synthetic::has_errors(synthetic::validate_tape(tampered))) {
    return EXIT_FAILURE;
  }
  if (first.manifest_json.find("\"calibration_status\":\"not_calibrated_step9\"") ==
      std::string::npos) {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
