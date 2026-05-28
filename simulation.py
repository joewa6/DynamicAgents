from collections import defaultdict

import numpy as np
from scipy.spatial import cKDTree

from config import (
    W, H, MAX_ENERGY, FOOD_ENERGY, ENERGY_DECAY,
    REPRO_THRESHOLD, REPRO_COST, MAX_POP, MAX_FOOD,
    FOOD_EAT_RADIUS, CELL_SIZE, INIT_AGENTS, INIT_FOOD,
)


class Simulation:
    def __init__(self):
        self.reset()

    def reset(self):
        n = INIT_AGENTS
        self.x     = np.random.uniform(2, W - 2, n)
        self.y     = np.random.uniform(2, H - 2, n)
        self.vx    = np.random.uniform(-1, 1, n)
        self.vy    = np.random.uniform(-1, 1, n)
        self.e     = np.random.uniform(40, 70, n)
        self.coop  = np.random.uniform(0, 1, n)
        self.spd   = np.random.uniform(0.7, 2.7, n)
        self.perc  = np.random.uniform(18, 70, n)
        self.alive = np.ones(n, dtype=bool)
        self.fx    = np.random.uniform(0, W, INIT_FOOD)
        self.fy    = np.random.uniform(0, H, INIT_FOOD)
        self.round = 0

    # ------------------------------------------------------------------ #
    #  Public                                                              #
    # ------------------------------------------------------------------ #

    def tick(self, food_rate=8, mutation=0.15):
        self._spawn_food(food_rate)
        self._move()
        self._eat_food()
        self._interact()
        self._decay()
        self._reproduce(mutation)
        self._cull()
        self.round += 1

    # ------------------------------------------------------------------ #
    #  Movement (vectorised)                                               #
    # ------------------------------------------------------------------ #

    def _move(self):
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
            nn      = np.argmin(masked, axis=1)
            ar      = np.arange(len(idx))
            found   = masked[ar, nn] < np.inf
            d       = np.sqrt(masked[ar, nn] + 1e-9)
            sx      = np.where(found, dx[ar, nn] / d, 0.0)
            sy      = np.where(found, dy[ar, nn] / d, 0.0)
            f       = 0.1 * self.spd[idx]
            wander  = ~found
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

        self.x[idx] += self.vx[idx]
        self.y[idx] += self.vy[idx]

        self.vx[idx] = np.where(self.x[idx] < 2,     np.abs(self.vx[idx]),  self.vx[idx])
        self.vx[idx] = np.where(self.x[idx] > W - 2, -np.abs(self.vx[idx]), self.vx[idx])
        self.vy[idx] = np.where(self.y[idx] < 2,     np.abs(self.vy[idx]),  self.vy[idx])
        self.vy[idx] = np.where(self.y[idx] > H - 2, -np.abs(self.vy[idx]), self.vy[idx])
        self.x[idx]  = np.clip(self.x[idx], 2, W - 2)
        self.y[idx]  = np.clip(self.y[idx], 2, H - 2)

    # ------------------------------------------------------------------ #
    #  Food                                                                #
    # ------------------------------------------------------------------ #

    def _spawn_food(self, rate):
        n_new = min(rate, MAX_FOOD - len(self.fx))
        if n_new > 0:
            self.fx = np.append(self.fx, np.random.uniform(0, W, n_new))
            self.fy = np.append(self.fy, np.random.uniform(0, H, n_new))

    def _eat_food(self):
        if len(self.fx) == 0:
            return
        idx = np.where(self.alive)[0]
        if len(idx) == 0:
            return

        food_tree  = cKDTree(np.stack([self.fx, self.fy], axis=1))
        agent_pos  = np.stack([self.x[idx], self.y[idx]], axis=1)
        dists, fi  = food_tree.query(agent_pos, distance_upper_bound=FOOD_EAT_RADIUS)
        n_food     = len(self.fx)
        valid      = dists < FOOD_EAT_RADIUS

        eaten = set()
        for k in range(len(idx)):
            if valid[k] and fi[k] < n_food and fi[k] not in eaten:
                self.e[idx[k]] = min(MAX_ENERGY, self.e[idx[k]] + FOOD_ENERGY)
                eaten.add(int(fi[k]))

        if eaten:
            keep   = np.array([j for j in range(n_food) if j not in eaten])
            self.fx = self.fx[keep] if len(keep) else np.empty(0)
            self.fy = self.fy[keep] if len(keep) else np.empty(0)

    # ------------------------------------------------------------------ #
    #  Interactions — cKDTree, vectorised energy updates                  #
    # ------------------------------------------------------------------ #

    def _interact(self):
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

        r_ij  = np.minimum(self.perc[gi], self.perc[gj])
        dx    = self.x[gi] - self.x[gj]
        dy    = self.y[gi] - self.y[gj]
        valid = (dx ** 2 + dy ** 2) < r_ij ** 2
        gi, gj = gi[valid], gj[valid]
        if len(gi) == 0:
            return

        s       = self.coop[gi] + self.coop[gj]
        mutual  = s > 1.3
        fight   = s < 0.7
        exploit = ~mutual & ~fight

        delta = np.zeros(len(self.e))
        np.add.at(delta, gi[mutual], 2.5)
        np.add.at(delta, gj[mutual], 2.5)
        np.add.at(delta, gi[fight],  -3.5)
        np.add.at(delta, gj[fight],  -3.5)

        gi_e, gj_e = gi[exploit], gj[exploit]
        i_sel = self.coop[gi_e] < self.coop[gj_e]
        np.add.at(delta, gi_e[i_sel],    3.0)
        np.add.at(delta, gj_e[i_sel],   -4.5)
        np.add.at(delta, gi_e[~i_sel],  -4.5)
        np.add.at(delta, gj_e[~i_sel],   3.0)

        self.e += delta
        np.clip(self.e, a_min=None, a_max=MAX_ENERGY, out=self.e)

    # ------------------------------------------------------------------ #
    #  Decay, reproduction, death                                          #
    # ------------------------------------------------------------------ #

    def _decay(self):
        idx = np.where(self.alive)[0]
        self.e[idx] -= ENERGY_DECAY + self.spd[idx] * 0.025 + self.perc[idx] * 0.001

    def _reproduce(self, mutation):
        idx   = np.where(self.alive & (self.e >= REPRO_THRESHOLD))[0]
        alive = int(self.alive.sum())
        for i in idx:
            if alive >= MAX_POP:
                break
            self.e[i] -= REPRO_COST
            self._add_agent(
                np.clip(self.x[i] + np.random.uniform(-12, 12), 2, W - 2),
                np.clip(self.y[i] + np.random.uniform(-12, 12), 2, H - 2),
                i, mutation,
            )
            alive += 1

    def _add_agent(self, x, y, parent, mutation):
        def m(v, rng, lo, hi):
            return float(np.clip(v + np.random.uniform(-rng, rng) * mutation * 2, lo, hi))

        dead = np.where(~self.alive)[0]
        if len(dead):
            i = dead[0]
        else:
            i = len(self.x)
            for attr in ('x', 'y', 'vx', 'vy', 'e', 'coop', 'spd', 'perc'):
                setattr(self, attr, np.append(getattr(self, attr), 0.0))
            self.alive = np.append(self.alive, False)

        self.x[i]    = x
        self.y[i]    = y
        self.vx[i]   = np.random.uniform(-1, 1)
        self.vy[i]   = np.random.uniform(-1, 1)
        self.e[i]    = 25.0 + np.random.uniform(0, 20)
        self.coop[i] = m(self.coop[parent], 0.4, 0.0, 1.0)
        self.spd[i]  = m(self.spd[parent],  1.5, 0.4, 3.5)
        self.perc[i] = m(self.perc[parent], 30,  12,  90)
        self.alive[i] = True

    def _cull(self):
        self.alive &= self.e > 0

    # ------------------------------------------------------------------ #
    #  Stats                                                               #
    # ------------------------------------------------------------------ #

    def stats(self):
        idx = np.where(self.alive)[0]
        n   = len(idx)
        if n == 0:
            return dict(pop=0, avg_energy=0.0, avg_coop=0.0,
                        avg_spd=0.0, avg_perc=0.0, food=len(self.fx))
        return dict(
            pop       = n,
            avg_energy= float(self.e[idx].mean()),
            avg_coop  = float(self.coop[idx].mean()),
            avg_spd   = float(self.spd[idx].mean()),
            avg_perc  = float(self.perc[idx].mean()),
            food      = len(self.fx),
        )
