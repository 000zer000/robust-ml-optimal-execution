# Manuscript Claim Traceability

The manuscript reports controlled simulator results and direct systems measurements. This table
maps its headline quantitative claims to the canonical committed evidence. Run
`python scripts/validate_paper_claims.py` to verify the values and their appearance in
`paper/main.tex`.

| Manuscript claim | Registered value | Canonical evidence |
|---|---:|---|
| A perfect intermediate-event label oracle can worsen execution in the matched controller fixture | true | `data/sample/analysis/step25-prediction-decision-value/report.json` → `payload.engineering_summary.perfect_label_oracle_can_worsen_execution_fixture` |
| Raw imitation agreement on OOD decisions | 69.30% | `data/sample/imitation/step26-imitation-validation/report.json` → `evaluation.ood.student_raw.final_action_agreement` |
| OOD agreement with validation-selected teacher fallback | 94.78% | same report → `evaluation.ood.student_with_teacher_fallback.final_action_agreement` |
| OOD teacher-fallback rate | 82.61% | same report → `evaluation.ood.student_with_teacher_fallback.fallback_rate` |
| Registered stress cells and non-central rank switches | 43 cells; 16/42 | `data/sample/robustness/step28-engineering-matrix/report.json` → `ranking_summary` |
| Paired controlled contrasts whose 95% intervals cross zero | 85/129 | `data/sample/statistics/step29-engineering-inference/report.json` → `contrast_rows` and `negative_results` |
| Point winners with at least 80% bootstrap probability of remaining best | 21/43 | same report → `ranking_summary` |
| Unstable point winners under the 80% diagnostic | 22/43 | same report → `ranking_summary` |
| Four-thread optimized matching throughput | 17.316 Mops/s | `results/validation/step30/performance_report.json` → `cpp_matching.4.optimized.throughput_ops_per_second` |
| Transfer-inclusive temporal-model GPU speedup at batch 256 | 1.704× | `evidence/performance/STEP30_CUDA_GATE.json` → `models.temporal_5s.256.transfer_inclusive_speedup_vs_cpu` |
| Python test inventory and branch-aware coverage | 480; 91% | `FINAL_RELEASE_MANIFEST.json` |
| Native tests per build/sanitizer matrix | 53/53 | `FINAL_RELEASE_MANIFEST.json` and GitHub Actions |

## Interpretation boundary

- Strategy comparisons are registered controlled-simulator evidence, not historical backtests.
- CPU and CUDA values are measurements on the hardware identified in their evidence files; they
  are not universal latency guarantees or exchange round-trip measurements.
- Aggregate-L2 queue allocation, impact, and synthetic order-flow behavior are explicit scenario
  assumptions. They are stress-tested but not claimed to be identified true-market parameters.
- Historical ingestion and replay engineering exists, but the locked historical performance test
  remains unopened until a qualifying dataset is admitted.
