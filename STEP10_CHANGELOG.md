# Step 10 change log — Simulator validation gate

## Added

- Public Gate B validation API and machine-readable report types.
- Exact hand-calculated FIFO/partial-fill oracle.
- Exact seven-stage latency arithmetic oracle.
- Independent deque/map differential reference book.
- 32-seed, 64,000-command per-command differential campaign.
- 64-seed, 16,384-step randomized generator invariant campaign.
- 2,048-case structured mutation campaign.
- Four paired directional-sensitivity studies.
- Deterministic validation executable and committed report fixture.
- JSON Schema Draft 2020-12 validation-report contract.
- Python report/schema/reproducibility validator.
- CI and local validation integration.
- Installed CMake package configuration and version file.
- Clean downstream `find_package` consumer test.

## Defects corrected

### S10-F01 — Incomplete installed CMake package

The install exported targets but did not install `robust_executionConfig.cmake`. External projects
could not use `find_package(robust_execution)`. A generated package config and version file are now
installed, and the exported target is named `robust_execution::core`.

### S10-F02 — Mutation workload unsuitable for sanitizers

The first structured-mutation implementation repeatedly copied a 256-step tape, making the sanitizer
gate unnecessarily expensive. The same 2,048 mutation cases now use a smaller, high-activity
32-step baseline while preserving all mutation categories and detection requirements.

### S10-F03 — Release test command assumption

The repository has a Release build preset but no Release test preset. Release validation now uses
`ctest --test-dir build/gcc-release` rather than claiming an unavailable preset.

## Governance

- No frozen research document was modified.
- The specification lock was not regenerated.
- No historical-calibration, strategy-performance or live-profitability claim was introduced.
- The unapproved Step 5 terminal-rejection schema amendment remains unapplied.

## Version

Repository version advanced from `0.6.0` to `0.7.0` for the Gate B validation API and corrected CMake
package export.
