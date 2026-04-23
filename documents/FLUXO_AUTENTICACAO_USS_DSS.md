# Fluxo de Autenticação: USS Solicitando Token ao DSS

## Visão Geral do Fluxo

```
┌─────────────┐                   ┌──────────────┐                ┌─────────┐
│   USS       │                   │   AUTH       │                │   DSS   │
│             │                   │   (ICEA)     │                │         │
└─────────────┘                   └──────────────┘                └─────────┘
      │                                 │                             │
      │  1. GET /token?                 │                             │
      │  audience=core-service          │                             │
      │  scope=utm.strategic_coordination
      │  apikey=<API_KEY>               │                             │
      ├────────────────────────────────>│                             │
      │                                 │                             │
      │                 2. Valida credenciais                         │
      │                                 │                             │
      │  3. JWT Token (access_token)    │                             │
      │<────────────────────────────────┤                             │
      │                                 │                             │
      │  4. Authorization: Bearer <JWT>                               │
      │  GET /dss/v1/constraints        │                             │
      ├────────────────────────────────────────────────────────────>│
      │                                                              │
      │                                       5. Valida JWT          │
      │                                                              │
      │                   6. Response com dados solicitados          │
      │<────────────────────────────────────────────────────────────┤
      │                                                              │
```

## Detalhes da Implementação

### Passo 1: Configuração das Variáveis de Ambiente

No arquivo `.env`, configure:

```env
# URL do serviço de autenticação ICEA (BR-UTM)
ICEA_AUTH_URL=https://api.sandbox.br-utm.org/token

# API Key fornecida pelo ICEA para autenticação
ICEA_API_KEY=sua_api_key_aqui

# URL base do DSS (Discovery and Synchronization Service)
DSS_BASE_URL=https://api.sandbox.br-utm.org
```

### Passo 2: Classe ICEAAuthenticator (apps/dss_client/auth.py)

A classe `ICEAAuthenticator` é responsável por gerenciar a obtenção e cache de tokens:

```python
from apps.dss_client.auth import ICEAAuthenticator

# Instanciar o autenticador
authenticator = ICEAAuthenticator()

# Obter token com cache automático
token = authenticator.get_token(
    intended_audience="core-service",
    scope="utm.strategic_coordination"
)
```

**Características principais:**

- **Cache de Token**: Armazena tokens em cache do Django para evitar requisições desnecessárias
- **Renovação Automática**: Renova o token automaticamente antes que expire (5 minutos antes)
- **Validação JWT**: Decodifica e valida o tempo de expiração do token
- **Tratamento de Erros**: Levanta `DSSAuthenticationError` em caso de falha

### Passo 3: Fluxo Completo de Requisição ao DSS

Quando você usar o `DSSClient`, o fluxo é:

```python
from apps.dss_client.client import DSSClient

# 1. Criar cliente com autenticação automática
client = DSSClient(
    intended_audience="core-service",
    scope="utm.strategic_coordination",
    auto_authenticate=True  # Ativa autenticação automática
)

# 2. Fazer requisições autenticadas
constraints = client.query_constraints()

# 3. Submeter Operational Intent Reference
result = client.submit_operational_intent_reference(
    oir_id="seu-oir-id",
    extents={...},
    uss_base_url="https://seu-uss.com",
    state="Accepted"
)
```

**O que acontece internamente:**

1. `DSSClient.__init__()` chama `authenticator.get_token()`
2. `ICEAAuthenticator.get_token()` tenta obter do cache
3. Se não estiver em cache ou expirado, faz GET para `ICEA_AUTH_URL`
4. Recebe `access_token` na resposta JSON
5. Armazena no cache com TTL baseado na expiração do JWT
6. Retorna o token ao cliente
7. Cliente inclui o token em todas as requisições: `Authorization: Bearer {token}`

### Passo 4: Estrutura da Requisição GET ao AUTH

**Requisição:**
```
GET /token?intended_audience=core-service&scope=utm.strategic_coordination&apikey=brutm
Host: api.sandbox.br-utm.org
```

**Parâmetros:**
- `intended_audience`: Identifica qual serviço o token é destinado (ex: `core-service`)
- `scope`: Define as permissões do token (ex: `utm.strategic_coordination`)
- `apikey`: Chave de autenticação fornecida pelo ICEA

**Resposta de Sucesso (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

**Estrutura do JWT (após decodificação):**
```json
{
  "iss": "https://auth.sandbox.br-utm.org",
  "aud": "core-service",
  "exp": 1712345678,
  "iat": 1712342078,
  "scope": "utm.strategic_coordination",
  "sub": "brutm-uss"
}
```

### Passo 5: Uso em Requisições ao DSS

Após obter o token, inclua-o em todas as requisições:

**Exemplo GET /dss/v1/constraints:**
```
GET /dss/v1/constraints HTTP/1.1
Host: api.sandbox.br-utm.org
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json
```

**Exemplo POST /dss/v1/constraints/query:**
```
POST /dss/v1/constraints/query HTTP/1.1
Host: api.sandbox.br-utm.org
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json

{
  "area_of_interest": {
    "volume": {
      "outline_polygon": {
        "vertices": [
          {"lat": -23.5505, "lng": -46.6333},
          {"lat": -23.5505, "lng": -46.6233},
          {"lat": -23.5405, "lng": -46.6233},
          {"lat": -23.5405, "lng": -46.6333}
        ]
      },
      "altitude_lower": {"value": 50, "units": "M", "reference": "W84"},
      "altitude_upper": {"value": 100, "units": "M", "reference": "W84"}
    },
    "time_start": {"value": "2024-04-04T10:00:00Z", "format": "RFC3339"},
    "time_end": {"value": "2024-04-04T11:00:00Z", "format": "RFC3339"}
  }
}
```

## Tratamento de Erros

### Erro de Autenticação (401)

**Causa comum:** Token expirado ou inválido

```python
from apps.dss_client.exceptions import DSSAuthenticationError

try:
    client = DSSClient(
        intended_audience="core-service",
        scope="utm.strategic_coordination"
    )
    constraints = client.query_constraints()
except DSSAuthenticationError as e:
    print(f"Falha de autenticação: {e}")
    # O Token será automaticamente renovado na próxima requisição
```

### Erro de Autorização (403)

**Causa comum:** API Key sem permissão para o escopo solicitado

```python
from apps.dss_client.exceptions import DSSAuthorizationError

try:
    constraints = client.query_constraints()
except DSSAuthorizationError as e:
    print(f"Acesso negado: {e}")
    # Verifique se a API Key tem permissão para 'utm.strategic_coordination'
```

### Erro de Conexão

**Causa comum:** ICEA_AUTH_URL indisponível

```python
from apps.dss_client.exceptions import DSSConnectionError

try:
    authenticator = ICEAAuthenticator()
    token = authenticator.get_token("core-service", "utm.strategic_coordination")
except DSSConnectionError as e:
    print(f"Erro de conexão: {e}")
    # Verifique a URL do servidor de autenticação
```

## Cache de Token

O sistema implementa cache automático para evitar múltiplas requisições ao servidor de autenticação:

### Como funciona:

```
1ª Requisição:
   USS -> AUTH (GET /token) -> Obtém token -> Cache (TTL: 55 min)
   
Requisições 2-n (próximos 55 minutos):
   USS -> Cache -> Retorna token (sem contactar AUTH)
   
Quando expire o cache (55 min):
   USS -> AUTH (GET /token) -> Obtém novo token -> Cache
```

### Configuração da Margem de Renovação:

```python
class ICEAAuthenticator:
    TOKEN_REFRESH_MARGIN = 300  # 5 minutos antes de expirar
```

Isso garante que o token seja renovado 5 minutos antes de expirar, evitando requisições com tokens inválidos.

## Exemplo Completo de Uso

```python
from apps.dss_client.client import DSSClient
from apps.dss_client.exceptions import DSSAuthenticationError, DSSConnectionError
import uuid
from datetime import datetime, timedelta

def criar_e_submeter_oir():
    try:
        # 1. Criar cliente (com autenticação automática)
        client = DSSClient(
            intended_audience="core-service",
            scope="utm.strategic_coordination",
            auto_authenticate=True
        )
        
        # 2. Preparar dados da operação
        oir_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        extents = {
            "volume": {
                "outline_polygon": {
                    "vertices": [
                        {"lat": -23.5505, "lng": -46.6333},
                        {"lat": -23.5505, "lng": -46.6233},
                        {"lat": -23.5405, "lng": -46.6233},
                        {"lat": -23.5405, "lng": -46.6333}
                    ]
                },
                "altitude_lower": {"value": 50, "units": "M", "reference": "W84"},
                "altitude_upper": {"value": 100, "units": "M", "reference": "W84"}
            },
            "time_start": {"value": (now + timedelta(hours=1)).isoformat() + "Z", "format": "RFC3339"},
            "time_end": {"value": (now + timedelta(hours=2)).isoformat() + "Z", "format": "RFC3339"}
        }
        
        # 3. Submeter OIR (token é enviado automaticamente)
        result = client.submit_operational_intent_reference(
            oir_id=oir_id,
            extents=extents,
            uss_base_url="https://seu-uss.com",
            state="Accepted"
        )
        
        # 4. Processar resultado
        if result.get('operational_intent_reference'):
            print(f"✓ OIR criada com sucesso: {oir_id}")
            
            conflicts = result.get('conflicting_oirs', [])
            if conflicts:
                print(f"⚠ {len(conflicts)} conflito(s) detectado(s):")
                for oir in conflicts:
                    print(f"  - {oir['id']} (USS: {oir['uss_base_url']})")
        
    except DSSAuthenticationError as e:
        print(f"✗ Erro de autenticação: {e}")
    except DSSConnectionError as e:
        print(f"✗ Erro de conexão: {e}")
    except Exception as e:
        print(f"✗ Erro: {e}")

if __name__ == "__main__":
    criar_e_submeter_oir()
```

## Resumo do Fluxo

| Etapa | Ator | Ação | Status Esperado |
|-------|------|------|-----------------|
| 1 | USS | GET /token (com apikey) | 200 OK |
| 2 | AUTH | Valida credenciais | ✓ Válido |
| 3 | AUTH | Retorna access_token | JWT válido |
| 4 | USS | Armazena em cache | TTL configurado |
| 5 | USS | GET /dss/v1/... com Bearer token | 200 OK |
| 6 | DSS | Valida token | ✓ Válido |
| 7 | DSS | Processa requisição | 200 OK com dados |

---

**Última atualização:** Março 2026  
**Compatibilidade:** ASTM F3548-22, BR-UTM Sandbox  
**Referência:** RFC 7519 (JWT), RFC 6750 (Bearer Token Usage)
