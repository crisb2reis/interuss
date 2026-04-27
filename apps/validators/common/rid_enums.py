"""
Enums Remote ID para validação USS/DSS.

Cobre: RIDAuthority, HorizontalAccuracy, VerticalAccuracy,
       SpeedAccuracy, RIDOperationalStatus, UAType.

Referência: documents/validação/schemas/enums.py (ASTM F3548-21, ASTM F3411)
"""
from enum import Enum

class RIDAuthority(str, Enum):
    DISPLAY_PROVIDER = "rid.display_provider"
    SERVICE_PROVIDER = "rid.service_provider"

class HorizontalAccuracy(str, Enum):
    HAUnknown = "HAUnknown"
    HA10NMPlus = "HA10NMPlus"
    HA10NM = "HA10NM"
    HA4NM = "HA4NM"
    HA2NM = "HA2NM"
    HA1NM = "HA1NM"
    HA05NM = "HA05NM"
    HA03NM = "HA03NM"
    HA01NM = "HA01NM"
    HA005NM = "HA005NM"
    HA30m = "HA30m"
    HA10m = "HA10m"
    HA3m = "HA3m"
    HA1m = "HA1m"

class VerticalAccuracy(str, Enum):
    VAUnknown = "VAUnknown"
    VA150mPlus = "VA150mPlus"
    VA150m = "VA150m"
    VA45m = "VA45m"
    VA25m = "VA25m"
    VA10m = "VA10m"
    VA3m = "VA3m"
    VA1m = "VA1m"

class SpeedAccuracy(str, Enum):
    SAUnknown = "SAUnknown"
    SA10mpsPlus = "SA10mpsPlus"
    SA10mps = "SA10mps"
    SA3mps = "SA3mps"
    SA1mps = "SA1mps"
    SA03mps = "SA03mps"

class RIDOperationalStatus(str, Enum):
    Undeclared = "Undeclared"
    Ground = "Ground"
    Airborne = "Airborne"
    Emergency = "Emergency"
    RemoteIDSystemFailure = "RemoteIDSystemFailure"

class UAType(str, Enum):
    NotDeclared = "NotDeclared"
    Aeroplane = "Aeroplane"
    Helicopter = "Helicopter"
    Gyroplane = "Gyroplane"
    HybridLift = "HybridLift"
    Ornithopter = "Ornithopter"
    Glider = "Glider"
    Kite = "Kite"
    FreeBalloon = "FreeBalloon"
    CaptiveBalloon = "CaptiveBalloon"
    Airship = "Airship"
    FreeFallOrParachute = "FreeFallOrParachute"
    Rocket = "Rocket"
    TetheredPoweredAircraft = "TetheredPoweredAircraft"
    GroundObstacle = "GroundObstacle"
    Other = "Other"
