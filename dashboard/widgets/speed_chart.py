"""
speed_chart.py — Graphique matplotlib temps réel de la vitesse F1 26.
S'alimente via append(speed) appelé par la fenêtre principale.
"""
from ..constants import HISTORY, BG_DARK, GRID_COLOR, TEXT_COLOR
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from collections import deque
import matplotlib
matplotlib.use("QtAgg")


class SpeedChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._data: deque[float] = deque([0.0] * HISTORY, maxlen=HISTORY)

        fig = Figure(figsize=(8, 3), facecolor=BG_DARK)
        self._ax = fig.add_subplot(111, facecolor=BG_DARK)
        self._ax.set_ylim(0, 380)
        self._ax.set_xlim(0, HISTORY - 1)
        self._ax.set_ylabel("km/h", color=TEXT_COLOR)
        self._ax.tick_params(colors=TEXT_COLOR)
        self._ax.grid(True, color=GRID_COLOR, linewidth=0.5)
        for spine in self._ax.spines.values():
            spine.set_edgecolor(GRID_COLOR)

        (self._line,) = self._ax.plot(
            list(self._data), color="#4fc3f7", linewidth=1.5
        )

        self._canvas = FigureCanvas(fig)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

    def append(self, speed: float):
        self._data.append(speed)
        self._line.set_ydata(list(self._data))
        self._canvas.draw_idle()
