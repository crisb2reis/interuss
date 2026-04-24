from enum import Enum
from pydantic import BaseModel, Field, UUID4, field_validator
from typing import List, Optional, Literal
from ..common.schemas import (
    Volume4DSchema, validate_url_https_no_slash, TimeSchema, AltitudeSchema, 
    PositionAccuracyHorizontalEnum, PositionAccuracyVerticalEnum
)

class FlightTypeEnum(str, Enum):
    VLOS = "VLOS"
    EVLOS = "EVLOS"
    BVLOS = "BVLOS"

class ExecutionStyleEnum(str, Enum):
    HYPOTHETICAL = "Hypothetical"
    IF_ALLOWED = "IfAllowed"
    IN_REALITY = "InReality"
    DESPITE_CONFLICT = "DespiteConflict"

class USSAvailabilityEnum(str, Enum):
    UNKNOWN = "Unknown"
    NORMAL = "Normal"
    DOWN = "Down"

class EntityOVNSchema(BaseModel):
    value: str = Field(..., min_length=16, max_length=128, pattern=r"^[a-zA-Z0-9._\-+/=]+$")

class BasicInformationSchema(BaseModel):
    usage_state: Literal["Planned", "InUse", "Closed"]
    uas_state: str = ""
    area: List[Volume4DSchema] = []
    description: str = ""
    utm_id: Optional[UUID4] = None
    specific_session_id: str = ""

class FlightPlanBodySchema(BaseModel):
    basic_information: BasicInformationSchema
    uas: Optional[dict] = None
    operator: Optional[dict] = None
    telemetry: Optional[dict] = None
    astm_f3548_21: Optional[dict] = None
    uspace_flight_authorisation: Optional[dict] = None
    rpas_operating_rules_2_6: Optional[dict] = None
    additional_information: dict = {}

class FlightPlanRequestSchema(BaseModel):
    flight_plan: FlightPlanBodySchema
    execution_style: ExecutionStyleEnum = ExecutionStyleEnum.IF_ALLOWED
    request_id: Optional[str] = ""

class SubscriptionAdvancedSchema(BaseModel):
    uss_base_url: str 
    implicit_subscription: bool = False
    dependent_operational_intents: List[UUID4] = []
    notification_index: int = Field(0, ge=0)

    @field_validator("uss_base_url")
    @classmethod
    def check_url(cls, v):
        return validate_url_https_no_slash(v)

# Importing later to avoid circular dependency since DSS schemas import from here
from ..dss.schemas import OperationalIntentReferenceSchema, ConstraintReferenceSchema, SubscriptionState, GeozoneSchema

class OperationalIntentDetails(BaseModel):
    volumes: List[Volume4DSchema] = []
    off_nominal_volumes: List[Volume4DSchema] = []
    priority: int = 0

class OperationalIntent(BaseModel):
    reference: OperationalIntentReferenceSchema
    details: OperationalIntentDetails

class PutOperationalIntentDetailsParameters(BaseModel):
    operational_intent_id: str
    operational_intent: Optional[OperationalIntent] = None
    subscriptions: List[SubscriptionState] = Field(..., min_length=1)

class ConstraintDetails(BaseModel):
    volumes: List[Volume4DSchema] = Field(..., min_length=1)
    type: str
    geozone: Optional[GeozoneSchema] = None

class Constraint(BaseModel):
    reference: ConstraintReferenceSchema
    details: ConstraintDetails

class PutConstraintDetailsParameters(BaseModel):
    constraint_id: str
    constraint: Optional[Constraint] = None
    subscriptions: List[SubscriptionState] = Field(..., min_length=1)

class Velocity(BaseModel):
    speed: float
    units_speed: Literal["MetersPerSecond"] = "MetersPerSecond"
    track: float = 0.0

class Position(BaseModel):
    longitude: float = Field(..., ge=-180, le=180)
    latitude: float = Field(..., ge=-90, le=90)
    accuracy_h: PositionAccuracyHorizontalEnum
    accuracy_v: PositionAccuracyVerticalEnum
    extrapolated: bool = False
    altitude: Optional[AltitudeSchema] = None

class VehicleTelemetry(BaseModel):
    time_measured: TimeSchema
    position: Position
    velocity: Velocity

class GetOperationalIntentTelemetryResponse(BaseModel):
    operational_intent_id: str
    telemetry: Optional[VehicleTelemetry] = None
    next_telemetry_opportunity: Optional[TimeSchema] = None
