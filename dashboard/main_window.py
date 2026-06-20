from f1_parser import parse_packet, PacketCarTelemetryData, PacketLapData, PacketTimeTrialData, PacketParticipantsData, TEAM_NAMES
import socket
import threading

from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMenu
from PyQt6.QtCore import QTimer, QPoint
from PyQt6.QtGui import QFont

from .constants import BG_DARK, BG_MID, TEXT_COLOR, UPDATE_MS
from .widgets.speed_chart import SpeedChart, ms_to_str, COLOR_RIVAL

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class DashboardWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("F1 26 - Telemetrie")
        self.resize(900, 420)
        self.setStyleSheet(
            f"background-color: {BG_DARK}; color: {TEXT_COLOR};")

        self._speed = 0
        self._lap_ms = 0.0
        self._lap_num = 0
        self._last_lap_ms_completed = 0.0  # lastLapTimeInMS du dernier tour complet

        # Rival ghost
        self._rival_idx = -1
        self._rival_speed = 0
        self._rival_lap_ms = 0.0
        self._rival_last_lap_ms_completed = 0.0
        self._rival_position = 0
        self._rival_global_cycle = 1
        self._rival_saved_idx: dict = {}  # {nom -> cycle_key}

        # PB ghost (meilleur tour personnel)
        self._pb_idx = -1
        self._pb_speed = 0
        self._pb_lap_ms = 0.0
        self._pb_saved = False
        self._tt_pb_lap_ms = 0

        # Time Trial : infos statiques du rival
        self._tt_rival_lap_ms = 0
        self._tt_rival_s1_ms = 0
        self._tt_rival_s2_ms = 0
        self._tt_rival_s3_ms = 0
        self._tt_rival_valid = False
        self._tt_rival_name = ""
        self._tt_rival_team = ""
        self._tt_rival_assists = ""

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

        # Bouton overlay tours
        self._btn_overlay = QPushButton("Overlay tours ▾")
        self._btn_overlay.setFixedSize(150, 30)
        self._btn_overlay.setStyleSheet(
            "QPushButton{background:#1e3a5f;color:#ce93d8;border:1px solid #ce93d8;"
            "border-radius:4px;font-size:11px;}"
            "QPushButton:hover{background:#2a4f80;}"
        )
        self._btn_overlay.clicked.connect(self._show_overlay_menu)
        top.addWidget(self._btn_overlay)
        top.addSpacing(8)

        # Bouton toggle mode affichage
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

        self._chart = SpeedChart()
        root.addWidget(self._chart)

        # Bandeau info rival Time Trial
        self._lbl_rival_info = QLabel("")
        self._lbl_rival_info.setFont(QFont("Segoe UI", 10))
        self._lbl_rival_info.setStyleSheet(
            f"color: {COLOR_RIVAL}; background: {BG_MID};"
            "border-radius:4px; padding: 2px 8px;")
        self._lbl_rival_info.setVisible(False)
        root.addWidget(self._lbl_rival_info)

        self.statusBar().setStyleSheet(f"color: #aaa; background: {BG_MID};")
        self.statusBar().showMessage("En attente de donnees UDP sur le port 20777...")

    def _show_overlay_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu{background:#16213e;color:#cccccc;border:1px solid #333355;}"
            "QMenu::item{padding:4px 20px;}"
            "QMenu::item:selected{background:#2a2a4a;}"
            "QMenu::indicator{width:13px;height:13px;}"
        )
        laps = self._chart.lap_info()
        best = self._chart.best_lap_num()

        # Tour en cours (joueur)
        action_cur = menu.addAction("Tour en cours")
        action_cur.setCheckable(True)
        action_cur.setChecked(self._chart._show_cur)
        action_cur.setData("cur")
        menu.addSeparator()

        if not laps:
            action = menu.addAction("Aucun tour enregistre")
            action.setEnabled(False)
        else:
            for lap_num, lap_time_ms in laps:
                label = f"Tour {lap_num}  {ms_to_str(lap_time_ms)}"
                if lap_num == best:
                    label = f"★ {label}"
                action = menu.addAction(label)
                action.setCheckable(True)
                action.setChecked(lap_num in self._chart._visible)
                action.setData(lap_num)
            menu.addSeparator()
            clear_action = menu.addAction("Tout effacer")
            clear_action.setData("clear")

        # Section Rival
        menu.addSeparator()
        rival_header = menu.addAction("── Rival ──")
        rival_header.setEnabled(False)

        action_rival_cur = menu.addAction("Tour en cours (rival)")
        action_rival_cur.setCheckable(True)
        action_rival_cur.setChecked(self._chart._show_rival_cur)
        action_rival_cur.setData("rival_cur")

        rival_laps = self._chart.rival_lap_info()
        best_rival = self._chart.best_rival_lap_num()
        for lap_num, lap_time_ms, lbl in rival_laps:
            display = lbl if lbl else f"Rival Tour {lap_num}"
            label = f"{display}  {ms_to_str(lap_time_ms)}"
            if lap_num == best_rival:
                label = f"★ {label}"
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(lap_num in self._chart._rival_visible)
            action.setData(("rival", lap_num))

        chosen = menu.exec(self._btn_overlay.mapToGlobal(
            QPoint(0, self._btn_overlay.height())))
        if chosen is None:
            return
        if chosen.data() == "cur":
            self._chart.set_cur_visible(not self._chart._show_cur)
        elif chosen.data() == "clear":
            self._chart.set_visible_laps(set())
        elif chosen.data() == "rival_cur":
            self._chart.set_rival_cur_visible(not self._chart._show_rival_cur)
        elif isinstance(chosen.data(), tuple) and chosen.data()[0] == "rival":
            lap_num = chosen.data()[1]
            visible = set(self._chart._rival_visible)
            if lap_num in visible:
                visible.discard(lap_num)
            else:
                visible.add(lap_num)
            self._chart.set_visible_rival_laps(visible)
        elif isinstance(chosen.data(), int):
            visible = set(self._chart._visible)
            lap_num = chosen.data()
            if lap_num in visible:
                visible.discard(lap_num)
            else:
                visible.add(lap_num)
            self._chart.set_visible_laps(visible)

    def _toggle_mode(self):
        if self._chart._mode == "full_lap":
            self._chart.set_mode("window")
            self._btn_mode.setText("Mode : Fenetre 30s")
        else:
            self._chart.set_mode("full_lap")
            self._btn_mode.setText("Mode : Tour complet")

    def _start_udp(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1_048_576)
        self._sock.bind(("0.0.0.0", 20777))
        self._sock.settimeout(1.0)
        threading.Thread(target=self._udp_loop,
                         daemon=True, name="udp").start()

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
                if self._rival_idx >= 0:
                    self._rival_speed = packet.carTelemetryData[self._rival_idx].speed
                if self._pb_idx >= 0:
                    self._pb_speed = packet.carTelemetryData[self._pb_idx].speed
            elif isinstance(packet, PacketTimeTrialData):
                rd = packet.rivalDataSet
                if rd.valid:
                    self._tt_rival_lap_ms = rd.lapTimeInMS
                    self._tt_rival_s1_ms = rd.sector1TimeInMS
                    self._tt_rival_s2_ms = rd.sector2TimeInMS
                    self._tt_rival_s3_ms = rd.sector3TimeInMS
                    self._tt_rival_valid = True
                    self._tt_rival_team = TEAM_NAMES.get(
                        rd.teamId, f"Team {rd.teamId}")
                    self._tt_rival_assists = (
                        f"TC={'On' if rd.tractionControl else 'Off'}  "
                        f"ABS={'On' if rd.antiLockBrakes else 'Off'}  "
                        f"Gear={'Auto' if rd.gearboxAssist else 'Man'}"
                    )
                pb = packet.personalBestDataSet
                if pb.valid:
                    self._tt_pb_lap_ms = pb.lapTimeInMS
            elif isinstance(packet, PacketParticipantsData):
                rd_card_idx = getattr(self, '_tt_rival_card_idx', -1)
                # Mettre à jour l'index du rival à partir du TimeTrialData
                # On stocke déjà _rival_idx depuis PacketLapData
                if self._rival_idx >= 0 and self._rival_idx < len(packet.participants):
                    p = packet.participants[self._rival_idx]
                    self._tt_rival_name = p.name
            elif isinstance(packet, PacketLapData):
                idx = packet.header.playerCarIndex
                lap = packet.lapData[idx]
                self._lap_ms = float(lap.currentLapTimeInMS)
                self._lap_num = int(lap.currentLapNum)
                self._last_lap_ms_completed = float(lap.lastLapTimeInMS)

                # Trouver le rival :
                # En Time Trial -> timeTrialRivalCarIdx (ghost rival)
                # En course     -> voiture directement devant (carPosition - 1)
                tt_rival = packet.timeTrialRivalCarIdx  # 255 si invalide
                if tt_rival != 255 and tt_rival < len(packet.lapData):
                    rival_idx = tt_rival
                else:
                    player_pos = int(lap.carPosition)
                    rival_pos = (player_pos - 1) if player_pos > 1 else 2
                    rival_idx = -1
                    for i, ld in enumerate(packet.lapData):
                        if i != idx and int(ld.carPosition) == rival_pos:
                            rival_idx = i
                            break

                if rival_idx >= 0:
                    self._rival_idx = rival_idx
                    rlap = packet.lapData[rival_idx]
                    self._rival_lap_ms = float(rlap.currentLapTimeInMS)
                    self._rival_last_lap_ms_completed = float(
                        rlap.lastLapTimeInMS)
                    self._rival_position = int(rlap.carPosition)

                # PB ghost index
                tt_pb = packet.timeTrialPBCarIdx
                if tt_pb != 255 and tt_pb < len(packet.lapData):
                    self._pb_idx = tt_pb
                    self._pb_lap_ms = float(
                        packet.lapData[tt_pb].currentLapTimeInMS)

    def _refresh(self):
        speed = self._speed
        lap_ms = self._lap_ms
        lap_num = self._lap_num

        last_lap_ms = getattr(self, '_last_lap_ms', lap_ms)
        last_lap_num = getattr(self, '_last_lap_num', lap_num)

        is_new_lap = (lap_num != last_lap_num)
        is_restart = (not is_new_lap and lap_ms < last_lap_ms - 500)

        if is_new_lap:
            # Tour complet : sauvegarder joueur + ghosts, puis reset buffers
            if last_lap_num > 0 and self._last_lap_ms_completed > 0:
                self._chart.commit_lap(
                    last_lap_num, self._last_lap_ms_completed)

                # Rival ghost : cle = last_lap_num, label = nom du rival
                rival_name = self._tt_rival_name or (
                    f"Rival {self._rival_idx}" if self._rival_idx >= 0 else None)
                if rival_name:
                    lap_label = f"{rival_name} (T{last_lap_num})"
                    # Conserver les anciens, ne jamais écraser
                    if last_lap_num not in self._chart._rival_laps:
                        saved = self._chart.commit_rival_lap(
                            last_lap_num, self._rival_last_lap_ms_completed,
                            label=lap_label)
                        if saved is not None:
                            self._chart.set_visible_rival_laps(
                                self._chart._rival_visible | {last_lap_num})

                # PB ghost : cle = 0, remplace si meilleur temps
                if self._tt_pb_lap_ms > 0:
                    existing = self._chart._rival_laps.get(0)
                    if existing is None or self._tt_pb_lap_ms < existing["lap_time_ms"]:
                        saved = self._chart.commit_pb_lap(self._tt_pb_lap_ms)
                        if saved:
                            self._chart.set_visible_rival_laps(
                                self._chart._rival_visible | {0})

            # Reset buffers pour le nouveau tour
            self._chart.reset()
            self._chart.reset_rival()
            self._chart.reset_pb()

        elif is_restart:
            # Restart sans compléter le tour : jeter les données partielles
            self._chart.reset()
            self._chart.reset_rival()
            self._chart.reset_pb()

        self._last_lap_num = lap_num
        self._last_lap_ms = lap_ms

        # Accumuler les ghosts en continu
        if self._rival_idx >= 0:
            self._chart.append_rival(
                float(self._rival_speed), self._rival_lap_ms)
        if self._pb_idx >= 0:
            self._chart.append_pb(float(self._pb_speed), self._pb_lap_ms)

        self._lbl_lap.setText(f"Tour {lap_num}")
        self._lbl_speed.setText(f"{speed} km/h")
        self._chart.append(float(speed), lap_ms)

        # Bandeau rival Time Trial
        if self._tt_rival_valid:
            name_part = f"{self._tt_rival_name}  " if self._tt_rival_name else ""
            team_part = f"({self._tt_rival_team})  " if self._tt_rival_team else ""
            assists = getattr(self, '_tt_rival_assists', '')
            s1 = ms_to_str(self._tt_rival_s1_ms)
            s2 = ms_to_str(self._tt_rival_s2_ms)
            s3 = ms_to_str(self._tt_rival_s3_ms)
            lap = ms_to_str(self._tt_rival_lap_ms)
            self._lbl_rival_info.setText(
                f"Rival : {name_part}{team_part}—  "
                f"Tour : {lap}    S1 : {s1}    S2 : {s2}    S3 : {s3}    {assists}")
            self._lbl_rival_info.setVisible(True)

        rival_info = ""
        if self._rival_idx >= 0:
            rival_info = f"  |  Rival (P{self._rival_position}) : {self._rival_speed} km/h"
        self.statusBar().showMessage(
            f"Vitesse : {speed} km/h  |  Tps tour : {lap_ms/1000:.3f} s  |  Tour : {lap_num}{rival_info}")

    def closeEvent(self, event):
        try:
            self._sock.close()
        except Exception:
            pass
        super().closeEvent(event)
