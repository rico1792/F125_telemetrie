import socket
import threading

from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFont

from .constants import BG_DARK, BG_MID, TEXT_COLOR, UPDATE_MS
from .widgets.speed_chart import SpeedChart

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from f1_parser import parse_packet, PacketCarTelemetryData


class DashboardWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("F1 26 - Telemetrie")
        self.resize(900, 420)
        self.setStyleSheet(f"background-color: {BG_DARK}; color: {TEXT_COLOR};")

        self._speed = 0

        self._build_ui()
        self._start_udp()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(UPDATE_MS)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        top = QHBoxLayout()
        title = QLabel("F1 26 - Vitesse")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff;")
        top.addWidget(title)
        top.addStretch()

        self._lbl_speed = QLabel("0 km/h")
        self._lbl_speed.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        self._lbl_speed.setStyleSheet("color: #4fc3f7;")
        top.addWidget(self._lbl_speed)
        root.addLayout(top)

        self._chart = SpeedChart()
        root.addWidget(self._chart)

        self.statusBar().setStyleSheet(f"color: #aaa; background: {BG_MID};")
        self.statusBar().showMessage("En attente de donnees UDP sur le port 20777...")

    def _start_udp(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1_048_576)
        self._sock.bind(("0.0.0.0", 20777))
        self._sock.settimeout(1.0)
        threading.Thread(target=self._udp_loop, daemon=True, name="udp").start()

    def _udp_loop(self):
        while True:
            try:
                data, _ = self._sock.recvfrom(4096)
            except socket.timeout:
                continue
            except Exception:
                break
            packet = parse_packet(data)
            if isinstance(packet, PacketCarTelemetryData):
                idx = packet.header.playerCarIndex
                self._speed = packet.carTelemetryData[idx].speed

    def _refresh(self):
        speed = self._speed
        self._lbl_speed.setText(f"{speed} km/h")
        self._chart.append(float(speed))
        self.statusBar().showMessage(f"Vitesse : {speed} km/h")

    def closeEvent(self, event):
        try:
            self._sock.close()
        except Exception:
            pass
        super().closeEvent(event)
