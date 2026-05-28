"""
v2 simulation — social trust, kin recognition, sexual reproduction.

Agents now carry 8 genes and maintain a relationship memory that decays
over time.  Before any interaction both agents must consent (attitude ≥
selectivity threshold).  Reproduction is sexual: two bonded agents blend
genes and pay an energy cost.  Kin recognition lets agents carry prior
experience with one agent forward to unknown genetic relatives.
"""

from dataclasses import dataclass, field

import numpy as np
from scipy.spatial import cKDTree

from config import (
    W, H, MAX_ENERGY, FOOD_ENERGY, ENERGY_DECAY,
    REPRO_THRESHOLD, REPRO_COST, REPRO_SCORE_MIN,
    REPRO_COUNT_MIN, REPRO_COOLDOWN, MAX_POP, MAX_FOOD,
    FOOD_EAT_RADIUS, INIT_AGENTS, INIT_FOOD,
    MEMORY_DECAY, MAX_MEMORY, MAX_PAIRS_TICK,
    BOND_MIN_SCORE, BOND_MIN_COUNT, BOND_CACHE_FREQ, GC_FREQ,
)


@dataclass
class BirthRing:
    x: float
    y: float
    born: int   # round number when born, used for animation age


class Simulation:
    def __init__(self):
        self.reset()

    # ------------------------------------------------------------------ #
    #  Initialisation                                                      #
    # ------------------------------------------------------------------ #

    def reset(self):
        n = INIT_AGENTS
        self.x            = np.random.uniform(2, W - 2, n)
        self.y            = np.random.uniform(2, H - 2, n)
        self.vx           = np.random.uniform(-1, 1, n)
        self.vy           = np.random.uniform(-1, 1, n)
        self.e            = np.random.uniform(40, 70, n)
        self.alive        = np.ones(n, dtype=bool)

        # 8 genes
        self.coop         = np.random.uniform(0, 1, n)
        self.openness     = np.random.uniform(0.2, 0.8, n)
        self.selectivity  = np.random.uniform(0, 0.8, n)
        self.trustRate    = np.random.uniform(0.1, 0.9, n)
        self.forgiveness  = np.random.uniform(0.1, 0.9, n)
        self.kinBias      = np.random.uniform(0, 0.6, n)
        self.spd          = np.random.uniform(0.7, 2.7, n)
        self.perc         = np.random.uniform(18, 70, n)

        # Stable unique IDs — never reused when a slot is recycled
        self.uid          = np.arange(n, dtype=np.int64)
        self._uid_counter = n

        # Food
        self.fx = np.random.uniform(0, W, INIT_FOOD)
        self.fy = np.random.uniform(0, H, INIT_FOOD)

        # memory[uid_owner][uid_other] = {'s': score, 'n': count, 'g': gene_vec}
        # Scores are kept current via batch decay every 10 ticks.
        self.memory: dict[int, dict[int, dict]] = {}

        # (min_uid, max_uid) → round when the pair may next reproduce
        self.repro_cd: dict[tuple, int] = {}

        # Visual effects
        self.birth_rings: list[BirthRing] = []

        # Cached bond list rebuilt every BOND_CACHE_FREQ ticks
        self._bond_cache: list[tuple] = []

        self.round = 0

    # ------------------------------------------------------------------ #
    #  Public tick                                                         #
    # ------------------------------------------------------------------ #

    def tick(self, food_rate: int = 8, mutation: float = 0.15) -> None:
        self._spawn_food(food_rate)
        self._move()
        self._eat_food()
        self._decay_energy()
        self._interact_and_reproduce(mutation)
        self._cull()

        self.round += 1

        if self.round % 10 == 0:
            self._batch_decay_memory()
        if self.round % BOND_CACHE_FREQ == 0:
            self._rebuild_bond_cache()
        if self.round % GC_FREQ == 0:
            self._gc()

    # ------------------------------------------------------------------ #
    #  Movement (vectorised)                                               #
    # ------------------------------------------------------------------ #

    def _move(self) -> None:
        idx = np.where(self.alive)[0]
        if len(idx) == 0:
            return
        x, y = self.x[idx], self.y[idx]

        if len(self.fx) > 0:
            dx    = self.fx[None, :] - x[:, None]
            dy    = self.fy[None, :] - y[:, None]
            dist2 = dx ** 2 + dy ** 2
            perc2 = (self.perc[idx] * 3) ** 2
            masked = np.where(dist2 < perc2[:, None], dist2, np.inf)
            nn     = np.argmin(masked, axis=1)
            ar     = np.arange(len(idx))
            found  = masked[ar, nn] < np.inf
            d      = np.sqrt(masked[ar, nn] + 1e-9)
            sx     = np.where(found, dx[ar, nn] / d, 0.0)
            sy     = np.where(found, dy[ar, nn] / d, 0.0)
            f      = 0.1 * self.spd[idx]
            wander = ~found
            self.vx[idx] += sx * f + np.random.uniform(-0.1, 0.1, len(idx)) * wander
            self.vy[idx] += sy * f + np.random.uniform(-0.1, 0.1, len(idx)) * wander
        else:
            self.vx[idx] += np.random.uniform(-0.22, 0.22, len(idx))
            self.vy[idx] += np.random.uniform(-0.22, 0.22, len(idx))

        spd   = np.sqrt(self.vx[idx] ** 2 + self.vy[idx] ** 2) + 1e-9
        over  = spd > self.spd[idx]
        scale = np.where(over, self.spd[idx] / spd, 1.0)
        self.vx[idx] *= scale
        self.vy[idx] *= scale
        self.x[idx]  += self.vx[idx]
        self.y[idx]  += self.vy[idx]

        self.vx[idx] = np.where(self.x[idx] < 2,     np.abs(self.vx[idx]),  self.vx[idx])
        self.vx[idx] = np.where(self.x[idx] > W - 2, -np.abs(self.vx[idx]), self.vx[idx])
        self.vy[idx] = np.where(self.y[idx] < 2,     np.abs(self.vy[idx]),  self.vy[idx])
        self.vy[idx] = np.where(self.y[idx] > H - 2, -np.abs(self.vy[idx]), self.vy[idx])
        self.x[idx]  = np.clip(self.x[idx], 2, W - 2)
        self.y[idx]  = np.clip(self.y[idx], 2, H - 2)

    # ------------------------------------------------------------------ #
    #  Food                                                                #
    # ------------------------------------------------------------------ #

    def _spawn_food(self, rate: int) -> None:
        n_new = min(rate, MAX_FOOD - len(self.fx))
        if n_new > 0:
            self.fx = np.append(self.fx, np.random.uniform(0, W, n_new))
            self.fy = np.append(self.fy, np.random.uniform(0, H, n_new))

    def _eat_food(self) -> None:
        if len(self.fx) == 0:
            return
        idx = np.where(self.alive)[0]
        if len(idx) == 0:
            return
        tree  = cKDTree(np.stack([self.fx, self.fy], axis=1))
        pos   = np.stack([self.x[idx], self.y[idx]], axis=1)
        dists, fi = tree.query(pos, distance_upper_bound=FOOD_EAT_RADIUS)
        n_food = len(self.fx)
        valid  = dists < FOOD_EAT_RADIUS
        eaten  = set()
        for k in range(len(idx)):
            if valid[k] and fi[k] < n_food and fi[k] not in eaten:
                self.e[idx[k]] = min(MAX_ENERGY, self.e[idx[k]] + FOOD_ENERGY)
                eaten.add(int(fi[k]))
        if eaten:
            keep   = np.array([j for j in range(n_food) if j not in eaten])
            self.fx = self.fx[keep] if len(keep) else np.empty(0)
            self.fy = self.fy[keep] if len(keep) else np.empty(0)

    # ------------------------------------------------------------------ #
    #  Energy decay                                                        #
    # ------------------------------------------------------------------ #

    def _decay_energy(self) -> None:
        idx = np.where(self.alive)[0]
        self.e[idx] -= ENERGY_DECAY + self.spd[idx] * 0.025 + self.perc[idx] * 0.001

    # ------------------------------------------------------------------ #
    #  Memory helpers                                                      #
    # ------------------------------------------------------------------ #

    def _gene_vec(self, i: int) -> np.ndarray:
        """Normalised 8-element gene vector for slot i."""
        return np.array([
            self.coop[i], self.openness[i], self.selectivity[i],
            self.trustRate[i], self.forgiveness[i], self.kinBias[i],
            self.spd[i] / 3.5, self.perc[i] / 90.0,
        ], dtype=np.float32)

    def _attitude(self, i: int, uid_i: int, uid_j: int, gvec_j: np.ndarray) -> float:
        """How agent i feels about agent j right now.

        Returns a value in roughly [-1, 1].  Positive = willing to engage.
        Default for total strangers is openness[i].
        If kinBias is significant, blends in experience with genetic relatives.
        """
        mem_i = self.memory.get(uid_i, {})

        if uid_j in mem_i:
            return float(mem_i[uid_j]['s'])

        direct = float(self.openness[i])

        # Kin recognition: blend in experience with gene-similar agents
        kb = float(self.kinBias[i])
        if kb > 0.05 and len(mem_i) > 0 and np.random.random() < 0.4:
            sample = list(mem_i.values())
            if len(sample) > 12:
                sample = [sample[k] for k in np.random.choice(len(sample), 12, replace=False)]
            kin_s = kin_w = 0.0
            for entry in sample:
                if 'g' not in entry:
                    continue
                sim = 1.0 - float(np.mean(np.abs(gvec_j - entry['g'])))
                kin_s += entry['s'] * sim
                kin_w += sim
            if kin_w > 0:
                direct = direct * (1.0 - kb) + (kin_s / kin_w) * kb

        return direct

    def _update_memory(self, uid_owner: int, uid_other: int,
                       delta_e: float, owner_i: int, other_j: int) -> None:
        if uid_owner not in self.memory:
            self.memory[uid_owner] = {}
        mem = self.memory[uid_owner]

        current = mem[uid_other]['s'] if uid_other in mem else float(self.openness[owner_i])
        count   = mem[uid_other]['n'] if uid_other in mem else 0

        tr  = float(self.trustRate[owner_i])
        fg  = float(self.forgiveness[owner_i])
        upd = tr * 0.25 if delta_e > 0 else -(1.0 - fg) * 0.35
        new_score = float(np.clip(current + upd, -1.0, 1.0))

        mem[uid_other] = {
            's': new_score,
            'n': count + 1,
            'g': self._gene_vec(other_j),
        }

        # Evict the weakest memory if over the limit
        if len(mem) > MAX_MEMORY:
            worst = min(mem, key=lambda u: abs(mem[u]['s']))
            del mem[worst]

    def _batch_decay_memory(self) -> None:
        """Multiply all stored scores by MEMORY_DECAY^10 (called every 10 ticks)."""
        factor = MEMORY_DECAY ** 10
        for mem in self.memory.values():
            for entry in mem.values():
                entry['s'] *= factor

    # ------------------------------------------------------------------ #
    #  Interactions + reproduction (main per-tick social loop)             #
    # ------------------------------------------------------------------ #

    def _interact_and_reproduce(self, mutation: float) -> None:
        idx = np.where(self.alive)[0]
        if len(idx) < 2:
            return

        pos   = np.stack([self.x[idx], self.y[idx]], axis=1)
        tree  = cKDTree(pos)
        max_r = float(self.perc[idx].max())

        raw = tree.query_pairs(r=max_r, output_type='ndarray')
        if len(raw) == 0:
            return

        pi, pj = raw[:, 0], raw[:, 1]
        gi, gj = idx[pi], idx[pj]

        # Filter to actual per-pair perception radius
        r_ij  = np.minimum(self.perc[gi], self.perc[gj])
        dx    = self.x[gi] - self.x[gj]
        dy    = self.y[gi] - self.y[gj]
        valid = (dx ** 2 + dy ** 2) < r_ij ** 2
        gi, gj = gi[valid], gj[valid]

        n_pairs = len(gi)
        if n_pairs > MAX_PAIRS_TICK:
            sel    = np.random.choice(n_pairs, MAX_PAIRS_TICK, replace=False)
            gi, gj = gi[sel], gj[sel]

        for k in range(len(gi)):
            i, j = int(gi[k]), int(gj[k])
            if not (self.alive[i] and self.alive[j]):
                continue
            self._process_pair(i, j, mutation)

    def _process_pair(self, i: int, j: int, mutation: float) -> None:
        uid_i, uid_j = int(self.uid[i]), int(self.uid[j])
        gvec_j = self._gene_vec(j)
        gvec_i = self._gene_vec(i)

        att_i = self._attitude(i, uid_i, uid_j, gvec_j)
        att_j = self._attitude(j, uid_j, uid_i, gvec_i)

        thresh_i = self.selectivity[i] * 0.5 - 0.3
        thresh_j = self.selectivity[j] * 0.5 - 0.3

        if att_i < thresh_i or att_j < thresh_j:
            return  # consent refused

        # One-shot interaction game (same payoff table as v1)
        s = self.coop[i] + self.coop[j]
        if s > 1.3:
            di = dj = 2.5                     # mutualism
        elif s < 0.7:
            di = dj = -3.5                    # fighting
        else:
            if self.coop[i] < self.coop[j]:  # i more selfish
                di, dj = 3.0, -4.5
            else:
                di, dj = -4.5, 3.0

        self.e[i] = min(MAX_ENERGY, self.e[i] + di)
        self.e[j] = min(MAX_ENERGY, self.e[j] + dj)

        self._update_memory(uid_i, uid_j, di, i, j)
        self._update_memory(uid_j, uid_i, dj, j, i)

        self._try_reproduce(i, j, uid_i, uid_j, mutation)

    def _try_reproduce(self, i: int, j: int, uid_i: int, uid_j: int,
                       mutation: float) -> None:
        if self.alive.sum() >= MAX_POP:
            return
        if self.e[i] < REPRO_THRESHOLD or self.e[j] < REPRO_THRESHOLD:
            return

        pair_key = (min(uid_i, uid_j), max(uid_i, uid_j))
        if self.repro_cd.get(pair_key, 0) > self.round:
            return

        mem_ij = self.memory.get(uid_i, {}).get(uid_j)
        mem_ji = self.memory.get(uid_j, {}).get(uid_i)
        if mem_ij is None or mem_ji is None:
            return
        if mem_ij['s'] < REPRO_SCORE_MIN or mem_ji['s'] < REPRO_SCORE_MIN:
            return
        if mem_ij['n'] < REPRO_COUNT_MIN or mem_ji['n'] < REPRO_COUNT_MIN:
            return

        self.e[i] -= REPRO_COST
        self.e[j] -= REPRO_COST
        self.repro_cd[pair_key] = self.round + REPRO_COOLDOWN

        cx = float(np.clip((self.x[i] + self.x[j]) / 2 + np.random.uniform(-15, 15), 2, W - 2))
        cy = float(np.clip((self.y[i] + self.y[j]) / 2 + np.random.uniform(-15, 15), 2, H - 2))
        self._add_agent(cx, cy, i, j, mutation)
        self.birth_rings.append(BirthRing(x=cx, y=cy, born=self.round))

    def _add_agent(self, x: float, y: float, p1: int, p2: int, mutation: float) -> None:
        """Sexual reproduction: blend genes at midpoint and mutate."""
        def bm(g1, g2, lo, hi):
            return float(np.clip((g1 + g2) / 2 + np.random.uniform(-0.5, 0.5) * mutation * 2, lo, hi))

        dead = np.where(~self.alive)[0]
        if len(dead):
            i = dead[0]
        else:
            i = len(self.x)
            for attr in ('x', 'y', 'vx', 'vy', 'e',
                         'coop', 'openness', 'selectivity', 'trustRate',
                         'forgiveness', 'kinBias', 'spd', 'perc'):
                setattr(self, attr, np.append(getattr(self, attr), 0.0))
            self.alive = np.append(self.alive, False)
            self.uid   = np.append(self.uid, 0)

        self.uid[i]          = self._uid_counter; self._uid_counter += 1
        self.x[i]            = x
        self.y[i]            = y
        self.vx[i]           = np.random.uniform(-1, 1)
        self.vy[i]           = np.random.uniform(-1, 1)
        self.e[i]            = 20.0 + np.random.uniform(0, 15)
        self.coop[i]         = bm(self.coop[p1],        self.coop[p2],        0.0, 1.0)
        self.openness[i]     = bm(self.openness[p1],    self.openness[p2],    0.0, 1.0)
        self.selectivity[i]  = bm(self.selectivity[p1], self.selectivity[p2], 0.0, 1.0)
        self.trustRate[i]    = bm(self.trustRate[p1],   self.trustRate[p2],   0.0, 1.0)
        self.forgiveness[i]  = bm(self.forgiveness[p1], self.forgiveness[p2], 0.0, 1.0)
        self.kinBias[i]      = bm(self.kinBias[p1],     self.kinBias[p2],     0.0, 1.0)
        self.spd[i]          = bm(self.spd[p1],         self.spd[p2],         0.4, 3.5)
        self.perc[i]         = bm(self.perc[p1],        self.perc[p2],         12,  90)
        self.alive[i]        = True

    # ------------------------------------------------------------------ #
    #  Culling                                                             #
    # ------------------------------------------------------------------ #

    def _cull(self) -> None:
        self.alive &= self.e > 0

    # ------------------------------------------------------------------ #
    #  Bond cache                                                          #
    # ------------------------------------------------------------------ #

    def _rebuild_bond_cache(self) -> None:
        """Rebuild list of (x1,y1,x2,y2,score) for strong mutual bonds."""
        idx         = np.where(self.alive)[0]
        uid_to_pos  = {int(self.uid[i]): i for i in idx}
        bonds       = []
        seen: set   = set()

        # Shuffle so we don't always favour early agents when capping
        perm = np.random.permutation(idx)
        for i in perm:
            uid_i = int(self.uid[i])
            for uid_j, entry_i in self.memory.get(uid_i, {}).items():
                pair = (min(uid_i, uid_j), max(uid_i, uid_j))
                if pair in seen:
                    continue
                if entry_i['s'] < BOND_MIN_SCORE or entry_i['n'] < BOND_MIN_COUNT:
                    continue
                if uid_j not in uid_to_pos:
                    continue
                # Require mutual bond
                entry_j = self.memory.get(uid_j, {}).get(uid_i)
                if entry_j is None or entry_j['s'] < BOND_MIN_SCORE:
                    continue
                seen.add(pair)
                j      = uid_to_pos[uid_j]
                mutual = (entry_i['s'] + entry_j['s']) / 2
                bonds.append((self.x[i], self.y[i], self.x[j], self.y[j], mutual))
                if len(bonds) >= 180:
                    self._bond_cache = bonds
                    return
        self._bond_cache = bonds

    @property
    def bonds(self) -> list[tuple]:
        return self._bond_cache

    # ------------------------------------------------------------------ #
    #  Garbage collection                                                  #
    # ------------------------------------------------------------------ #

    def _gc(self) -> None:
        alive_uids  = set(self.uid[self.alive].tolist())
        dead_owners = [u for u in self.memory if u not in alive_uids]
        for u in dead_owners:
            del self.memory[u]
        expired = [k for k, v in self.repro_cd.items() if v < self.round - 300]
        for k in expired:
            del self.repro_cd[k]
        self.birth_rings = [b for b in self.birth_rings if self.round - b.born < 60]

    # ------------------------------------------------------------------ #
    #  Stats                                                               #
    # ------------------------------------------------------------------ #

    def stats(self) -> dict:
        idx = np.where(self.alive)[0]
        n   = len(idx)
        if n == 0:
            return dict(pop=0, avg_energy=0.0, avg_coop=0.0, avg_openness=0.0,
                        avg_selectivity=0.0, avg_kinBias=0.0,
                        avg_trustRate=0.0, avg_forgiveness=0.0,
                        avg_spd=0.0, avg_perc=0.0, food=len(self.fx),
                        n_bonds=len(self._bond_cache))
        return dict(
            pop             = n,
            avg_energy      = float(self.e[idx].mean()),
            avg_coop        = float(self.coop[idx].mean()),
            avg_openness    = float(self.openness[idx].mean()),
            avg_selectivity = float(self.selectivity[idx].mean()),
            avg_kinBias     = float(self.kinBias[idx].mean()),
            avg_trustRate   = float(self.trustRate[idx].mean()),
            avg_forgiveness = float(self.forgiveness[idx].mean()),
            avg_spd         = float(self.spd[idx].mean()),
            avg_perc        = float(self.perc[idx].mean()),
            food            = len(self.fx),
            n_bonds         = len(self._bond_cache),
        )
