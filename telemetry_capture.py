
# telemetry_capture.py
import socket
import sys
import time
from f1_parser import parse_packet, PacketCarTelemetryData, PacketLapData
from telemetry_store import telemetry_buf  # buffer partagé

UDP_IP = "0.0.0.0"
UDP_PORT = 20777


def run_capture():
    """Boucle de capture UDP F1 25 -> remplit telemetry_buf et loggue une ligne statut."""
    # >>> Ajout: try/except autour du bind + message clair si port occupé
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((UDP_IP, UDP_PORT))
        sock.setblocking(False)
        print(f"[capture] Écoute UDP sur {UDP_IP}:{UDP_PORT} (OK)")
        print("[capture] Assure-toi que F1 25 envoie vers 127.0.0.1:20777")
    except OSError as e:
        print(
            f"[capture][ERREUR] Impossible de bind sur {UDP_IP}:{UDP_PORT} -> {e}")
        print("[capture] Le port est peut-être déjà utilisé (instance précédente ?)")
        return  # on sort proprement: le thread ne tourne pas

    last_lap_pkt = None
    last_print = 0
    PRINT_HZ = 20  # rafraîchissement console

    try:
        while True:
            try:
                data, addr = sock.recvfrom(4096)
            except BlockingIOError:
                time.sleep(0.001)  # micro-sommeil pour ne pas saturer le CPU
                continue
            except Exception as e:
                # >>> Ajout: log de l'erreur ponctuelle de réception
                print(f"[capture][recv error] {type(e).__name__}: {e}")
                continue

            packet = parse_packet(data)
            if not packet:
                continue

            # 1) Mémoriser LapData
            if isinstance(packet, PacketLapData):
                last_lap_pkt = packet
                continue

            # 2) Traiter CarTelemetry et pousser dans le buffer
            if isinstance(packet, PacketCarTelemetryData):
                player_idx = packet.header.playerCarIndex
                car = packet.carTelemetryData[player_idx]
                # Fallback si LapData pas encore reçu
                lap = last_lap_pkt.lapData[player_idx] if last_lap_pkt else None
                pos_str = str(lap.carPosition) if lap else "?"
                lap_num = lap.currentLapNum if lap else 0
                last_ms = lap.lastLapTimeInMS if lap else 0
                invalid = int(lap.currentLapInvalid) if lap else 0
                lapDist = float(lap.lapDistance) if lap else 0.0

                # Ligne statut rate-limitée
                now = time.time()
                if now - last_print >= 1.0 / PRINT_HZ:
                    sys.stdout.write(
                        f"\rVitesse: {car.speed:4d} km/h | "
                        f"Pos: {pos_str} | Lap: {lap_num} | "
                        f"LastLap: {last_ms} ms | Invalid: {invalid}"
                    )
                    sys.stdout.flush()
                    last_print = now

                telemetry_buf.append({
                    "t": time.time(),
                    "speed": car.speed,
                    "rpm": car.engineRPM,
                    "gear": car.gear,
                    "throttle": car.throttle,
                    "brake": car.brake,
                    "steer": car.steer,
                    "lap": lap_num,
                    "invalid": invalid,
                    "lapDist": lapDist,
                })
    except KeyboardInterrupt:
        print("\n[capture] Arrêt demandé (Ctrl+C)")
    finally:
        try:
            sock.close()
            print("\n[capture] Socket fermée.")
        except Exception:
            pass
