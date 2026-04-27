"""
Schemas de Mapeamento de Drones (BR-UTM).

Portado de: documents/validação/schemas/requests/drone_mapping.py
Específico BR-UTM: associa número serial + SISANT a um identificador
human-readable de drone. Sem equivalênte direto no ASTM F3548-21.
"""
from pydantic import BaseModel, Field
from typing import List, Optional

class CreateDroneMappingRequestSchema(BaseModel):
    id: str = Field(
        ..., description="Human-readable identifier/name for the drone"
    )
    serial_number: str = Field(..., description="Drone serial number")
    sisant: str = Field(..., description="SISANT number for the drone")
    created_by: Optional[str] = Field(
        None, description="Who created this mapping"
    )


class BulkCreateDroneMappingsRequestSchema(BaseModel):
    mappings: List[CreateDroneMappingRequestSchema] = Field(
        ..., description="List of drone mappings to create"
    )
    created_by: Optional[str] = Field(
        None, description="Who created these mappings"
    )


class UpdateDroneMappingRequestSchema(BaseModel):
    id: Optional[str] = Field(
        None, description="Human-readable identifier/name for the drone"
    )
    serial_number: Optional[str] = Field(
        None, description="Drone serial number"
    )
    sisant: Optional[str] = Field(
        None, description="SISANT number for the drone"
    )
    updated_by: Optional[str] = Field(
        None, description="Who updated this mapping"
    )
