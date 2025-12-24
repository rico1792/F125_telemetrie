
# telemetry_capture.py
import socket
import sys
import time
from f1_parser import (
    parse_packet,
    PacketCarTelemetryData,
    PacketLapData,
    PacketTimeTrialData,
)
from telemetry_store import append_point, get_logger, telemetry_stat, telemetry_lock

UDP_IP = "0.0.0.0"
UDP_PORT = 20777
_logger = get_logger()


def run_capture():
    """Boucle de capture UDP F1 25 -> append_point(...) + statut console + meta TimeTrial."""
    # Socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET,
                            socket.SO_RCVBUF, 1_048_576)  # 1 MiB
            _logger.info("SO_RCVBUF set to 1MiB")
        except Exception as e:
            _logger.warning("SO_RCVBUF set failed: %s", e)
        sock.bind((UDP_IP, UDP_PORT))
        sock.setblocking(False)
        print(f"[capture] Écoute UDP sur {UDP_IP}:{UDP_PORT} (OK)")
        print("[capture] Assure-toi que F1 25 envoie vers 127.0.0.1:20777")
        _logger.info("UDP bind OK on %s:%d", UDP_IP, UDP_PORT)
    except OSError as e:
        msg = f"[capture][ERREUR] Impossible de bind sur {UDP_IP}:{UDP_PORT} -> {e}"
        print(msg)
        _logger.error(msg)
        return

    last_lap_pkt = None
    tt_pb_idx = 255       # index PB en Time Trial (255 = invalide)
    tt_rival_idx = 255    # index Rival en Time Trial (255 = invalide)

    last_print = 0
    PRINT_HZ = 20  # console seulement
    pkt_count = 0
    t0 = time.time()
    last_pps_log = t0

    try:
        while True:
            try:
                data, addr = sock.recvfrom(4096)
            except BlockingIOError:
                time.sleep(0.001)
                continue
            except Exception as e:
                _logger.error("recvfrom ERROR: %s", e)
                continue

            packet = parse_packet(data)
            if not packet:
                continue

            # --- Time Trial meta (PB/Rival times & carIdx) ---
            if isinstance(packet, PacketTimeTrialData):
                try:
                    with telemetry_lock:
                        # Personal Best
                        telemetry_stat["tt_pb_car_idx"] = int(
                            packet.personalBestDataSet.carIdx)
                        telemetry_stat["tt_pb_lap_ms"] = int(
                            packet.personalBestDataSet.lapTimeInMS)
                        telemetry_stat["tt_pb_valid"] = int(
                            packet.personalBestDataSet.valid)
                        # Rival
                        telemetry_stat["tt_rival_car_idx"] = int(
                            packet.rivalDataSet.carIdx)
                        telemetry_stat["tt_rival_lap_ms"] = int(
                            packet.rivalDataSet.lapTimeInMS)
                        telemetry_stat["tt_rival_valid"] = int(
                            packet.rivalDataSet.valid)
                        # Optionnel : session best du joueur
                        telemetry_stat["tt_player_session_best_ms"] = int(
                            packet.playerSessionBestDataSet.lapTimeInMS
                        )
                except Exception as e:
                    _logger.warning("TIME_TRIAL meta update failed: %s", e)
                # on continue la boucle (on attend les trames CarTelemetry/LapData)
                continue

            # --- LapData: garder l'index PB & Rival (Time Trial) ---
            if isinstance(packet, PacketLapData):
                last_lap_pkt = packet
                try:
                    tt_pb_idx = int(getattr(packet, "timeTrialPBCarIdx", 255))
                except Exception:
                    tt_pb_idx = 255
                try:
                    tt_rival_idx = int(
                        getattr(packet, "timeTrialRivalCarIdx", 255))
                except Exception:
                    tt_rival_idx = 255
                # mettre à jour meta (utile si TIME_TRIAL arrive en décalé)
                try:
                    with telemetry_lock:
                        telemetry_stat["tt_pb_car_idx"] = tt_pb_idx
                        telemetry_stat["tt_rival_car_idx"] = tt_rival_idx
                except Exception:
                    pass
                continue  # on attend les trames de télémétrie pour pousser les points

            # --- CarTelemetryData: pousser player + pb + rival (si valides) ---
            if isinstance(packet, PacketCarTelemetryData):
                pkt_count += 1
                now = time.time()

                # Log PPS (packets per second) toutes les 5 s
                if now - last_pps_log >= 5.0:
                    pps = pkt_count / max(1e-6, (now - t0))
                    _logger.info("PPS=%.1f (packets count=%d)", pps, pkt_count)
                    last_pps_log = now

                # Indices de voiture
                player_idx = packet.header.playerCarIndex
                indices = [("player", player_idx)]

                # Ajouter PB & Rival si valides (0..21)
                if isinstance(tt_pb_idx, int) and 0 <= tt_pb_idx < len(packet.carTelemetryData):
                    indices.append(("pb", tt_pb_idx))
                if isinstance(tt_rival_idx, int) and 0 <= tt_rival_idx < len(packet.carTelemetryData):
                    indices.append(("rival", tt_rival_idx))

                # Parcourir les séries à enregistrer
                for who, car_idx in indices:
                    try:
                        car = packet.carTelemetryData[car_idx]
                    except Exception:
                        continue

                    # LapData correspondant à cette voiture (si dispo)
                    lap = None
                    if last_lap_pkt is not None:
                        try:
                            lap = last_lap_pkt.lapData[car_idx]
                        except Exception:
                            lap = None

                    pos_str = str(
                        getattr(lap, "carPosition", "?")) if lap else "?"
                    lap_num = int(getattr(lap, "currentLapNum", 0) or 0)
                    last_ms = int(getattr(lap, "lastLapTimeInMS", 0) or 0)
                    invalid = int(getattr(lap, "currentLapInvalid", 0) or 0)
                    lapDist = float(getattr(lap, "lapDistance", 0.0) or 0.0)
                    curLapMs = float(
                        getattr(lap, "currentLapTimeInMS", 0.0) or 0.0)

                    # Console (rate-limité) pour le player seulement
                    if who == "player" and (now - last_print >= 1.0 / PRINT_HZ):
                        sys.stdout.write(
                            f"\r[{who}] Vitesse: {car.speed:4d} km/h "
                            f"Pos: {pos_str} Lap: {lap_num} "
                            f"LastLap: {last_ms} ms Invalid: {invalid} "
                            f"Laps time: {curLapMs:.0f} ms "
                        )
                        sys.stdout.flush()
                        last_print = now

                    # Pousser le point
                    append_point({
                        "t": time.time(),
                        "t_game_ms": curLapMs,
                        "speed": car.speed,
                        "rpm": car.engineRPM,
                        "gear": car.gear,
                        "throttle": car.throttle,
                        "brake": car.brake,
                        "lap": lap_num,
                        "invalid": invalid,
                        "lapDist": lapDist,
                        "who": who,  # <-- player / pb / rival
                    })

    except KeyboardInterrupt:
        print("\n[capture] Arrêt demandé (Ctrl+C)")
        _logger.info("Capture stopped by user")
    finally:
        try:
            sock.close()
            print("\n[capture] Socket fermée.")
            _logger.info("Socket closed")
        except Exception:
            pass
