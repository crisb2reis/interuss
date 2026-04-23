# Guia de Integração: USS Solicitando Token ao DSS

## 1. Visão Geral da Arquitetura

```
┌──────────────────────────────────────────────────────────────────────┐
│                         USS (Seu Sistema)                            │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────────────┐                                             │
│  │  DSSClient         │ ← Classe principal para interagir com DSS   │
│  │  (client.py)       │                                             │
│  └──────────┬─────────┘                                             │
│             │ usa                                                   │
│             ▼                                                       │
│  ┌────────────────────────────────┐                                │
│  │  ICEAAuthenticator             │ ← Gerencia tokens               │
│  │  (auth.py)                     │   • Obtém novo token            │
│  │                                │   • Valida expiração            │
│  │  Cache Django:                 │   • Cacheao automático         │
│  │  {token_key: token_value}      │                                │
│  └──────────┬─────────────────────┘                                │
│             │                                                       │
└─────────────┼───────────────────────────────────────────────────────┘
              │ GET /token?apikey=...
              │ intended_audience=core-service
              │ scope=utm.strategic_coordination
              │
              ▼
        ┌───────────────┐
        │  AUTH (ICEA)  │
        │               │
        │ api.sandbox   │
        │ .br-utm.org   │
        │ /token        │
        └───────┬───────┘
                │ Retorna: {access_token: "JWT..."}
                │
              ▼
    ┌─────────────────────┐
    │  DSS                │
    │                     │
    │ api.sandbox         │
    │ .br-utm.org         │
    │ /dss/v1/...         │
    └─────────────────────┘
```

## 2. Componentes Principais

### 2.1 ICEAAuthenticator (apps/dss_client/auth.py)

**Responsabilidade:** Gerenciar obtenção e cache de tokens JWT

**Métodos principais:**
- `get_token(intended_audience, scope)` - Obtém token do cache ou renovado
- `_authenticate(intended_audience, scope)` - Requisição ao AUTH
- `_is_token_valid(token)` - Valida se token ainda é usável
- `_get_token_ttl(token)` - Calcula TTL para cache

**Uso básico:**
```python
from apps.dss_client.auth import ICEAAuthenticator

authenticator = ICEAAuthenticator()
token = authenticator.get_token(
    intended_audience="core-service",
    scope="utm.strategic_coordination"
)
```

### 2.2 DSSClient (apps/dss_client/client.py)

**Responsabilidade:** Cliente HTTP para o DSS com autenticação integrada

**Métodos principais:**
- `__init__()` - Inicializa com autenticação automática (opcional)
- `query_constraints()` - GET /dss/v1/constraints
- `query_constraints_with_area()` - POST /dss/v1/constraints/query
- `submit_operational_intent_reference()` - PUT /dss/v1/operational_intent_references/{id}
- `get_operational_intent_reference()` - GET /dss/v1/operational_intent_references/{id}
- `delete_operational_intent_reference()` - DELETE /dss/v1/operational_intent_references/{id}

**Uso básico:**
```python
from apps.dss_client.client import DSSClient

# Criação com autenticação automática
client = DSSClient(
    intended_audience="core-service",
    scope="utm.strategic_coordination",
    auto_authenticate=True
)

# Requisição autenticada (token enviado automaticamente)
constraints = client.query_constraints()
```

### 2.3 Exceções (apps/dss_client/exceptions.py)

**Tipos de erro:**
- `DSSAuthenticationError` (401) - Token inválido/expirado
- `DSSAuthorizationError` (403) - Sem permissão
- `DSSNotFoundError` (404) - Recurso não encontrado
- `DSSConflictError` (409) - OIR com conflito
- `DSSValidationError` (400) - Dados inválidos
- `DSSConnectionError` - Erro de rede
- `DSSServerError` (5xx) - Erro do servidor

## 3. Fluxo de Integração Passo-a-Passo

### Passo 1: Configuração (.env)

```env
# URL do servidor de autenticação ICEA
ICEA_AUTH_URL=https://api.sandbox.br-utm.org/token

# API Key fornecida pelo ICEA
ICEA_API_KEY=sua_api_key_aqui

# URL base do DSS
DSS_BASE_URL=https://api.sandbox.br-utm.org/dss

# Cache Django (importante para TTL de tokens)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
    }
}
```

### Passo 2: Configuração Django (config/settings/base.py)

```python
# Já configurado, mas adicionar se necessário:
ICEA_API_KEY = env('ICEA_API_KEY', default='')
ICEA_AUTH_URL = env('ICEA_AUTH_URL', default='https://api.sandbox.br-utm.org/token')
DSS_BASE_URL = env('DSS_BASE_URL', default='https://api.sandbox.br-utm.org/dss')

# Cache para armazenar tokens
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "TIMEOUT": 3600,  # 1 hora
    }
}
```

### Passo 3: Usar no Código

```python
# Opção A: Autenticação automática
from apps.dss_client.client import DSSClient

client = DSSClient(
    intended_audience="core-service",
    scope="utm.strategic_coordination",
    auto_authenticate=True
)

# Token é obtido automaticamente na inicialização
constraints = client.query_constraints()

# Opção B: Autenticação manual
from apps.dss_client.auth import ICEAAuthenticator
from apps.dss_client.client import DSSClient

authenticator = ICEAAuthenticator()
token = authenticator.get_token(
    intended_audience="core-service",
    scope="utm.strategic_coordination"
)

client = DSSClient(
    token=token,
    auto_authenticate=False
)

constraints = client.query_constraints()
```

### Passo 4: Tratamento de Erros

```python
from apps.dss_client.exceptions import (
    DSSAuthenticationError,
    DSSAuthorizationError,
    DSSConnectionError
)

try:
    client = DSSClient(
        intended_audience="core-service",
        scope="utm.strategic_coordination",
        auto_authenticate=True
    )
    
    result = client.submit_operational_intent_reference(
        oir_id="my-oir-id",
        extents={...},
        uss_base_url="https://meu-uss.com"
    )
    
except DSSAuthenticationError as e:
    # Token inválido/expirado - será renovado automaticamente
    print(f"Erro de autenticação: {e}")
    
except DSSAuthorizationError as e:
    # API Key sem permissão
    print(f"Acesso negado: {e}")
    # Verificar permissões com ICEA
    
except DSSConnectionError as e:
    # Servidor indisponível - implementar retry
    print(f"Erro de conexão: {e}")
    # Implementar backoff exponencial
    
except Exception as e:
    print(f"Erro inesperado: {e}")
```

## 4. Sequência HTTP Completa

### Requisição 1: Obter Token (POST AUTH)

```
GET /token?intended_audience=core-service&scope=utm.strategic_coordination&apikey=brutm HTTP/1.1
Host: api.sandbox.br-utm.org
User-Agent: Python/requests

---

HTTP/1.1 200 OK
Content-Type: application/json

{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

### Requisição 2: Usar Token no DSS

```
GET /dss/v1/constraints HTTP/1.1
Host: api.sandbox.br-utm.org
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json

---

HTTP/1.1 200 OK
Content-Type: application/json

{
  "constraints": [...]
}
```

## 5. Cache de Token - Funcionamento Interno

```
Timeline:
  t=0:00    → 1ª requisição de token
            → GET /token enviado
            → Token obtido com exp=3600s
            → Cache TTL = 3300s (5 min antes)
            
  t=0:10    → 2ª requisição
            → Token do cache (ainda válido)
            → Sem contactar AUTH
            
  t=0:55    → 3ª requisição
            → Cache expirou (55 > 55 min)
            → Nova requisição ao AUTH
            → Novo token obtido
            → Cache atualizado

Configuração:
  TOKEN_REFRESH_MARGIN = 300  # 5 minutos antes de expirar
  CACHE_KEY_PREFIX = "dss_token"
  CACHE_TTL = token.exp - now - margin
```

## 6. Integração em Views/Services

### Exemplo: View Django com DSSClient

```python
# apps/flight_plans/views.py
from rest_framework import viewsets
from apps.dss_client.client import DSSClient
from apps.dss_client.exceptions import DSSAuthenticationError

class FlightPlanViewSet(viewsets.ModelViewSet):
    def perform_create(self, serializer):
        flight_plan = serializer.save()
        
        # Submeter ao DSS
        try:
            client = DSSClient(
                intended_audience="core-service",
                scope="utm.strategic_coordination"
            )
            
            result = client.submit_operational_intent_reference(
                oir_id=str(flight_plan.id),
                extents=flight_plan.get_extents(),
                uss_base_url=settings.USS_BASE_URL
            )
            
            flight_plan.dss_reference = result['operational_intent_reference']['id']
            flight_plan.save()
            
        except DSSAuthenticationError:
            # Log e retry automático na próxima requisição
            logger.warning("Token expirado, será renovado na próxima requisição")
        except Exception as e:
            logger.error(f"Erro ao submeter ao DSS: {e}")
```

### Exemplo: Celery Task com DSSClient

```python
# apps/sync/tasks.py
from celery import shared_task
from apps.dss_client.client import DSSClient

@shared_task(bind=True, max_retries=3)
def sync_flight_plan_to_dss(self, flight_plan_id):
    try:
        flight_plan = FlightPlan.objects.get(id=flight_plan_id)
        
        client = DSSClient(
            intended_audience="core-service",
            scope="utm.strategic_coordination"
        )
        
        result = client.submit_operational_intent_reference(...)
        
        flight_plan.dss_reference = result['id']
        flight_plan.save()
        
    except Exception as e:
        # Retry com backoff exponencial
        raise self.retry(exc=e, countdown=2 ** self.request.retries)
```

## 7. Checklist de Implementação

- [ ] Variáveis de ambiente (.env) configuradas
- [ ] Cache Django configurado
- [ ] Classe `ICEAAuthenticator` está em `apps/dss_client/auth.py`
- [ ] Classe `DSSClient` está em `apps/dss_client/client.py`
- [ ] Exceções customizadas em `apps/dss_client/exceptions.py`
- [ ] Testes unitários para autenticação
- [ ] Testes integrados com sandbox BR-UTM
- [ ] Tratamento de erros em views/tasks
- [ ] Logging configurado
- [ ] Monitoramento de tokens em produção

## 8. Testes

### Teste Manual no Shell Django

```bash
python manage.py shell
```

```python
from apps.dss_client.client import DSSClient

# Teste 1: Autenticação
client = DSSClient(
    intended_audience="core-service",
    scope="utm.strategic_coordination"
)
print(f"Token obtido: {client.token[:50]}...")

# Teste 2: Consultar constraints
constraints = client.query_constraints()
print(f"Constraints: {constraints}")

# Teste 3: Submeter OIR
import uuid
result = client.submit_operational_intent_reference(
    oir_id=str(uuid.uuid4()),
    extents={...},
    uss_base_url="https://test-uss.com"
)
print(f"OIR criada: {result['operational_intent_reference']['id']}")
```

### Teste Automatizado

```bash
python exemplo_request_token.py
```

## 9. Troubleshooting

### Problema: Token não é obtido

**Solução:**
- Verificar `ICEA_AUTH_URL` em .env
- Verificar `ICEA_API_KEY` em .env
- Testar conexão: `curl https://api.sandbox.br-utm.org/token?apikey=...`
- Verificar logs do Django

### Problema: Acesso negado (403)

**Solução:**
- Verificar se API Key tem permissão para `utm.strategic_coordination`
- Contactar ICEA para confirmar permissões
- Tentar com escopo diferente

### Problema: Token expirado durante operação

**Solução:**
- Não fazer nada! Token é renovado automaticamente
- Se quiser renovar manualmente:
  ```python
  from django.core.cache import cache
  cache.delete("dss_token:core-service:utm.strategic_coordination")
  ```

### Problema: Cache não funciona

**Solução:**
- Verificar `CACHES` em `settings.py`
- Usar `django.core.cache.backends.locmem.LocMemCache` em desenvolvimento
- Usar Redis em produção: `django.core.cache.backends.redis.RedisCache`

## 10. Referências

- [ASTM F3548-22](https://www.astm.org/f3548-22.html) - Padrão para UAS Traffic Management
- [RFC 7519](https://tools.ietf.org/html/rfc7519) - JSON Web Token (JWT)
- [RFC 6750](https://tools.ietf.org/html/rfc6750) - Bearer Token Usage
- [BR-UTM Sandbox Docs](https://br-utm.org)
- [InterUSS Requirements](https://github.com/interuss/InterUSS-Platform)

---

**Versão:** 1.0  
**Data:** Março 2026  
**Compatibilidade:** Django 5.2+, Python 3.9+
