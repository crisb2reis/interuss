"""
Schemas de Telemetria USS — ASTM F3548-21 / ED-269
Consolida VehicleTelemetry e GetOperationalIntentTelemetryResponse
como tipos canônicos reutilizáveis fora de uss/schemas.py.

Referência: documents/validação/schemas/external/uss/telemetry.py
"""
from pydantic import BaseModel
from typing import Optional, Literal
from uuid import UUID
from ..common.schemas import TimeSchema, AltitudeSchema, LatLngPointSchema, PositionAccuracyHorizontalEnum, PositionAccuracyVerticalEnum


class VelocitySchema(BaseModel):
    """Velocidade do veículo (UAS). Ref: ASTM F3548-21 §A3.1."""
    speed: float
    units_speed: Literal["MetersPerSecond"] = "MetersPerSecond"
    track: Optional[float] = 0.0


class PositionSchema(BaseModel):
    """Posição do veículo para fins de telemetria USS. Ref: ASTM F3548-21 §A3.2."""
    longitude: float
    latitude: float
    accuracy_h: Optional[PositionAccuracyHorizontalEnum] = None
    accuracy_v: Optional[PositionAccuracyVerticalEnum] = None
    extrapolated: bool = False
    altitude: Optional[AltitudeSchema] = None


class VehicleTelemetrySchema(BaseModel):
    """Posição, altitude e velocidade do veículo. Ref: ASTM F3548-21 §A3.3."""
    time_measured: TimeSchema
    position: Optional[PositionSchema] = None
    velocity: Optional[VelocitySchema] = None


class GetOperationalIntentTelemetryResponseSchema(BaseModel):
    """
    Resposta a uma requisição peer-to-peer de telemetria de um operational intent
    off-nominal. Ref: ASTM F3548-21 §A2.7.
    """
    operational_intent_id: Optional[UUID] = None
    telemetry: Optional[VehicleTelemetrySchema] = None
    next_telemetry_opportunity: Optional[TimeSchema] = None
