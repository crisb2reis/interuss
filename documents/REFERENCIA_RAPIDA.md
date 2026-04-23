# ⚡ Referência Rápida: USS Solicitando Token ao DSS

## 🎯 Essencial (30 segundos)

```python
from apps.dss_client.client import DSSClient

# ✓ Token obtido automaticamente
client = DSSClient(
    intended_audience="core-service",
    scope="utm.strategic_coordination"
)

# ✓ Requisição autenticada (Bearer token enviado automaticamente)
constraints = client.query_constraints()
```

---

## 📋 Referência Rápida por Tarefa

### Obter Token Manualmente
```python
from apps.dss_client.auth import ICEAAuthenticator

authenticator = ICEAAuthenticator()
token = authenticator.get_token(
    intended_audience="core-service",
    scope="utm.strategic_coordination"
)
```

### Consultar Constraints
```python
client = DSSClient(intended_audience="core-service", scope="utm.strategic_coordination")
result = client.query_constraints()
# → {"constraints": [...]}
```

### Consultar com Área
```python
area = {
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

result = client.query_constraints_with_area(area)
```

### Submeter OIR (Operational Intent Reference)
```python
import uuid

result = client.submit_operational_intent_reference(
    oir_id=str(uuid.uuid4()),
    extents={...},  # área + tempo (veja exemplo acima)
    uss_base_url="https://seu-uss.com",
    state="Accepted"
)

# Verificar conflitos
if result.get('conflicting_oirs'):
    print(f"⚠ {len(result['conflicting_oirs'])} conflito(s)")
```

### Obter OIR Específica
```python
result = client.get_operational_intent_reference(oir_id="seu-oir-id")
# → {"operational_intent_reference": {...}}
```

### Deletar OIR
```python
result = client.delete_operational_intent_reference(oir_id="seu-oir-id")
```

---

## 🚨 Tratamento de Erros

```python
from apps.dss_client.exceptions import (
    DSSAuthenticationError,    # 401
    DSSAuthorizationError,     # 403
    DSSNotFoundError,          # 404
    DSSConflictError,          # 409
    DSSValidationError,        # 400
    DSSConnectionError,        # Rede
    DSSServerError             # 5xx
)

try:
    client = DSSClient(intended_audience="core-service", scope="utm.strategic_coordination")
    result = client.submit_operational_intent_reference(...)
except DSSAuthenticationError:
    # Token expirado/inválido (será renovado automaticamente)
    pass
except DSSConflictError as e:
    # OIR conflita com outra
    print(f"Conflitos: {e.conflicting_references}")
except DSSConnectionError:
    # Tentar novamente com backoff
    pass
```

---

## ⚙️ Configuração

### .env
```env
ICEA_AUTH_URL=https://api.sandbox.br-utm.org/token
ICEA_API_KEY=brutm
DSS_BASE_URL=https://api.sandbox.br-utm.org
```

### Django Settings (já está)
```python
ICEA_API_KEY = env('ICEA_API_KEY', default='')
ICEA_AUTH_URL = env('ICEA_AUTH_URL', default='https://api.sandbox.br-utm.org/token')
DSS_BASE_URL = env('DSS_BASE_URL', default='https://api.sandbox.br-utm.org')
```

---

## 🧪 Testes Rápidos

### No Shell Django
```bash
python manage.py shell
```

```python
from apps.dss_client.client import DSSClient

client = DSSClient(intended_audience="core-service", scope="utm.strategic_coordination")
print(client.query_constraints())
```

### Suite de Testes
```bash
python manage.py test apps.dss_client.test_authentication_integration -v 2
```

### Exemplos Executáveis
```bash
python exemplo_request_token.py
```

---

## 📊 Estrutura de Resposta

### Constraints
```json
{
  "constraints": [
    {
      "id": "constraint-id",
      "uss_base_url": "https://uss.com",
      "time_range": {...},
      "volume": {...}
    }
  ]
}
```

### OIR Submetida
```json
{
  "operational_intent_reference": {
    "id": "oir-id",
    "uss_base_url": "https://uss.com",
    "state": "Accepted",
    "time_range": {...},
    "extents": [...]
  },
  "subscribers": [...],
  "conflicting_oirs": [...]
}
```

---

## 🔄 Cache Automático

**Sem fazer nada, você tem:**
- ✓ Cache de token
- ✓ TTL baseado em expiração
- ✓ Renovação automática (5 min antes)
- ✓ Validação JWT
- ✓ Fallback se cache inválido

**Timeline:**
```
t=0:00   GET /token → Cache (TTL: 3300s)
t=0:05   Use cache
t=0:55   Cache expira → Renova automaticamente
t=1:00   Use novo token
```

---

## 🐛 Troubleshooting Rápido

| Problema | Solução |
|----------|---------|
| Token não obtido | Verificar `ICEA_AUTH_URL` e `ICEA_API_KEY` |
| 403 Forbidden | API Key sem permissão para escopo |
| 409 Conflict | Ajustar área/tempo da operação |
| Conexão lenta | Normal, retry será automático |
| Token expirado | Será renovado na próxima requisição |

---

## 📚 Leitura Recomendada

1. **RESUMO_USS_TOKEN_DSS.md** - Visão geral (10 min)
2. **FLUXO_AUTENTICACAO_USS_DSS.md** - Técnico (20 min)
3. **GUIA_INTEGRACAO_TOKEN_DSS.md** - Prático (25 min)
4. **DIAGRAMAS_USS_TOKEN_DSS.md** - Visual (15 min)

---

## 🚀 Integração em 3 Linhas

```python
from apps.dss_client.client import DSSClient

client = DSSClient(intended_audience="core-service", scope="utm.strategic_coordination")
result = client.submit_operational_intent_reference(oir_id=id, extents=ext, uss_base_url=url)
```

---

## 📞 Recurso Rápido

**Classes:**
- `ICEAAuthenticator` - Gerencia tokens
- `DSSClient` - Requisições ao DSS
- `DSSAuthenticationError`, `DSSConflictError`, etc. - Exceções

**Métodos principais:**
- `get_token()` - Obter JWT
- `query_constraints()` - GET constraints
- `submit_operational_intent_reference()` - Criar/atualizar OIR
- `get_operational_intent_reference()` - Obter OIR
- `delete_operational_intent_reference()` - Deletar OIR

**Arquivos:**
- `apps/dss_client/auth.py` - Autenticação
- `apps/dss_client/client.py` - Cliente DSS
- `apps/dss_client/exceptions.py` - Exceções

---

## ✅ Checklist Mínimo

- [ ] Importar `DSSClient`
- [ ] Criar instância com `intended_audience` e `scope`
- [ ] Fazer requisição (token automático)
- [ ] Tratar exceções

**Pronto!** 🎉

---

**Versão:** 1.0 | **Compatibilidade:** Django 5.2+, Python 3.9+ | **Padrão:** ASTM F3548
