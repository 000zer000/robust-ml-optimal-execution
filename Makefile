SHELL := /usr/bin/env bash
PYTHON ?= python3
PYTHONPATH := python

.PHONY: help spec-check repository-check event-model-check policy-contract-check synthetic-market-check simulator-validation-check data-source-check raw-capture-check data-validation-check canonical-data-check historical-replay-check queue-model-check metrics-check baselines-check almgren-chriss-check adaptive-baselines-check prediction-data-check simple-models-check temporal-model-check ml-mpc-check matching-check matching-demo-check kernel-demo-check policy-demo-check configure build test-cpp test-python test sample event-model-sample sanitize clang-test lint typecheck format-check wheel clean ci-local

help:
	@printf '%s\n' \
	  'spec-check       verify frozen research documents' \
	  'repository-check validate required repository structure' \
	  'event-model-check validate schemas, fixtures and audit chain' \
	  'policy-contract-check validate Step 8 schemas and fixtures' \
	  'synthetic-market-check validate Step 9 configs, schemas and deterministic tape' \
	  'build            configure and build GCC Debug' \
	  'test             run C++ and Python tests' \
	  'sample           generate deterministic bootstrap artifact' \
	  'event-model-sample regenerate deterministic Step 5 fixtures' \
	  'matching-check    run all C++ matching-engine tests' \
	  'matching-demo-check verify deterministic Step 6 hand tape' \
	  'kernel-demo-check   verify deterministic Step 7 replay fixture' \
	  'policy-demo-check   verify deterministic Step 8 policy fixture' \
	  'synthetic-market-check validate deterministic Step 9 generator fixture' \
	  'simulator-validation-check validate Step 10 Gate B report and rerun' \
	  'data-source-check validate the Step 11 source-selection contract' \
	  'raw-capture-check validate Step 12 capture engineering and fixtures' \
	  'data-validation-check validate Step 13 admission and quarantine outputs' \
	  'canonical-data-check validate Step 14 canonical datasets' \
	  'historical-replay-check validate Step 15 aggregate-L2 replay' \
	  'queue-model-check validate Step 16 queue assumptions and exact FIFO comparisons' \
	  'metrics-check     validate Step 17 exact accounting, audits and tail metrics' \
	  'baselines-check   validate Step 18 basic schedules and leakage controls' \
	  'almgren-chriss-check validate Step 19 discrete Almgren-Chriss schedule' \
	  'adaptive-baselines-check validate Step 20 queue-aware heuristic and non-ML MPC' \
	  'prediction-data-check validate Step 21 causal features, targets and leakage tests' \
	  'simple-models-check validate Step 22 simple models, calibration and artifacts' \
	  'temporal-model-check validate Step 23 causal Conv1D-LSTM and artifacts' \
  'ml-mpc-check validate Step 24 ML-assisted MPC and ablations' \
	  'imitation-learning-check validate Step 26 behavior cloning, DAgger and fallback' \
	  'rl-check validate Step 27 PPO engineering, reward audit and OOD transfer' \
	  'sanitize         run GCC ASan+UBSan build/tests' \
	  'clang-test       run independent Clang build/tests' \
	  'lint             run pinned Ruff' \
	  'typecheck        run pinned mypy' \
	  'wheel            build Python wheel with C++ binding' \
	  'ci-local         execute all locally available Step 23 checks'

spec-check:
	$(PYTHON) scripts/verify_specification_lock.py

repository-check:
	$(PYTHON) scripts/validate_repository.py

event-model-check:
	$(PYTHON) scripts/validate_event_model.py

policy-contract-check:
	$(PYTHON) scripts/validate_policy_contracts.py

synthetic-market-check: build
	$(PYTHON) scripts/validate_synthetic_market.py

simulator-validation-check: build
	$(PYTHON) scripts/validate_simulator_gate.py

data-source-check:
	$(PYTHON) scripts/validate_step11_source_decision.py

raw-capture-check:
	$(PYTHON) scripts/validate_step12_capture.py

data-validation-check:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/validate_step13_data.py

canonical-data-check:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/validate_step14_data.py

historical-replay-check: build
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/validate_step15_replay.py
	$(PYTHON) scripts/check_historical_demo.py

queue-model-check: build
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/validate_step16_queue_models.py
	$(PYTHON) scripts/check_queue_demo.py

metrics-check: build
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/validate_step17_metrics.py
	$(PYTHON) scripts/check_metrics_demo.py

baselines-check: build
	$(PYTHON) scripts/validate_step18_baselines.py

almgren-chriss-check: build
	$(PYTHON) scripts/validate_step19_almgren_chriss.py

adaptive-baselines-check: build
	$(PYTHON) scripts/validate_step20_adaptive.py

prediction-data-check:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/validate_step21_prediction.py

simple-models-check:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/validate_step22_simple_models.py

temporal-model-check:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/validate_step23_temporal_model.py

ml-mpc-check: build
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/validate_step24_ml_mpc.py

prediction-decision-value-check: build
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/validate_step25_prediction_decision_value.py

imitation-learning-check: build
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/validate_step26_imitation.py

rl-check:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/validate_step27_rl.py

robustness-check:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/validate_step28_robustness.py

statistics-check:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/validate_step29_statistics.py

performance-check:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/validate_step30_performance.py

configure:
	cmake --preset gcc-debug

build: configure
	cmake --build --preset gcc-debug

test-cpp: build
	ctest --preset gcc-debug

test-python:
	rm -f .coverage .coverage.base .coverage.temporal .coverage.simple .coverage.imitation .coverage.rl .coverage.robustness .coverage.statistics .coverage.performance
	PYTHONPATH=$(PYTHONPATH) coverage run --branch --source=python/robust_execution -m pytest -q tests/python/test_temporal_models.py
	mv .coverage .coverage.temporal
	PYTHONPATH=$(PYTHONPATH) coverage run --branch --source=python/robust_execution -m pytest -q tests/python/test_simple_models.py
	mv .coverage .coverage.simple
	PYTHONPATH=$(PYTHONPATH) coverage run --branch --source=python/robust_execution -m pytest -q tests/python/test_imitation_learning.py
	mv .coverage .coverage.imitation
	PYTHONPATH=$(PYTHONPATH) coverage run --branch --source=python/robust_execution -m pytest -q tests/python/test_rl_step27.py
	mv .coverage .coverage.rl
	PYTHONPATH=$(PYTHONPATH) coverage run --branch --source=python/robust_execution -m pytest -q tests/python/test_robustness_step28.py -k "not full_artifact_regeneration"
	mv .coverage .coverage.robustness
	PYTHONPATH=$(PYTHONPATH) coverage run --branch --source=python/robust_execution -m pytest -q tests/python/test_statistics_step29.py
	mv .coverage .coverage.statistics
	PYTHONPATH=$(PYTHONPATH) coverage run --branch --source=python/robust_execution -m pytest -q tests/python/test_performance_step30.py
	mv .coverage .coverage.performance
	PYTHONPATH=$(PYTHONPATH) coverage run --branch --source=python/robust_execution -m pytest -q tests/python --ignore=tests/python/test_temporal_models.py --ignore=tests/python/test_simple_models.py --ignore=tests/python/test_imitation_learning.py --ignore=tests/python/test_rl_step27.py --ignore=tests/python/test_robustness_step28.py --ignore=tests/python/test_statistics_step29.py --ignore=tests/python/test_performance_step30.py
	mv .coverage .coverage.base
	coverage combine .coverage.temporal .coverage.simple .coverage.imitation .coverage.rl .coverage.robustness .coverage.statistics .coverage.performance .coverage.base
	coverage report -m --fail-under=90

test: spec-check repository-check event-model-check policy-contract-check synthetic-market-check simulator-validation-check data-source-check raw-capture-check data-validation-check canonical-data-check historical-replay-check queue-model-check metrics-check baselines-check almgren-chriss-check adaptive-baselines-check prediction-data-check simple-models-check temporal-model-check ml-mpc-check prediction-decision-value-check imitation-learning-check rl-check robustness-check statistics-check performance-check test-cpp test-python

sample:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m robust_execution bootstrap-sample configs/bootstrap/sample.toml --output results/sample/bootstrap_result.json
	$(PYTHON) scripts/check_deterministic_sample.py

matching-check: build
	ctest --preset gcc-debug -R matching

matching-demo-check: build
	$(PYTHON) scripts/check_matching_demo.py

kernel-demo-check: build
	$(PYTHON) scripts/check_kernel_demo.py

policy-demo-check: build
	$(PYTHON) scripts/check_policy_demo.py

event-model-sample:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m robust_execution event-model-sample --output-dir data/sample/event_model
	$(PYTHON) scripts/validate_event_model.py

sanitize:
	cmake --preset asan-ubsan
	cmake --build --preset asan-ubsan
	ctest --preset asan-ubsan

clang-test:
	cmake --preset clang-debug
	cmake --build --preset clang-debug
	ctest --preset clang-debug

lint:
	uv tool run --from ruff==0.15.22 ruff check python tests/python scripts

format-check:
	uv tool run --from ruff==0.15.22 ruff format --check python tests/python scripts

typecheck:
	uv tool run --from mypy==2.3.0 mypy python/robust_execution

wheel:
	uv build --wheel

ci-local:
	bash scripts/run_bootstrap_validation.sh

clean:
	rm -rf build dist .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
