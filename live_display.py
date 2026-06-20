"""
live_display.py - Affiche la vitesse en temps reel sur une seule ligne.
Usage : py -3 live_display.py   (Ctrl+C pour quitter)
"""
import socket
import sys
from f1_parser import parse_packet, PacketCarTelemetryData

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", 20777))
sock.settimeout(1.0)
print("Ecoute UDP port 20777... (Ctrl+C pour quitter)")

try:
    while True:
        try:
            data, _ = sock.recvfrom(4096)
        except socket.timeout:
            continue
        packet = parse_packet(data)
        if isinstance(packet, PacketCarTelemetryData):
            idx = packet.header.playerCarIndex
            speed = packet.carTelemetryData[idx].speed
            sys.stdout.write(f"\rVitesse : {speed:>4d} km/h   ")
            sys.stdout.flush()
except KeyboardInterrupt:
    print("\nArrete.")
finally:
    sock.close()
