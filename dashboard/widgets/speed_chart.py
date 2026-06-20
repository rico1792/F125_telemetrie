"""
speed_chart.py - Graphique vitesse F1 26.
- Tour en cours : ligne bleue vive
- Tours en overlay (selectionnes par l'utilisateur) : lignes colorees
"""
from ..constants import BG_DARK, GRID_COLOR, TEXT_COLOR
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib
matplotlib.use("QtAgg")


WINDOW_S = 30

_OVERLAY_COLORS = [
    "#ff8a65", "#ce93d8", "#a5d6a7", "#ffd54f",
    "#ef9a9a", "#80cbc4", "#ffab40", "#b39ddb",
]
COLOR_CURRENT = "#4fc3f7"
COLOR_BEST = "#ffd54f"


def ms_to_str(ms: float) -> str:
    if ms <= 0:
        return "--:--.---"
    total_s, ms_part = divmod(int(ms), 1000)
    m, s = divmod(total_s, 60)
    return f"{m}:{s:02d}.{ms_part:03d}"


class SpeedChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._mode = "full_lap"
        self._cur_times:  list = []
        self._cur_speeds: list = []
        self._laps: dict = {}
        self._visible: set = set()
        self._overlay_lines: dict = {}

        fig = Figure(figsize=(8, 4), facecolor=BG_DARK)
        self._ax = fig.add_subplot(111, facecolor=BG_DARK)
        self._ax.set_ylim(0, 380)
        self._ax.set_xlabel("Temps du tour (s)", color=TEXT_COLOR)
        self._ax.set_ylabel("km/h", color=TEXT_COLOR)
        self._ax.tick_params(colors=TEXT_COLOR)
        self._ax.grid(True, color=GRID_COLOR, linewidth=0.5)
        for spine in self._ax.spines.values():
            spine.set_edgecolor(GRID_COLOR)

        (self._cur_line,) = self._ax.plot(
            [], [], color=COLOR_CURRENT, linewidth=2, zorder=10
        )

        self._canvas = FigureCanvas(fig)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

    def set_mode(self, mode: str):
        self._mode = mode
        self._redraw_current()

    def append(self, speed: float, lap_ms: float):
        self._cur_speeds.append(speed)
        self._cur_times.append(lap_ms / 1000.0)
        self._redraw_current()

    def commit_lap(self, lap_num: int, lap_time_ms: float):
        if len(self._cur_times) < 5:
            return False
        self._laps[lap_num] = {
            "times":       list(self._cur_times),
            "speeds":      list(self._cur_speeds),
            "lap_time_ms": lap_time_ms,
        }
        return True

    def set_visible_laps(self, lap_nums: set):
        self._visible = set(lap_nums)
        self._rebuild_overlays()

    def reset(self):
        self._cur_times.clear()
        self._cur_speeds.clear()
        self._cur_line.set_xdata([])
        self._cur_line.set_ydata([])
        self._ax.set_xlim(0, 1)
        self._canvas.draw_idle()

    def best_lap_num(self):
        if not self._laps:
            return None
        return min(
            (n for n, d in self._laps.items() if d["lap_time_ms"] > 0),
            key=lambda n: self._laps[n]["lap_time_ms"],
            default=None,
        )

    def lap_info(self):
        return sorted(
            [(n, d["lap_time_ms"]) for n, d in self._laps.items()],
            key=lambda x: x[0],
        )

    def _rebuild_overlays(self):
        for lap_num in list(self._overlay_lines):
            if lap_num not in self._visible:
                self._overlay_lines[lap_num].remove()
                del self._overlay_lines[lap_num]

        best = self.best_lap_num()
        color_idx = 0
        for lap_num in sorted(self._visible):
            if lap_num not in self._laps:
                continue
            if lap_num in self._overlay_lines:
                continue
            rec = self._laps[lap_num]
            color = COLOR_BEST if lap_num == best else _OVERLAY_COLORS[color_idx % len(
                _OVERLAY_COLORS)]
            color_idx += 1
            (line,) = self._ax.plot(
                rec["times"], rec["speeds"],
                color=color, linewidth=1.5, alpha=0.75, zorder=5,
            )
            self._overlay_lines[lap_num] = line

        self._canvas.draw_idle()
        # Mettre a jour l'axe X apres changement des overlays
        self._redraw_current()

    def _max_reference_duration(self) -> float:
        """Duree max parmi tous les tours completes (pas seulement les visibles).
        Sert a etendre l'axe X meme quand le tour en cours est court."""
        if not self._laps:
            return 0.0
        return max(
            (d["times"][-1] for d in self._laps.values() if d["times"]),
            default=0.0,
        )

    def _redraw_current(self):
        if not self._cur_times:
            # Meme sans data en cours, on maintient l'axe sur la duree de reference
            ref = self._max_reference_duration()
            if ref > 0:
                self._ax.set_xlim(0.0, ref)
                self._canvas.draw_idle()
            return

        if self._mode == "full_lap":
            xs, ys = self._cur_times, self._cur_speeds
            # Axe X = max entre la progression actuelle et le tour de reference le plus long
            x_max = max(self._cur_times[-1],
                        self._max_reference_duration(), 1.0)
            x_min = 0.0
        else:
            t_end = self._cur_times[-1]
            t_start = max(0.0, t_end - WINDOW_S)
            pairs = [(t, s) for t, s in zip(self._cur_times, self._cur_speeds)
                     if t >= t_start]
            xs = [p[0] for p in pairs]
            ys = [p[1] for p in pairs]
            x_min, x_max = t_start, max(t_end, t_start + 1.0)

        self._cur_line.set_xdata(xs)
        self._cur_line.set_ydata(ys)
        self._ax.set_xlim(x_min, x_max)
        self._canvas.draw_idle()
