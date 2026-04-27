"""
Schemas de Geometria e Zonas (Geo).

Portado de: documents/validação/schemas/geo.py
Cobre: Position (telemetria/posição) e GeoZone (ED-269).
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Any
from .schemas import AltitudeSchema, PositionAccuracyHorizontalEnum, PositionAccuracyVerticalEnum


class PositionSchema(BaseModel):
    """Representação de uma posição 3D com acurácia. Ref: geo.py."""
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    accuracy_h: Optional[PositionAccuracyHorizontalEnum] = None
    accuracy_v: Optional[PositionAccuracyVerticalEnum] = None
    extrapolated: bool = False
    altitude: Optional[AltitudeSchema] = None


class GeoZoneSchema(BaseModel):
    """Representação genérica de uma GeoZone. Ref: geo.py."""
    identifier: str
    country: str
    zone_authority: List[Any]
    type: str
    restriction: str
    name: Optional[str] = None
    restriction_conditions: Optional[List[Any]] = None
    region: Optional[int] = Field(None, ge=0, le=65535)
    reason: Optional[List[str]] = Field(default=None, max_length=9)
    other_reason_info: Optional[str] = Field(default=None, max_length=30)
    regulation_exemption: Optional[str] = None
    u_space_class: Optional[str] = None
    message: Optional[str] = None
    additional_properties: Optional[dict] = Field(default=None)
