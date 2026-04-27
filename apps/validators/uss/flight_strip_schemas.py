"""
Schemas de Flight Strip (Faixa de Vôo — BR-UTM).

Portado de: documents/validação/schemas/requests/flight_strip.py
Específico BR-UTM: modelo operacional de faixas de vôo por área de cor
(vermelho/amarelo/verde/etc.) com janelas de decolagem e pouso.
"""
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum

class FlightAreaEnum(str, Enum):
    RED = "red"
    YELLOW = "yellow"
    ORANGE = "orange"
    GREEN = "green"
    BLUE = "blue"
    PURPLE = "purple"


class CreateFlightStripRequestSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=20, description="Flight strip name")
    flight_area: FlightAreaEnum = Field(..., description="Flight area color zone")
    height: Optional[int] = Field(None, gt=0, description="Flight height in meters")
    takeoff_space: Optional[str] = Field(None, min_length=1, max_length=10, description="Takeoff space identifier")
    landing_space: Optional[str] = Field(None, min_length=1, max_length=10, description="Landing space identifier")
    takeoff_time: Optional[str] = Field(None, pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$", description="Takeoff time in HH:MM format")
    landing_time: Optional[str] = Field(None, pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$", description="Landing time in HH:MM format")
    description: Optional[str] = Field(None, max_length=500, description="Flight strip description")
    active: bool = Field(default=True, description="Whether the flight strip is active")


class UpdateFlightStripRequestSchema(BaseModel):
    flight_area: Optional[FlightAreaEnum] = Field(None, description="Flight area color zone")
    height: Optional[int] = Field(None, gt=0, description="Flight height in meters")
    takeoff_space: Optional[str] = Field(None, min_length=1, max_length=10, description="Takeoff space identifier")
    landing_space: Optional[str] = Field(None, min_length=1, max_length=10, description="Landing space identifier")
    takeoff_time: Optional[str] = Field(None, pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$", description="Takeoff time in HH:MM format")
    landing_time: Optional[str] = Field(None, pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$", description="Landing time in HH:MM format")
    description: Optional[str] = Field(None, max_length=500, description="Flight strip description")
    active: Optional[bool] = Field(None, description="Whether the flight strip is active")


class SearchFlightStripsRequestSchema(BaseModel):
    flight_area: Optional[FlightAreaEnum] = Field(None, description="Filter by flight area")
    takeoff_time_start: Optional[str] = Field(None, pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$", description="Filter takeoff time from")
    takeoff_time_end: Optional[str] = Field(None, pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$", description="Filter takeoff time to")
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
