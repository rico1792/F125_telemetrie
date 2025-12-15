import struct
from typing import List, Optional

# Constantes
MAX_NUM_CARS_IN_UDP_DATA = 22
MAX_PARTICIPANT_NAME_LEN = 32
MAX_TYRE_STINTS = 8
MAX_NUM_TYRE_SETS = 13 + 7

# Enum pour les types de paquets


class PacketId:
    MOTION = 0
    SESSION = 1
    LAP_DATA = 2
    EVENT = 3
    PARTICIPANTS = 4
    CAR_SETUPS = 5
    CAR_TELEMETRY = 6
    CAR_STATUS = 7
    FINAL_CLASSIFICATION = 8
    LOBBY_INFO = 9
    CAR_DAMAGE = 10
    SESSION_HISTORY = 11
    TYRE_SETS = 12
    MOTION_EX = 13
    TIME_TRIAL = 14
    LAP_POSITIONS = 15

# Classes pour les structures de données


class PacketHeader:
    def __init__(self, data: bytes):
        unpacked = struct.unpack('<HBBBBBQfIIBB', data[:29])
        self.packetFormat = unpacked[0]
        self.gameYear = unpacked[1]
        self.gameMajorVersion = unpacked[2]
        self.gameMinorVersion = unpacked[3]
        self.packetVersion = unpacked[4]
        self.packetId = unpacked[5]
        self.sessionUID = unpacked[6]
        self.sessionTime = unpacked[7]
        self.frameIdentifier = unpacked[8]
        self.overallFrameIdentifier = unpacked[9]
        self.playerCarIndex = unpacked[10]
        self.secondaryPlayerCarIndex = unpacked[11]


class CarMotionData:
    def __init__(self, data: bytes):
        unpacked = struct.unpack('<fff fff hhh hhh fff fff', data[:60])
        self.worldPositionX = unpacked[0]
        self.worldPositionY = unpacked[1]
        self.worldPositionZ = unpacked[2]
        self.worldVelocityX = unpacked[3]
        self.worldVelocityY = unpacked[4]
        self.worldVelocityZ = unpacked[5]
        self.worldForwardDirX = unpacked[6]
        self.worldForwardDirY = unpacked[7]
        self.worldForwardDirZ = unpacked[8]
        self.worldRightDirX = unpacked[9]
        self.worldRightDirY = unpacked[10]
        self.worldRightDirZ = unpacked[11]
        self.gForceLateral = unpacked[12]
        self.gForceLongitudinal = unpacked[13]
        self.gForceVertical = unpacked[14]
        self.yaw = unpacked[15]
        self.pitch = unpacked[16]
        self.roll = unpacked[17]


class PacketMotionData:
    def __init__(self, data: bytes):
        self.header = PacketHeader(data)
        self.carMotionData = [CarMotionData(
            data[29 + i*60:29 + (i+1)*60]) for i in range(MAX_NUM_CARS_IN_UDP_DATA)]

# Autres classes pour les autres paquets (simplifiées pour l'exemple, à compléter selon les besoins)


class MarshalZone:
    def __init__(self, data: bytes):
        self.zoneStart, self.zoneFlag = struct.unpack('<fB', data[:5])


class WeatherForecastSample:
    def __init__(self, data: bytes):
        unpacked = struct.unpack('<BBBBBBBBBB', data[:10])
        self.sessionType = unpacked[0]
        self.timeOffset = unpacked[1]
        self.weather = unpacked[2]
        self.trackTemperature = unpacked[3]
        self.trackTemperatureChange = unpacked[4]
        self.airTemperature = unpacked[5]
        self.airTemperatureChange = unpacked[6]
        self.rainPercentage = unpacked[7]


class PacketSessionData:
    def __init__(self, data: bytes):
        self.header = PacketHeader(data)
        # Parsing simplifié, à compléter
        offset = 29
        self.weather = data[offset]
        offset += 1
        self.trackTemperature = struct.unpack('<b', data[offset:offset+1])[0]
        # ... continuer pour tous les champs

# Classe pour CarTelemetryData (complète)


class CarTelemetryData:
    def __init__(self, data: bytes):
        unpacked = struct.unpack(
            '<H f f f B b H B B H HHHH BBBB BBBB H ffff BBBB', data[:60])
        self.speed = unpacked[0]
        self.throttle = unpacked[1]
        self.steer = unpacked[2]
        self.brake = unpacked[3]
        self.clutch = unpacked[4]
        self.gear = unpacked[5]
        self.engineRPM = unpacked[6]
        self.drs = unpacked[7]
        self.revLightsPercent = unpacked[8]
        self.revLightsBitValue = unpacked[9]
        self.brakesTemperature = unpacked[10:14]
        self.tyresSurfaceTemperature = unpacked[14:18]
        self.tyresInnerTemperature = unpacked[18:22]
        self.engineTemperature = unpacked[22]
        self.tyresPressure = unpacked[23:27]
        self.surfaceType = unpacked[27:31]


class PacketCarTelemetryData:
    def __init__(self, data: bytes):
        self.header = PacketHeader(data)
        self.carTelemetryData = [CarTelemetryData(
            data[29 + i*60:29 + (i+1)*60]) for i in range(MAX_NUM_CARS_IN_UDP_DATA)]
        offset = 29 + MAX_NUM_CARS_IN_UDP_DATA * 60
        self.mfdPanelIndex = data[offset]
        self.mfdPanelIndexSecondaryPlayer = data[offset+1]
        self.suggestedGear = struct.unpack('<b', data[offset+2:offset+3])[0]

# Fonction principale pour parser un paquet


def parse_packet(data: bytes) -> Optional[object]:
    if len(data) < 29:
        return None
    header = PacketHeader(data)
    packet_id = header.packetId

    if packet_id == PacketId.MOTION:
        return PacketMotionData(data)
    elif packet_id == PacketId.SESSION:
        return PacketSessionData(data)
    elif packet_id == PacketId.LAP_DATA:
        # À implémenter
        pass
    elif packet_id == PacketId.EVENT:
        # À implémenter
        pass
    elif packet_id == PacketId.PARTICIPANTS:
        # À implémenter
        pass
    elif packet_id == PacketId.CAR_SETUPS:
        # À implémenter
        pass
    elif packet_id == PacketId.CAR_TELEMETRY:
        try:
            return PacketCarTelemetryData(data)
        except struct.error:
            return None
    elif packet_id == PacketId.CAR_STATUS:
        # À implémenter
        pass
    elif packet_id == PacketId.FINAL_CLASSIFICATION:
        # À implémenter
        pass
    elif packet_id == PacketId.LOBBY_INFO:
        # À implémenter
        pass
    elif packet_id == PacketId.CAR_DAMAGE:
        # À implémenter
        pass
    elif packet_id == PacketId.SESSION_HISTORY:
        # À implémenter
        pass
    elif packet_id == PacketId.TYRE_SETS:
        # À implémenter
        pass
    elif packet_id == PacketId.MOTION_EX:
        # À implémenter
        pass
    elif packet_id == PacketId.TIME_TRIAL:
        # À implémenter
        pass
    elif packet_id == PacketId.LAP_POSITIONS:
        # À implémenter
        pass
    return None
