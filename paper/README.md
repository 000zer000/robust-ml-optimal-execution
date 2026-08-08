# Research paper

**Robust ML-Assisted Optimal Execution in Limit Order Books: Causal Microstructure Forecasting, Model Predictive Control, and Low-Latency Systems Evaluation**

- [`Robust_ML_Optimal_Execution_Research_Paper.pdf`](Robust_ML_Optimal_Execution_Research_Paper.pdf) — compiled manuscript
- [`main.tex`](main.tex) — LaTeX source
- [`references.bib`](references.bib) — bibliography
- [`CLAIM_TRACEABILITY.md`](CLAIM_TRACEABILITY.md) — headline claims mapped to committed evidence
- [`figures/`](figures/) — publication figures
- [`make_figures.py`](make_figures.py) — repository-relative figure-generation script

Regenerate the figures from the committed Step 25–30 reports from any working directory:

```bash
python -m pip install -e '.[paper]'
python paper/make_figures.py
```

Use `--output-dir PATH` to render into a scratch directory without replacing the committed
publication figures. The plotted values and layout are deterministic for the pinned dependencies;
PDF/PNG bytes can still vary across operating-system font and graphics stacks.

Compile the paper from the repository root with [Tectonic](https://tectonic-typesetting.github.io/):

```bash
make paper-build
```

The first build downloads the standard TeX bundle. The target validates manuscript claims against
the committed reports before compiling and writes `output/pdf/Robust_ML_Optimal_Execution_Research_Paper.pdf`.
It leaves the tracked canonical PDF unchanged, so a reader can build from a fresh clone without
dirtying the source tree. `SOURCE_DATE_EPOCH` is fixed by the target for repeatable metadata; exact
PDF bytes can still vary with the Tectonic engine or bundle version. To check claim consistency
without compiling, run `make paper-check`.

The manuscript develops the mathematical formulation, execution infrastructure, causal prediction
models, model-predictive controllers, imitation-learning and PPO policies, robustness/statistical
methodology, and CPU/GPU performance study implemented in this repository. Strategy findings are
registered controlled-simulator evidence; the paper does not present historical-market backtest
results.
