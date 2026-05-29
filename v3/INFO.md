# DynamicAgents V3: How It Works

V3 is an interactive group-dynamics toy model. It is not trying to be a full
ecology simulator. The current design goal is:

```text
small population + visible social structure + tunable founding traits
```

The fun part is watching local rules create temporary groups, isolates, bonded
pairs, blobs, collapses, and little social phase transitions.

## Big Picture

The world is a 900 x 600 continuous 2D space.

Agents move around, consume food, interact with nearby agents, form pairwise
bonds, and sometimes reproduce through strong social bonds. Each agent has ten
heritable genes that shape how it moves, who it interacts with, and how those
interactions affect energy and bonds.

The simulation is intentionally tuned for small groups:

- initial agents: 50
- max population: 200
- target population: 80
- initial food: 45
- max food: 80

The target population matters. Reproduction is damped as population approaches
the target, so the sim does not become only a survival/explosion game.

## Tick Loop

Each simulation tick does roughly this:

1. Spawn new food according to the food-rate control.
2. Build a spatial grid for nearby-agent lookup.
3. For each live agent:
   - steer toward visible food, or wander randomly
   - cap velocity by its speed gene
   - move and bounce off walls
   - eat nearby food
   - scan nearby grid cells for other agents
   - decide whether interactions happen
   - update energy and pairwise bonds
   - possibly queue a bonded reproduction event
   - pay metabolic, speed, and perception energy costs
4. Remove eaten food.
5. Kill agents whose energy reaches zero.
6. Spawn queued offspring.
7. Periodically decay old bonds and remove old birth rings.

## Agents

Each agent has:

- position: `x`, `y`
- velocity: `vx`, `vy`
- energy: `e`
- age
- generation number
- parent IDs
- permanent unique ID
- gene vector

Agents are stored in fixed slots up to `MAX_POP`. Slots can be reused after an
agent dies, but each new agent gets a new UID.

## Genes

Each gene has a fixed range. Most are 0..1, but movement and metabolism genes use
their own physical-ish ranges.

| Gene | Range | Meaning |
|---|---:|---|
| `coop` | 0..1 | How cooperative/generous the agent is during interactions. |
| `openness` | 0..1 | Probability of accepting an interaction. |
| `selectivity` | 0..1 | How genetically similar another agent must be before interaction. |
| `forgiveness` | 0..1 | Dampens negative bond updates after bad interactions. |
| `kin_bias` | 0..1 | Extra energy reward for interacting with genetically similar agents. |
| `speed` | 0.4..3.5 | Movement speed cap, with extra energy cost. |
| `perception` | 15..90 | Food/neighbour vision radius, with extra energy cost. |
| `metabolism` | 0.05..0.30 | Baseline energy drain. |
| `bond_thresh` | 0.3..0.9 | Bond strength needed for reproduction. |
| `fertility` | 0..1 | Chance gate for bonded reproduction. |

## Founding Distributions

Before a run starts, the setup screen lets you choose initial distributions for
each gene.

For every gene you can set:

- functional form: `uniform`, `normal`, `bimodal`, `low-skew`, `high-skew`
- mean
- standard deviation

These settings affect only newly reset founding populations. Offspring are made
by crossover and mutation from their parents.

The setup screen has:

- an `All attributes` tab showing all distributions on normalized 0..1 scales
- one tab per gene with a larger distribution preview
- `balanced` preset
- `random` preset
- `start run`

The compact founding-gene section in the sidebar is only a quick editor. The
main setup screen is the real founding-population editor.

## Genetics

Founders are sampled from the selected per-gene distributions.

Offspring are produced by crossover:

```text
child_gene = alpha * parent_a_gene + (1 - alpha) * parent_b_gene
```

Then mutation may perturb each gene. Mutation is clamped to the gene's allowed
range.

Genetic distance is normalized Euclidean distance across all genes. It is used
for:

- selectivity gates
- kin-bias bonus

## Food And Energy

Food is a soft ecological pressure, not the desired center of the model.

Food:

- appears at `food_rate`
- is capped at `MAX_FOOD`
- gives `FOOD_ENERGY = 20`
- can be eaten within a 10px radius

The food-rate slider supports fractional values. Internally, fractional food is
accumulated in `food_carry`, so `0.1` means roughly one food item every ten
ticks.

Energy is capped at `MAX_ENERGY = 100`.

Each tick, agents pay:

```text
BASE_DECAY + metabolism + speed_cost + perception_cost
```

where:

```text
speed_cost = speed * 0.025
perception_cost = perception * 0.001
```

So fast, perceptive, high-metabolism agents are more expensive to maintain.

## Interactions

Agents only consider nearby agents from adjacent spatial-grid cells.

An interaction requires:

1. both agents are within the smaller perception radius
2. both pass openness checks
3. both pass selectivity checks based on genetic distance

Interaction outcomes depend mostly on the two `coop` values:

### Mutualism

If both agents are cooperative enough:

```text
coop_i + coop_j > 1.3
```

then:

- both gain energy
- their bond increases

### Fight

If both are competitive:

```text
coop_i + coop_j < 0.7
```

then:

- both lose energy
- their bond decreases

### Exploitation

Mixed cooperation/competition creates an exploitative interaction:

- lower-coop agent gains energy
- higher-coop agent loses energy
- bond decreases

Negative bond updates are softened by average forgiveness.

## Bonds

Bonds are pairwise relational state.

Each bond stores:

- score: 0..1
- rounds: number of live interactions
- last interaction tick
- positive interaction count
- negative interaction count

Only one canonical bond entry exists per pair.

Active bonds are those with score at least `BOND_ACTIVE_THRESHOLD = 0.35`.
The frontend draws active bonds as green lines.

Bonds decay over time when stale. Very weak bonds are deleted.

## Reproduction

Reproduction is deliberately social, not just energy-based.

A pair can reproduce only when:

- bond score is above both agents' required threshold
- bond has existed for at least `MIN_BOND_ROUNDS = 60`
- both parents have at least `REPRO_ENERGY = 90`
- population is below `MAX_POP`
- a fertility chance passes
- the carrying-capacity birth gate passes

The birth gate is:

```text
birth_gate = clamp(1 - population / target_population, 0, 1)
```

This means bonded reproduction slows as population approaches the target. At or
above the target, reproduction is effectively shut off. This helps structure
matter more than runaway population growth.

When a child is born:

- both parents pay `REPRO_COST = 45`
- one child is spawned near the parents
- a yellow birth ring appears
- the parents' bond score is reduced as a refractory period

## Visual Encoding

Main canvas:

- agents are colored from red/competitive to blue/cooperative
- agent size indicates energy
- agents have a pale outline for visibility
- food is very faint pale grey
- active bonds are green lines
- yellow rings mark recent birth events

Sidebar:

- population counters
- speed, food, target population, mutation controls
- gene-average spider/radar diagram
- collapsed quick founding-gene editor
- legend

Bottom charts:

- population + selected gene history
- configurable phase plot

The phase plot can show any two agent traits or environmental variables. It also
has a heat mode that bins recent points into a density map.

## Speed Modes

Speed controls simulation ticks relative to visual frames.

Positive values:

- `1`: one tick per frame
- `10`: ten ticks per frame
- `100`: one hundred ticks per frame
- `1000`: one thousand ticks per frame

Negative values:

- `-10`: one tick every ten frames
- `-100`: one tick every hundred frames
- `-1000`: one tick every thousand frames

`MAX` runs as many ticks as possible for most of each visual-frame interval,
then yields so the UI can still update.

## Server And Deployment

V3 is a Julia app.

Local run:

```bash
cd v3
julia --project=. -e 'using Pkg; Pkg.instantiate()'
julia --threads=auto --project=. run.jl
```

Open:

```text
http://localhost:8000
```

The server uses one public port. It serves:

- static frontend at `/`
- WebSocket stream at `/ws`

That one-port design is important for Render deployment.

## Render

The repository has:

- `render.yaml`
- `v3/Dockerfile`

Render can deploy this as a Docker web service. It provides the `PORT`
environment variable, and V3 binds to it automatically.

## What V3 Is Good For

V3 is good for:

- playing with founding distributions
- watching group formation
- seeing social structure emerge or fail
- intuition-building
- demoing the model to friends

V3 is not yet the serious measurement scanner. That role belongs to V4.

## What V4 Adds

V4 is planned as a headless social-phase-space scanner:

- many runs
- Latin hypercube sampling
- population metrics
- bond-network metrics
- social-structure metrics
- structure scoring
- PCA and parameter-vs-score plots

V3 is the interactive playground. V4 is the measurement rig.
