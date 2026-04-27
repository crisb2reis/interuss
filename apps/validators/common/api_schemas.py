"""
Schemas genéricos de resposta da API.

Portado de: documents/validação/schemas/api.py
Convencão: ApiResponseSchema é o envelope padrão para respostas de sucesso
com message e data opcionais.
"""
from pydantic import BaseModel
from typing import Optional, Any

class ApiResponseSchema(BaseModel):
    message: Optional[str] = None
    data: Optional[Any] = None
