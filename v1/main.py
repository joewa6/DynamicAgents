import sys
import collections

import numpy as np
import pygame
from matplotlib.colors import LinearSegmentedColormap
from scipy.ndimage import gaussian_filter

from config import W, H, PANEL_W, SCREEN_W, MAX_ENERGY, MAX_POP, FPS
from simulation import Simulation

# ── colour map: defector (red-orange) → violet → cooperator (cyan) ──────────
_CMAP = LinearSegmentedColormap.from_list("sim", [
    (1.00, 0.18, 0.02),
    (0.70, 0.00, 0.95),
    (0.00, 0.72, 1.00),
])

TRAIL_DECAY  = 0.78
GLOW_SIGMA   = 2.8    # sigma for gaussian bloom
GLOW_BOOST   = 2.2    # bloom brightness multiplier
HIST_LEN     = 300


# ── slider widget ─────────────────────────────────────────────────────────────

class Slider:
    """A draggable horizontal slider rendered in the side panel."""

    BAR_H  = 6
    KNOB_R = 8
    W      = PANEL_W - 30

    def __init__(self, x, y, label, lo, hi, value, fmt="{:.0f}", integer=False):
        self.x, self.y  = x, y
        self.label      = label
        self.lo, self.hi = float(lo), float(hi)
        self._value     = float(value)
        self.fmt        = fmt
        self.integer    = integer
        self.dragging   = False

    @property
    def value(self):
        v = self._value
        return int(round(v)) if self.integer else v

    def _frac(self):
        return (self._value - self.lo) / (self.hi - self.lo)

    def knob_x(self):
        return self.x + int(self._frac() * self.W)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            kx, ky = self.knob_x(), self.y
            if abs(mx - kx) <= self.KNOB_R + 4 and abs(my - ky) <= self.KNOB_R + 4:
                self.dragging = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            mx = event.pos[0]
            frac = np.clip((mx - self.x) / self.W, 0, 1)
            self._value = self.lo + frac * (self.hi - self.lo)

    def draw(self, surface, font):
        # Track
        bar_y = self.y
        pygame.draw.line(surface, (50, 50, 70),
                         (self.x, bar_y), (self.x + self.W, bar_y), self.BAR_H)
        # Filled portion
        kx = self.knob_x()
        pygame.draw.line(surface, (80, 110, 200),
                         (self.x, bar_y), (kx, bar_y), self.BAR_H)
        # Knob
        col = (160, 200, 255) if self.dragging else (120, 160, 230)
        pygame.draw.circle(surface, col, (kx, bar_y), self.KNOB_R)
        pygame.draw.circle(surface, (200, 220, 255), (kx, bar_y), self.KNOB_R, 1)
        # Labels
        label_surf = font.render(self.label, True, (140, 140, 160))
        val_surf   = font.render(self.fmt.format(self.value), True, (200, 210, 230))
        surface.blit(label_surf, (self.x, bar_y - 18))
        surface.blit(val_surf,   (self.x + self.W - val_surf.get_width(), bar_y - 18))


# ── rendering helpers ─────────────────────────────────────────────────────────

def _agent_rgb(sim, idx):
    """Return (n, 3) float32 [0,1] colours for the given alive indices."""
    if len(idx) == 0:
        return np.empty((0, 3), dtype=np.float32)
    base   = _CMAP(sim.coop[idx])[:, :3].astype(np.float32)
    bright = (0.28 + (sim.e[idx] / MAX_ENERGY) * 0.72).astype(np.float32)
    return base * bright[:, None]


def _paint(canvas, px, py, rgb):
    """Vectorised pixel paint with np.maximum.at (handles duplicates)."""
    for c in range(3):
        np.maximum.at(canvas[:, :, c], (py, px), rgb[:, c])
    # soft cross neighbour at half intensity
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
    food_color = np.array([0.18, 0.92, 0.28], dtype=np.float32)
    for c in range(3):
        np.maximum.at(canvas[:, :, c], (fpy, fpx), food_color[c])
    # 3×3 glow blob for food
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            w = 0.9 if (dy == 0 and dx == 0) else 0.35
            py2 = np.clip(fpy + dy, 0, H - 1)
            px2 = np.clip(fpx + dx, 0, W - 1)
            for c in range(3):
                np.maximum.at(canvas[:, :, c], (py2, px2), food_color[c] * w)


def _bloom(canvas):
    """Cheap bloom: blur half-resolution copy, upsample back."""
    half    = canvas[::2, ::2]
    blurred = gaussian_filter(half, sigma=[GLOW_SIGMA, GLOW_SIGMA, 0])
    up      = np.repeat(np.repeat(blurred, 2, axis=0), 2, axis=1)
    return up[:H, :W]


def _blit_canvas(screen, canvas, bloom):
    """Composite canvas + bloom → uint8 → blit to the sim area of screen."""
    frame = np.clip((canvas + bloom * GLOW_BOOST) * 255, 0, 255).astype(np.uint8)
    surf  = pygame.surfarray.make_surface(frame.transpose(1, 0, 2))
    screen.blit(surf, (0, 0))


# ── mini graph ────────────────────────────────────────────────────────────────

def _draw_graph(surface, font, coop_hist, pop_hist, px, py, gw, gh):
    pygame.draw.rect(surface, (10, 10, 20), (px, py, gw, gh))
    pygame.draw.rect(surface, (35, 35, 55), (px, py, gw, gh), 1)

    def _line(hist, color, scale=1.0):
        n = len(hist)
        if n < 2:
            return
        pts = [(px + int(k / (n - 1) * gw),
                py + gh - 1 - int(hist[k] * scale * (gh - 2)))
               for k in range(n)]
        pygame.draw.lines(surface, color, False, pts, 1)

    _line(coop_hist, (80,  130, 255))
    _line(pop_hist,  (110, 110, 110), scale=1.0 / MAX_POP)

    surface.blit(font.render("coop", True, (70, 100, 200)), (px + 3, py + 2))
    surface.blit(font.render("pop",  True, (90,  90, 90)),  (px + 40, py + 2))


# ── panel ─────────────────────────────────────────────────────────────────────

def _draw_panel(surface, font_h, font_s,
                sliders, sim, coop_hist, pop_hist,
                running, trails, speed):
    px = W  # panel left edge
    rect = pygame.Rect(px, 0, PANEL_W, H)
    pygame.draw.rect(surface, (12, 12, 22), rect)
    pygame.draw.line(surface, (40, 40, 60), (px, 0), (px, H), 1)

    # Title
    surface.blit(font_h.render("swarm sim", True, (160, 170, 200)), (px + 10, 10))

    # Sliders
    for sl in sliders:
        sl.draw(surface, font_s)

    # Play / pause button
    btn_y = sliders[-1].y + 30
    btn_rect = pygame.Rect(px + 15, btn_y, PANEL_W - 30, 26)
    pygame.draw.rect(surface, (30, 80, 50) if running else (60, 30, 30),
                     btn_rect, border_radius=4)
    pygame.draw.rect(surface, (60, 120, 80) if running else (100, 50, 50),
                     btn_rect, 1, border_radius=4)
    label = "▶  PAUSE" if running else "▶  PLAY"
    lsurf = font_s.render(label, True, (200, 230, 200) if running else (230, 180, 180))
    surface.blit(lsurf, (btn_rect.centerx - lsurf.get_width() // 2,
                          btn_rect.centery - lsurf.get_height() // 2))

    # Reset button
    rst_rect = pygame.Rect(px + 15, btn_y + 34, PANEL_W - 30, 22)
    pygame.draw.rect(surface, (30, 30, 55), rst_rect, border_radius=4)
    pygame.draw.rect(surface, (55, 55, 90), rst_rect, 1, border_radius=4)
    rsurf = font_s.render("↺  RESET", True, (150, 150, 200))
    surface.blit(rsurf, (rst_rect.centerx - rsurf.get_width() // 2,
                          rst_rect.centery - rsurf.get_height() // 2))

    # Trails toggle
    tr_rect = pygame.Rect(px + 15, btn_y + 63, PANEL_W - 30, 22)
    pygame.draw.rect(surface, (20, 40, 35) if trails else (25, 25, 40),
                     tr_rect, border_radius=4)
    pygame.draw.rect(surface, (40, 90, 70) if trails else (50, 50, 70),
                     tr_rect, 1, border_radius=4)
    tsurf = font_s.render(f"trails: {'ON' if trails else 'OFF'}", True,
                           (130, 210, 170) if trails else (120, 120, 150))
    surface.blit(tsurf, (tr_rect.centerx - tsurf.get_width() // 2,
                          tr_rect.centery - tsurf.get_height() // 2))

    # Stats
    s = sim.stats()
    stats_y = btn_y + 100
    for i, (label, val) in enumerate([
        ("population", f"{s['pop']}"),
        ("round",      f"{sim.round:,}"),
        ("food",       f"{s['food']}"),
        ("avg energy", f"{s['avg_energy']:.0f}"),
        ("avg coop",   f"{s['avg_coop']:.3f}"),
        ("avg speed",  f"{s['avg_spd']:.2f}"),
        ("avg percep", f"{s['avg_perc']:.1f}"),
    ]):
        surface.blit(font_s.render(label, True, (80, 80, 100)),
                     (px + 12, stats_y + i * 18))
        vsurf = font_s.render(val, True, (190, 200, 220))
        surface.blit(vsurf, (px + PANEL_W - vsurf.get_width() - 12,
                              stats_y + i * 18))

    # Mini graph
    graph_y = stats_y + 7 * 18 + 12
    graph_h = H - graph_y - 8
    if graph_h > 30:
        _draw_graph(surface, font_s, coop_hist, pop_hist,
                    px + 10, graph_y, PANEL_W - 20, graph_h)

    return btn_rect, rst_rect, tr_rect


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, H))
    pygame.display.set_caption("swarm sim")
    clock  = pygame.time.Clock()

    font_h = pygame.font.SysFont("monospace", 13, bold=True)
    font_s = pygame.font.SysFont("monospace", 11)

    sim       = Simulation()
    running   = False
    trails    = True
    canvas    = np.zeros((H, W, 3), dtype=np.float32)
    coop_hist = collections.deque(maxlen=HIST_LEN)
    pop_hist  = collections.deque(maxlen=HIST_LEN)

    # Sliders — x position is relative to screen (panel area)
    sx = W + 15
    sliders = [
        Slider(sx, 55,  "speed (ticks/frame)", 1, 30,  5,  "{:.0f}", integer=True),
        Slider(sx, 110, "food rate",            0, 30,  8,  "{:.0f}", integer=True),
        Slider(sx, 165, "mutation",             0,  1, 0.15, "{:.2f}"),
        Slider(sx, 220, "trail decay",         0.5, 0.99, TRAIL_DECAY, "{:.2f}"),
    ]
    speed_sl, food_sl, mut_sl, trail_sl = sliders

    # Track button rects across frames so clicks register on the same-frame rect
    btn_rect = rst_rect = tr_rect = None

    while True:
        prev_btn, prev_rst, prev_tr = btn_rect, rst_rect, tr_rect

        # ── events ──────────────────────────────────────────────────────── #
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            for sl in sliders:
                sl.handle_event(event)

            if event.type == pygame.KEYDOWN:
                k = event.key
                if   k == pygame.K_SPACE: running = not running
                elif k == pygame.K_r:
                    sim.reset(); canvas[:] = 0
                    coop_hist.clear(); pop_hist.clear()
                elif k == pygame.K_t:     trails = not trails

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if prev_btn and prev_btn.collidepoint(mx, my):
                    running = not running
                elif prev_rst and prev_rst.collidepoint(mx, my):
                    sim.reset(); canvas[:] = 0
                    coop_hist.clear(); pop_hist.clear()
                elif prev_tr and prev_tr.collidepoint(mx, my):
                    trails = not trails

        # ── simulate ────────────────────────────────────────────────────── #
        speed     = speed_sl.value
        food_rate = food_sl.value
        mutation  = float(mut_sl.value)
        trail_dec = float(trail_sl.value)

        if running:
            for _ in range(speed):
                sim.tick(food_rate=food_rate, mutation=mutation)

        idx    = np.where(sim.alive)[0]
        colors = _agent_rgb(sim, idx)

        s = sim.stats()
        if s['pop'] > 0:
            coop_hist.append(s['avg_coop'])
            pop_hist.append(float(s['pop']))

        # ── render sim area ─────────────────────────────────────────────── #
        canvas *= trail_dec if trails else 0.0

        if len(idx) > 0:
            px_ = np.clip(sim.x[idx].astype(int), 1, W - 2)
            py_ = np.clip(sim.y[idx].astype(int), 1, H - 2)
            _paint(canvas, px_, py_, colors)

        _paint_food(canvas, sim)

        bloom = _bloom(canvas)
        _blit_canvas(screen, canvas, bloom)

        # ── render panel ────────────────────────────────────────────────── #
        btn_rect, rst_rect, tr_rect = _draw_panel(
            screen, font_h, font_s,
            sliders, sim, coop_hist, pop_hist,
            running, trails, speed,
        )

        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main()
