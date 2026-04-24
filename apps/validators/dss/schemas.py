from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Literal
from ..common.schemas import Volume4DSchema, validate_url_https_no_slash
from ..uss.schemas import USSAvailabilityEnum

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

class GeozoneSchema(BaseModel):
    identifier: str = Field(..., max_length=7)
    country: str = Field(..., pattern=r"^[A-Z]{3}$")
    restriction: Literal["COMMON", "CUSTOMIZED", "PROHIBITED", "REQ_AUTHORISATION", "CONDITIONAL", "NO_RESTRICTION"]
    restriction_conditions: Optional[str] = Field(None, max_length=10000)
    region: int = Field(..., ge=0, le=65535)
    reason: List[str] = Field(..., max_length=9)

class AuthoritySchema(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    service: Optional[str] = Field(None, max_length=200)
    contact_name: Optional[str] = Field(None, max_length=200)
    email: Optional[str] = Field(None, max_length=200, pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    phone: Optional[str] = Field(None, max_length=200)
    site_url: Optional[str] = Field(None, max_length=200)
    
    @model_validator(mode='after')
    def check_at_least_one_contact(self) -> 'AuthoritySchema':
        if not self.site_url and not self.email and not self.phone:
            raise ValueError("At least one contact method (email, phone, or site_url) must be specified.")
        return self

class SubscriptionSchema(BaseModel):
    uss_base_url: str
    notify_for_operational_intents: bool = False
    notify_for_constraints: bool = False

    @field_validator("uss_base_url")
    @classmethod
    def check_url(cls, v: str):
        return validate_url_https_no_slash(v)
