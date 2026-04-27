"""
Schemas de Alocação de Espaço Aéreo.

Portado de: documents/validação/schemas/airspace.py
Agrega: OIs, Constraints (ASTM F3548-21) e ISAs (ASTM F3411) numa única
representação de janela de espaço aéreo consultada.
"""
from pydantic import BaseModel
from typing import List
from datetime import datetime

from .schemas import Volume4DSchema
from ..uss.schemas import Constraint, OperationalIntent
from ..dss.remoteid_schemas import IdentificationServiceAreaFullSchema
from ..uss.remoteid_schemas import RIDFlightSchema

class AirspaceAllocationsSchema(BaseModel):
    timestamp: datetime
    area_of_interest: Volume4DSchema
    constraints: List[Constraint] = []
    operational_intents: List[OperationalIntent] = []
    identification_service_areas: List[IdentificationServiceAreaFullSchema] = []

    @property
    def total_volumes(self) -> int:
        return (
            len(self.constraints)
            + len(self.operational_intents)
            + len(self.identification_service_areas)
        )


class AirspaceFlightsSchema(BaseModel):
    timestamp: datetime
    flights: List[RIDFlightSchema] = []
