"""
Schemas DSS de Remote ID (Identificação de Serviço e Subscrições RID).

Portado de: documents/validação/schemas/external/dss/remoteid.py
Referência: ASTM F3411 (Remote ID) + InterUSS RID DSS interface
Cobre: ISA (Identification Service Area) CRUD e Subscriptions RID.
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from uuid import UUID
from ..common.schemas import Volume4DSchema, TimeSchema, validate_url_https_no_slash
from .schemas import SubscriptionState, SubscriberToNotify

class IdentificationServiceAreaSchema(BaseModel):
    uss_base_url: str
    owner: str
    time_start: TimeSchema
    time_end: TimeSchema
    version: str
    id: str

    @field_validator("uss_base_url")
    @classmethod
    def check_url(cls, v: str):
        return validate_url_https_no_slash(v)

class IdentificationServiceAreaDetailsSchema(BaseModel):
    volumes: List[Volume4DSchema] = Field(..., min_length=1)

class IdentificationServiceAreaFullSchema(BaseModel):
    reference: IdentificationServiceAreaSchema
    details: IdentificationServiceAreaDetailsSchema

class RIDSubscriptionSchema(BaseModel):
    id: str
    uss_base_url: str
    owner: str
    version: str
    notification_index: Optional[int] = 0
    time_end: Optional[TimeSchema] = None
    time_start: Optional[TimeSchema] = None

    @field_validator("uss_base_url")
    @classmethod
    def check_url(cls, v: str):
        return validate_url_https_no_slash(v)

class CreateISAParametersSchema(BaseModel):
    extents: Volume4DSchema
    uss_base_url: str

    @field_validator("uss_base_url")
    @classmethod
    def check_url(cls, v: str):
        return validate_url_https_no_slash(v)

class UpdateISAParametersSchema(BaseModel):
    extents: Volume4DSchema
    uss_base_url: str

    @field_validator("uss_base_url")
    @classmethod
    def check_url(cls, v: str):
        return validate_url_https_no_slash(v)

class PutISAResponseSchema(BaseModel):
    service_area: IdentificationServiceAreaSchema
    subscribers: Optional[List[SubscriberToNotify]] = []

class DeleteISAResponseSchema(BaseModel):
    service_area: IdentificationServiceAreaSchema
    subscribers: Optional[List[SubscriberToNotify]] = []

class GetISAResponseSchema(BaseModel):
    service_area: IdentificationServiceAreaSchema

class SearchISAResponseSchema(BaseModel):
    service_areas: List[IdentificationServiceAreaSchema] = []

class CreateRIDSubscriptionParametersSchema(BaseModel):
    extents: Volume4DSchema
    uss_base_url: str

    @field_validator("uss_base_url")
    @classmethod
    def check_url(cls, v: str):
        return validate_url_https_no_slash(v)

class UpdateRIDSubscriptionParametersSchema(BaseModel):
    extents: Volume4DSchema
    uss_base_url: str

    @field_validator("uss_base_url")
    @classmethod
    def check_url(cls, v: str):
        return validate_url_https_no_slash(v)

class PutRIDSubscriptionResponseSchema(BaseModel):
    subscription: RIDSubscriptionSchema
    service_areas: Optional[List[IdentificationServiceAreaSchema]] = []

class DeleteRIDSubscriptionResponseSchema(BaseModel):
    subscription: RIDSubscriptionSchema

class GetRIDSubscriptionResponseSchema(BaseModel):
    subscription: RIDSubscriptionSchema

class SearchRIDSubscriptionsResponseSchema(BaseModel):
    subscriptions: Optional[List[RIDSubscriptionSchema]] = []
