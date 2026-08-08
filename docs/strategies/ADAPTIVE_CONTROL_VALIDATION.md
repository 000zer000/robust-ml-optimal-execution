# Gate D — Classical/adaptive strategy gate

## Decision

**Engineering decision: PASS.**

**Historical research activation: BLOCKED until Gate C.**

The implementation-side Gate D requirements are satisfied:

- immediate aggressive execution exists and is tested;
- TWAP exists and is tested;
- past-only volume scheduling has an explicit anti-leakage cutoff;
- discrete Almgren–Chriss has mathematical oracles and stable limiting cases;
- a queue/liquidity-aware non-ML heuristic exists under the same causal action contract;
- a finite-horizon non-ML MPC exists and re-solves at every observation;
- adaptive calibration objects require pre-episode cutoffs and provenance;
- all strategies share execution-policy interface action constraints and execution-metrics layer accounting;
- synthetic validation retains negative/non-ranking results rather than weakening baselines.

Gate D is **not** interpreted as permission to claim fair historical calibration while Gate C has zero admitted live days. Before any historical ML-versus-MPC comparison, the non-ML controller parameters must be frozen on the allowed development/calibration period and then held fixed on the locked evaluation period.

The ML-assisted controller in ML-assisted MPC analysis must use the same action space, inventory/terminal rules, latency treatment, and MPC constraints. It may add only the predeclared learned prediction inputs. This prevents weakening the non-ML comparator.
