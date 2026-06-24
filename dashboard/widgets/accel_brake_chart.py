"""
accel_brake_chart.py - Widget graphique accélérateur + freins pour la télémétrie.

Affiche les entrées accélérateur (vert) et frein (rouge) en pourcentage (0-100 %)
sur le temps d'un tour. Même structure que SpeedChart : tour en cours en temps
réel + overlays de tours passés pour comparaison.
"""
from ..constants import BG_DARK, GRID_COLOR, TEXT_COLOR
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib
matplotlib.use("QtAgg")

WINDOW_S = 30

COLOR_THROTTLE = "#66bb6a"   # vert : accélérateur tour en cours
COLOR_BRAKE    = "#ef5350"   # rouge : freins tour en cours

# Palette de couleurs pour les overlays (une couleur par tour; même couleur pour
# throttle (solid) et brake (dashed) du même tour).
_OVERLAY_COLORS = [
    "#ff8a65", "#ce93d8", "#a5d6a7", "#ffd54f",
    "#ef9a9a", "#80cbc4", "#ffab40", "#b39ddb",
]


def ms_to_str(ms: float) -> str:
    if ms <= 0:
        return "--:--.---"
    total_s, ms_part = divmod(int(ms), 1000)
    m, s = divmod(total_s, 60)
    return f"{m}:{s:02d}.{ms_part:03d}"


class AccelBrakeChart(QWidget):
    """Widget PyQt qui affiche accélérateur et freins au cours d'un tour.

    Attributs internes :
    - _cur_times / _cur_throttles / _cur_brakes : données du tour en cours (%)
    - _laps : {lap_num: {times, throttles, brakes, lap_time_ms}}
    - _visible : set de lap_num à afficher en overlay
    - _overlay_lines : {lap_num: (throttle_line, brake_line)}
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._mode = "full_lap"

        self._cur_times:     list = []
        self._cur_throttles: list = []
        self._cur_brakes:    list = []

        self._laps:          dict = {}
        self._visible:       set  = set()
        self._overlay_lines: dict = {}

        self._show_cur: bool = True

        fig = Figure(figsize=(8, 2.5), facecolor=BG_DARK)
        self._ax = fig.add_subplot(111, facecolor=BG_DARK)
        self._ax.set_ylim(0, 100)
        self._ax.set_xlabel("Temps du tour (s)", color=TEXT_COLOR)
        self._ax.set_ylabel("%", color=TEXT_COLOR)
        self._ax.tick_params(colors=TEXT_COLOR)
        self._ax.grid(True, color=GRID_COLOR, linewidth=0.5)
        for spine in self._ax.spines.values():
            spine.set_edgecolor(GRID_COLOR)

        (self._throttle_line,) = self._ax.plot(
            [], [], color=COLOR_THROTTLE, linewidth=2, zorder=10, label="Accélérateur"
        )
        (self._brake_line,) = self._ax.plot(
            [], [], color=COLOR_BRAKE, linewidth=2, zorder=10, label="Freins"
        )

        self._legend = self._ax.legend(
            loc="upper left", framealpha=0.25, facecolor=BG_DARK,
            edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=9
        )

        self._canvas = FigureCanvas(fig)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

    # ── Données du tour courant ──────────────────────────────────────────

    def append(self, throttle: float, brake: float, lap_ms: float):
        """Ajoute un point (throttle et brake en 0-1, lap_ms en millisecondes)."""
        if lap_ms <= 0:
            return
        t = lap_ms / 1000.0
        if self._cur_times and t < self._cur_times[-1]:
            return
        self._cur_throttles.append(throttle * 100.0)
        self._cur_brakes.append(brake * 100.0)
        self._cur_times.append(t)
        self._redraw_current()

    def commit_lap(self, lap_num: int, lap_time_ms: float) -> bool:
        if len(self._cur_times) < 5:
            return False
        self._laps[lap_num] = {
            "times":       list(self._cur_times),
            "throttles":   list(self._cur_throttles),
            "brakes":      list(self._cur_brakes),
            "lap_time_ms": lap_time_ms,
        }
        return True

    def reset(self):
        self._cur_times.clear()
        self._cur_throttles.clear()
        self._cur_brakes.clear()
        self._throttle_line.set_xdata([])
        self._throttle_line.set_ydata([])
        self._brake_line.set_xdata([])
        self._brake_line.set_ydata([])
        self._ax.set_xlim(0, 1)
        self._canvas.draw_idle()

    def set_cur_visible(self, show: bool):
        self._show_cur = show
        self._throttle_line.set_visible(show)
        self._brake_line.set_visible(show)
        self._canvas.draw_idle()

    def set_mode(self, mode: str):
        self._mode = mode
        self._redraw_current()

    # ── Overlays ─────────────────────────────────────────────────────────

    def lap_info(self):
        return sorted(
            [(n, d["lap_time_ms"]) for n, d in self._laps.items()],
            key=lambda x: x[0],
        )

    def best_lap_num(self):
        if not self._laps:
            return None
        return min(
            (n for n, d in self._laps.items() if d["lap_time_ms"] > 0),
            key=lambda n: self._laps[n]["lap_time_ms"],
            default=None,
        )

    def set_visible_laps(self, lap_nums: set):
        self._visible = set(lap_nums)
        self._rebuild_overlays()

    def _rebuild_overlays(self):
        for lap_num in list(self._overlay_lines):
            if lap_num not in self._visible:
                t_line, b_line = self._overlay_lines.pop(lap_num)
                t_line.remove()
                b_line.remove()

        best = self.best_lap_num()
        color_idx = 0
        for lap_num in sorted(self._visible):
            if lap_num not in self._laps:
                continue
            if lap_num in self._overlay_lines:
                continue
            rec = self._laps[lap_num]
            color = "#ffd54f" if lap_num == best else _OVERLAY_COLORS[color_idx % len(_OVERLAY_COLORS)]
            color_idx += 1
            star = "\u2605 " if lap_num == best else ""
            lbl_t = f"{star}T{lap_num} Accel  {ms_to_str(rec['lap_time_ms'])}"
            lbl_b = f"{star}T{lap_num} Freins"
            (t_line,) = self._ax.plot(
                rec["times"], rec["throttles"],
                color=color, linewidth=1.5, alpha=0.75, zorder=5, label=lbl_t,
            )
            (b_line,) = self._ax.plot(
                rec["times"], rec["brakes"],
                color=color, linewidth=1.5, alpha=0.75, zorder=5, linestyle="--", label=lbl_b,
            )
            self._overlay_lines[lap_num] = (t_line, b_line)

        self._canvas.draw_idle()
        self._update_legend()
        self._redraw_current()

    # ── Dessin interne ───────────────────────────────────────────────────

    def _max_reference_duration(self) -> float:
        durations = [d["times"][-1] for d in self._laps.values() if d["times"]]
        return max(durations, default=0.0)

    def _redraw_current(self):
        if not self._cur_times:
            ref = self._max_reference_duration()
            if ref > 0:
                self._ax.set_xlim(0.0, ref)
                self._canvas.draw_idle()
            return

        if self._mode == "full_lap":
            xs = self._cur_times
            ys_t = self._cur_throttles
            ys_b = self._cur_brakes
            x_max = max(self._cur_times[-1], self._max_reference_duration(), 1.0)
            x_min = 0.0
        else:
            t_end = self._cur_times[-1]
            t_start = max(0.0, t_end - WINDOW_S)
            pairs = [
                (t, th, br)
                for t, th, br in zip(self._cur_times, self._cur_throttles, self._cur_brakes)
                if t >= t_start
            ]
            xs   = [p[0] for p in pairs]
            ys_t = [p[1] for p in pairs]
            ys_b = [p[2] for p in pairs]
            x_min, x_max = t_start, max(t_end, t_start + 1.0)

        self._throttle_line.set_xdata(xs)
        self._throttle_line.set_ydata(ys_t)
        self._throttle_line.set_visible(self._show_cur)
        self._brake_line.set_xdata(xs)
        self._brake_line.set_ydata(ys_b)
        self._brake_line.set_visible(self._show_cur)
        self._ax.set_xlim(x_min, x_max)
        self._update_legend()
        self._canvas.draw_idle()

    def _update_legend(self):
        lines, labels = [], []
        if self._show_cur and self._cur_times:
            lines += [self._throttle_line, self._brake_line]
            labels += ["Accélérateur", "Freins"]
        for t_line, b_line in self._overlay_lines.values():
            lines += [t_line, b_line]
            labels += [t_line.get_label(), b_line.get_label()]
        if lines:
            self._legend = self._ax.legend(
                lines, labels,
                loc="upper left", framealpha=0.25, facecolor=BG_DARK,
                edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=9
            )
        else:
            if self._legend:
                self._legend.remove()
                self._legend = None
