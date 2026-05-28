# DynamicAgents

Two real-time spatial evolutionary simulations built in Python (pygame + NumPy + SciPy).
Both demonstrate emergent collective behaviour arising from simple local rules — the difference
is the social complexity of the agents.

```
python v1/main.py   ← spatial prisoner's dilemma (fast, clean)
python v2/main.py   ← social trust, kin recognition, sexual reproduction
```

---

## v1 — Spatial Prisoner's Dilemma

The classic setup. Agents move, eat, and play a one-shot game with every neighbour.
Three genes evolve under selection pressure: cooperativeness, speed, and perception.
No memory. No consent. Cooperation persists only through spatial clustering.

### Genes

| Gene | Range | Effect | Cost |
|---|---|---|---|
| `cooperativeness` | 0–1 | Determines interaction outcome | High coop exploited by defectors |
| `speed` | 0.4–3.5 | Max movement per tick | Burns extra energy each round |
| `perception` | 12–90 px | Vision range for food and neighbours | Also burns extra energy |

### Tick sequence

1. **Move** — steer toward nearest visible food (within 3× perception); wander if none visible
2. **Eat** — absorb food pellet within 10 px (+22 energy)
3. **Interact** — play one-shot game with every neighbour inside perception radius

| Combined coop | Outcome |
|---|---|
| `sum > 1.3` | Mutualism — both +2.5 energy |
| `sum < 0.7` | Fighting — both −3.5 energy |
| Mixed | Exploitation — selfish agent +3.0, cooperative agent −4.5 |

4. **Decay** — lose `0.13 + speed × 0.025 + perception × 0.001` energy each tick

### Reproduction

- Asexual. Trigger: energy ≥ 80. Cost: 33 energy from parent.
- Child spawns within 12 px with parent's genes ± mutation noise.
- Population cap: 1400.

### What to watch

The openness of the population is entirely determined by spatial clustering.
A patch of blue agents (high coop) thrives through mutualism. A red defector
entering the patch profits initially, but depletes the cluster and then fights
other defectors. This is why a mixed equilibrium stabilises rather than total defection.

---

## v2 — Social Trust, Kin Recognition, Sexual Reproduction

A significantly more complex model. Agents now maintain **relationship memory**,
require **consent** before any interaction, reproduce **sexually** only with
sufficiently trusted partners, and can use experience with known agents to infer
attitudes toward their **genetic relatives**.

### Genes (8 total)

| Gene | Range | What it does | Trade-off |
|---|---|---|---|
| `cooperativeness` | 0–1 | Interaction game payoff | High coop exploited by defectors |
| `openness` | 0–1 | Default attitude toward strangers | High openness → more interactions, more exposure |
| `selectivity` | 0–1 | Minimum attitude needed to consent to interact | High selectivity → safe but misses opportunities |
| `trustRate` | 0–1 | How fast positive experiences build memory score | High → bonds form quickly; betrayals also sting more |
| `forgiveness` | 0–1 | How much a bad interaction damages memory | Low → long grudges, slow to re-engage |
| `kinBias` | 0–1 | Weight of genetic similarity in attitude toward strangers | High → strong in-group preference |
| `speed` | 0.4–3.5 | Max movement per tick | Burns extra energy per round |
| `perception` | 12–90 px | Vision range | Also burns extra energy per round |

Reproduction is **sexual** — two parents blend all 8 genes at the midpoint, then
mutate by ±mutation. Children spawn with low energy near their parents.

### Relationship memory

Each agent holds a `{uid → {score, count, gene_snapshot}}` dictionary.

- **score** runs −1 to +1 and decays 2% per round toward zero (batch-applied every 10 ticks)
- **count** tracks total interactions with that agent (used for reproduction gating)
- **gene_snapshot** is the last observed gene vector of the other agent — enables kin recognition

### Consent gate

Before any interaction, both agents independently evaluate their attitude toward
the other. If either attitude falls below their personal selectivity threshold, the
interaction is silently skipped.

```
threshold = selectivity × 0.5 − 0.3
```

At selectivity = 0: threshold = −0.3 (accepts almost anyone).
At selectivity = 1: threshold = +0.2 (requires a genuinely positive history).

### Attitude calculation

```
attitude_i_toward_j =
  if j is known in memory:    memory_score[j]
  else:                        openness[i]   ...blended with kin signal below
```

**Kin recognition** (when j is a stranger): agent i scans a sample of its
memory for agents whose gene vector is similar to j's, weighted by `kinBias`.
This means prior experience with one agent shapes attitude toward their genetic
relatives, even before any direct interaction.

### Tick sequence

1. **Spawn food**
2. **Move** (same vectorised steering as v1)
3. **Eat food** (cKDTree nearest-pellet query)
4. **Energy decay** (same formula as v1)
5. **Interact + reproduce** — for each pair within perception range:
   - Evaluate consent (both agents must pass threshold)
   - Play interaction game (same payoff table as v1)
   - Update both agents' memory scores
   - Check reproduction eligibility

### Reproduction trigger (sexual)

A pair reproduces when **all** of the following hold:

| Condition | Value |
|---|---|
| Mutual memory score | ≥ 0.65 |
| Interaction count (each direction) | ≥ 5 separate rounds |
| Energy of both parents | ≥ 60 |
| Cooldown since last reproduction (this pair) | ≥ 80 rounds |

Cost: 20 energy from each parent. The child receives blended genes ± mutation noise.

### Visual language

| Visual element | Meaning |
|---|---|
| Orange-red agent | Low cooperativeness (defector) |
| Cyan-blue agent | High cooperativeness (cooperator) |
| Brightness | Energy level |
| **Green line** | Active social bond (mutual memory score > 0.5, ≥ 5 interactions) |
| **Gold expanding ring** | Birth event — a new agent just spawned |
| Glow + trail | Bloom from the float32 canvas; trail persistence controlled by slider |

### Chart (bottom of panel)

| Line | Colour | What it shows |
|---|---|---|
| `coop` | Blue | Average cooperativeness |
| `open` | Green | Average openness — watch this drift to diagnose social pressure |
| `sel` | Orange | Average selectivity |
| `pop` | Grey | Population (normalised) |

**Watch the openness line.** If it drifts upward, the population is selecting for
sociability. If it collapses toward 0, isolated or highly selective phenotypes have
won — usually a sign that defectors are present and trust has been broken at scale.

### Scenarios to try

**Trust collapse under food scarcity**
Drop food rate to 2–3. Agents must rely on mutualism bonds for energy income.
Agents with no bonds starve. Social density should drop sharply then recover as
only the well-connected survive.

**Kin network formation**
Set kinBias high in the initial population (it is random, so just watch). Agents
that have high kinBias and positive memory will extend trust to genetic relatives
before ever meeting them directly, seeding clusters that look like families.

**Mutation breaks kin recognition**
Crank mutation to 0.7+. Gene vectors in memory no longer match offspring reliably.
Kin recognition misfires constantly. Social structure becomes incoherent — watch
the openness and selectivity lines destabilise.

**Observe the bond network**
Use speed = 1 (slow) and watch green bond lines accumulate and dissolve in real time.
Stable cooperator clusters should show dense green webs. Defector patches will be
sparse — they interact but never form bonds.

---

## Controls (both versions)

| Slider | Range | Default | Effect |
|---|---|---|---|
| **speed** | 1–20 (v2) / 1–30 (v1) ticks/frame | 3–5 | Simulation clock rate. No effect on dynamics. |
| **food rate** | 0–30 pellets/tick | 8 | Dominant lever. Low food → strong selection on social traits. |
| **mutation** | 0.00–1.00 | 0.15 | Gene drift per reproduction. 0 = locked lineages; 0.6+ = chaos. |
| **trail decay** | 0.50–0.99 | 0.78 | How fast motion trails fade. 0.99 = long comet tails. |

| Key / Button | Action |
|---|---|
| **PLAY / PAUSE** or `Space` | Toggle simulation |
| **RESET** or `R` | Fresh random population |
| **trails ON/OFF** or `T` | Toggle trail persistence |

---

## Architecture

```
DynamicAgents/
  v1/
    config.py       ← all constants
    simulation.py   ← 3-gene agent, cKDTree interactions, vectorised NumPy
    main.py         ← pygame loop, surfarray rendering, glow, sliders
  v2/
    config.py       ← all constants (extended for memory/trust params)
    simulation.py   ← 8-gene agent, memory, consent, sexual reproduction
    main.py         ← adds bond lines, birth rings, 4-line chart
  README.md
```

### Rendering pipeline (both versions)

1. Decay the persistent float32 canvas by `trail_decay` each frame
2. Paint agent positions with `np.maximum.at` (vectorised, no per-agent loop)
3. Half-resolution Gaussian blur of the canvas → bloom layer
4. Composite `canvas + bloom × GLOW_BOOST` → uint8 → `pygame.surfarray.make_surface`
5. Blit alpha-channel overlays on top: bond lines (v2), birth rings (v2), food dots

### Simulation performance

- **Movement**: fully NumPy-vectorised (no Python loop over agents)
- **Neighbour search**: `scipy.spatial.cKDTree.query_pairs` → O(n log n)
- **Interaction loop**: Python loop over pairs, capped at 2500/tick in v2
- **Memory operations**: O(1) dict lookups per pair; batch-decayed every 10 ticks
- **Bond cache**: rebuilt every 8 ticks, not every frame

---

## Dependencies

```bash
pip install pygame numpy scipy matplotlib
```
