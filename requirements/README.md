# Dependency policy

The Python runtime package intentionally has no third-party runtime dependency at
bootstrap. `uv.lock` therefore locks the project itself and supported Python range.
C++ binding build dependencies are exact pins in `pyproject.toml`; development tools
are exact direct pins in `tool-versions.lock` and in CI invocations.

A fully resolved, hash-complete lock for later scientific dependencies will be created
when those dependencies are introduced. No unneeded ML/data stack is installed at
Step 4.

Step 23 adds an optional `deep-models` extra pinned to NumPy 2.3.5, scikit-learn 1.8.0, and PyTorch 2.10.0. It is intentionally not imported by the core prediction package. The minimal bootstrap lock remains dependency-light; hosted deep-model validation installs the exact optional pins explicitly.
