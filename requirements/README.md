# Dependency policy

The installable runtime package intentionally has no mandatory third-party dependency, so the CLI and C++ binding remain lightweight. Build-isolation dependencies are pinned in `pyproject.toml`.

- `test.lock` pins every direct dependency used by the full Python suite, static checks, and fresh-clone reproduction guide.
- `tool-versions.lock` records standalone build and quality tools.
- `capture.lock` isolates the live WebSocket capture dependency.
- `canonical.lock` isolates PyArrow because Parquet byte layout is version-sensitive.
- The optional dependency groups in `pyproject.toml` describe narrower runtime capabilities.

CI repeats exact direct pins in workflow files so dependency changes are explicit in review. Transitive packages are constrained by those pinned top-level releases; the canonical published artifacts are additionally protected by schema and SHA-256 checks.
