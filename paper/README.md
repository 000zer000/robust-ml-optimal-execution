# Research paper

**Robust ML-Assisted Optimal Execution in Limit Order Books: Causal Microstructure Forecasting, Model Predictive Control, and Low-Latency Systems Evaluation**

- [`Robust_ML_Optimal_Execution_Research_Paper.pdf`](Robust_ML_Optimal_Execution_Research_Paper.pdf) — compiled 16-page manuscript
- [`main.tex`](main.tex) — LaTeX source
- [`references.bib`](references.bib) — bibliography
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

The manuscript develops the mathematical formulation, execution infrastructure, causal prediction models, model-predictive controllers, imitation-learning and PPO policies, robustness/statistical methodology, and CPU/GPU performance study implemented in this repository.
