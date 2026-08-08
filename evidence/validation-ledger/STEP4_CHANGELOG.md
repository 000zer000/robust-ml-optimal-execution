# Step 4 Change Log — Repository Bootstrap

## Research specification

No frozen research question, scope, hypothesis, statistical rule, method requirement,
or completion criterion was changed. The governed files are protected by
`governance/SPECIFICATION_LOCK.json` and tested locally and in CI.

## Operational files added

- C++20 library, CLI diagnostic executable, pybind11 boundary, and CTest tests;
- Python package, strict TOML config, JSON logging, CLI, manifests, and tests;
- CMake modules and GCC/Clang/sanitizer presets;
- `pyproject.toml`, `uv.lock`, exact tool-version file, Makefile, Dockerfile;
- GitHub Actions workflows for CI, sanitizers, and reproducibility;
- repository validation and deterministic-sample scripts;
- standard data/config/experiment/result directory contracts;
- bootstrap architecture and pending-license note.

## Existing operational files changed

- `README.md`: Step 4 commands/status added; central question retained verbatim.
- `ROADMAP.md`: current-next-action marker advanced from Step 3 to Step 5.

Neither file is in the frozen specification hash set because status/build instructions
must evolve during implementation.
