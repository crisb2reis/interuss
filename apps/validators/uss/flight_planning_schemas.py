"""
Schemas USS de Flight Planning (Interface de Teste Automatizado).

Portado de: documents/validação/schemas/flight_planning.py
Referência: InterUSS SCD Flight Planning ATI v0.7.0
Cobre: Upsert/Delete de plano de voo, Clear Area, User Notifications
e os enums de resultado/status de planejamento.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from .schemas import ExecutionStyleEnum

class PlanningActivityResultEnum(str, Enum):
    COMPLETED = "Completed"
    REJECTED = "Rejected"
    FAILED = "Failed"
    NOT_SUPPORTED = "NotSupported"

class FlightPlanStatusEnum(str, Enum):
    NOT_PLANNED = "NotPlanned"
    PLANNED = "Planned"
    INVALID_AFTER_PLANNING = "InvalidAfterPlanning"
    CLOSED = "Closed"

class AdvisoryInclusionEnum(str, Enum):
    UNKNOWN = "Unknown"
    AT_LEAST_ONE = "AtLeastOneAdvisoryOrCondition"
    NONE = "None"

class UpsertFlightPlanRequestSchema(BaseModel):
    flight_plan: dict = Field(..., description="Complete flight plan information")
    execution_style: ExecutionStyleEnum = Field(..., description="Style of execution")
    request_id: str = Field(..., description="Unique request identifier")

class UpsertFlightPlanResponseSchema(BaseModel):
    planning_result: PlanningActivityResultEnum = Field(..., description="Result of the planning activity")
    notes: Optional[str] = Field(None, description="Human-readable explanation")
    flight_plan_status: FlightPlanStatusEnum = Field(..., description="Status of the flight plan")
    as_planned: Optional[dict] = Field(None, description="Flight plan as actually planned")
    includes_advisories: AdvisoryInclusionEnum = Field(
        default=AdvisoryInclusionEnum.UNKNOWN,
        description="Nature of advisories included"
    )

class DeleteFlightPlanResponseSchema(BaseModel):
    planning_result: PlanningActivityResultEnum = Field(..., description="Result of the deletion")
    notes: Optional[str] = Field(None, description="Human-readable explanation")
    flight_plan_status: FlightPlanStatusEnum = Field(..., description="Status after deletion")
    includes_advisories: AdvisoryInclusionEnum = Field(
        default=AdvisoryInclusionEnum.UNKNOWN,
        description="Nature of advisories included"
    )

class ClearAreaRequestSchema(BaseModel):
    request_id: str = Field(..., description="Unique request identifier")
    extent: Dict[str, Any] = Field(..., description="Volume4D area to clear")

class ClearAreaOutcomeSchema(BaseModel):
    success: bool = Field(default=False, description="Whether the area was cleared successfully")
    message: Optional[str] = Field(None, description="Information about any problems")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional structured data")

class ClearAreaResponseSchema(BaseModel):
    outcome: ClearAreaOutcomeSchema = Field(..., description="Result of the clear area operation")

class UserNotificationSchema(BaseModel):
    id: str
    message: str
    observed_at: datetime
    type: str

class QueryUserNotificationsResponseSchema(BaseModel):
    user_notifications: List[UserNotificationSchema] = Field(
        default_factory=list,
        description="List of user notifications"
    )
