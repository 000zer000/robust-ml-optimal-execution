#include "robust_execution/util/sha256.hpp"

#include <cstdlib>

int main() {
  using robust_execution::util::sha256_hex;
  if (sha256_hex("") !=
          "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" ||
      sha256_hex("abc") !=
          "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad" ||
      sha256_hex("abc") == sha256_hex("abd")) {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
