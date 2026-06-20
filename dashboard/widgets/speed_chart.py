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
COLOR_RIVAL = "#ff8a65"
_RIVAL_COLORS = ["#ff8a65", "#ef9a9a", "#ffab40", "#ffcc80"]


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
        self._show_cur: bool = True

        # Rival
        self._rival_cur_times:  list = []
        self._rival_cur_speeds: list = []
        self._rival_laps: dict = {}
        self._rival_visible: set = set()
        self._rival_overlay_lines: dict = {}
        self._show_rival_cur: bool = False

        # PB ghost (meilleur tour personnel)
        self._pb_cur_times:  list = []
        self._pb_cur_speeds: list = []
        self._legend = None

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
            [], [], color=COLOR_CURRENT, linewidth=2, zorder=10, label="Tour en cours"
        )
        (self._rival_cur_line,) = self._ax.plot(
            [], [], color=COLOR_RIVAL, linewidth=2, linestyle="--", alpha=0.85, zorder=9, visible=False, label="Rival (en cours)"
        )

        self._legend = self._ax.legend(
            loc="upper left", framealpha=0.25, facecolor=BG_DARK,
            edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=9
        )

        self._canvas = FigureCanvas(fig)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

    def set_cur_visible(self, show: bool):
        self._show_cur = show
        self._cur_line.set_visible(show)
        self._canvas.draw_idle()

    def set_mode(self, mode: str):
        self._mode = mode
        self._redraw_current()

    def append(self, speed: float, lap_ms: float):
        if lap_ms <= 0:
            return  # pas encore franchi la ligne de depart
        t = lap_ms / 1000.0
        # Ignorer les points non monotones (paquets en desordre ou transitoires)
        if self._cur_times and t < self._cur_times[-1]:
            return
        self._cur_speeds.append(speed)
        self._cur_times.append(t)
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

    # ── Rival ───────────────────────────────────────────────────────────

    def append_rival(self, speed: float, lap_ms: float):
        if lap_ms <= 0 or speed <= 0:
            return  # ghost hors piste ou à l'arrêt
        t = lap_ms / 1000.0
        # Ignorer les points non monotones
        if self._rival_cur_times and t < self._rival_cur_times[-1]:
            return
        self._rival_cur_speeds.append(speed)
        self._rival_cur_times.append(t)
        self._redraw_rival_cur()

    def reset_rival(self):
        self._rival_cur_times.clear()
        self._rival_cur_speeds.clear()
        self._rival_cur_line.set_xdata([])
        self._rival_cur_line.set_ydata([])
        self._canvas.draw_idle()

    def append_pb(self, speed: float, lap_ms: float):
        t = lap_ms / 1000.0
        if self._pb_cur_times and t < self._pb_cur_times[-1]:
            return
        self._pb_cur_speeds.append(speed)
        self._pb_cur_times.append(t)

    def reset_pb(self):
        self._pb_cur_times.clear()
        self._pb_cur_speeds.clear()

    def commit_pb_lap(self, lap_time_ms: float) -> bool:
        """Sauvegarde le PB ghost dans _rival_laps avec la cle 0 et le label fixe."""
        if len(self._pb_cur_times) < 5:
            return False
        self._rival_laps[0] = {
            "times":       list(self._pb_cur_times),
            "speeds":      list(self._pb_cur_speeds),
            "lap_time_ms": lap_time_ms,
            "label":       "Meilleur perso",
        }
        return True

    def commit_pb_from_player_lap(self, lap_time_ms: float) -> bool:
        """Sauvegarde le tour courant du JOUEUR comme PB ghost (donnees exactes)."""
        if len(self._cur_times) < 5:
            return False
        existing = self._rival_laps.get(0)
        if existing is not None and lap_time_ms >= existing["lap_time_ms"]:
            return False  # pas un nouveau PB
        self._rival_laps[0] = {
            "times":       list(self._cur_times),
            "speeds":      list(self._cur_speeds),
            "lap_time_ms": lap_time_ms,
            "label":       "Meilleur perso",
        }
        return True

    def commit_rival_lap(self, lap_num: int, lap_time_ms: float, label: str = ""):
        if len(self._rival_cur_times) < 5:
            return None
        self._rival_laps[lap_num] = {
            "times":       list(self._rival_cur_times),
            "speeds":      list(self._rival_cur_speeds),
            "lap_time_ms": lap_time_ms,
            "label":       label,
        }
        return lap_num

    def set_rival_cur_visible(self, show: bool):
        self._show_rival_cur = show
        self._redraw_rival_cur()
        self._redraw_current()  # met à jour l'axe X si le rival s'étend plus loin

    def set_visible_rival_laps(self, lap_nums: set):
        self._rival_visible = set(lap_nums)
        self._rebuild_rival_overlays()

    def best_rival_lap_num(self):
        if not self._rival_laps:
            return None
        return min(
            (n for n, d in self._rival_laps.items() if d["lap_time_ms"] > 0),
            key=lambda n: self._rival_laps[n]["lap_time_ms"],
            default=None,
        )

    def rival_lap_info(self):
        """Retourne [(lap_num, lap_time_ms, label), ...] triés par lap_num."""
        return sorted(
            [(n, d["lap_time_ms"], d.get("label", ""))
             for n, d in self._rival_laps.items()],
            key=lambda x: x[0],
        )

    def _rebuild_rival_overlays(self):
        for lap_num in list(self._rival_overlay_lines):
            if lap_num not in self._rival_visible:
                self._rival_overlay_lines[lap_num].remove()
                del self._rival_overlay_lines[lap_num]

        best = self.best_rival_lap_num()
        color_idx = 0
        for lap_num in sorted(self._rival_visible):
            if lap_num not in self._rival_laps:
                continue
            if lap_num in self._rival_overlay_lines:
                continue
            rec = self._rival_laps[lap_num]
            color = COLOR_BEST if lap_num == best else _RIVAL_COLORS[color_idx % len(
                _RIVAL_COLORS)]
            color_idx += 1
            lbl = rec.get("label") or f"Rival {lap_num}"
            (line,) = self._ax.plot(
                rec["times"], rec["speeds"],
                color=color, linewidth=1.5, alpha=0.75, zorder=5, linestyle="--",
                label=lbl,
            )
            self._rival_overlay_lines[lap_num] = line

        self._canvas.draw_idle()
        self._update_legend()
        self._redraw_current()

    def _redraw_rival_cur(self):
        self._rival_cur_line.set_visible(self._show_rival_cur)
        if self._show_rival_cur and self._rival_cur_times:
            self._rival_cur_line.set_xdata(self._rival_cur_times)
            self._rival_cur_line.set_ydata(self._rival_cur_speeds)
        self._update_legend()
        self._canvas.draw_idle()

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
            star = "\u2605 " if lap_num == best else ""
            (line,) = self._ax.plot(
                rec["times"], rec["speeds"],
                color=color, linewidth=1.5, alpha=0.75, zorder=5,
                label=f"{star}Tour {lap_num}  {ms_to_str(rec['lap_time_ms'])}",
            )
            self._overlay_lines[lap_num] = line

        self._canvas.draw_idle()
        self._update_legend()
        # Mettre a jour l'axe X apres changement des overlays
        self._redraw_current()

    def _update_legend(self):
        """Reconstruit la legende avec toutes les lignes visibles."""
        lines, labels = [], []
        if self._show_cur and self._cur_times:
            lines.append(self._cur_line)
            labels.append("Tour en cours")
        if self._show_rival_cur and self._rival_cur_times:
            lines.append(self._rival_cur_line)
            labels.append("Rival (en cours)")
        for line in self._overlay_lines.values():
            lines.append(line)
            labels.append(line.get_label())
        for line in self._rival_overlay_lines.values():
            lines.append(line)
            labels.append(line.get_label())
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

    def _max_reference_duration(self) -> float:
        all_laps = list(self._laps.values()) + list(self._rival_laps.values())
        durations = [d["times"][-1] for d in all_laps if d["times"]]
        if self._show_rival_cur and self._rival_cur_times:
            durations.append(self._rival_cur_times[-1])
        return max(durations, default=0.0)

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
        self._cur_line.set_visible(self._show_cur)
        self._ax.set_xlim(x_min, x_max)
        self._update_legend()
        self._canvas.draw_idle()
