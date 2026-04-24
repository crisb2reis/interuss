from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Literal, Any
import re
from datetime import datetime
from enum import Enum

from ..common.schemas import Volume4DSchema, validate_url_https_no_slash, TimeSchema
from ..uss.schemas import USSAvailabilityEnum
from .ed269_enums import (
    CodeZoneTypeEnum, CodeRestrictionTypeEnum, CodeZoneReasonTypeEnum,
    CodeYesNoTypeEnum, CodeWeekDayTypeEnum, CodeVerticalReferenceTypeEnum,
    CodeAuthorityRoleEnum, UomDistanceEnum
)

class OIRPayloadSchema(BaseModel):
    extents: List[Volume4DSchema] = Field(..., min_length=1)
    uss_base_url: str
    state: Literal["Accepted", "Activated", "Nonconforming", "Contingent"]
    subscription_id: Optional[str] = None
    key: List[str] = []
    new_subscription: Optional[dict] = None
    uss_availability: Optional[USSAvailabilityEnum] = None

    @field_validator("uss_base_url")
    @classmethod
    def check_url(cls, v: str):
        return validate_url_https_no_slash(v)


class AuthoritySchema(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    service: Optional[str] = Field(None, max_length=200)
    contact_name: Optional[str] = Field(None, max_length=200)
    email: Optional[str] = Field(None, max_length=200, pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    phone: Optional[str] = Field(None, max_length=200)
    site_url: Optional[str] = Field(None, max_length=200)
    purpose: Optional[CodeAuthorityRoleEnum] = None
    interval_before: Optional[str] = Field(None, pattern=r"^P(?:\d+D)?(?:T(?:\d+H)?(?:\d+M)?)?$")
    
    @model_validator(mode='after')
    def check_at_least_one_contact(self) -> 'AuthoritySchema':
        if not self.site_url and not self.email and not self.phone:
            raise ValueError("At least one contact method (email, phone, or site_url) must be specified.")
        return self


class GeoJSONPolygonSchema(BaseModel):
    type: Literal["Polygon"]
    coordinates: List[List[List[float]]]

    @field_validator("coordinates")
    @classmethod
    def validate_geojson_polygon(cls, v):
        for ring in v:
            if len(ring) < 4:
                raise ValueError("A linear ring must have at least 4 positions.")
            for pos in ring:
                if len(pos) != 2:
                    raise ValueError("Each position must have exactly 2 coordinates [lon, lat].")
            if ring[0] != ring[-1]:
                raise ValueError("The first and last positions of a linear ring must be equivalent.")
        return v


class AirspaceVolumeSchema(BaseModel):
    uomDimensions: UomDistanceEnum
    lowerLimit: Optional[int] = None
    lowerVerticalReference: Optional[CodeVerticalReferenceTypeEnum] = None
    upperLimit: Optional[int] = None
    upperVerticalReference: Optional[CodeVerticalReferenceTypeEnum] = None
    horizontalProjection: GeoJSONPolygonSchema


class DailyPeriodSchema(BaseModel):
    day: List[CodeWeekDayTypeEnum] = Field(..., min_length=1, max_length=7)
    startTime: Optional[str] = None
    endTime: Optional[str] = None


class TimePeriodSchema(BaseModel):
    permanent: CodeYesNoTypeEnum
    startDateTime: Optional[str] = None
    endDateTime: Optional[str] = None
    schedule: Optional[List[DailyPeriodSchema]] = None


class UasZoneSchema(BaseModel):
    identifier: str = Field(..., max_length=7)
    country: str = Field(..., pattern=r"^[A-Z]{3}$")
    type: CodeZoneTypeEnum
    restriction: CodeRestrictionTypeEnum
    zoneAuthority: List[AuthoritySchema] = Field(..., min_length=1)
    geometry: List[AirspaceVolumeSchema] = Field(..., min_length=1)
    name: Optional[str] = Field(None, max_length=200)
    restrictionConditions: Optional[List[str]] = None
    region: Optional[int] = Field(0, ge=0, le=65535)
    reason: Optional[List[CodeZoneReasonTypeEnum]] = Field(None, max_length=9)
    otherReasonInfo: Optional[str] = Field(None, max_length=30)
    regulationExemption: Optional[CodeYesNoTypeEnum] = None
    uSpaceClass: Optional[str] = Field(None, max_length=100)
    message: Optional[str] = Field(None, max_length=200)
    additionalProperties: Optional[dict] = None
    applicability: Optional[List[TimePeriodSchema]] = None

GeozoneSchema = UasZoneSchema

class FetchRestrictionsRequestSchema(BaseModel):
    geometry: AirspaceVolumeSchema


class FetchRestrictionsResponseSchema(BaseModel):
    restrictions: List[UasZoneSchema]


class ErrorResponseSchema(BaseModel):
    message: str


class SubscriptionSchema(BaseModel):
    id: str
    version: str
    notification_index: int = Field(0, ge=0)
    time_start: Optional[TimeSchema] = None
    time_end: Optional[TimeSchema] = None
    uss_base_url: str
    notify_for_operational_intents: bool = False
    notify_for_constraints: bool = False
    implicit_subscription: bool = False
    dependent_operational_intents: List[str] = []

    @field_validator("uss_base_url")
    @classmethod
    def check_url(cls, v: str):
        return validate_url_https_no_slash(v)


class QuerySubscriptionParameters(BaseModel):
    area_of_interest: Optional[Volume4DSchema] = None


class QuerySubscriptionsResponse(BaseModel):
    subscriptions: List[SubscriptionSchema] = []


class GetSubscriptionResponse(BaseModel):
    subscription: SubscriptionSchema


class PutSubscriptionParameters(BaseModel):
    extents: Volume4DSchema
    uss_base_url: str
    notify_for_operational_intents: bool = False
    notify_for_constraints: bool = False

    @field_validator("uss_base_url")
    @classmethod
    def check_url(cls, v: str):
        return validate_url_https_no_slash(v)


class OperationalIntentStateEnum(str, Enum):
    ACCEPTED = "Accepted"
    ACTIVATED = "Activated"
    NONCONFORMING = "Nonconforming"
    CONTINGENT = "Contingent"


class OperationalIntentReferenceSchema(BaseModel):
    id: str
    flight_type: str # From FlightTypeEnum in USS
    manager: str
    uss_availability: USSAvailabilityEnum
    version: int
    state: OperationalIntentStateEnum
    ovn: Optional[str] = None
    time_start: Optional[TimeSchema] = None
    time_end: Optional[TimeSchema] = None
    uss_base_url: str
    subscription_id: Optional[str] = None


class ConstraintReferenceSchema(BaseModel):
    id: str
    manager: str
    uss_availability: USSAvailabilityEnum
    version: int
    ovn: Optional[str] = None
    time_start: TimeSchema
    time_end: TimeSchema
    uss_base_url: str


class ImmutableKeySchema(BaseModel):
    key: List[str] = []


class ImplicitSubscriptionParameters(BaseModel):
    uss_base_url: str
    notify_for_constraints: bool = False


class PutOperationalIntentReferenceParameters(BaseModel):
    extents: List[Volume4DSchema] = Field(..., min_length=1)
    key: Optional[List[str]] = None
    state: OperationalIntentStateEnum
    uss_base_url: str
    subscription_id: Optional[str] = None
    new_subscription: Optional[ImplicitSubscriptionParameters] = None
    flight_type: str


class QueryOperationalIntentReferenceParameters(BaseModel):
    area_of_interest: Optional[Volume4DSchema] = None


class QueryOperationalIntentReferenceResponse(BaseModel):
    operational_intent_references: List[OperationalIntentReferenceSchema] = []


class AirspaceConflictResponse(BaseModel):
    message: Optional[str] = None
    missing_operational_intents: List[OperationalIntentReferenceSchema] = []
    missing_constraints: List[ConstraintReferenceSchema] = []

class UssAvailabilityStatus(BaseModel):
    uss: str
    availability: USSAvailabilityEnum

class UssAvailabilityStatusResponse(BaseModel):
    status: UssAvailabilityStatus
    version: str

class SetUssAvailabilityStatusParameters(BaseModel):
    old_version: str = ""
    availability: USSAvailabilityEnum

class ExchangeRecord(BaseModel):
    url: str
    method: str
    headers: List[str] = []
    recorder_role: Literal["Client", "Server"]
    request_time: TimeSchema
    request_body: str = ""
    response_time: Optional[TimeSchema] = None
    response_body: str = ""
    response_code: int = 0
    problem: Optional[str] = None

class ErrorReport(BaseModel):
    report_id: Optional[str] = None
    exchange: ExchangeRecord

class PlanningRecord(BaseModel):
    time: TimeSchema
    ovns: List[str] = []
    missing_operational_intents: List[str] = []
    missing_constraints: List[str] = []
    operational_intent_id: Optional[str] = None
    problem: Optional[str] = None

class SubscriptionState(BaseModel):
    subscription_id: str
    notification_index: int = Field(0, ge=0)

class SubscriberToNotify(BaseModel):
    subscriptions: List[SubscriptionState] = Field(..., min_length=1)
    uss_base_url: str

