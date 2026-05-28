# DynamicAgents V4 Scanner

V4 is a measurement framework for scanning social phase space.

Run a batch:

```bash
julia --project=v4 v4/run.jl 100
```

Larger batch:

```bash
julia --project=v4 v4/run.jl 1000 --ticks 5000 --seed 7 --out v4/results/scan_1000.csv
```

Outputs:

- CSV results at the `--out` path
- HTML report next to it, e.g. `v4/results/scan_1000.html`

The scanner uses Latin hypercube sampling over:

- food rate
- mutation rate
- target population
- initial gene means
- initial gene standard deviations

Each run records population metrics, bond-network metrics, social-structure
metrics, a rough `structure_score`, and PCA coordinates over the sampled
parameter space.
