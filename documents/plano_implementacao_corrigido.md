# Plano de Implementação: Arquitetura Completa do DSSClient (CORRIGIDO)

Este plano detalha as etapas necessárias para consolidar o fluxo do cliente do DSS de acordo com os requisitos e configurações (ASTM F3548 e ASTM Sandbox do BR-UTM).

---

## Fase 1 — Autenticação (ICEA / AUTH Server)

### Objetivo
Obter um JWT válido para acessar os endpoints DSS com gestão adequada do ciclo de vida do token.

### Implementação

**CORREÇÃO 1:** Separar a autenticação em módulo dedicado

```python
# apps/dss_client/auth.py (NOVO ARQUIVO)
import requests
from django.conf import settings
from django.core.cache import cache
from .exceptions import DSSAuthenticationError
from datetime import datetime, timedelta
import jwt

class ICEAAuthenticator:
    """Gerenciador de autenticação com cache de token"""
    
    CACHE_KEY_PREFIX = "dss_token"
    TOKEN_REFRESH_MARGIN = 300  # 5 minutos antes de expirar
    
    def __init__(self, auth_url: str = None, api_key: str = None):
        self.auth_url = auth_url or getattr(
            settings, 'ICEA_AUTH_URL', 
            "https://api.sandbox.br-utm.org/token"
        )
        self.api_key = api_key or getattr(settings, 'ICEA_API_KEY', '')
    
    def get_token(self, intended_audience: str, scope: str) -> str:
        """
        Obtém token válido (do cache ou renovando)
        """
        cache_key = f"{self.CACHE_KEY_PREFIX}:{intended_audience}:{scope}"
        
        # Tentar obter do cache
        cached_token = cache.get(cache_key)
        if cached_token and self._is_token_valid(cached_token):
            return cached_token
        
        # Renovar token
        token = self._authenticate(intended_audience, scope)
        
        # Armazenar no cache
        ttl = self._get_token_ttl(token)
        cache.set(cache_key, token, ttl)
        
        return token
    
    def _authenticate(self, intended_audience: str, scope: str) -> str:
        """
        Autentica e obtém novo token
        """
        if not intended_audience:
            raise ValueError("intended_audience é obrigatório")
        if not scope:
            raise ValueError("scope é obrigatório")
        
        params = {
            'intended_audience': intended_audience,
            'scope': scope,
            'apikey': self.api_key
        }
        
        try:
            response = requests.get(
                self.auth_url, 
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            token_data = response.json()
            access_token = token_data.get('access_token')
            
            if not access_token:
                raise DSSAuthenticationError(
                    "Resposta de autenticação sem access_token"
                )
            
            return access_token
            
        except requests.RequestException as e:
            raise DSSAuthenticationError(
                f"Falha ao autenticar: {str(e)}"
            )
    
    def _is_token_valid(self, token: str) -> bool:
        """
        Verifica se o token ainda é válido
        """
        try:
            decoded = jwt.decode(
                token, 
                options={"verify_signature": False}
            )
            exp = decoded.get('exp')
            if not exp:
                return False
            
            # Considerar inválido se expirar em menos de 5 minutos
            expiry = datetime.fromtimestamp(exp)
            margin = timedelta(seconds=self.TOKEN_REFRESH_MARGIN)
            
            return datetime.now() + margin < expiry
            
        except jwt.DecodeError:
            return False
    
    def _get_token_ttl(self, token: str) -> int:
        """
        Calcula TTL do token para cache
        """
        try:
            decoded = jwt.decode(
                token, 
                options={"verify_signature": False}
            )
            exp = decoded.get('exp')
            if exp:
                ttl = exp - datetime.now().timestamp()
                # Reduzir TTL pela margem de segurança
                return max(int(ttl - self.TOKEN_REFRESH_MARGIN), 60)
        except:
            pass
        
        # Default: 1 hora
        return 3600
```

---

## Fase 2 — Cliente HTTP Robusto

### Objetivo
Centralizar e tratar de maneira uniforme todas as chamadas HTTP ao DSS com tratamento granular de erros.

### Implementação

**CORREÇÃO 2:** Expandir exceções específicas

```python
# apps/dss_client/exceptions.py (ATUALIZADO)
class DSSException(Exception):
    """Exceção base para erros do DSS"""
    pass

class DSSConnectionError(DSSException):
    """Erro de conexão com DSS"""
    pass

class DSSAuthenticationError(DSSException):
    """Erro de autenticação"""
    pass

class DSSAuthorizationError(DSSException):
    """Erro de autorização (403)"""
    pass

class DSSNotFoundError(DSSException):
    """Recurso não encontrado (404)"""
    pass

class DSSConflictError(DSSException):
    """Conflito de recursos (409)"""
    def __init__(self, message, conflicting_references=None):
        super().__init__(message)
        self.conflicting_references = conflicting_references or []

class DSSValidationError(DSSException):
    """Erro de validação de dados (400)"""
    pass

class DSSServerError(DSSException):
    """Erro interno do servidor DSS (5xx)"""
    pass
```

**CORREÇÃO 3:** Melhorar método `_request` com tratamento específico

```python
# apps/dss_client/client.py (ATUALIZADO)
def _request(self, method: str, path: str, json: Dict = None, 
             params: Dict = None) -> Dict[str, Any]:
    """
    Método centralizado para requisições HTTP ao DSS
    
    Args:
        method: Verbo HTTP (GET, POST, PUT, DELETE)
        path: Caminho relativo do endpoint
        json: Payload JSON (opcional)
        params: Query parameters (opcional)
    
    Returns:
        Response JSON parseado
    
    Raises:
        DSSAuthenticationError: Token inválido/expirado (401)
        DSSAuthorizationError: Sem permissão (403)
        DSSNotFoundError: Recurso não encontrado (404)
        DSSConflictError: Conflito de recursos (409)
        DSSValidationError: Dados inválidos (400)
        DSSServerError: Erro do servidor (5xx)
        DSSConnectionError: Outros erros de conexão
    """
    headers = {
        "Authorization": f"Bearer {self.token}",
        "Content-Type": "application/json"
    }
    
    url = urllib.parse.urljoin(self.base_url, path)
    
    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=json,
            params=params,
            timeout=30
        )
        
        # Tratamento específico por código de status
        if response.status_code == 401:
            raise DSSAuthenticationError(
                f"Token inválido ou expirado: {response.text}"
            )
        
        elif response.status_code == 403:
            raise DSSAuthorizationError(
                f"Acesso negado: {response.text}"
            )
        
        elif response.status_code == 404:
            raise DSSNotFoundError(
                f"Recurso não encontrado: {response.text}"
            )
        
        elif response.status_code == 409:
            # Conflito - extrair OIRs conflitantes se disponível
            try:
                error_data = response.json()
                conflicting = error_data.get('operational_intent_references', [])
                raise DSSConflictError(
                    f"Conflito detectado: {response.text}",
                    conflicting_references=conflicting
                )
            except ValueError:
                raise DSSConflictError(f"Conflito detectado: {response.text}")
        
        elif response.status_code == 400:
            raise DSSValidationError(
                f"Dados inválidos: {response.text}"
            )
        
        elif response.status_code >= 500:
            raise DSSServerError(
                f"Erro do servidor DSS [{response.status_code}]: {response.text}"
            )
        
        elif response.status_code >= 400:
            raise DSSConnectionError(
                f"Erro HTTP [{response.status_code}]: {response.text}"
            )
        
        # Sucesso
        return response.json() if response.text else {}
        
    except requests.RequestException as e:
        raise DSSConnectionError(f"Erro de conexão: {str(e)}")
```

---

## Fase 3 — Query de Constraints (DSS)

### Objetivo
Adaptar-se às diferentes interações para buscar restrições no ecosistema.

### Implementação

**MANTIDO** (sem alterações necessárias)

```python
def query_constraints(self) -> Dict[str, Any]:
    """
    Consulta constraints sem filtro de área.
    GET /dss/v1/constraints
    
    Returns:
        Response com lista de constraints
    """
    return self._request(
        method="GET",
        path="/dss/v1/constraints"
    )
```

---

## Fase 4 — Suporte a Query com Área (InterUSS compliant)

### Objetivo
Suportar instâncias ativas do DSS que obrigatoriamente precisam de um polígono/extensão espacial.

### Implementação

**CORREÇÃO 4:** Adicionar validação de área

```python
def query_constraints_with_area(self, area: Dict[str, Any]) -> Dict[str, Any]:
    """
    Consulta constraints filtradas por área.
    POST /dss/v1/constraints/query
    
    Args:
        area: Dicionário com área de interesse no formato ASTM
              Exemplo: {
                  "volume": {
                      "outline_polygon": {
                          "vertices": [
                              {"lat": -23.5, "lng": -46.6},
                              {"lat": -23.5, "lng": -46.5},
                              {"lat": -23.4, "lng": -46.5},
                              {"lat": -23.4, "lng": -46.6}
                          ]
                      },
                      "altitude_lower": {"value": 0, "reference": "W84", "units": "M"},
                      "altitude_upper": {"value": 120, "reference": "W84", "units": "M"}
                  },
                  "time_start": {"value": "2024-01-01T10:00:00Z", "format": "RFC3339"},
                  "time_end": {"value": "2024-01-01T12:00:00Z", "format": "RFC3339"}
              }
    
    Returns:
        Response com lista de constraints na área
    
    Raises:
        DSSValidationError: Se a área estiver mal formatada
    """
    # Validação básica
    if not area:
        raise DSSValidationError("Área de interesse não pode ser vazia")
    
    if not isinstance(area, dict):
        raise DSSValidationError("Área deve ser um dicionário")
    
    # Validar estrutura mínima (volume com outline_polygon)
    volume = area.get('volume', {})
    if not volume.get('outline_polygon'):
        raise DSSValidationError(
            "Área deve conter 'volume.outline_polygon'"
        )
    
    vertices = volume.get('outline_polygon', {}).get('vertices', [])
    if len(vertices) < 3:
        raise DSSValidationError(
            "Polígono deve ter no mínimo 3 vértices"
        )
    
    return self._request(
        method="POST",
        path="/dss/v1/constraints/query",
        json={"area_of_interest": area}
    )
```

---

## Fase 5 — Criação de Referência de Intenção Operacional (OIR) e Tratativa de Conflito

### Objetivo
Enviar uma nova Intenção Operacional (OIR) para o DSS e inspecionar o retorno de outras OIRs na mesma área/período.

### Implementação

**CORREÇÃO 5:** Implementar método completo `submit_operational_intent_reference`

```python
from typing import List, Optional

def submit_operational_intent_reference(
    self,
    oir_id: str,
    extents: Dict[str, Any],
    uss_base_url: str,
    state: str = "Accepted",
    subscription_id: Optional[str] = None,
    key: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Submete ou atualiza uma Operational Intent Reference (OIR) no DSS.
    PUT /dss/v1/operational_intent_references/{id}
    
    Args:
        oir_id: ID único da intenção operacional (UUID formato string)
        extents: Dicionário com extensões espaciais e temporais
        uss_base_url: URL base da USS responsável
        state: Estado da OIR (Accepted, Activated, Nonconforming, Contingent)
        subscription_id: ID da subscrição (opcional)
        key: Lista de OIR IDs conhecidas para detecção de conflito
    
    Returns:
        Dicionário contendo:
        - operational_intent_reference: A OIR criada/atualizada
        - subscribers: Lista de assinantes notificados
        - conflicting_oirs: Lista de OIRs conflitantes (vazia se sem conflito)
    
    Raises:
        DSSValidationError: Dados inválidos
        DSSConflictError: Conflito com outras OIRs
    
    Example:
        >>> extents = {
        ...     "volume": {
        ...         "outline_polygon": {
        ...             "vertices": [
        ...                 {"lat": -23.5, "lng": -46.6},
        ...                 {"lat": -23.5, "lng": -46.5},
        ...                 {"lat": -23.4, "lng": -46.5}
        ...             ]
        ...         },
        ...         "altitude_lower": {"value": 0, "units": "M"},
        ...         "altitude_upper": {"value": 120, "units": "M"}
        ...     },
        ...     "time_start": {"value": "2024-01-01T10:00:00Z"},
        ...     "time_end": {"value": "2024-01-01T12:00:00Z"}
        ... }
        >>> result = client.submit_operational_intent_reference(
        ...     oir_id="550e8400-e29b-41d4-a716-446655440000",
        ...     extents=extents,
        ...     uss_base_url="https://uss.example.com"
        ... )
    """
    # Validações
    if not oir_id:
        raise DSSValidationError("oir_id é obrigatório")
    
    if not extents:
        raise DSSValidationError("extents é obrigatório")
    
    if not uss_base_url:
        raise DSSValidationError("uss_base_url é obrigatório")
    
    # Estados válidos conforme ASTM F3548
    valid_states = ["Accepted", "Activated", "Nonconforming", "Contingent"]
    if state not in valid_states:
        raise DSSValidationError(
            f"Estado inválido '{state}'. Deve ser um de: {valid_states}"
        )
    
    # Montar payload
    payload = {
        "extents": extents,
        "uss_base_url": uss_base_url,
        "state": state
    }
    
    if subscription_id:
        payload["subscription_id"] = subscription_id
    
    if key:
        payload["key"] = key
    
    # Enviar requisição
    path = f"/dss/v1/operational_intent_references/{oir_id}"
    
    try:
        response = self._request(
            method="PUT",
            path=path,
            json=payload
        )
        
        # Processar resposta
        result = {
            "operational_intent_reference": response.get(
                "operational_intent_reference", {}
            ),
            "subscribers": response.get("subscribers", []),
            "conflicting_oirs": []
        }
        
        # Extrair OIRs conflitantes (se houver)
        neighbors = response.get("operational_intent_references", [])
        
        if neighbors:
            # Filtrar OIRs que não sejam a própria OIR criada
            conflicting = [
                oir for oir in neighbors 
                if oir.get("id") != oir_id
            ]
            result["conflicting_oirs"] = conflicting
        
        return result
        
    except DSSConflictError as e:
        # Conflito 409 - reempacotar com informações
        raise DSSConflictError(
            f"Conflito ao submeter OIR {oir_id}: {str(e)}",
            conflicting_references=e.conflicting_references
        )


def get_operational_intent_reference(self, oir_id: str) -> Dict[str, Any]:
    """
    Obtém detalhes de uma OIR específica.
    GET /dss/v1/operational_intent_references/{id}
    
    Args:
        oir_id: ID da OIR a consultar
    
    Returns:
        Detalhes da OIR
    
    Raises:
        DSSNotFoundError: OIR não encontrada
    """
    if not oir_id:
        raise DSSValidationError("oir_id é obrigatório")
    
    path = f"/dss/v1/operational_intent_references/{oir_id}"
    return self._request(method="GET", path=path)


def delete_operational_intent_reference(
    self, 
    oir_id: str,
    key: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Remove uma OIR do DSS.
    DELETE /dss/v1/operational_intent_references/{id}
    
    Args:
        oir_id: ID da OIR a remover
        key: Lista de OIR IDs conhecidas (para versionamento)
    
    Returns:
        Resposta da remoção
    """
    if not oir_id:
        raise DSSValidationError("oir_id é obrigatório")
    
    path = f"/dss/v1/operational_intent_references/{oir_id}"
    params = {"key": ",".join(key)} if key else None
    
    return self._request(method="DELETE", path=path, params=params)
```

---

## Fase 6 — Classe Principal Atualizada

### Implementação Completa

```python
# apps/dss_client/client.py (VERSÃO FINAL)
import requests
from django.conf import settings
from .exceptions import *
from .auth import ICEAAuthenticator
import urllib.parse
from typing import Optional, Dict, Any, List


class DSSClient:
    """
    Cliente robusto para interação com DSS (Discovery and Synchronization Service)
    Compatível com ASTM F3548 e BR-UTM Sandbox
    """
    
    def __init__(
        self, 
        base_url: str = None,
        token: str = None,
        intended_audience: str = None,
        scope: str = None,
        auto_authenticate: bool = True
    ):
        """
        Inicializa o cliente DSS
        
        Args:
            base_url: URL base do DSS
            token: Token JWT (se já disponível)
            intended_audience: Audience para autenticação automática
            scope: Scope para autenticação automática
            auto_authenticate: Se True, autentica automaticamente
        """
        self.base_url = base_url or getattr(
            settings, 'DSS_BASE_URL',
            "https://dss.sandbox.br-utm.org/dss"
        )
        
        self.token = token
        self.authenticator = ICEAAuthenticator()
        
        # Autenticação automática se solicitado
        if auto_authenticate and not token:
            if not intended_audience or not scope:
                raise ValueError(
                    "intended_audience e scope são obrigatórios "
                    "para autenticação automática"
                )
            self.token = self.authenticator.get_token(
                intended_audience, 
                scope
            )
    
    def _request(self, method: str, path: str, json: Dict = None, 
                 params: Dict = None) -> Dict[str, Any]:
        """[Código já mostrado acima]"""
        # ... (implementação completa mostrada na Fase 2)
    
    # Constraints
    def query_constraints(self) -> Dict[str, Any]:
        """[Código já mostrado acima]"""
        # ... (Fase 3)
    
    def query_constraints_with_area(self, area: Dict[str, Any]) -> Dict[str, Any]:
        """[Código já mostrado acima]"""
        # ... (Fase 4)
    
    # Operational Intent References
    def submit_operational_intent_reference(
        self,
        oir_id: str,
        extents: Dict[str, Any],
        uss_base_url: str,
        state: str = "Accepted",
        subscription_id: Optional[str] = None,
        key: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """[Código já mostrado acima]"""
        # ... (Fase 5)
    
    def get_operational_intent_reference(self, oir_id: str) -> Dict[str, Any]:
        """[Código já mostrado acima]"""
        # ... (Fase 5)
    
    def delete_operational_intent_reference(
        self, 
        oir_id: str,
        key: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """[Código já mostrado acima]"""
        # ... (Fase 5)
```

---

## Resumo das Correções

| # | Problema Original | Correção Aplicada |
|---|---|---|
| 1 | Autenticação acoplada ao cliente | Separado em módulo `auth.py` com cache |
| 2 | Token sem gestão de expiração | Implementado validação JWT e renovação automática |
| 3 | Tratamento genérico de erros | Criadas exceções específicas por código HTTP |
| 4 | Método OIR ausente | Implementado `submit_operational_intent_reference` completo |
| 5 | Sem validação de parâmetros | Validações adicionadas em todos os métodos |
| 6 | Sem suporte a query params | Adicionado parâmetro `params` em `_request` |
| 7 | Timeout não configurado | Timeout de 30s adicionado |
| 8 | Inicialização inflexível | Construtor com autenticação automática opcional |

---

## Próximos Passos

### 1. Testes Unitários
Criar `apps/dss_client/tests/test_client.py` com cobertura de:
- Autenticação e renovação de token
- Cada endpoint (constraints, OIR)
- Tratamento de erros específicos
- Validações de entrada

### 2. Documentação de Uso
Atualizar `passo_a_passo.md` com exemplos práticos de:
- Inicialização do cliente
- Consulta de constraints
- Submissão de OIR com detecção de conflitos
- Tratamento de exceções

### 3. Configurações Django
Adicionar em `settings.py`:
```python
# DSS Configuration
DSS_BASE_URL = env('DSS_BASE_URL', default='https://dss.sandbox.br-utm.org/dss')
ICEA_AUTH_URL = env('ICEA_AUTH_URL', default='https://api.sandbox.br-utm.org/token')
ICEA_API_KEY = env('ICEA_API_KEY', default='')

# Cache para tokens (recomendado Redis em produção)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}
```

### 4. Requirements
Adicionar em `requirements.txt`:
```
requests>=2.31.0
PyJWT>=2.8.0
```
