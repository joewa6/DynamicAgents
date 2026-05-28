import sys
import collections

import numpy as np
import pygame
from matplotlib.colors import LinearSegmentedColormap
from scipy.ndimage import gaussian_filter

from config import W, H, PANEL_W, SCREEN_W, MAX_ENERGY, MAX_POP, FPS
from simulation import Simulation

# ── colour maps ───────────────────────────────────────────────────────────────
# Agent body: defector (orange-red) → violet → cooperator (cyan)
_AGENT_CMAP = LinearSegmentedColormap.from_list("agent", [
    (1.00, 0.18, 0.02),
    (0.70, 0.00, 0.95),
    (0.00, 0.72, 1.00),
])

TRAIL_DECAY = 0.78
GLOW_SIGMA  = 2.8
GLOW_BOOST  = 2.2
HIST_LEN    = 300

# ── slider ────────────────────────────────────────────────────────────────────

class Slider:
    BAR_H  = 6
    KNOB_R = 9
    W_PX   = PANEL_W - 32

    def __init__(self, x, y, label, lo, hi, value, fmt="{:.0f}", integer=False):
        self.x, self.y       = x, y
        self.label           = label
        self.lo, self.hi     = float(lo), float(hi)
        self._v              = float(value)
        self.fmt             = fmt
        self.integer         = integer
        self.dragging        = False

    @property
    def value(self):
        return int(round(self._v)) if self.integer else self._v

    def _frac(self):
        return (self._v - self.lo) / (self.hi - self.lo)

    def knob_x(self):
        return self.x + int(self._frac() * self.W_PX)

    def handle_event(self, event):
        kx, ky = self.knob_x(), self.y
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if abs(event.pos[0] - kx) <= self.KNOB_R + 4 and abs(event.pos[1] - ky) <= self.KNOB_R + 4:
                self.dragging = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            frac   = np.clip((event.pos[0] - self.x) / self.W_PX, 0, 1)
            self._v = self.lo + frac * (self.hi - self.lo)

    def draw(self, surface, font):
        kx  = self.knob_x()
        bar_y = self.y
        pygame.draw.line(surface, (45, 45, 65), (self.x, bar_y), (self.x + self.W_PX, bar_y), self.BAR_H)
        pygame.draw.line(surface, (75, 105, 195), (self.x, bar_y), (kx, bar_y), self.BAR_H)
        col = (155, 195, 255) if self.dragging else (110, 155, 230)
        pygame.draw.circle(surface, col, (kx, bar_y), self.KNOB_R)
        pygame.draw.circle(surface, (210, 225, 255), (kx, bar_y), self.KNOB_R, 1)
        lbl  = font.render(self.label, True, (130, 130, 155))
        val  = font.render(self.fmt.format(self.value), True, (195, 210, 230))
        surface.blit(lbl, (self.x, bar_y - 20))
        surface.blit(val, (self.x + self.W_PX - val.get_width(), bar_y - 20))


# ── rendering helpers ─────────────────────────────────────────────────────────

def _agent_rgb(sim, idx):
    if len(idx) == 0:
        return np.empty((0, 3), dtype=np.float32)
    base   = _AGENT_CMAP(sim.coop[idx])[:, :3].astype(np.float32)
    bright = (0.28 + (sim.e[idx] / MAX_ENERGY) * 0.72).astype(np.float32)
    return base * bright[:, None]


def _paint(canvas, px, py, rgb):
    for c in range(3):
        np.maximum.at(canvas[:, :, c], (py, px), rgb[:, c])
    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        py2 = np.clip(py + dy, 0, canvas.shape[0] - 1)
        px2 = np.clip(px + dx, 0, canvas.shape[1] - 1)
        for c in range(3):
            np.maximum.at(canvas[:, :, c], (py2, px2), rgb[:, c] * 0.45)


def _paint_food(canvas, sim):
    if len(sim.fx) == 0:
        return
    fpx = np.clip(sim.fx.astype(int), 0, W - 1)
    fpy = np.clip(sim.fy.astype(int), 0, H - 1)
    food_col = np.array([0.18, 0.92, 0.28], dtype=np.float32)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            w   = 0.9 if (dy == 0 and dx == 0) else 0.35
            py2 = np.clip(fpy + dy, 0, H - 1)
            px2 = np.clip(fpx + dx, 0, W - 1)
            for c in range(3):
                np.maximum.at(canvas[:, :, c], (py2, px2), food_col[c] * w)


def _bloom(canvas):
    half    = canvas[::2, ::2]
    blurred = gaussian_filter(half, sigma=[GLOW_SIGMA, GLOW_SIGMA, 0])
    up      = np.repeat(np.repeat(blurred, 2, axis=0), 2, axis=1)
    return up[:H, :W]


def _blit_canvas(screen, canvas, bloom):
    frame = np.clip((canvas + bloom * GLOW_BOOST) * 255, 0, 255).astype(np.uint8)
    surf  = pygame.surfarray.make_surface(frame.transpose(1, 0, 2))
    screen.blit(surf, (0, 0))


def _draw_bonds(screen, bond_surf, bonds):
    bond_surf.fill((0, 0, 0, 0))
    for x1, y1, x2, y2, score in bonds:
        alpha = int(np.clip(score * 160, 30, 200))
        pygame.draw.line(bond_surf, (30, 220, 90, alpha),
                         (int(x1), int(y1)), (int(x2), int(y2)), 1)
    screen.blit(bond_surf, (0, 0))


def _draw_birth_rings(screen, ring_surf, sim):
    ring_surf.fill((0, 0, 0, 0))
    for ring in sim.birth_rings:
        age = sim.round - ring.born
        if age <= 0 or age > 50:
            continue
        r     = int(age * 0.7 + 3)
        alpha = int(255 * max(0, 1 - age / 50))
        pygame.draw.circle(ring_surf, (255, 205, 35, alpha),
                           (int(ring.x), int(ring.y)), r, 2)
    screen.blit(ring_surf, (0, 0))


# ── chart ─────────────────────────────────────────────────────────────────────

_CHART_LINES = [
    ('avg_coop',        (80,  135, 255), 'coop'),
    ('avg_openness',    (50,  210, 130), 'open'),
    ('avg_selectivity', (240, 155,  40), 'sel'),
]
_POP_COL = (110, 110, 110)


def _draw_chart(surface, font, hists, pop_hist, px, py, gw, gh):
    pygame.draw.rect(surface, (9, 9, 18), (px, py, gw, gh))
    pygame.draw.rect(surface, (32, 32, 52), (px, py, gw, gh), 1)

    def _line(hist, color, scale=1.0, floor=0.0):
        n = len(hist)
        if n < 2:
            return
        pts = [(int(px + k / (n - 1) * gw),
                int(py + gh - 2 - max(0, min(gh - 4, int((hist[k] - floor) * scale * (gh - 4))))))
               for k in range(n)]
        pygame.draw.lines(surface, color, False, pts, 1)

    _line(pop_hist, _POP_COL, scale=1.0 / MAX_POP)
    for key, col, _ in _CHART_LINES:
        if key in hists:
            _line(hists[key], col)

    # Legend
    lx, ly = px + 4, py + 3
    for key, col, lbl in _CHART_LINES:
        lsurf = font.render(lbl, True, col)
        surface.blit(lsurf, (lx, ly))
        lx += lsurf.get_width() + 8
    psurf = font.render("pop", True, _POP_COL)
    surface.blit(psurf, (lx, ly))


# ── panel ─────────────────────────────────────────────────────────────────────

def _draw_panel(surface, font_h, font_b, font_s,
                sliders, sim, hists, pop_hist,
                running, trails, speed):
    px = W
    pygame.draw.rect(surface, (11, 11, 20), (px, 0, PANEL_W, H))
    pygame.draw.line(surface, (38, 38, 58), (px, 0), (px, H), 1)

    surface.blit(font_h.render("DynamicAgents v2", True, (150, 165, 200)), (px + 10, 10))

    for sl in sliders:
        sl.draw(surface, font_b)

    # Buttons
    btn_y = sliders[-1].y + 36
    btn_r  = pygame.Rect(px + 12, btn_y, PANEL_W - 24, 28)
    rst_r  = pygame.Rect(px + 12, btn_y + 36, PANEL_W - 24, 24)
    tr_r   = pygame.Rect(px + 12, btn_y + 68, PANEL_W - 24, 24)

    for rect, col_bg, col_bd, label, txt_col in [
        (btn_r, (28, 78, 48) if running else (58, 28, 28),
                (55, 115, 75) if running else (95, 48, 48),
                "▶  PAUSE" if running else "▶  PLAY",
                (195, 230, 195) if running else (230, 180, 180)),
        (rst_r, (28, 28, 52), (52, 52, 88), "↺  RESET", (148, 148, 198)),
        (tr_r,  (18, 40, 32) if trails else (24, 24, 40),
                (38, 88, 68) if trails else (48, 48, 68),
                f"trails: {'ON' if trails else 'OFF'}",
                (125, 205, 165) if trails else (115, 115, 148)),
    ]:
        pygame.draw.rect(surface, col_bg, rect, border_radius=4)
        pygame.draw.rect(surface, col_bd, rect, 1, border_radius=4)
        ts = font_b.render(label, True, txt_col)
        surface.blit(ts, (rect.centerx - ts.get_width() // 2,
                          rect.centery - ts.get_height() // 2))

    # Stats
    s      = sim.stats()
    stat_y = btn_y + 104
    rows = [
        ("population",  f"{s['pop']}"),
        ("round",       f"{sim.round:,}"),
        ("food",        f"{s['food']}"),
        ("bonds",       f"{s['n_bonds']}"),
        ("energy",      f"{s['avg_energy']:.0f}"),
        ("coop",        f"{s['avg_coop']:.3f}"),
        ("openness",    f"{s['avg_openness']:.3f}"),
        ("selectivity", f"{s['avg_selectivity']:.3f}"),
        ("kin bias",    f"{s['avg_kinBias']:.3f}"),
        ("trust rate",  f"{s['avg_trustRate']:.3f}"),
        ("forgiveness", f"{s['avg_forgiveness']:.3f}"),
    ]
    for i, (lbl, val) in enumerate(rows):
        surface.blit(font_s.render(lbl, True, (78, 78, 98)), (px + 12, stat_y + i * 17))
        vs = font_s.render(val, True, (188, 200, 220))
        surface.blit(vs, (px + PANEL_W - vs.get_width() - 12, stat_y + i * 17))

    # Chart
    chart_y = stat_y + len(rows) * 17 + 10
    chart_h = H - chart_y - 8
    if chart_h > 40:
        _draw_chart(surface, font_s, hists, pop_hist,
                    px + 8, chart_y, PANEL_W - 16, chart_h)

    return btn_r, rst_r, tr_r


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    pygame.init()
    # Use SCALED so pygame requests the full pixel resolution on Retina displays
    screen = pygame.display.set_mode((SCREEN_W, H), pygame.SCALED | pygame.RESIZABLE)
    pygame.display.set_caption("DynamicAgents v2 — social trust + kin recognition")
    clock = pygame.time.Clock()

    # Larger fonts to stay sharp on HiDPI screens
    font_h = pygame.font.SysFont("monospace", 15, bold=True)
    font_b = pygame.font.SysFont("monospace", 13)
    font_s = pygame.font.SysFont("monospace", 12)

    sim     = Simulation()
    running = False
    trails  = True
    canvas  = np.zeros((H, W, 3), dtype=np.float32)

    # Persistent SRCALPHA overlay surfaces (created once)
    bond_surf = pygame.Surface((W, H), pygame.SRCALPHA)
    ring_surf = pygame.Surface((W, H), pygame.SRCALPHA)

    hists    = {key: collections.deque(maxlen=HIST_LEN) for key, _, _ in _CHART_LINES}
    pop_hist = collections.deque(maxlen=HIST_LEN)

    sx = W + 16
    sliders = [
        Slider(sx, 58,  "speed (ticks/frame)", 1, 20,  3,  "{:.0f}", integer=True),
        Slider(sx, 115, "food rate",            0, 30,  8,  "{:.0f}", integer=True),
        Slider(sx, 172, "mutation",             0,  1, 0.15, "{:.2f}"),
        Slider(sx, 229, "trail decay",         0.5, 0.99, TRAIL_DECAY, "{:.2f}"),
    ]
    speed_sl, food_sl, mut_sl, trail_sl = sliders

    btn_r = rst_r = tr_r = None

    while True:
        prev_btn, prev_rst, prev_tr = btn_r, rst_r, tr_r

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            for sl in sliders:
                sl.handle_event(event)
            if event.type == pygame.KEYDOWN:
                k = event.key
                if   k == pygame.K_SPACE: running = not running
                elif k == pygame.K_r:
                    sim.reset(); canvas[:] = 0
                    for dq in hists.values(): dq.clear()
                    pop_hist.clear()
                elif k == pygame.K_t: trails = not trails
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if prev_btn and prev_btn.collidepoint(mx, my): running = not running
                elif prev_rst and prev_rst.collidepoint(mx, my):
                    sim.reset(); canvas[:] = 0
                    for dq in hists.values(): dq.clear()
                    pop_hist.clear()
                elif prev_tr and prev_tr.collidepoint(mx, my): trails = not trails

        speed     = speed_sl.value
        food_rate = food_sl.value
        mutation  = float(mut_sl.value)
        trail_dec = float(trail_sl.value)

        if running:
            for _ in range(speed):
                sim.tick(food_rate=food_rate, mutation=mutation)

        # Track history
        s = sim.stats()
        if s['pop'] > 0:
            for key, _, _ in _CHART_LINES:
                hists[key].append(s[key])
            pop_hist.append(float(s['pop']))

        # ── render sim area ─────────────────────────────────────────────── #
        idx    = np.where(sim.alive)[0]
        colors = _agent_rgb(sim, idx)

        canvas *= trail_dec if trails else 0.0
        if len(idx) > 0:
            px_ = np.clip(sim.x[idx].astype(int), 1, W - 2)
            py_ = np.clip(sim.y[idx].astype(int), 1, H - 2)
            _paint(canvas, px_, py_, colors)
        _paint_food(canvas, sim)

        bloom = _bloom(canvas)
        _blit_canvas(screen, canvas, bloom)

        # Bond lines and birth rings drawn as alpha overlays
        _draw_bonds(screen, bond_surf, sim.bonds)
        _draw_birth_rings(screen, ring_surf, sim)

        # ── panel ───────────────────────────────────────────────────────── #
        btn_r, rst_r, tr_r = _draw_panel(
            screen, font_h, font_b, font_s,
            sliders, sim, hists, pop_hist,
            running, trails, speed,
        )

        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main()
