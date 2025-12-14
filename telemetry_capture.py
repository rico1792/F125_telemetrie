import socket
import sys
from f1_parser import parse_packet, PacketCarTelemetryData

# Configuration UDP
UDP_IP = "0.0.0.0"
UDP_PORT = 20777      # Port par défaut pour F1 25

# Créer le socket UDP
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))
sock.setblocking(False)  # Mode non-bloquant pour réactivité maximale

print("Écoute des données de télémétrie sur {}:{}".format(UDP_IP, UDP_PORT))
print("Assurez-vous que dans F1 25, la télémétrie est activée et configurée pour envoyer vers 127.0.0.1:20777")

try:
    while True:
        try:
            data, addr = sock.recvfrom(2048)
            packet = parse_packet(data)
            if packet and isinstance(packet, PacketCarTelemetryData):
                speed = packet.carTelemetryData[packet.header.playerCarIndex].speed
                sys.stdout.write(f"\rVitesse: {speed} km/h")
                sys.stdout.flush()

        except BlockingIOError:
            continue  # Pas de données disponibles, continuer immédiatement
        except Exception:
            continue  # Ignorer les erreurs de parsing
except KeyboardInterrupt:
    print("\nArrêt de l'écoute...")
finally:
    sock.close()
