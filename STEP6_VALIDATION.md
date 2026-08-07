# Step 6 Validation Report — C++ Price-Time-Priority Matching Engine

**Date:** 2026-08-06  
**Repository version:** 0.3.0  
**Status:** PASS for Step 6 acceptance  
**Next step:** Step 7 — deterministic event-driven kernel and latency

## 1. Scope protected

Step 6 did not change the approved central research question, research hypotheses, final project scope, or experimental protocol. The SHA-256 specification lock passed for all seven frozen files.

A governance defect was discovered and repaired: the working directory contained the earlier uncorrected Step 2 files even though `SPECIFICATION_LOCK.json` contained hashes for the corrected package. The seven files were restored byte-for-byte from `robust-execution-step2-specification-corrected.zip`; no new specification amendment was made.

## 2. Step 6 acceptance result

The required C++ exact-mode matching mechanics are implemented:

- ordered bid and ask books;
- strict price priority;
- FIFO time priority within a price level;
- maker-price execution;
- market and limit orders;
- GTC, IOC, and FOK semantics;
- post-only rejection;
- partial fills;
- cancellation from arbitrary queue position;
- atomic cancel-replace;
- replacement priority loss;
- quantity and price validation;
- deterministic rejection diagnostics;
- deterministic identifiers and canonical state;
- complete active/history queries;
- explicit invariant validation.

The engine is venue-neutral and applies only to synthetic exact mode. It does not claim to reproduce a named venue.

## 3. Architecture review

The first implementation grew to 1,189 lines in one source file. That contradicted the project's requirement to avoid monolithic simulator code, so it was rejected before Step 6 freeze and refactored into:

| Unit | Responsibility | Lines |
|---|---|---:|
| `matching_engine.cpp` | public façade, ownership, forwarding | 97 |
| `matching_engine_commands.cpp` | command validation and submit/cancel/replace | 569 |
| `matching_engine_book.cpp` | matching, levels, queries, invariants, canonical state | 492 |
| `matching_engine_internal.hpp` | private implementation contract | 161 |
| public `matching_engine.hpp` | stable public API | 199 |

No behavioural regression appeared after the split.

## 4. C++ test matrix

Fourteen CTest executables passed under every executed compiler/sanitizer configuration. Six are dedicated to Step 6.

| Test | Principal coverage |
|---|---|
| `re_test_matching_price_time` | price priority, FIFO, partial fills, maker price, maker/taker symmetry |
| `re_test_matching_order_semantics` | post-only, FOK atomic rejection, IOC cancellation, market restrictions, quantity/price failures |
| `re_test_matching_cancel_replace` | middle cancellation, terminal/mismatch failures, replacement atomicity, lost priority, crossing replacement |
| `re_test_matching_book_queries` | best prices, depth views, crossing and fillability queries |
| `re_test_matching_determinism` | 400 deterministic generated commands with invariants after every command and byte-identical final state |
| `re_test_matching_validation` | invalid instrument/configurations, duplicate IDs, malformed timestamps, Step 5 payload validation |

Legacy Step 4/5 C++ tests also remain green.

### GCC 14.2.0 Debug

- configure: PASS;
- warnings as errors: PASS;
- build: PASS;
- CTest: **14/14 passed**.

### GCC 14.2.0 Release + IPO

- configure/build: PASS;
- interprocedural optimisation requested and accepted;
- CTest: **14/14 passed**;
- deterministic demo: PASS.

### Clang 17 Debug

- independent compiler configure/build: PASS;
- warnings as errors: PASS;
- CTest: **14/14 passed**.

### GCC ASan + UBSan

- instrumented build: PASS;
- CTest: **14/14 passed**;
- AddressSanitizer findings: none;
- UndefinedBehaviorSanitizer findings: none.

TSan was not run as a Step 6 claim because the engine is deliberately single-threaded and no concurrent scheduler exists yet. Concurrency and practical TSan testing remain in the later simulator validation/performance gates.

## 5. Python and repository regression gate

- frozen specification: **7/7 hashes passed**;
- repository structure contract: **31 required files passed**;
- Step 5 event model: **4 schemas and 9-record audit chain passed**;
- Python tests: **47/47 passed**;
- branch-aware Python coverage: **93.69%**;
- deterministic bootstrap sample: PASS;
- Python compilation: PASS;
- Python 100-character line check: PASS;
- JSON parsing: PASS;
- TOML parsing: PASS;
- workflow YAML parsing: PASS.

The repository-size validator was corrected to ignore generated `build/`, `dist/`, and tool-cache directories while retaining the 10 MiB limit for source and committed artifacts. The previous implementation incorrectly treated sanitizer binaries as repository source.

## 6. Deterministic hand tape

`robust_execution_matching_demo` executes a fixed non-empirical tape containing:

1. two resting asks;
2. one crossing IOC buy with two price-level matches;
3. replacement of a partially filled ask;
4. one resting bid;
5. one market sell fill.

Its output is compared byte-for-byte with:

`data/sample/matching_engine/expected_state.txt`

Result: **PASS**.

The final state has one bid at 100, one ask at 103, six accepted-order history records, and deterministic next-ID counters. This fixture is a correctness artifact, not an empirical result or performance benchmark.

## 7. Installation/export validation

A clean CMake installation to `/tmp/re-step6-install` succeeded. It installed:

- the core static library;
- the build-info executable;
- the matching-demo executable;
- public model and exchange headers;
- CMake target exports.

The installed build-info executable reported version 0.3.0, and the installed matching demo reproduced the committed expected state byte-for-byte.

## 8. Exact semantics validated

### Matching

- best eligible price first;
- FIFO within level;
- resting maker price determines execution price;
- partially filled makers retain position;
- filled levels are removed;
- no crossed resting book remains.

### Time in force

- GTC limit remainder rests;
- IOC limit/market remainder auto-cancels;
- FOK prechecks all eligible liquidity and rejects without mutation if incomplete;
- market GTC is unsupported and rejected;
- post-only requires GTC limit and rejects if crossing.

### Cancellation and replacement

- cancellation preserves cumulative fills and removes all leaves;
- client/exchange mismatch is distinguished from unknown order;
- already-terminal current state is retained in engine-local diagnostics;
- invalid replacement leaves the original untouched;
- valid replacement assigns new client/exchange IDs and new priority;
- replacement may cross and then rest its remainder.

### Tick and lot boundary

Canonical `PriceTicks` and `QuantityLots` structurally prevent fractional tick/lot values inside the engine. Raw decimal conversion and explicit raw `TickViolation`/`LotViolation` belong to the venue adapter after Step 11, not to this canonical core.

## 9. Defect isolated without silent schema change

The Step 5 model contains `RejectReason::AlreadyTerminal`, but its cancel/replace rejection validators forbid a terminal `resulting_state`. Step 6 therefore uses an engine-local `EngineFailure.current_state` and did not emit a false Step 5 rejection event.

The proposed conditional correction is documented in:

`docs/proposals/STEP5_CANCEL_REJECT_STATE_AMENDMENT.md`

It has **not** been applied and requires Othmane's explicit approval.

## 10. Tool/environment limitations

- Docker is unavailable in this container; the Docker job was not executed locally.
- pybind11 is not installed and the package registry is inaccessible, so the isolated wheel/binding job was not rerun in Step 6.
- Ruff and mypy are not installed locally and could not be downloaded; syntax, tests, coverage, line-length, two compilers, warnings-as-errors, and sanitizers were executed instead. The pinned hosted checks remain configured, but no hosted CI success is claimed before a repository push.
- No performance benchmark was run or claimed in Step 6.

## 11. Acceptance decision

**Step 6 is accepted.** The matching engine meets the roadmap deliverable and is ready to be driven by the Step 7 scheduler. Step 7 must preserve the matching rules and add deterministic event scheduling, latency paths, event envelopes, replay hashes, and causal availability without embedding policy logic into the exchange core.
