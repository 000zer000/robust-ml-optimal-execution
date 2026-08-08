#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  RESEARCH_PYTHON="$ROOT/.venv/bin/python"
else
  RESEARCH_PYTHON="${ROBUST_EXECUTION_PYTHON:-python3}"
fi
export LOKY_MAX_CPU_COUNT="${LOKY_MAX_CPU_COUNT:-1}"

"$RESEARCH_PYTHON" scripts/verify_specification_lock.py
"$RESEARCH_PYTHON" scripts/validate_repository.py
"$RESEARCH_PYTHON" scripts/validate_event_model.py
"$RESEARCH_PYTHON" scripts/validate_policy_contracts.py
"$RESEARCH_PYTHON" scripts/validate_synthetic_market.py
"$RESEARCH_PYTHON" scripts/validate_simulator_gate.py
"$RESEARCH_PYTHON" scripts/validate_source_decision.py
"$RESEARCH_PYTHON" scripts/validate_market_capture.py
PYTHONPATH=python "$RESEARCH_PYTHON" scripts/validate_raw_data.py
PYTHONPATH=python "$RESEARCH_PYTHON" scripts/validate_canonical_data.py
PYTHONPATH=python "$RESEARCH_PYTHON" scripts/validate_historical_replay.py
PYTHONPATH=python "$RESEARCH_PYTHON" scripts/validate_queue_models.py
PYTHONPATH=python "$RESEARCH_PYTHON" scripts/validate_execution_metrics.py
PYTHONPATH=python "$RESEARCH_PYTHON" scripts/validate_baselines.py
PYTHONPATH=python "$RESEARCH_PYTHON" scripts/validate_almgren_chriss.py
PYTHONPATH=python "$RESEARCH_PYTHON" scripts/validate_adaptive_control.py
PYTHONPATH=python "$RESEARCH_PYTHON" scripts/validate_causal_prediction.py
PYTHONPATH=python "$RESEARCH_PYTHON" scripts/validate_simple_models.py
PYTHONPATH=python "$RESEARCH_PYTHON" scripts/validate_temporal_model.py
PYTHONPATH=python "$RESEARCH_PYTHON" scripts/validate_ml_mpc.py
PYTHONPATH=python "$RESEARCH_PYTHON" scripts/validate_prediction_decision_value.py
PYTHONPATH=python "$RESEARCH_PYTHON" scripts/validate_imitation_learning.py
PYTHONPATH=python "$RESEARCH_PYTHON" scripts/validate_reinforcement_learning.py
PYTHONPATH=python "$RESEARCH_PYTHON" scripts/validate_robustness.py
PYTHONPATH=python "$RESEARCH_PYTHON" scripts/validate_statistical_inference.py
PYTHONPATH=python "$RESEARCH_PYTHON" scripts/validate_performance.py
"$RESEARCH_PYTHON" scripts/validate_paper_claims.py
"$RESEARCH_PYTHON" scripts/validate_release.py
"$RESEARCH_PYTHON" -m compileall -q python/robust_execution scripts tests
"$RESEARCH_PYTHON" -m ruff check python tests/python scripts paper
"$RESEARCH_PYTHON" -m ruff format --check python tests/python scripts paper
"$RESEARCH_PYTHON" -m mypy python/robust_execution
PYTHONPATH=python "$RESEARCH_PYTHON" -m pytest --cov=robust_execution --cov-branch --cov-report=term-missing tests/python
"$RESEARCH_PYTHON" scripts/check_deterministic_sample.py

cmake --preset gcc-debug
cmake --build --preset gcc-debug
ctest --preset gcc-debug
"$RESEARCH_PYTHON" scripts/check_matching_demo.py
"$RESEARCH_PYTHON" scripts/check_kernel_demo.py
"$RESEARCH_PYTHON" scripts/check_policy_demo.py
"$RESEARCH_PYTHON" scripts/check_historical_demo.py
"$RESEARCH_PYTHON" scripts/check_queue_demo.py
"$RESEARCH_PYTHON" scripts/check_metrics_demo.py

cmake --preset clang-debug
cmake --build --preset clang-debug
ctest --preset clang-debug

cmake --preset asan-ubsan
cmake --build --preset asan-ubsan
ctest --preset asan-ubsan

cmake --preset tsan
cmake --build --preset tsan
TSAN_OPTIONS=halt_on_error=1:second_deadlock_stack=1 ctest --preset tsan

PYTHONPATH=python "$RESEARCH_PYTHON" -m robust_execution bootstrap-sample \
  configs/bootstrap/sample.toml --output results/sample/bootstrap_result.json

printf 'Complete engineering validation: PASS; historical Gate C remains blocked\n'
