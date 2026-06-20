"""
speed_chart.py - Graphique vitesse F1 26 avec axe X = temps du tour en cours.
Deux modes : 'full_lap' (depuis 0) ou 'window' (N dernieres secondes).
"""
import matplotlib
matplotlib.use("QtAgg")

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from PyQt6.QtWidgets import QWidget, QVBoxLayout

from ..constants import BG_DARK, GRID_COLOR, TEXT_COLOR

WINDOW_S = 30   # secondes visibles en mode fenetre glissante


class SpeedChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._mode = "full_lap"   # "full_lap" | "window"
        self._speeds: list = []
        self._times:  list = []

        fig = Figure(figsize=(8, 3), facecolor=BG_DARK)
        self._ax = fig.add_subplot(111, facecolor=BG_DARK)
        self._ax.set_ylim(0, 380)
        self._ax.set_xlabel("Temps du tour (s)", color=TEXT_COLOR)
        self._ax.set_ylabel("km/h", color=TEXT_COLOR)
        self._ax.tick_params(colors=TEXT_COLOR)
        self._ax.grid(True, color=GRID_COLOR, linewidth=0.5)
        for spine in self._ax.spines.values():
            spine.set_edgecolor(GRID_COLOR)

        (self._line,) = self._ax.plot([], [], color="#4fc3f7", linewidth=1.5)

        self._canvas = FigureCanvas(fig)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

    def set_mode(self, mode: str):
        """mode = 'full_lap' ou 'window'."""
        self._mode = mode
        self._redraw()

    def append(self, speed: float, lap_ms: float):
        """Ajoute un point. lap_ms = currentLapTimeInMS du jeu."""
        self._speeds.append(speed)
        self._times.append(lap_ms / 1000.0)
        self._redraw()

    def reset(self):
        """Vide le graphique au debut d'un nouveau tour."""
        self._speeds.clear()
        self._times.clear()
        self._line.set_xdata([])
        self._line.set_ydata([])
        self._ax.set_xlim(0, 1)
        self._canvas.draw_idle()

    def _redraw(self):
        if not self._times:
            return
        if self._mode == "full_lap":
            xs = self._times
            ys = self._speeds
            x_min = 0.0
            x_max = max(self._times[-1], 1.0)
        else:  # window
            t_end   = self._times[-1]
            t_start = max(0.0, t_end - WINDOW_S)
            pairs   = [(t, s) for t, s in zip(self._times, self._speeds) if t >= t_start]
            xs      = [p[0] for p in pairs]
            ys      = [p[1] for p in pairs]
            x_min   = t_start
            x_max   = max(t_end, t_start + 1.0)

        self._line.set_xdata(xs)
        self._line.set_ydata(ys)
        self._ax.set_xlim(x_min, x_max)
        self._canvas.draw_idle()
