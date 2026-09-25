"""
Direct Assetto Corsa Shared Memory Reader.
Reads physics, graphics, and static car data from Windows shared memory mmap.
"""

import time
import mmap
import ctypes
import logging

logger = logging.getLogger("DualSenseACBridge.ACSharedMemory")


class SPageFilePhysics(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ('packetId', ctypes.c_int32),
        ('gas', ctypes.c_float),
        ('brake', ctypes.c_float),
        ('fuel', ctypes.c_float),
        ('gear', ctypes.c_int32),
        ('rpms', ctypes.c_int32),
        ('steerAngle', ctypes.c_float),
        ('speedKmh', ctypes.c_float),
        ('velocity', ctypes.c_float * 3),
        ('accG', ctypes.c_float * 3),
        ('wheelSlip', ctypes.c_float * 4),
        ('wheelLoad', ctypes.c_float * 4),
        ('wheelsPressure', ctypes.c_float * 4),
        ('wheelAngularSpeed', ctypes.c_float * 4),
        ('tyreWear', ctypes.c_float * 4),
        ('tyreDirtyLevel', ctypes.c_float * 4),
        ('tyreCoreTemperature', ctypes.c_float * 4),
        ('camberRAD', ctypes.c_float * 4),
        ('suspensionTravel', ctypes.c_float * 4),
        ('drs', ctypes.c_float),
        ('tc', ctypes.c_float),
        ('heading', ctypes.c_float),
        ('pitch', ctypes.c_float),
        ('roll', ctypes.c_float),
        ('cgHeight', ctypes.c_float),
        ('carDamage', ctypes.c_float * 5),
        ('numberOfTyresOut', ctypes.c_int32),
        ('pitLimiterOn', ctypes.c_int32),
        ('abs', ctypes.c_float),
        ('kersCharge', ctypes.c_float),
        ('kersInput', ctypes.c_float),
        ('autoShifterOn', ctypes.c_int32),
        ('rideHeight', ctypes.c_float * 2),
        ('turboBoost', ctypes.c_float),
        ('ballast', ctypes.c_float),
        ('airDensity', ctypes.c_float),
        ('airTemp', ctypes.c_float),
        ('roadTemp', ctypes.c_float),
        ('localAngularVel', ctypes.c_float * 3),
        ('finalFF', ctypes.c_float),
        ('performanceMeter', ctypes.c_float),
        ('engineBrake', ctypes.c_int32),
        ('ersRecoveryLevel', ctypes.c_int32),
        ('ersPowerLevel', ctypes.c_int32),
        ('ersHeatCharging', ctypes.c_int32),
        ('ersIsCharging', ctypes.c_int32),
        ('kersCurrentKJ', ctypes.c_float),
        ('drsAvailable', ctypes.c_int32),
        ('drsEnabled', ctypes.c_int32),
        ('brakeTemp', ctypes.c_float * 4),
        ('clutch', ctypes.c_float),
        ('tyreTempI', ctypes.c_float * 4),
        ('tyreTempM', ctypes.c_float * 4),
        ('tyreTempO', ctypes.c_float * 4),
        ('isAIControlled', ctypes.c_int32),
        ('tyreContactPoint', ctypes.c_float * 4 * 3),
        ('tyreContactNormal', ctypes.c_float * 4 * 3),
        ('tyreContactHeading', ctypes.c_float * 4 * 3),
        ('brakeBias', ctypes.c_float),
        ('localVelocity', ctypes.c_float * 3),
    ]


class SPageFileGraphic(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ('packetId', ctypes.c_int32),
        ('status', ctypes.c_int32),
        ('session', ctypes.c_int32),
        ('currentTime', ctypes.c_wchar * 15),
        ('lastTime', ctypes.c_wchar * 15),
        ('bestTime', ctypes.c_wchar * 15),
        ('split', ctypes.c_wchar * 15),
        ('completedLaps', ctypes.c_int32),
        ('position', ctypes.c_int32),
        ('iCurrentTime', ctypes.c_int32),
        ('iLastTime', ctypes.c_int32),
        ('iBestTime', ctypes.c_int32),
        ('sessionTimeLeft', ctypes.c_float),
        ('distanceTraveled', ctypes.c_float),
        ('isInPit', ctypes.c_int32),
        ('currentSectorIndex', ctypes.c_int32),
        ('lastSectorTime', ctypes.c_int32),
        ('numberOfLaps', ctypes.c_int32),
        ('tyreCompound', ctypes.c_wchar * 33),
        ('replayTimeMultiplier', ctypes.c_float),
        ('normalizedCarPosition', ctypes.c_float),
        ('carCoordinates', ctypes.c_float * 3),
        ('penaltyTime', ctypes.c_float),
        ('flag', ctypes.c_int32),
        ('idealLineOn', ctypes.c_int32),
        ('isInPitLine', ctypes.c_int32),
        ('surfaceGrip', ctypes.c_float),
        ('mandatoryPitDone', ctypes.c_int32),
        ('windSpeed', ctypes.c_float),
        ('windDirection', ctypes.c_float),
    ]


class SPageFileStatic(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ('_smVersion', ctypes.c_wchar * 15),
        ('_acVersion', ctypes.c_wchar * 15),
        ('numberOfSessions', ctypes.c_int32),
        ('numCars', ctypes.c_int32),
        ('carModel', ctypes.c_wchar * 33),
        ('track', ctypes.c_wchar * 33),
        ('playerName', ctypes.c_wchar * 33),
        ('playerSurname', ctypes.c_wchar * 33),
        ('playerNick', ctypes.c_wchar * 33),
        ('sectorCount', ctypes.c_int32),
        ('maxTorque', ctypes.c_float),
        ('maxPower', ctypes.c_float),
        ('maxRpm', ctypes.c_int32),
        ('maxFuel', ctypes.c_float),
        ('suspensionMaxTravel', ctypes.c_float * 4),
        ('tyreRadius', ctypes.c_float * 4),
        ('maxTurboBoost', ctypes.c_float),
        ('airTemp', ctypes.c_float),
        ('roadTemp', ctypes.c_float),
        ('penaltiesEnabled', ctypes.c_int32),
        ('aidFuelRate', ctypes.c_float),
        ('aidTireRate', ctypes.c_float),
        ('aidMechanicalDamage', ctypes.c_float),
        ('aidAllowTyreBlankets', ctypes.c_int32),
        ('aidStability', ctypes.c_float),
        ('aidAutoClutch', ctypes.c_int32),
        ('aidAutoBlip', ctypes.c_int32),
        ('hasDRS', ctypes.c_int32),
        ('hasERS', ctypes.c_int32),
        ('hasKERS', ctypes.c_int32),
        ('kersMaxJ', ctypes.c_float),
        ('engineBrakeSettingsCount', ctypes.c_int32),
        ('ersPowerControllerCount', ctypes.c_int32),
        ('trackSPlineLength', ctypes.c_float),
        ('trackConfiguration', ctypes.c_wchar * 33),
        ('ersMaxJ', ctypes.c_float),
        ('isTimedRace', ctypes.c_int32),
        ('hasExtraLap', ctypes.c_int32),
        ('carSkin', ctypes.c_wchar * 33),
        ('reversedGridPositions', ctypes.c_int32),
        ('pitWindowStart', ctypes.c_int32),
        ('pitWindowEnd', ctypes.c_int32),
    ]


class ACSharedMemoryReader:
    def __init__(self):
        self.mmap_physics = None
        self.mmap_graphics = None
        self.mmap_static = None

        self.physics = None
        self.graphics = None
        self.static = None

        self.connected = False
        self.car_model = ""
        self.max_rpm = 7000
        self.max_power = 0.0
        self.max_torque = 0.0

        self.last_packet_id = -1
        self.last_packet_change_time = 0.0

    def connect(self) -> bool:
        try:
            self.mmap_physics = mmap.mmap(0, ctypes.sizeof(SPageFilePhysics), "acpmf_physics")
            self.physics = SPageFilePhysics.from_buffer(self.mmap_physics)

            try:
                self.mmap_graphics = mmap.mmap(0, ctypes.sizeof(SPageFileGraphic), "acpmf_graphics")
                self.graphics = SPageFileGraphic.from_buffer(self.mmap_graphics)
            except Exception:
                self.graphics = None

            try:
                self.mmap_static = mmap.mmap(0, ctypes.sizeof(SPageFileStatic), "acpmf_static")
                self.static = SPageFileStatic.from_buffer(self.mmap_static)
                self.car_model = str(self.static.carModel)
                self.max_rpm = self.static.maxRpm if self.static.maxRpm > 0 else 7000
                self.max_power = float(self.static.maxPower)
                self.max_torque = float(self.static.maxTorque)
            except Exception:
                self.static = None

            self.connected = True
            logger.info(f"Connected to Assetto Corsa Shared Memory! Car: {self.car_model}, Max RPM: {self.max_rpm}")
            return True
        except Exception:
            self.connected = False
            return False

    def close(self):
        self.connected = False
        self.physics = None
        self.graphics = None
        self.static = None
        for m in (self.mmap_physics, self.mmap_graphics, self.mmap_static):
            if m:
                try:
                    m.close()
                except Exception:
                    pass
        self.mmap_physics = None
        self.mmap_graphics = None
        self.mmap_static = None

    def is_game_running(self) -> bool:
        """
        Returns True only if Assetto Corsa is actively sending physics updates.
        Verifies packetId updates within a 0.5s watchdog and checks graphics status.
        """
        if not self.connected or not self.physics:
            if not self.connect():
                return False

        try:
            current_pkt = int(self.physics.packetId)
            now = time.time()

            # If graphics page is available, check status:
            # 0 = AC_OFF, 1 = AC_REPLAY, 2 = AC_LIVE, 3 = AC_PAUSE
            if self.graphics:
                status = int(self.graphics.status)
                if status != 2:
                    return False

            if current_pkt != self.last_packet_id and current_pkt > 0:
                self.last_packet_id = current_pkt
                self.last_packet_change_time = now
                return True

            # If packetId hasn't changed in > 1.0s, session is paused or ended
            if (now - self.last_packet_change_time) > 1.0:
                return False

            return True
        except Exception:
            self.close()
            return False
