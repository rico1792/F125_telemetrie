
import struct
from typing import List, Optional

# Constantes (F1 26 / 2026 Season Pack)
MAX_NUM_CARS_IN_UDP_DATA = 24
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
    CAR_TELEMETRY_2 = 16  # Nouveau F1 26 : Active Aero / Overtake Mode

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
    # F1 26 : gForce passe de float à int16 quantisé (÷1000 pour valeur réelle)
    # Format : 3f pos + 3f vel + 3h fwdDir + 3h rightDir + 3h gForce(int16) + 3f yaw/pitch/roll
    _FMT = '<fff fff hhh hhh hhh fff'
    _SIZE = struct.calcsize(_FMT)  # 54 octets

    def __init__(self, data: bytes):
        unpacked = struct.unpack(self._FMT, data[:self._SIZE])
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
        # Valeurs quantisées — diviser par 1000.0 pour obtenir la valeur réelle en G
        self.gForceLateral = unpacked[12] / 1000.0
        self.gForceLongitudinal = unpacked[13] / 1000.0
        self.gForceVertical = unpacked[14] / 1000.0
        self.yaw = unpacked[15]
        self.pitch = unpacked[16]
        self.roll = unpacked[17]


class PacketMotionData:
    def __init__(self, data: bytes):
        self.header = PacketHeader(data)
        stride = CarMotionData._SIZE  # 54 octets (F1 26)
        self.carMotionData = [
            CarMotionData(data[29 + i*stride: 29 + (i+1)*stride])
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
    # F1 26 : engineTemperature = uint8 (B) et non uint16 → 59 octets/voiture
    _FMT = '<H f f f B b H B B H HHHH BBBB BBBB B ffff BBBB'
    _SIZE = struct.calcsize(_FMT)  # 59

    def __init__(self, data: bytes):
        unpacked = struct.unpack(self._FMT, data[:self._SIZE])
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
        stride = CarTelemetryData._SIZE  # 59 octets (F1 26)
        self.carTelemetryData = [
            CarTelemetryData(data[29 + i*stride: 29 + (i+1)*stride])
            for i in range(MAX_NUM_CARS_IN_UDP_DATA)
        ]
        offset = 29 + MAX_NUM_CARS_IN_UDP_DATA * stride
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
    F1 26 : m_teamId passe de uint8 a uint16 -> format '<BH IIII BBBBBB' (25 octets)
    """
    _FMT = '<BH IIII BBBBBB'  # 1 + 2 + 4*4 + 6*1 = 25 octets
    _SIZE = struct.calcsize(_FMT)  # 25

    def __init__(self, data: bytes):
        unpacked = struct.unpack(self._FMT, data[:self._SIZE])
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
    F1 26 : 3 x TimeTrialDataSet (25 octets chacun) -> total 104 octets (29 header + 75 data)
    """

    def __init__(self, data: bytes):
        self.header = PacketHeader(data)
        off = 29
        sz = TimeTrialDataSet._SIZE  # 25
        self.playerSessionBestDataSet = TimeTrialDataSet(data[off: off + sz])
        off += sz
        self.personalBestDataSet = TimeTrialDataSet(data[off: off + sz])
        off += sz
        self.rivalDataSet = TimeTrialDataSet(data[off: off + sz])

# --------------------------------------------------------------------------
# CAR TELEMETRY 2 (nouveau F1 26 — paquet ID 16)
# Active Aero, Overtake Mode, indicateur réglementation 2026
# --------------------------------------------------------------------------


class CarTelemetry2Data:
    # uint8  activeAeroMode            (0=Corner, 1=Straight)
    # uint8  activeAeroAvailable       (0=non dispo, 1=dispo)
    # uint16 activeAeroActivationDistance (0=non dispo, sinon X mètres)
    # uint8  overtakeAvailable         (0=non dispo, 1=dispo)
    # uint8  overtakeActive            (0=inactif, 1=actif)
    # uint16 overtakeActivationDistance (0=non dispo, sinon X mètres)
    # uint8  regulations2026           (0=pré-2026, 1=2026)
    # uint8  drivingWrongWay           (0=normal, 1=à contresens)
    _FMT = '<BBH BBH BB'  # 1+1+2+1+1+2+1+1 = 10 octets
    _SIZE = struct.calcsize(_FMT)  # 10

    def __init__(self, data: bytes):
        unpacked = struct.unpack(self._FMT, data[:self._SIZE])
        self.activeAeroMode = unpacked[0]
        self.activeAeroAvailable = unpacked[1]
        self.activeAeroActivationDistance = unpacked[2]
        self.overtakeAvailable = unpacked[3]
        self.overtakeActive = unpacked[4]
        self.overtakeActivationDistance = unpacked[5]
        self.regulations2026 = unpacked[6]
        self.drivingWrongWay = unpacked[7]


class PacketCarTelemetry2Data:
    """
    Paquet ID 16 (F1 26) : données actives aéro + overtake pour 24 voitures.
    Taille : 29 (header) + 24 * 10 = 269 octets.
    """

    def __init__(self, data: bytes):
        self.header = PacketHeader(data)
        stride = CarTelemetry2Data._SIZE  # 10
        self.carTelemetry2Data = [
            CarTelemetry2Data(data[29 + i * stride: 29 + (i + 1) * stride])
            for i in range(MAX_NUM_CARS_IN_UDP_DATA)
        ]


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

    elif packet_id == PacketId.CAR_TELEMETRY_2:
        try:
            return PacketCarTelemetry2Data(data)
        except struct.error as e:
            print(f"[CAR_TELEMETRY_2 struct.error] len={len(data)} -> {e}")
        return None

    # Type inconnu
    return None
