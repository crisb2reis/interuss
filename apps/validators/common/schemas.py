from pydantic import BaseModel, field_validator, model_validator, Field
from typing import Literal, Optional, List
from datetime import datetime
from urllib.parse import urlparse
from enum import Enum

def validate_url_https_no_slash(v: str) -> str:
    result = urlparse(v)
    if result.scheme != "https":
        raise ValueError("URL must use HTTPS scheme.")
    if v.endswith("/"):
        raise ValueError("URL must not end with a trailing slash.")
    return v

class PositionAccuracyVerticalEnum(str, Enum):
    VAUnknown = "VAUnknown"
    VA150mPlus = "VA150mPlus"
    VA150m = "VA150m"
    VA45m = "VA45m"
    VA25m = "VA25m"
    VA10m = "VA10m"
    VA3m = "VA3m"
    VA1m = "VA1m"

class PositionAccuracyHorizontalEnum(str, Enum):
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


class AltitudeSchema(BaseModel):
    value: float
    units: Literal["M"]
    reference: Literal["W84"]

    @field_validator("value")
    @classmethod
    def check_range(cls, v: float):
        if not -8000 <= v <= 100000:
            raise ValueError(f"Altitude value {v} is out of ASTM range (-8000..100000).")
        return v

class TimeSchema(BaseModel):
    value: str
    format: Literal["RFC3339"]

    @field_validator("value")
    @classmethod
    def check_utc(cls, v: str):
        if not v.endswith("Z"):
            raise ValueError(f"Time value must end with 'Z' (UTC). Got: {v}")
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError as e:
            raise ValueError(f"Invalid RFC3339 time: {e}")
        return v

class LatLngPointSchema(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)

class RadiusSchema(BaseModel):
    value: float = Field(..., gt=0)
    units: Literal["M"]

class CircleSchema(BaseModel):
    center: LatLngPointSchema
    radius: RadiusSchema

class PolygonSchema(BaseModel):
    vertices: List[LatLngPointSchema]

    @field_validator("vertices")
    @classmethod
    def check_polygon(cls, v: List[LatLngPointSchema]):
        if len(v) < 3:
            raise ValueError(f"Polygon must have at least 3 vertices. Got {len(v)}.")
        
        # Check for duplicates
        points = [(p.lat, p.lng) for p in v]
        if len(set(points)) != len(points):
            raise ValueError("Polygon has duplicate vertices.")
        
        # ASTM: Last point must not be same as first (implicit closure)
        if points[0] == points[-1]:
            raise ValueError("The last vertex should not be identical to the first (ASTM implicit closure).")
        
        return v

class Volume3DSchema(BaseModel):
    outline_polygon: Optional[PolygonSchema] = None
    outline_circle: Optional[CircleSchema] = None
    altitude_lower: Optional[AltitudeSchema] = None
    altitude_upper: Optional[AltitudeSchema] = None

    @model_validator(mode='after')
    def check_outline_and_altitudes(self) -> 'Volume3DSchema':
        if not self.outline_polygon and not self.outline_circle:
            raise ValueError("Volume must have either 'outline_polygon' or 'outline_circle'.")
        if self.outline_polygon and self.outline_circle:
            raise ValueError("Volume cannot have both 'outline_polygon' and 'outline_circle'.")
        
        if self.altitude_lower and self.altitude_upper:
            if self.altitude_lower.value >= self.altitude_upper.value:
                raise ValueError("altitude_lower must be strictly less than altitude_upper.")
        return self

class Volume4DSchema(BaseModel):
    volume: Volume3DSchema
    time_start: TimeSchema
    time_end: TimeSchema

    @model_validator(mode='after')
    def check_time_order(self) -> 'Volume4DSchema':
        t_start = datetime.fromisoformat(self.time_start.value.replace("Z", "+00:00"))
        t_end = datetime.fromisoformat(self.time_end.value.replace("Z", "+00:00"))
        if t_start >= t_end:
            raise ValueError("time_start must be strictly before time_end.")
        return self
