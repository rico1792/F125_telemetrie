"""
iracing_window.py - Dashboard télémétrie iRacing (accélérateur, freins, vitesse).

Utilise pyirsdk pour lire les données en mémoire partagée d'iRacing et les
afficher dans les mêmes widgets SpeedChart et AccelBrakeChart que le dashboard F1.
"""
import irsdk

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton,
)
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFont

from dashboard.constants import BG_DARK, BG_MID, TEXT_COLOR, UPDATE_MS
from dashboard.widgets.speed_chart import SpeedChart, ms_to_str
from dashboard.widgets.accel_brake_chart import AccelBrakeChart


class IracingWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("iRacing - Télémétrie")
        self.resize(900, 620)
        self.setStyleSheet(
            f"background-color: {BG_DARK}; color: {TEXT_COLOR};"
        )

        self._ir = irsdk.IRSDK()
        self._connected = False

        # Données instantanées
        self._speed    = 0.0   # km/h
        self._throttle = 0.0   # 0-1
        self._brake    = 0.0   # 0-1
        self._lap_ms   = 0.0   # ms
        self._lap_num  = 0

        self._last_lap_ms  = 0.0
        self._last_lap_num = 0

        self._build_ui()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(UPDATE_MS)

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        # Barre du haut
        top = QHBoxLayout()

        title = QLabel("iRacing - Vitesse")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff;")
        top.addWidget(title)
        top.addStretch()

        self._btn_mode = QPushButton("Mode : Tour complet")
        self._btn_mode.setFixedSize(180, 30)
        self._btn_mode.setStyleSheet(
            "QPushButton{background:#1e3a5f;color:#4fc3f7;border:1px solid #4fc3f7;"
            "border-radius:4px;font-size:11px;}"
            "QPushButton:hover{background:#2a4f80;}"
        )
        self._btn_mode.clicked.connect(self._toggle_mode)
        top.addWidget(self._btn_mode)
        top.addSpacing(12)

        self._lbl_lap = QLabel("Tour —")
        self._lbl_lap.setFont(QFont("Segoe UI", 14))
        self._lbl_lap.setStyleSheet("color: #aaaaaa;")
        top.addWidget(self._lbl_lap)
        top.addSpacing(16)

        self._lbl_speed = QLabel("0 km/h")
        self._lbl_speed.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        self._lbl_speed.setStyleSheet("color: #4fc3f7;")
        top.addWidget(self._lbl_speed)

        root.addLayout(top)

        self._speed_chart = SpeedChart()
        root.addWidget(self._speed_chart)

        self._accel_chart = AccelBrakeChart()
        root.addWidget(self._accel_chart)

        self.statusBar().setStyleSheet(f"color: #aaa; background: {BG_MID};")
        self.statusBar().showMessage("En attente de iRacing...")

    # ── Logique de rafraîchissement ───────────────────────────────────────

    def _refresh(self):
        # Tentative de connexion si non connecté
        if not self._connected:
            try:
                self._ir.startup()
                if self._ir.is_initialized and self._ir.is_connected:
                    self._connected = True
                    self.statusBar().showMessage("iRacing connecté.")
                else:
                    self.statusBar().showMessage("En attente de iRacing...")
                    return
            except Exception:
                self.statusBar().showMessage("En attente de iRacing...")
                return

        # Vérifier que la connexion est toujours active
        self._ir.freeze_var_buffer_latest()
        if not self._ir.is_connected:
            self._connected = False
            self.statusBar().showMessage("iRacing déconnecté. En attente...")
            return

        # Lire les valeurs de télémétrie
        throttle   = float(self._ir["Throttle"]          or 0.0)
        brake      = float(self._ir["Brake"]             or 0.0)
        speed_ms   = float(self._ir["Speed"]             or 0.0)   # m/s
        lap_time_s = float(self._ir["LapCurrentLapTime"] or 0.0)   # s
        lap_num    = int(self._ir["Lap"]                 or 0)
        last_lap_s = float(self._ir["LapLastLapTime"]    or 0.0)   # s

        speed_kmh  = speed_ms * 3.6
        lap_ms     = lap_time_s * 1000.0
        last_lap_ms = last_lap_s * 1000.0

        is_new_lap  = (lap_num != self._last_lap_num)
        is_restart  = (not is_new_lap and lap_ms < self._last_lap_ms - 500)

        if is_new_lap:
            if self._last_lap_num > 0 and last_lap_ms > 0:
                self._speed_chart.commit_lap(self._last_lap_num, last_lap_ms)
                self._accel_chart.commit_lap(self._last_lap_num, last_lap_ms)
                # PB from player lap
                self._speed_chart.commit_pb_from_player_lap(last_lap_ms)
            self._speed_chart.reset()
            self._accel_chart.reset()

        elif is_restart:
            self._speed_chart.reset()
            self._speed_chart.reset_rival()
            self._speed_chart.reset_pb()
            self._accel_chart.reset()

        self._last_lap_num = lap_num
        self._last_lap_ms  = lap_ms

        self._lbl_lap.setText(f"Tour {lap_num}")
        self._lbl_speed.setText(f"{speed_kmh:.0f} km/h")
        self._speed_chart.append(speed_kmh, lap_ms)
        self._accel_chart.append(throttle, brake, lap_ms)

        # Synchroniser les overlays
        if self._accel_chart._visible != self._speed_chart._visible:
            self._accel_chart.set_visible_laps(set(self._speed_chart._visible))

        self.statusBar().showMessage(
            f"Vitesse : {speed_kmh:.0f} km/h  |  "
            f"Accel : {throttle*100:.0f}%  |  "
            f"Frein : {brake*100:.0f}%  |  "
            f"Tps tour : {lap_time_s:.3f} s  |  Tour : {lap_num}"
        )

    def _toggle_mode(self):
        if self._speed_chart._mode == "full_lap":
            self._speed_chart.set_mode("window")
            self._accel_chart.set_mode("window")
            self._btn_mode.setText("Mode : Fenetre 30s")
        else:
            self._speed_chart.set_mode("full_lap")
            self._accel_chart.set_mode("full_lap")
            self._btn_mode.setText("Mode : Tour complet")

    def closeEvent(self, event):
        try:
            self._ir.shutdown()
        except Exception:
            pass
        super().closeEvent(event)
