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
        unpacked = struct.unpack('<BBBbbbbb', data[:8])
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
        offset = 29
        
        # Champs de base
        unpacked_basic = struct.unpack('<BbbBHBbBHHBBBBBB', data[offset:offset+16])
        self.weather = unpacked_basic[0]
        self.trackTemperature = unpacked_basic[1]
        self.airTemperature = unpacked_basic[2]
        self.totalLaps = unpacked_basic[3]
        self.trackLength = unpacked_basic[4]
        self.sessionType = unpacked_basic[5]
        self.trackId = unpacked_basic[6]
        self.formula = unpacked_basic[7]
        self.sessionTimeLeft = unpacked_basic[8]
        self.sessionDuration = unpacked_basic[9]
        self.pitSpeedLimit = unpacked_basic[10]
        self.gamePaused = unpacked_basic[11]
        self.isSpectating = unpacked_basic[12]
        self.spectatorCarIndex = unpacked_basic[13]
        self.sliProNativeSupport = unpacked_basic[14]
        self.numMarshalZones = unpacked_basic[15]
        offset += 16
        
        # Zones de marshals (21 max)
        self.marshalZones = []
        for i in range(21):
            zone_data = data[offset:offset+5]
            self.marshalZones.append(MarshalZone(zone_data))
            offset += 5
        
        # Autres champs
        unpacked_safety = struct.unpack('<BBB', data[offset:offset+3])
        self.safetyCarStatus = unpacked_safety[0]
        self.networkGame = unpacked_safety[1]
        self.numWeatherForecastSamples = unpacked_safety[2]
        offset += 3
        
        # Prévisions météo (64 max)
        self.weatherForecastSamples = []
        for i in range(64):
            sample_data = data[offset:offset+8]
            if i < self.numWeatherForecastSamples:
                self.weatherForecastSamples.append(WeatherForecastSample(sample_data))
            offset += 8
        
        # Champs restants
        remaining_data = struct.unpack('<BBIIIBBBBBBBBBBBBBBBIBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBFF', 
                                     data[offset:offset+70])
        self.forecastAccuracy = remaining_data[0]
        self.aiDifficulty = remaining_data[1]
        self.seasonLinkIdentifier = remaining_data[2]
        self.weekendLinkIdentifier = remaining_data[3]
        self.sessionLinkIdentifier = remaining_data[4]
        self.pitStopWindowIdealLap = remaining_data[5]
        self.pitStopWindowLatestLap = remaining_data[6]
        self.pitStopRejoinPosition = remaining_data[7]
        self.steeringAssist = remaining_data[8]
        self.brakingAssist = remaining_data[9]
        self.gearboxAssist = remaining_data[10]
        self.pitAssist = remaining_data[11]
        self.pitReleaseAssist = remaining_data[12]
        self.ERSAssist = remaining_data[13]
        self.DRSAssist = remaining_data[14]
        self.dynamicRacingLine = remaining_data[15]
        self.dynamicRacingLineType = remaining_data[16]
        self.gameMode = remaining_data[17]
        self.ruleSet = remaining_data[18]
        self.timeOfDay = remaining_data[19]
        self.sessionLength = remaining_data[20]
        self.speedUnitsLeadPlayer = remaining_data[21]
        self.temperatureUnitsLeadPlayer = remaining_data[22]
        self.speedUnitsSecondaryPlayer = remaining_data[23]
        self.temperatureUnitsSecondaryPlayer = remaining_data[24]
        self.numSafetyCarPeriods = remaining_data[25]
        self.numVirtualSafetyCarPeriods = remaining_data[26]
        self.numRedFlagPeriods = remaining_data[27]
        self.equalCarPerformance = remaining_data[28]
        self.recoveryMode = remaining_data[29]
        self.flashbackLimit = remaining_data[30]
        self.surfaceType = remaining_data[31]
        self.lowFuelMode = remaining_data[32]
        self.raceStarts = remaining_data[33]
        self.tyreTemperature = remaining_data[34]
        self.pitLaneTyreSim = remaining_data[35]
        self.carDamage = remaining_data[36]
        self.carDamageRate = remaining_data[37]
        self.collisions = remaining_data[38]
        self.collisionsOffForFirstLapOnly = remaining_data[39]
        self.mpUnsafePitRelease = remaining_data[40]
        self.mpOffForGriefing = remaining_data[41]
        self.cornerCuttingStringency = remaining_data[42]
        self.parcFermeRules = remaining_data[43]
        self.pitStopExperience = remaining_data[44]
        self.safetyCar = remaining_data[45]
        self.safetyCarExperience = remaining_data[46]
        self.formationLap = remaining_data[47]
        self.formationLapExperience = remaining_data[48]
        self.redFlags = remaining_data[49]
        self.affectsLicenceLevelSolo = remaining_data[50]
        self.affectsLicenceLevelMP = remaining_data[51]
        self.numSessionsInWeekend = remaining_data[52]
        
        # Structure du weekend (12 sessions max)
        offset += 53  # Ajuster pour les données déjà lues
        weekend_data = struct.unpack('<12B', data[offset:offset+12])
        self.weekendStructure = list(weekend_data)
        offset += 12
        
        # Distances des secteurs
        sector_data = struct.unpack('<ff', data[offset:offset+8])
        self.sector2LapDistanceStart = sector_data[0]
        self.sector3LapDistanceStart = sector_data[1]

# Classe pour CarTelemetryData (complète)


class CarTelemetryData:
    def __init__(self, data: bytes):
        unpacked = struct.unpack(
            '<HfffBbHBBHHHHHBBBBBBBBHffffBBBB', data[:60])
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
        self.brakesTemperature = [unpacked[10], unpacked[11], unpacked[12], unpacked[13]]
        self.tyresSurfaceTemperature = [unpacked[14], unpacked[15], unpacked[16], unpacked[17]]
        self.tyresInnerTemperature = [unpacked[18], unpacked[19], unpacked[20], unpacked[21]]
        self.engineTemperature = unpacked[22]
        self.tyresPressure = [unpacked[23], unpacked[24], unpacked[25], unpacked[26]]
        self.surfaceType = [unpacked[27], unpacked[28], unpacked[29], unpacked[30]]


class PacketCarTelemetryData:
    def __init__(self, data: bytes):
        self.header = PacketHeader(data)
        self.carTelemetryData = [CarTelemetryData(
            data[29 + i*60:29 + (i+1)*60]) for i in range(MAX_NUM_CARS_IN_UDP_DATA)]
        offset = 29 + MAX_NUM_CARS_IN_UDP_DATA * 60
        self.mfdPanelIndex = data[offset]
        self.mfdPanelIndexSecondaryPlayer = data[offset+1]
        self.suggestedGear = struct.unpack('<b', data[offset+2:offset+3])[0]


# Classe pour LapData
class LapData:
    def __init__(self, data: bytes):
        unpacked = struct.unpack('<IIHBHBHBHBffBBBBBBBBBBBBBBBHHBfB', data[:58])
        self.lastLapTimeInMS = unpacked[0]
        self.currentLapTimeInMS = unpacked[1]
        self.sector1TimeMSPart = unpacked[2]
        self.sector1TimeMinutesPart = unpacked[3]
        self.sector2TimeMSPart = unpacked[4]
        self.sector2TimeMinutesPart = unpacked[5]
        self.deltaToCarInFrontMSPart = unpacked[6]
        self.deltaToCarInFrontMinutesPart = unpacked[7]
        self.deltaToRaceLeaderMSPart = unpacked[8]
        self.deltaToRaceLeaderMinutesPart = unpacked[9]
        self.lapDistance = unpacked[10]
        self.totalDistance = unpacked[11]
        self.safetyCarDelta = unpacked[12]
        self.carPosition = unpacked[13]
        self.currentLapNum = unpacked[14]
        self.pitStatus = unpacked[15]
        self.numPitStops = unpacked[16]
        self.sector = unpacked[17]
        self.currentLapInvalid = unpacked[18]
        self.penalties = unpacked[19]
        self.totalWarnings = unpacked[20]
        self.cornerCuttingWarnings = unpacked[21]
        self.numUnservedDriveThroughPens = unpacked[22]
        self.numUnservedStopGoPens = unpacked[23]
        self.gridPosition = unpacked[24]
        self.driverStatus = unpacked[25]
        self.resultStatus = unpacked[26]
        self.pitLaneTimerActive = unpacked[27]
        self.pitLaneTimeInLaneInMS = unpacked[28]
        self.pitStopTimerInMS = unpacked[29]
        self.pitStopShouldServePen = unpacked[30]
        self.speedTrapFastestSpeed = unpacked[31]
        self.speedTrapFastestLap = unpacked[32]


class PacketLapData:
    def __init__(self, data: bytes):
        self.header = PacketHeader(data)
        self.lapData = [LapData(data[29 + i*58:29 + (i+1)*58]) for i in range(MAX_NUM_CARS_IN_UDP_DATA)]
        offset = 29 + MAX_NUM_CARS_IN_UDP_DATA * 58
        self.timeTrialPBCarIdx = data[offset]
        self.timeTrialRivalCarIdx = data[offset+1]


# Classe pour les événements
class EventDataDetails:
    def __init__(self, data: bytes, event_code: str):
        if event_code == "FTLP":  # FastestLap
            unpacked = struct.unpack('<Bf', data[:5])
            self.vehicleIdx = unpacked[0]
            self.lapTime = unpacked[1]
        elif event_code == "RTMT":  # Retirement
            unpacked = struct.unpack('<BB', data[:2])
            self.vehicleIdx = unpacked[0]
            self.reason = unpacked[1]
        elif event_code == "DRSD":  # DRS Disabled
            self.reason = data[0]
        elif event_code == "TMPT":  # TeamMate In Pits
            self.vehicleIdx = data[0]
        elif event_code == "RCWN":  # Race Winner
            self.vehicleIdx = data[0]
        elif event_code == "PENA":  # Penalty
            unpacked = struct.unpack('<BBBBBBB', data[:7])
            self.penaltyType = unpacked[0]
            self.infringementType = unpacked[1]
            self.vehicleIdx = unpacked[2]
            self.otherVehicleIdx = unpacked[3]
            self.time = unpacked[4]
            self.lapNum = unpacked[5]
            self.placesGained = unpacked[6]
        elif event_code == "SPTP":  # Speed Trap
            unpacked = struct.unpack('<BfBBBf', data[:11])
            self.vehicleIdx = unpacked[0]
            self.speed = unpacked[1]
            self.isOverallFastestInSession = unpacked[2]
            self.isDriverFastestInSession = unpacked[3]
            self.fastestVehicleIdxInSession = unpacked[4]
            self.fastestSpeedInSession = unpacked[5]
        elif event_code == "STLG":  # Start Lights
            self.numLights = data[0]
        elif event_code == "DTSV":  # Drive Through Penalty Served
            self.vehicleIdx = data[0]
        elif event_code == "SGSV":  # Stop Go Penalty Served
            unpacked = struct.unpack('<Bf', data[:5])
            self.vehicleIdx = unpacked[0]
            self.stopTime = unpacked[1]
        elif event_code == "FLBK":  # Flashback
            unpacked = struct.unpack('<If', data[:8])
            self.flashbackFrameIdentifier = unpacked[0]
            self.flashbackSessionTime = unpacked[1]
        elif event_code == "BUTN":  # Buttons
            self.buttonStatus = struct.unpack('<I', data[:4])[0]
        elif event_code == "OVTK":  # Overtake
            unpacked = struct.unpack('<BB', data[:2])
            self.overtakingVehicleIdx = unpacked[0]
            self.beingOvertakenVehicleIdx = unpacked[1]
        elif event_code == "SCAR":  # Safety Car
            unpacked = struct.unpack('<BB', data[:2])
            self.safetyCarType = unpacked[0]
            self.eventType = unpacked[1]
        elif event_code == "COLL":  # Collision
            unpacked = struct.unpack('<BB', data[:2])
            self.vehicle1Idx = unpacked[0]
            self.vehicle2Idx = unpacked[1]


class PacketEventData:
    def __init__(self, data: bytes):
        self.header = PacketHeader(data)
        self.eventStringCode = data[29:33].decode('ascii', errors='ignore').rstrip('\x00')
        self.eventDetails = EventDataDetails(data[33:49], self.eventStringCode)


# Classe pour les participants
class LiveryColour:
    def __init__(self, data: bytes):
        self.red = data[0]
        self.green = data[1] 
        self.blue = data[2]


class ParticipantData:
    def __init__(self, data: bytes):
        # Décompactage des premiers champs
        unpacked_base = struct.unpack('<BBBBBBBB', data[:8])
        self.aiControlled = unpacked_base[0]
        self.driverId = unpacked_base[1]
        self.networkId = unpacked_base[2]
        self.teamId = unpacked_base[3]
        self.myTeam = unpacked_base[4]
        self.raceNumber = unpacked_base[5]
        self.nationality = unpacked_base[6]
        
        # Nom (32 caractères)
        self.name = data[8:40].decode('utf-8', errors='ignore').rstrip('\x00')
        
        # Autres champs
        offset = 40
        unpacked_rest = struct.unpack('<BBHBBB', data[offset:offset+6])
        self.yourTelemetry = unpacked_rest[0]
        self.showOnlineNames = unpacked_rest[1]
        self.techLevel = unpacked_rest[2]
        self.platform = unpacked_rest[3]
        self.numColours = unpacked_rest[4]
        
        # Couleurs de la livrée (4 couleurs max)
        offset += 6
        self.liveryColours = []
        for i in range(4):
            colour_data = data[offset + i*3:offset + (i+1)*3]
            self.liveryColours.append(LiveryColour(colour_data))


class PacketParticipantsData:
    def __init__(self, data: bytes):
        self.header = PacketHeader(data)
        self.numActiveCars = data[29]
        self.participants = []
        for i in range(MAX_NUM_CARS_IN_UDP_DATA):
            participant_data = data[30 + i*58:30 + (i+1)*58]
            self.participants.append(ParticipantData(participant_data))


# Classe pour CarSetupData
class CarSetupData:
    def __init__(self, data: bytes):
        unpacked = struct.unpack('<BBBBffffBBBBBBBBBffffBf', data[:51])
        self.frontWing = unpacked[0]
        self.rearWing = unpacked[1]
        self.onThrottle = unpacked[2]
        self.offThrottle = unpacked[3]
        self.frontCamber = unpacked[4]
        self.rearCamber = unpacked[5]
        self.frontToe = unpacked[6]
        self.rearToe = unpacked[7]
        self.frontSuspension = unpacked[8]
        self.rearSuspension = unpacked[9]
        self.frontAntiRollBar = unpacked[10]
        self.rearAntiRollBar = unpacked[11]
        self.frontSuspensionHeight = unpacked[12]
        self.rearSuspensionHeight = unpacked[13]
        self.brakePressure = unpacked[14]
        self.brakeBias = unpacked[15]
        self.engineBraking = unpacked[16]
        self.rearLeftTyrePressure = unpacked[17]
        self.rearRightTyrePressure = unpacked[18]
        self.frontLeftTyrePressure = unpacked[19]
        self.frontRightTyrePressure = unpacked[20]
        self.ballast = unpacked[21]
        self.fuelLoad = unpacked[22]


class PacketCarSetupData:
    def __init__(self, data: bytes):
        self.header = PacketHeader(data)
        self.carSetupData = [CarSetupData(data[29 + i*51:29 + (i+1)*51]) for i in range(MAX_NUM_CARS_IN_UDP_DATA)]
        offset = 29 + MAX_NUM_CARS_IN_UDP_DATA * 51
        self.nextFrontWingValue = struct.unpack('<f', data[offset:offset+4])[0]

# Classe pour CarStatusData
class CarStatusData:
    def __init__(self, data: bytes):
        unpacked = struct.unpack('<BBBBBfffHHBBHBBBbfffffBBfffff', data[:56])
        self.tractionControl = unpacked[0]
        self.antiLockBrakes = unpacked[1]
        self.fuelMix = unpacked[2]
        self.frontBrakeBias = unpacked[3]
        self.pitLimiterStatus = unpacked[4]
        self.fuelInTank = unpacked[5]
        self.fuelCapacity = unpacked[6]
        self.fuelRemainingLaps = unpacked[7]
        self.maxRPM = unpacked[8]
        self.idleRPM = unpacked[9]
        self.maxGears = unpacked[10]
        self.drsAllowed = unpacked[11]
        self.drsActivationDistance = unpacked[12]
        self.actualTyreCompound = unpacked[13]
        self.visualTyreCompound = unpacked[14]
        self.tyresAgeLaps = unpacked[15]
        self.vehicleFIAFlags = unpacked[16]
        self.enginePowerICE = unpacked[17]
        self.enginePowerMGUK = unpacked[18]
        self.ersStoreEnergy = unpacked[19]
        self.ersDeployMode = unpacked[20]
        self.ersHarvestedThisLapMGUK = unpacked[21]
        self.ersHarvestedThisLapMGUH = unpacked[22]
        self.ersDeployedThisLap = unpacked[23]
        self.networkPaused = unpacked[24]


class PacketCarStatusData:
    def __init__(self, data: bytes):
        self.header = PacketHeader(data)
        self.carStatusData = [CarStatusData(data[29 + i*56:29 + (i+1)*56]) for i in range(MAX_NUM_CARS_IN_UDP_DATA)]


# Classe pour FinalClassificationData
class FinalClassificationData:
    def __init__(self, data: bytes):
        unpacked = struct.unpack('<BBBBBBBIdBBB8B8B8B', data[:47])
        self.position = unpacked[0]
        self.numLaps = unpacked[1]
        self.gridPosition = unpacked[2]
        self.points = unpacked[3]
        self.numPitStops = unpacked[4]
        self.resultStatus = unpacked[5]
        self.resultReason = unpacked[6]
        self.bestLapTimeInMS = unpacked[7]
        self.totalRaceTime = unpacked[8]
        self.penaltiesTime = unpacked[9]
        self.numPenalties = unpacked[10]
        self.numTyreStints = unpacked[11]
        self.tyreStintsActual = list(unpacked[12:20])
        self.tyreStintsVisual = list(unpacked[20:28])
        self.tyreStintsEndLaps = list(unpacked[28:36])


class PacketFinalClassificationData:
    def __init__(self, data: bytes):
        self.header = PacketHeader(data)
        self.numCars = data[29]
        self.classificationData = [FinalClassificationData(data[30 + i*47:30 + (i+1)*47]) for i in range(MAX_NUM_CARS_IN_UDP_DATA)]


# Classe pour LobbyInfoData
class LobbyInfoData:
    def __init__(self, data: bytes):
        unpacked_base = struct.unpack('<BBBBB', data[:5])
        self.aiControlled = unpacked_base[0]
        self.teamId = unpacked_base[1]
        self.nationality = unpacked_base[2]
        self.platform = unpacked_base[3]
        
        # Nom (32 caractères)
        self.name = data[5:37].decode('utf-8', errors='ignore').rstrip('\x00')
        
        # Autres champs
        unpacked_rest = struct.unpack('<BBBHB', data[37:42])
        self.carNumber = unpacked_rest[0]
        self.yourTelemetry = unpacked_rest[1]
        self.showOnlineNames = unpacked_rest[2]
        self.techLevel = unpacked_rest[3]
        self.readyStatus = unpacked_rest[4]


class PacketLobbyInfoData:
    def __init__(self, data: bytes):
        self.header = PacketHeader(data)
        self.numPlayers = data[29]
        self.lobbyPlayers = [LobbyInfoData(data[30 + i*42:30 + (i+1)*42]) for i in range(MAX_NUM_CARS_IN_UDP_DATA)]


# Classe pour CarDamageData
class CarDamageData:
    def __init__(self, data: bytes):
        unpacked = struct.unpack('<ffffBBBBBBBBBBBBBBBBBBBBBBBBBBBB', data[:43])
        self.tyresWear = [unpacked[0], unpacked[1], unpacked[2], unpacked[3]]
        self.tyresDamage = [unpacked[4], unpacked[5], unpacked[6], unpacked[7]]
        self.brakesDamage = [unpacked[8], unpacked[9], unpacked[10], unpacked[11]]
        self.tyreBlisters = [unpacked[12], unpacked[13], unpacked[14], unpacked[15]]
        self.frontLeftWingDamage = unpacked[16]
        self.frontRightWingDamage = unpacked[17]
        self.rearWingDamage = unpacked[18]
        self.floorDamage = unpacked[19]
        self.diffuserDamage = unpacked[20]
        self.sidepodDamage = unpacked[21]
        self.drsFault = unpacked[22]
        self.ersFault = unpacked[23]
        self.gearBoxDamage = unpacked[24]
        self.engineDamage = unpacked[25]
        self.engineMGUHWear = unpacked[26]
        self.engineESWear = unpacked[27]
        self.engineCEWear = unpacked[28]
        self.engineICEWear = unpacked[29]
        self.engineMGUKWear = unpacked[30]
        self.engineTCWear = unpacked[31]
        self.engineBlown = unpacked[32]
        self.engineSeized = unpacked[33]


class PacketCarDamageData:
    def __init__(self, data: bytes):
        self.header = PacketHeader(data)
        self.carDamageData = [CarDamageData(data[29 + i*43:29 + (i+1)*43]) for i in range(MAX_NUM_CARS_IN_UDP_DATA)]


# Classes pour Session History
class LapHistoryData:
    def __init__(self, data: bytes):
        unpacked = struct.unpack('<IHBHBHBB', data[:13])
        self.lapTimeInMS = unpacked[0]
        self.sector1TimeMSPart = unpacked[1]
        self.sector1TimeMinutesPart = unpacked[2]
        self.sector2TimeMSPart = unpacked[3]
        self.sector2TimeMinutesPart = unpacked[4]
        self.sector3TimeMSPart = unpacked[5]
        self.sector3TimeMinutesPart = unpacked[6]
        self.lapValidBitFlags = unpacked[7]


class TyreStintHistoryData:
    def __init__(self, data: bytes):
        unpacked = struct.unpack('<BBB', data[:3])
        self.endLap = unpacked[0]
        self.tyreActualCompound = unpacked[1]
        self.tyreVisualCompound = unpacked[2]


class PacketSessionHistoryData:
    def __init__(self, data: bytes):
        self.header = PacketHeader(data)
        offset = 29
        unpacked_basic = struct.unpack('<BBBBBBB', data[offset:offset+7])
        self.carIdx = unpacked_basic[0]
        self.numLaps = unpacked_basic[1]
        self.numTyreStints = unpacked_basic[2]
        self.bestLapTimeLapNum = unpacked_basic[3]
        self.bestSector1LapNum = unpacked_basic[4]
        self.bestSector2LapNum = unpacked_basic[5]
        self.bestSector3LapNum = unpacked_basic[6]
        offset += 7
        
        # Données d'historique des tours (100 max)
        self.lapHistoryData = []
        for i in range(100):
            lap_data = data[offset:offset+13]
            self.lapHistoryData.append(LapHistoryData(lap_data))
            offset += 13
        
        # Données d'historique des pneus
        self.tyreStintsHistoryData = []
        for i in range(MAX_TYRE_STINTS):
            stint_data = data[offset:offset+3]
            self.tyreStintsHistoryData.append(TyreStintHistoryData(stint_data))
            offset += 3


# Classes pour Tyre Sets
class TyreSetData:
    def __init__(self, data: bytes):
        unpacked = struct.unpack('<BBBBBBBhB', data[:9])
        self.actualTyreCompound = unpacked[0]
        self.visualTyreCompound = unpacked[1]
        self.wear = unpacked[2]
        self.available = unpacked[3]
        self.recommendedSession = unpacked[4]
        self.lifeSpan = unpacked[5]
        self.usableLife = unpacked[6]
        self.lapDeltaTime = unpacked[7]
        self.fitted = unpacked[8]


class PacketTyreSetsData:
    def __init__(self, data: bytes):
        self.header = PacketHeader(data)
        self.carIdx = data[29]
        offset = 30
        self.tyreSetData = [TyreSetData(data[offset + i*9:offset + (i+1)*9]) for i in range(MAX_NUM_TYRE_SETS)]
        offset += MAX_NUM_TYRE_SETS * 9
        self.fittedIdx = data[offset]


# Classe pour Motion Ex
class PacketMotionExData:
    def __init__(self, data: bytes):
        self.header = PacketHeader(data)
        offset = 29
        # Données étendues pour la voiture du joueur uniquement
        unpacked = struct.unpack('<ffffffffffffffffffffffffffffffffffffffff', data[offset:offset+244])
        self.suspensionPosition = [unpacked[0], unpacked[1], unpacked[2], unpacked[3]]
        self.suspensionVelocity = [unpacked[4], unpacked[5], unpacked[6], unpacked[7]]
        self.suspensionAcceleration = [unpacked[8], unpacked[9], unpacked[10], unpacked[11]]
        self.wheelSpeed = [unpacked[12], unpacked[13], unpacked[14], unpacked[15]]
        self.wheelSlipRatio = [unpacked[16], unpacked[17], unpacked[18], unpacked[19]]
        self.wheelSlipAngle = [unpacked[20], unpacked[21], unpacked[22], unpacked[23]]
        self.wheelLatForce = [unpacked[24], unpacked[25], unpacked[26], unpacked[27]]
        self.wheelLongForce = [unpacked[28], unpacked[29], unpacked[30], unpacked[31]]
        self.heightOfCOGAboveGround = unpacked[32]
        self.localVelocityX = unpacked[33]
        self.localVelocityY = unpacked[34]
        self.localVelocityZ = unpacked[35]
        self.angularVelocityX = unpacked[36]
        self.angularVelocityY = unpacked[37]
        self.angularVelocityZ = unpacked[38]
        self.angularAccelerationX = unpacked[39]
        self.angularAccelerationY = unpacked[40]
        self.angularAccelerationZ = unpacked[41]
        self.frontWheelsAngle = unpacked[42]
        self.wheelVertForce = [unpacked[43], unpacked[44], unpacked[45], unpacked[46]]
        self.frontAeroHeight = unpacked[47]
        self.rearAeroHeight = unpacked[48]
        self.frontRollAngle = unpacked[49]
        self.rearRollAngle = unpacked[50]
        self.chassisYaw = unpacked[51]
        self.chassisPitch = unpacked[52]
        self.wheelCamber = [unpacked[53], unpacked[54], unpacked[55], unpacked[56]]
        self.wheelCamberGain = [unpacked[57], unpacked[58], unpacked[59], unpacked[60]]


# Classes pour Time Trial
class TimeTrialDataSet:
    def __init__(self, data: bytes):
        unpacked = struct.unpack('<BBIIIIBBBBBB', data[:22])
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
    def __init__(self, data: bytes):
        self.header = PacketHeader(data)
        offset = 29
        self.playerSessionBestDataSet = TimeTrialDataSet(data[offset:offset+22])
        offset += 22
        self.personalBestDataSet = TimeTrialDataSet(data[offset:offset+22])
        offset += 22
        self.rivalDataSet = TimeTrialDataSet(data[offset:offset+22])


# Classe pour Lap Positions
class PacketLapPositionsData:
    def __init__(self, data: bytes):
        self.header = PacketHeader(data)
        offset = 29
        self.numLaps = data[offset]
        self.lapStart = data[offset+1]
        offset += 2
        
        # Positions pour chaque tour et chaque véhicule
        self.positionForVehicleIdx = []
        for lap in range(50):  # Maximum 50 tours
            lap_positions = []
            for car in range(MAX_NUM_CARS_IN_UDP_DATA):
                lap_positions.append(data[offset])
                offset += 1
            self.positionForVehicleIdx.append(lap_positions)


# Fonction principale pour parser un paquet


def parse_packet(data: bytes) -> Optional[object]:
    if len(data) < 29:
        return None
    header = PacketHeader(data)
    packet_id = header.packetId

    try:
        if packet_id == PacketId.MOTION:
            return PacketMotionData(data)
        elif packet_id == PacketId.SESSION:
            return PacketSessionData(data)
        elif packet_id == PacketId.LAP_DATA:
            return PacketLapData(data)
        elif packet_id == PacketId.EVENT:
            return PacketEventData(data)
        elif packet_id == PacketId.PARTICIPANTS:
            return PacketParticipantsData(data)
        elif packet_id == PacketId.CAR_SETUPS:
            return PacketCarSetupData(data)
        elif packet_id == PacketId.CAR_TELEMETRY:
            return PacketCarTelemetryData(data)
        elif packet_id == PacketId.CAR_STATUS:
            return PacketCarStatusData(data)
        elif packet_id == PacketId.FINAL_CLASSIFICATION:
            return PacketFinalClassificationData(data)
        elif packet_id == PacketId.LOBBY_INFO:
            return PacketLobbyInfoData(data)
        elif packet_id == PacketId.CAR_DAMAGE:
            return PacketCarDamageData(data)
        elif packet_id == PacketId.SESSION_HISTORY:
            return PacketSessionHistoryData(data)
        elif packet_id == PacketId.TYRE_SETS:
            return PacketTyreSetsData(data)
        elif packet_id == PacketId.MOTION_EX:
            return PacketMotionExData(data)
        elif packet_id == PacketId.TIME_TRIAL:
            return PacketTimeTrialData(data)
        elif packet_id == PacketId.LAP_POSITIONS:
            return PacketLapPositionsData(data)
    except (struct.error, IndexError) as e:
        print(f"Erreur lors du parsing du paquet {packet_id}: {e}")
        return None
    
    return None


# Fonctions utilitaires
def get_packet_type_name(packet_id: int) -> str:
    """Retourne le nom du type de paquet"""
    packet_names = {
        PacketId.MOTION: "Motion",
        PacketId.SESSION: "Session",
        PacketId.LAP_DATA: "Lap Data",
        PacketId.EVENT: "Event",
        PacketId.PARTICIPANTS: "Participants",
        PacketId.CAR_SETUPS: "Car Setups",
        PacketId.CAR_TELEMETRY: "Car Telemetry",
        PacketId.CAR_STATUS: "Car Status",
        PacketId.FINAL_CLASSIFICATION: "Final Classification",
        PacketId.LOBBY_INFO: "Lobby Info",
        PacketId.CAR_DAMAGE: "Car Damage",
        PacketId.SESSION_HISTORY: "Session History",
        PacketId.TYRE_SETS: "Tyre Sets",
        PacketId.MOTION_EX: "Motion Extended",
        PacketId.TIME_TRIAL: "Time Trial",
        PacketId.LAP_POSITIONS: "Lap Positions"
    }
    return packet_names.get(packet_id, f"Unknown ({packet_id})")


def is_valid_packet(data: bytes) -> bool:
    """Vérifie si les données correspondent à un paquet F1 25 valide"""
    if len(data) < 29:
        return False
    
    try:
        header = PacketHeader(data)
        return (header.packetFormat == 2025 and 
                header.gameYear == 25 and 
                0 <= header.packetId <= PacketId.LAP_POSITIONS)
    except:
        return False


def get_packet_size(packet_id: int) -> int:
    """Retourne la taille attendue d'un paquet selon son type"""
    packet_sizes = {
        PacketId.MOTION: 1349,
        PacketId.SESSION: 753,
        PacketId.LAP_DATA: 1285,
        PacketId.EVENT: 45,
        PacketId.PARTICIPANTS: 1284,
        PacketId.CAR_SETUPS: 1133,
        PacketId.CAR_TELEMETRY: 1352,
        PacketId.CAR_STATUS: 1239,
        PacketId.FINAL_CLASSIFICATION: 1042,
        PacketId.LOBBY_INFO: 954,
        PacketId.CAR_DAMAGE: 1041,
        PacketId.SESSION_HISTORY: 1460,
        PacketId.TYRE_SETS: 231,
        PacketId.MOTION_EX: 273,
        PacketId.TIME_TRIAL: 101,
        PacketId.LAP_POSITIONS: 1131
    }
    return packet_sizes.get(packet_id, 0)
