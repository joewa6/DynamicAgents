# DynamicAgents

A real-time spatial evolutionary simulation — a **spatial prisoner's dilemma** rendered with live glow effects and an interactive control panel. Watch cooperation and defection compete, cluster, and co-evolve as emergent patterns arise from simple local rules.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Pygame](https://img.shields.io/badge/Pygame-2.x-green)
![NumPy](https://img.shields.io/badge/NumPy-vectorised-orange)
![SciPy](https://img.shields.io/badge/SciPy-cKDTree-lightblue)

---

## Quick start

```bash
pip install pygame numpy scipy matplotlib
python main.py
```

Press **PLAY** in the panel (or `Space`) to start.

---

## What the simulation is

Each agent is a dot with three genes and an energy level. Energy is the single currency of survival: gain enough to reproduce, lose it all and die. Agents move around a bounded 900×500 world, eat food pellets for energy, and interact with neighbours. The interactions are the core of the simulation — they implement a one-shot game whose outcome is determined entirely by the cooperativeness scores of both agents.

The result is a **spatial prisoner's dilemma**: classical game theory predicts cooperation collapses in well-mixed populations, but spatial structure lets cooperator clusters persist, creating a rich mixed equilibrium rather than total defection.

---

## Agent properties

### State (changes every tick)

| Property | Description |
|---|---|
| `position` | (x, y) in the world |
| `velocity` | (vx, vy), capped by the `speed` gene |
| `energy` | 0 – 100. The agent dies when this hits 0; it reproduces when it exceeds 80 |

### Genes (inherited, mutate slowly)

| Gene | Range | Effect |
|---|---|---|
| `cooperativeness` | 0 – 1 | Determines interaction outcome. The central evolving trait. |
| `speed` | 0.4 – 3.5 | Max movement per tick. Faster agents find food sooner but burn more energy existing. |
| `perception` | 12 – 90 px | How far the agent can see food and neighbours. Wide perception also costs energy. |

The metabolic tension is intentional: every advantage has a cost. A fast, wide-seeing agent will starve in a food desert even if it never loses a fight.

---

## What happens each tick

Four steps occur in sequence for every agent:

### 1. Move

Each agent steers toward the nearest food pellet within **3× its perception radius**. If no food is visible, it wanders randomly. Velocity is capped at the `speed` gene value. Agents bounce off the world boundary.

### 2. Eat

If an agent is within **10 px** of a food pellet, it absorbs it:

```
energy += 22  (capped at 100)
```

The pellet is consumed and removed. One pellet can only be eaten by one agent per tick.

### 3. Interact

With every neighbour inside its perception radius, the agent plays a one-shot game determined by both agents' cooperativeness scores:

| Combined coop score | Outcome |
|---|---|
| Both high (`sum > 1.3`) | **Mutualism** — both gain +2.5 energy |
| Both low (`sum < 0.7`) | **Fighting** — both lose −3.5 energy |
| Mixed | **Exploitation** — the more selfish one gains +3.0; the cooperative one loses −4.5 |

All pair interactions for a tick are resolved simultaneously (vectorised via `np.add.at`), so no agent has an ordering advantage.

### 4. Decay

Every agent loses a baseline amount of energy per tick, plus extra for their genes:

```
energy -= 0.13 + (speed × 0.025) + (perception × 0.001)
```

No agent gets a free lunch just by existing.

---

## Reproduction and death

- **Reproduce** when energy ≥ 80. The parent pays 33 energy; a child spawns within 12 px with genes copied from the parent plus random mutations.
- **Die** when energy ≤ 0. The slot is recycled for future offspring.
- **Population cap**: 1400 agents maximum. Reproduction is blocked above this limit.

### Mutation

Each child gene is nudged by:

```
new_gene = clamp(parent_gene + uniform(-range, range) × mutation × 2, lo, hi)
```

Where `mutation` is the slider value (0 – 1). High mutation → rapid genetic drift, unstable lineages. Low mutation → slow change, strong inheritance.

---

## The core dynamic

This is a **spatial prisoner's dilemma**. In a well-mixed population, defectors (low coop) always win — they exploit cooperators and pay no cost when fighting each other if cooperators are abundant. Classical game theory predicts cooperation collapses.

**Space changes everything.** Because agents move locally and interact with neighbours, cooperators naturally cluster. A patch of high-coop agents (shown in blue/cyan) thrives through constant mutualism bonuses. A defector (red/orange) that enters the cluster initially profits from exploitation, but as it depletes cooperative neighbours it eventually fights other defectors and dies. This is why the simulation typically stabilises at a mixed equilibrium — spatial structure protects cooperator clusters long enough to persist.

---

## Controls

### Sliders (drag in the right panel)

| Slider | Range | Default | Effect |
|---|---|---|---|
| **speed** | 1 – 30 ticks/frame | 5 | How fast simulation time passes. No effect on dynamics, only on how quickly you see them. |
| **food rate** | 0 – 30 pellets/tick | 8 | **Most powerful lever.** High food → weak selection on cooperativeness, large mixed population. Low food → every interaction is life or death; cooperators in defector-heavy patches are wiped out, but cooperator clusters thrive. The interesting dynamics live at 4 – 12. |
| **mutation** | 0.00 – 1.00 | 0.15 | Genetic drift magnitude. 0 = locked lineages; 0.5+ = genes drift randomly, strategies don't stabilise. Sweet spot: 0.10 – 0.25. |
| **trail decay** | 0.50 – 0.99 | 0.78 | How fast motion trails fade per frame. 0.50 = trails vanish almost immediately (sharp). 0.99 = long luminous comet tails showing recent paths. |

### Buttons

| Button / Key | Action |
|---|---|
| **PLAY / PAUSE** or `Space` | Toggle simulation |
| **RESET** or `R` | Fresh random population |
| **trails ON/OFF** or `T` | Toggle trail persistence entirely |

---

## Visual language

| Colour | Meaning |
|---|---|
| Orange-red | Low cooperativeness (defector) |
| Violet | Mid cooperativeness |
| Cyan-blue | High cooperativeness (cooperator) |
| Brightness | Energy level — full brightness = high energy, near-black = almost dead |
| Lime green dots | Food pellets |
| Glow halo | Bloom effect proportional to the trail canvas intensity at that position |

---

## Live stats (right panel)

| Stat | Description |
|---|---|
| population | Number of living agents |
| round | Simulation ticks elapsed |
| food | Current food pellets on the field |
| avg energy | Mean energy across all agents |
| avg coop | Mean cooperativeness — watch this drift toward 0 (defectors win) or hold above 0.5 (cooperators persist) |
| avg speed | Mean speed gene |
| avg percep | Mean perception radius |

The mini graph at the bottom of the panel shows **avg coop** (blue) and **population** (grey) over the last 300 recorded frames.

---

## Scenarios to try

**Cooperators collapse**
Set food rate to 2. Watch avg coop drop as every interaction becomes critical and defectors outcompete. Often the population crashes and recovers with a different genetic balance.

**Stable cooperator clusters**
Set food rate to 8 – 12, mutation to 0.12. Blue patches form, hold their ground, and visibly resist orange invasion along their edges.

**Genetic drift**
Set mutation to 0.60. Genes randomise every few generations; no stable strategy emerges and cooperativeness oscillates wildly.

**Fast-forward to equilibrium**
Set speed to 20, watch for 1000+ rounds, then slow back to 5 to study the resulting population in detail.

**Comet trails**
Set trail decay to 0.97 and watch the luminous paths agents carve through the world, revealing flow patterns and congregation zones.

---

## Project structure

```
DynamicAgents/
  config.py       ← all constants and window dimensions
  simulation.py   ← agent state, tick logic, cKDTree interactions
  main.py         ← pygame game loop, rendering, slider UI
  README.md
```

### Key implementation notes

- **Vectorised movement**: the food-steering and speed-clamping are fully NumPy — no per-agent Python loops.
- **cKDTree interactions**: `scipy.spatial.cKDTree.query_pairs` finds all neighbour pairs in O(n log n). Energy deltas are accumulated with `np.add.at` and applied in one pass.
- **Surfarray rendering**: agents are painted into a float32 NumPy canvas with `np.maximum.at`, then a Gaussian bloom is composited on top before blitting via `pygame.surfarray.make_surface`. This avoids per-agent `draw.circle` calls entirely.
- **Food eating**: `cKDTree.query` finds the nearest pellet per agent in O(n log m); conflict resolution (one pellet per agent, one agent per pellet) runs in a short Python loop over the small result set.

---

## Dependencies

| Package | Purpose |
|---|---|
| `pygame` | Window, event loop, surfarray blit |
| `numpy` | Vectorised agent state arrays |
| `scipy` | cKDTree for O(n log n) neighbour search |
| `matplotlib` | LinearSegmentedColormap for agent colouring |
