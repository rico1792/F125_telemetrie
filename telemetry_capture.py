
# telemetry_capture.py
import socket
import sys
import time
from f1_parser import parse_packet, PacketCarTelemetryData, PacketLapData
from telemetry_store import append_point, get_logger

UDP_IP = "0.0.0.0"
UDP_PORT = 20777
_logger = get_logger()


def run_capture():
    """Boucle de capture UDP F1 25 -> append_point(...) + statut console."""
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

            if isinstance(packet, PacketLapData):
                last_lap_pkt = packet
                continue

            if isinstance(packet, PacketCarTelemetryData):
                pkt_count += 1
                now = time.time()

                # Log PPS (packets per second) toutes les 5 s
                if now - last_pps_log >= 5.0:
                    pps = pkt_count / max(1e-6, (now - t0))
                    _logger.info("PPS=%.1f (packets count=%d)", pps, pkt_count)
                    last_pps_log = now

                player_idx = packet.header.playerCarIndex
                car = packet.carTelemetryData[player_idx]
                lap = last_lap_pkt.lapData[player_idx] if last_lap_pkt else None

                pos_str = str(getattr(lap, "carPosition", "?")) if lap else "?"
                lap_num = int(getattr(lap, "currentLapNum", 0) or 0)
                last_ms = int(getattr(lap, "lastLapTimeInMS", 0) or 0)
                invalid = int(getattr(lap, "currentLapInvalid", 0) or 0)
                lapDist = float(getattr(lap, "lapDistance", 0.0) or 0.0)
                curLapMs = float(
                    getattr(lap, "currentLapTimeInMS", 0.0) or 0.0)

                # Console (rate-limité)
                if now - last_print >= 1.0 / PRINT_HZ:
                    sys.stdout.write(
                        f"\rVitesse: {car.speed:4d} km/h "
                        f"Pos: {pos_str} Lap: {lap_num} "
                        f"LastLap: {last_ms} ms Invalid: {invalid} "
                        f"Laps time: {curLapMs:.0f} ms "
                    )
                    sys.stdout.flush()
                    last_print = now

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
