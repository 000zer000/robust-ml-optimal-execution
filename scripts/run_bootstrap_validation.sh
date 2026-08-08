#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 scripts/verify_specification_lock.py
python3 scripts/validate_repository.py
python3 scripts/validate_event_model.py
python3 scripts/validate_policy_contracts.py
python3 scripts/validate_synthetic_market.py
python3 scripts/validate_simulator_gate.py
python3 scripts/validate_step11_source_decision.py
python3 scripts/validate_step12_capture.py
PYTHONPATH=python python3 scripts/validate_step13_data.py
PYTHONPATH=python python3 scripts/validate_step14_data.py
PYTHONPATH=python python3 scripts/validate_step15_replay.py
PYTHONPATH=python python3 scripts/validate_step16_queue_models.py
PYTHONPATH=python python3 scripts/validate_step17_metrics.py
PYTHONPATH=python python3 scripts/validate_step18_baselines.py
PYTHONPATH=python python3 scripts/validate_step19_almgren_chriss.py
PYTHONPATH=python python3 scripts/validate_step20_adaptive.py
PYTHONPATH=python python3 scripts/validate_step21_prediction.py
PYTHONPATH=python python3 scripts/validate_step22_simple_models.py
PYTHONPATH=python python3 scripts/validate_step23_temporal_model.py
PYTHONPATH=python python3 scripts/validate_step24_ml_mpc.py
PYTHONPATH=python python3 scripts/validate_step25_prediction_decision_value.py
PYTHONPATH=python python3 scripts/validate_step26_imitation.py
PYTHONPATH=python python3 scripts/validate_step27_rl.py
PYTHONPATH=python python3 scripts/validate_step28_robustness.py
PYTHONPATH=python python3 scripts/validate_step29_statistics.py
PYTHONPATH=python python3 scripts/validate_step30_performance.py
python3 scripts/validate_release.py
python3 -m compileall -q python/robust_execution scripts tests
python3 -m ruff check python tests/python scripts
python3 -m ruff format --check python tests/python scripts
python3 -m mypy python/robust_execution
PYTHONPATH=python python3 -m pytest --cov=robust_execution --cov-branch --cov-report=term-missing tests/python
python3 scripts/check_deterministic_sample.py

cmake --preset gcc-debug
cmake --build --preset gcc-debug
ctest --preset gcc-debug
python3 scripts/check_matching_demo.py
python3 scripts/check_kernel_demo.py
python3 scripts/check_policy_demo.py
python3 scripts/check_historical_demo.py
python3 scripts/check_queue_demo.py
python3 scripts/check_metrics_demo.py

cmake --preset clang-debug
cmake --build --preset clang-debug
ctest --preset clang-debug

cmake --preset asan-ubsan
cmake --build --preset asan-ubsan
ctest --preset asan-ubsan

cmake --preset tsan
cmake --build --preset tsan
TSAN_OPTIONS=halt_on_error=1:second_deadlock_stack=1 ctest --preset tsan

PYTHONPATH=python python3 -m robust_execution bootstrap-sample \
  configs/bootstrap/sample.toml --output results/sample/bootstrap_result.json

printf 'Steps 1-30 engineering validation: PASS; historical Gate C remains blocked\n'
