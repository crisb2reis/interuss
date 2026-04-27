"""
Schemas de Mapa Geoespacial (Geospatial Map Provider ATI).

Portado de: documents/validação/schemas/geospatial.py
Referência: InterUSS Geospatial Map Automated Testing Interface v0.1.0
Uso: validação de fontes HTTP ED-269, respostas de status e consultas geoespaciais.
"""
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List
from uuid import UUID
from enum import Enum

class GeospatialMapFormatEnum(str, Enum):
    ED_269 = "ED-269"

class GeospatialMapStatusEnum(str, Enum):
    PROCESSING = "Processing"
    READY = "Ready"
    ERROR = "Error"
    DEACTIVATED = "Deactivated"

class StatusResponseSchema(BaseModel):
    status: str = Field(..., description="Status of the automated testing interface")
    api_name: Optional[str] = Field(None, description="Name of the API")
    api_version: Optional[str] = Field(None, description="Version of the API")

class HttpSourceSchema(BaseModel):
    url: HttpUrl = Field(
        ...,
        description="URL where the geospatial dataset is downloaded",
        example="https://caa.example.com/geozones.json",
    )
    format: GeospatialMapFormatEnum = Field(
        default=GeospatialMapFormatEnum.ED_269,
        description="Dataset format",
        example=GeospatialMapFormatEnum.ED_269,
    )

class GeospatialMapHttpSourceSchema(BaseModel):
    https_source: HttpSourceSchema

class DataSourceSchema(BaseModel):
    id: UUID
    status: GeospatialMapStatusEnum
    message: Optional[str] = None

class GeospatialDataSourceStatusSchema(BaseModel):
    id: str
    status: str
    message: Optional[str] = None

class GeospatialDataSourceResponseSchema(BaseModel):
    data_source: GeospatialDataSourceStatusSchema

class ListGeospatialDataSourcesResponseSchema(BaseModel):
    data_sources: List[GeospatialDataSourceStatusSchema]

class GeospatialMapCheckResultSchema(BaseModel):
    features_selection_outcome: str
    message: Optional[str] = None

class GeospatialMapQueryReplySchema(BaseModel):
    results: List[GeospatialMapCheckResultSchema] = []
