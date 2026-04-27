"""
Schemas USS de Remote ID (voos, aeronaves, notificações ISA).

Portado de: documents/validação/schemas/external/uss/remoteid.py
Referência: ASTM F3411 (Remote ID) + InterUSS SP/DP interface
Cobre: RIDAircraftPosition, RIDAircraftState, RIDFlight, RIDFlightDetails,
       GetFlightsResponse e PutISANotificationParameters.
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from ..common.schemas import Volume4DSchema, TimeSchema, LatLngPointSchema
from ..common.rid_enums import (
    HorizontalAccuracy,
    VerticalAccuracy,
    SpeedAccuracy,
    RIDOperationalStatus,
    UAType
)
from ..dss.remoteid_schemas import IdentificationServiceAreaSchema
from ..dss.schemas import SubscriptionState

class RIDAircraftPositionSchema(BaseModel):
    lat: float
    lng: float
    alt: Optional[float] = None
    accuracy_h: Optional[HorizontalAccuracy] = None
    accuracy_v: Optional[VerticalAccuracy] = None
    extrapolated: Optional[bool] = False
    pressure_altitude: Optional[float] = None

class RIDHeightSchema(BaseModel):
    distance: Optional[float] = 0
    reference: str

class RIDAircraftStateSchema(BaseModel):
    timestamp: TimeSchema
    timestamp_accuracy: float
    position: RIDAircraftPositionSchema
    speed_accuracy: SpeedAccuracy
    operational_status: Optional[RIDOperationalStatus] = None
    track: Optional[float] = 361
    speed: Optional[float] = 255
    vertical_speed: Optional[float] = 63

class RIDRecentAircraftPositionSchema(BaseModel):
    time: TimeSchema
    position: RIDAircraftPositionSchema

class OperatingAreaSchema(BaseModel):
    aircraft_count: Optional[int] = Field(None, ge=1)
    volumes: Optional[List['OperatingAreaSchema']] = []

class RIDFlightSchema(BaseModel):
    id: str
    aircraft_type: UAType
    current_state: Optional[RIDAircraftStateSchema] = None
    operating_area: Optional[OperatingAreaSchema] = None
    simulated: Optional[bool] = False
    recent_positions: Optional[List[RIDRecentAircraftPositionSchema]] = []

class UASIDSchema(BaseModel):
    registration_id: Optional[str] = ""

class RIDAuthDataSchema(BaseModel):
    format: Optional[int] = 0
    data: Optional[str] = ""

class RIDFlightDetailsSchema(BaseModel):
    id: str
    uas_id: Optional[UASIDSchema] = None
    operator_id: Optional[str] = ""
    operator_location: Optional[LatLngPointSchema] = None
    operation_description: Optional[str] = ""
    auth_data: Optional[RIDAuthDataSchema] = None

class GetFlightsResponseSchema(BaseModel):
    timestamp: TimeSchema
    flights: Optional[List[RIDFlightSchema]] = []
    no_isas_present: Optional[bool] = False

class GetFlightDetailsResponseSchema(BaseModel):
    details: RIDFlightDetailsSchema

class GetIdentificationServiceAreaDetailsResponseSchema(BaseModel):
    extents: Volume4DSchema

class PutIdentificationServiceAreaNotificationParametersSchema(BaseModel):
    service_area: Optional[IdentificationServiceAreaSchema] = None
    subscriptions: List[SubscriptionState] = Field(..., min_length=1)
    extents: Optional[Volume4DSchema] = None
