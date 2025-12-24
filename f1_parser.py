
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

# --------------------------------------------------------------------------
# Structures de base
# --------------------------------------------------------------------------


class PacketHeader:
    def __init__(self, data: bytes):
        # 29 octets au total
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

# --------------------------------------------------------------------------
# MOTION (exemple abrégé)
# --------------------------------------------------------------------------


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
        self.carMotionData = [
            CarMotionData(data[29 + i*60: 29 + (i+1)*60])
            for i in range(MAX_NUM_CARS_IN_UDP_DATA)
        ]

# --------------------------------------------------------------------------
# SESSION (exemple abrégé)
# --------------------------------------------------------------------------


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
        # Parsing simplifié, à compléter si besoin
        offset = 29
        self.weather = data[offset]
        offset += 1
        self.trackTemperature = struct.unpack('<b', data[offset:offset+1])[0]
        # ... compléter tous les champs utiles

# --------------------------------------------------------------------------
# CAR TELEMETRY (complet)
# --------------------------------------------------------------------------


class CarTelemetryData:
    def __init__(self, data: bytes):
        # 60 octets par voiture (d’après spéc F1 25, résumé)
        unpacked = struct.unpack(
            '<H f f f B b H B B H HHHH BBBB BBBB H ffff BBBB', data[:60]
        )
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
        self.carTelemetryData = [
            CarTelemetryData(data[29 + i*60: 29 + (i+1)*60])
            for i in range(MAX_NUM_CARS_IN_UDP_DATA)
        ]
        offset = 29 + MAX_NUM_CARS_IN_UDP_DATA * 60
        self.mfdPanelIndex = data[offset]
        self.mfdPanelIndexSecondaryPlayer = data[offset + 1]
        self.suggestedGear = struct.unpack(
            '<b', data[offset + 2: offset + 3])[0]

# --------------------------------------------------------------------------
# LAP DATA (avec PB/Rival indices)
# --------------------------------------------------------------------------


class LapData:
    _STRUCT_FMT = (
        '<'  # little-endian
        'II'      # lastLapTimeInMS, currentLapTimeInMS
        'H' 'B'   # sector1TimeMSPart, sector1TimeMinutesPart
        'H' 'B'   # sector2TimeMSPart, sector2TimeMinutesPart
        'H' 'B'   # deltaToCarInFrontMSPart, deltaToCarInFrontMinutesPart
        'H' 'B'   # deltaToRaceLeaderMSPart, deltaToRaceLeaderMinutesPart
        'f' 'f' 'f'  # lapDistance, totalDistance, safetyCarDelta
        'BBBBBBBBBBBBBBB'  # 15 x uint8 (positions/états divers)
        'H' 'H'    # pitLaneTimeInLaneInMS, pitStopTimerInMS
        'B'        # pitStopShouldServePen
        'f'        # speedTrapFastestSpeed
        'B'        # speedTrapFastestLap
    )
    _STRUCT_SIZE = struct.calcsize(_STRUCT_FMT)

    def __init__(self, data: bytes):
        if len(data) < self._STRUCT_SIZE:
            raise struct.error(
                f"LapData: bloc trop court ({len(data)} < {self._STRUCT_SIZE})"
            )
        unpacked = struct.unpack(self._STRUCT_FMT, data)
        (
            self.lastLapTimeInMS,
            self.currentLapTimeInMS,
            self.sector1TimeMSPart,
            self.sector1TimeMinutesPart,
            self.sector2TimeMSPart,
            self.sector2TimeMinutesPart,
            self.deltaToCarInFrontMSPart,
            self.deltaToCarInFrontMinutesPart,
            self.deltaToRaceLeaderMSPart,
            self.deltaToRaceLeaderMinutesPart,
            self.lapDistance,
            self.totalDistance,
            self.safetyCarDelta,
            self.carPosition,
            self.currentLapNum,
            self.pitStatus,
            self.numPitStops,
            self.sector,
            self.currentLapInvalid,
            self.penalties,
            self.totalWarnings,
            self.cornerCuttingWarnings,
            self.numUnservedDriveThroughPens,
            self.numUnservedStopGoPens,
            self.gridPosition,
            self.driverStatus,
            self.resultStatus,
            self.pitLaneTimerActive,
            self.pitLaneTimeInLaneInMS,
            self.pitStopTimerInMS,
            self.pitStopShouldServePen,
            self.speedTrapFastestSpeed,
            self.speedTrapFastestLap,
        ) = unpacked


class PacketLapData:
    """
    Paquet 'Lap Data' :
    - Header (29 octets)
    - 22 blocs LapData (57 octets chacun)
    - 2 octets de fin (PB car idx, Rival car idx) si présents
    """

    def __init__(self, data: bytes):
        # 1) En-tête
        self.header = PacketHeader(data)

        # 2) Tableau LapData[22]
        base = 29
        stride = LapData._STRUCT_SIZE  # 57
        self.lapData: List[LapData] = []
        for i in range(MAX_NUM_CARS_IN_UDP_DATA):
            start = base + i * stride
            end = start + stride
            if end > len(data):
                raise struct.error(
                    f"PacketLapData: paquet trop court pour lapData[{i}] (end {end} > len {len(data)})"
                )
            self.lapData.append(LapData(data[start:end]))

        # 3) Champs complémentaires Time Trial (2 octets uint8)
        tail_off = base + MAX_NUM_CARS_IN_UDP_DATA * stride  # 29 + 22*57
        if tail_off + 2 <= len(data):
            self.timeTrialPBCarIdx = data[tail_off]
            self.timeTrialRivalCarIdx = data[tail_off + 1]
        else:
            # Sécurité si absent : indices invalides (255)
            self.timeTrialPBCarIdx = 255
            self.timeTrialRivalCarIdx = 255  # <-- correctif ajouté
        # NOTE: ces deux indices correspondent aux voitures PB et Rival en Time Trial
        # et permettent de lier leurs trames de télémétrie aux courbes. [1](https://dobleengineeringo365-my.sharepoint.com/personal/ebellemare_doble_com/Documents/Fichiers%20de%20conversation%20Microsoft%20Copilot/f1_parser.py)

# --------------------------------------------------------------------------
# TIME TRIAL (nouveau : utile pour afficher/valider PB/Rival)
# --------------------------------------------------------------------------


class TimeTrialDataSet:
    """
    Résumé d’un meilleur tour (PB, joueur session best, rival).
    Voir spéc F1 25 : PacketTimeTrialData / TimeTrialDataSet. [1](https://dobleengineeringo365-my.sharepoint.com/personal/ebellemare_doble_com/Documents/Fichiers%20de%20conversation%20Microsoft%20Copilot/f1_parser.py)
    """
    _FMT = '<BBIIII BBBBB B'  # mapping logique: on lit uint8/uint pour chaque champ (cf. spéc)
    # Détail des champs:
    # uint8 m_carIdx
    # uint8 m_teamId
    # uint   m_lapTimeInMS
    # uint   m_sector1TimeInMS
    # uint   m_sector2TimeInMS
    # uint   m_sector3TimeInMS
    # uint8  m_tractionControl
    # uint8  m_gearboxAssist
    # uint8  m_antiLockBrakes
    # uint8  m_equalCarPerformance
    # uint8  m_customSetup
    # uint8  m_valid

    def __init__(self, data: bytes):
        # Selon les builds, le type "uint" dans le doc EA est un 32-bit non signé
        # On lit avec '<BBIIII BBBBB B' (2*uint8 + 4*uint32 + 6*uint8) -> 2 + 16 + 6 = 24 octets
        # Si ta capture signale une taille différente, on ajustera le format (certaines toolchains écrivent '<I' pour uint32).
        unpacked = struct.unpack('<BBIIII BBBBB B', data[:24])
        self.carIdx = unpacked[0]
        self.teamId = unpacked[1]
        self.lapTimeInMS = unpacked[2]
        self.sector1TimeInMS = unpacked[3]
        self.sector2TimeInMS = unpacked[4]
        self.sector3TimeInMS = unpacked[5]
        self.tractionControl = unpacked[6]
        self.gearboxAssist = unpacked[7]
        self.antiLockBrakes = unpacked[8]
        self.equalCarPerformance = unpacked[9]
        self.customSetup = unpacked[10]
        self.valid = unpacked[11]


class PacketTimeTrialData:
    """
    Contient trois TimeTrialDataSet:
      - playerSessionBestDataSet
      - personalBestDataSet
      - rivalDataSet
    Cf. spéc F1 25. [1](https://dobleengineeringo365-my.sharepoint.com/personal/ebellemare_doble_com/Documents/Fichiers%20de%20conversation%20Microsoft%20Copilot/f1_parser.py)
    """

    def __init__(self, data: bytes):
        self.header = PacketHeader(data)
        off = 29
        self.playerSessionBestDataSet = TimeTrialDataSet(data[off: off + 24])
        off += 24
        self.personalBestDataSet = TimeTrialDataSet(data[off: off + 24])
        off += 24
        self.rivalDataSet = TimeTrialDataSet(data[off: off + 24])

# --------------------------------------------------------------------------
# parse_packet : dispatcher
# --------------------------------------------------------------------------


def parse_packet(data: bytes) -> Optional[object]:
    # 0) Paquet trop court pour contenir l'en-tête
    if len(data) < 29:
        return None

    # 1) En-tête + identifiant
    header = PacketHeader(data)
    packet_id = header.packetId

    # 2) Dispatch sur le type de paquet
    if packet_id == PacketId.MOTION:
        try:
            return PacketMotionData(data)
        except struct.error as e:
            print(f"[MOTION struct.error] len={len(data)} -> {e}")
        return None

    elif packet_id == PacketId.SESSION:
        try:
            return PacketSessionData(data)
        except struct.error as e:
            print(f"[SESSION struct.error] len={len(data)} -> {e}")
        return None

    elif packet_id == PacketId.LAP_DATA:
        # Diagnostic optionnel (stride théorique)
        total_len = len(data)
        # (si les 2 octets PB/Rival sont présents)
        stride_guess = (total_len - 29 - 2) / 22
        # print(f"[Diag LAP] len={total_len} -> stride_guess={stride_guess:.3f}")
        try:
            return PacketLapData(data)
        except struct.error as e:
            print(
                f"[LAP struct.error] len={total_len}, stride_guess={stride_guess:.3f} -> {e}")
        return None

    elif packet_id == PacketId.EVENT:
        # À implémenter si besoin
        return None

    elif packet_id == PacketId.PARTICIPANTS:
        # À implémenter si besoin
        return None

    elif packet_id == PacketId.CAR_SETUPS:
        # À implémenter si besoin
        return None

    elif packet_id == PacketId.CAR_TELEMETRY:
        try:
            return PacketCarTelemetryData(data)
        except struct.error as e:
            print(f"[CAR_TELEMETRY struct.error] len={len(data)} -> {e}")
        return None

    elif packet_id == PacketId.CAR_STATUS:
        # À implémenter si besoin
        return None

    elif packet_id == PacketId.FINAL_CLASSIFICATION:
        # À implémenter si besoin
        return None

    elif packet_id == PacketId.LOBBY_INFO:
        # À implémenter si besoin
        return None

    elif packet_id == PacketId.CAR_DAMAGE:
        # À implémenter si besoin
        return None

    elif packet_id == PacketId.SESSION_HISTORY:
        # À implémenter si besoin
        return None

    elif packet_id == PacketId.TYRE_SETS:
        # À implémenter si besoin
        return None

    elif packet_id == PacketId.MOTION_EX:
        # À implémenter si besoin
        return None

    elif packet_id == PacketId.TIME_TRIAL:
        try:
            return PacketTimeTrialData(data)
        except struct.error as e:
            print(f"[TIME_TRIAL struct.error] len={len(data)} -> {e}")
        return None

    elif packet_id == PacketId.LAP_POSITIONS:
        # À implémenter si besoin
        return None

    # Type inconnu
    return None
