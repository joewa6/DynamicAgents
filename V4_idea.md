# DynamicAgents V4 Idea

V3 is the saved fun/stable interactive build.

V4 should start from the rapid/performance-oriented version that existed just
before the V3 slow-motion speed control was added.

That previous rapid version had the sim loop running fast enough for performance
work, whereas V3 now intentionally paces the loop for human visualization:

- server loop paced around 20 visual frames per second
- positive speed values mean ticks per visual frame
- negative speed values mean one tick every 10/100/1000 frames
- useful for watching groups form directly

For V4, revive the performance orientation, but only after defining what a
good run means. V4 should be a measurement framework first.

- headless or decoupled simulation loop
- fast parameter sweeps
- scoring across many founding distributions
- visualization as a snapshot consumer, not the thing pacing the sim

Do not start with a million-run search. That would produce a cloud of points
without a scientific target. Start by measuring social structure.

The V4 scoring target should not simply reward survival or population growth.
The useful regime is:

- population stable
- multiple persistent bond communities
- non-zero turnover
- no runaway expansion
- no collapse
- no monoculture

Candidate score shape:

```text
score =
  survival
+ community_persistence
+ bond_modularity
+ turnover
- extinction
- monoculture
- explosion
```

This keeps V4 from discovering only the boring ecology result:

```text
food too low = death
food too high = blob growth
```

## V4: Social-Phase-Space Scanner

V4 should answer:

```text
Which parameter regimes produce persistent, non-trivial social structure?
```

Not:

```text
Which parameter regimes merely keep agents alive?
```

The first V4 artifact should be a headless scanner that runs many simulations
and records structural metrics.

## Per-Run Metrics

Population:

- final_population
- mean_population
- population_variance
- extinction_time

Bond network:

- mean_bond_strength
- bond_density
- largest_component_size
- num_components

Social structure:

- modularity
- clustering_coefficient
- mean_degree
- degree_gini

Build graph `G` from active bonds. Social structure metrics should come from
that graph, not just from raw population survival.

## Scoring

First rough score:

```text
structure_score =
    modularity
  + clustering_coefficient
  + persistence_bonus
  - extinction_penalty
  - monoculture_penalty
  - explosion_penalty
```

This lets a run be:

```text
survived but socially boring
```

which is different from:

```text
survived and formed stable factions
```

## First Experiment

Run:

- 100 runs
- 5000 ticks each

Sample with Latin hypercube sampling:

- food_rate
- mutation
- initial gene means
- initial gene variances

Then plot:

- parameter -> structure_score
- PCA(parameters) colored by structure_score

## First Hypothesis

The interesting phase transition is probably not food.

It is likely:

```text
cooperation vs selectivity vs forgiveness
```

Expected regimes:

- high cooperation, high selectivity, medium forgiveness -> persistent tribes
- high cooperation, low selectivity -> one giant blob
- low cooperation, low forgiveness -> fragmentation or collapse

V4 should test this before expanding the search space.

## Implementation Shape

Add a `v4/` project based on V3 simulation logic, but separate:

- `scanner.jl`: run batches
- `metrics.jl`: population and graph metrics
- `sampling.jl`: Latin hypercube parameter generation
- `score.jl`: structure score
- `export.jl`: CSV/JSONL run outputs
- optional viewer that consumes saved snapshots

V4 is not a bigger simulator yet.

V4 is the measurement layer that tells us what simulator changes matter.
