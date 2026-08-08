SHELL := /usr/bin/env bash
PYTHON ?= python3
PYTHONPATH := python
PAPER_SOURCE_DATE_EPOCH ?= 1786147200

.PHONY: help spec-check repository-check event-model-check policy-contract-check synthetic-market-check simulator-validation-check data-source-check raw-capture-check data-validation-check canonical-data-check historical-replay-check queue-model-check metrics-check baselines-check almgren-chriss-check adaptive-baselines-check prediction-data-check simple-models-check temporal-model-check ml-mpc-check prediction-decision-value-check imitation-learning-check rl-check robustness-check statistics-check performance-check paper-check paper-build matching-check matching-demo-check kernel-demo-check policy-demo-check configure build test-cpp test-python test sample event-model-sample sanitize clang-test lint typecheck format-check wheel clean ci-local

help:
	@printf '%s\n' \
	  'spec-check       verify frozen research documents' \
	  'repository-check validate required repository structure' \
	  'event-model-check validate schemas, fixtures and audit chain' \
	  'policy-contract-check validate execution-policy schemas and fixtures' \
	  'synthetic-market-check validate synthetic-market configs, schemas and deterministic tape' \
	  'build            configure and build GCC Debug' \
	  'test             run C++ and Python tests' \
	  'sample           generate deterministic bootstrap artifact' \
	  'event-model-sample regenerate deterministic event-model fixtures' \
	  'matching-check    run all C++ matching-engine tests' \
	  'matching-demo-check verify deterministic matching-engine hand tape' \
	  'kernel-demo-check   verify deterministic simulation-kernel replay fixture' \
	  'policy-demo-check   verify deterministic execution-policy fixture' \
	  'synthetic-market-check validate deterministic generator fixture' \
	  'simulator-validation-check validate simulator report and rerun' \
	  'data-source-check validate the market-data source contract' \
	  'raw-capture-check validate capture engineering and fixtures' \
	  'data-validation-check validate admission and quarantine outputs' \
	  'canonical-data-check validate canonical datasets' \
	  'historical-replay-check validate aggregate-L2 replay' \
	  'queue-model-check validate queue assumptions and exact FIFO comparisons' \
	  'metrics-check     validate exact accounting, audits and tail metrics' \
	  'baselines-check   validate basic schedules and leakage controls' \
	  'almgren-chriss-check validate discrete Almgren-Chriss schedule' \
	  'adaptive-baselines-check validate queue-aware heuristic and non-ML MPC' \
	  'prediction-data-check validate causal features, targets and leakage tests' \
	  'simple-models-check validate simple models, calibration and artifacts' \
	  'temporal-model-check validate causal Conv1D-LSTM and artifacts' \
	  'ml-mpc-check validate ML-assisted MPC and ablations' \
	  'prediction-decision-value-check validate decision-value analysis' \
	  'imitation-learning-check validate behavior cloning, DAgger and fallback' \
	  'rl-check validate PPO, reward audit and OOD transfer' \
	  'robustness-check validate robustness matrix' \
	  'statistics-check validate statistical inference' \
	  'performance-check validate performance evidence' \
	  'paper-check     validate manuscript claims against committed evidence' \
	  'paper-build     validate and compile the canonical research paper' \
	  'sanitize         run GCC ASan+UBSan build/tests' \
	  'clang-test       run independent Clang build/tests' \
	  'lint             run pinned Ruff' \
	  'typecheck        run pinned mypy' \
	  'wheel            build Python wheel with C++ binding' \
	  'ci-local         execute the complete local engineering validation suite'

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
	$(PYTHON) scripts/validate_source_decision.py

raw-capture-check:
	$(PYTHON) scripts/validate_market_capture.py

data-validation-check:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/validate_raw_data.py

canonical-data-check:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/validate_canonical_data.py

historical-replay-check: build
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/validate_historical_replay.py
	$(PYTHON) scripts/check_historical_demo.py

queue-model-check: build
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/validate_queue_models.py
	$(PYTHON) scripts/check_queue_demo.py

metrics-check: build
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/validate_execution_metrics.py
	$(PYTHON) scripts/check_metrics_demo.py

baselines-check: build
	$(PYTHON) scripts/validate_baselines.py

almgren-chriss-check: build
	$(PYTHON) scripts/validate_almgren_chriss.py

adaptive-baselines-check: build
	$(PYTHON) scripts/validate_adaptive_control.py

prediction-data-check:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/validate_causal_prediction.py

simple-models-check:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/validate_simple_models.py

temporal-model-check:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/validate_temporal_model.py

ml-mpc-check: build
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/validate_ml_mpc.py

prediction-decision-value-check: build
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/validate_prediction_decision_value.py

imitation-learning-check: build
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/validate_imitation_learning.py

rl-check:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/validate_reinforcement_learning.py

robustness-check:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/validate_robustness.py

statistics-check:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/validate_statistical_inference.py

performance-check:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/validate_performance.py

paper-check:
	$(PYTHON) scripts/validate_paper_claims.py

paper-build: paper-check
	mkdir -p tmp/paper-build output/pdf
	cd paper && SOURCE_DATE_EPOCH=$(PAPER_SOURCE_DATE_EPOCH) tectonic -X compile main.tex --outdir ../tmp/paper-build
	cp tmp/paper-build/main.pdf output/pdf/Robust_ML_Optimal_Execution_Research_Paper.pdf

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
	PYTHONPATH=$(PYTHONPATH) coverage run --branch --source=python/robust_execution -m pytest -q tests/python/test_rl.py
	mv .coverage .coverage.rl
	PYTHONPATH=$(PYTHONPATH) coverage run --branch --source=python/robust_execution -m pytest -q tests/python/test_robustness.py -k "not full_artifact_regeneration"
	mv .coverage .coverage.robustness
	PYTHONPATH=$(PYTHONPATH) coverage run --branch --source=python/robust_execution -m pytest -q tests/python/test_statistics.py
	mv .coverage .coverage.statistics
	PYTHONPATH=$(PYTHONPATH) coverage run --branch --source=python/robust_execution -m pytest -q tests/python/test_performance.py
	mv .coverage .coverage.performance
	PYTHONPATH=$(PYTHONPATH) coverage run --branch --source=python/robust_execution -m pytest -q tests/python --ignore=tests/python/test_temporal_models.py --ignore=tests/python/test_simple_models.py --ignore=tests/python/test_imitation_learning.py --ignore=tests/python/test_rl.py --ignore=tests/python/test_robustness.py --ignore=tests/python/test_statistics.py --ignore=tests/python/test_performance.py
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
