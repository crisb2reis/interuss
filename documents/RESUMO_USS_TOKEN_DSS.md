# USS Solicitando Token ao DSS - Resumo Executivo

## 📋 O que foi criado

Implementação completa do fluxo de autenticação para o USS (Unmanned Traffic System Service) solicitar e gerenciar tokens JWT junto ao servidor de autenticação ICEA (AUTH) para realizar operações no DSS (Discovery and Synchronization Service).

## 🎯 Componentes Principais

### 1. **ICEAAuthenticator** (`apps/dss_client/auth.py`)
Gerenciador de autenticação com cache automático de tokens.

```python
from apps.dss_client.auth import ICEAAuthenticator

authenticator = ICEAAuthenticator()
token = authenticator.get_token(
    intended_audience="core-service",
    scope="utm.strategic_coordination"
)
```

**Características:**
- Obtenção de tokens JWT via GET `/token?apikey=...`
- Cache automático com TTL baseado em expiração
- Renovação antes de expirar (5 minutos de margem)
- Decodificação e validação de JWT

### 2. **DSSClient** (`apps/dss_client/client.py`)
Cliente HTTP para o DSS com autenticação integrada.

```python
from apps.dss_client.client import DSSClient

client = DSSClient(
    intended_audience="core-service",
    scope="utm.strategic_coordination",
    auto_authenticate=True
)

# Token é enviado automaticamente em todas as requisições
constraints = client.query_constraints()
```

**Métodos disponíveis:**
- `query_constraints()` - GET /dss/v1/constraints
- `query_constraints_with_area()` - POST /dss/v1/constraints/query
- `submit_operational_intent_reference()` - PUT /dss/v1/operational_intent_references/{id}
- `get_operational_intent_reference()` - GET /dss/v1/operational_intent_references/{id}
- `delete_operational_intent_reference()` - DELETE /dss/v1/operational_intent_references/{id}

### 3. **Tratamento de Exceções** (`apps/dss_client/exceptions.py`)
Erros estruturados para diferentes cenários:

```python
from apps.dss_client.exceptions import (
    DSSAuthenticationError,    # 401 - Token inválido
    DSSAuthorizationError,     # 403 - Sem permissão
    DSSNotFoundError,          # 404 - Não encontrado
    DSSConflictError,          # 409 - OIR conflitante
    DSSValidationError,        # 400 - Dados inválidos
    DSSConnectionError,        # Erro de rede
    DSSServerError             # 5xx - Erro do servidor
)
```

## 🔄 Fluxo de Autenticação

```
1. USS solicita token
   ├─> GET /token?intended_audience=core-service&scope=utm.strategic_coordination&apikey=brutm
   └─> Resposta: {"access_token": "JWT...", "expires_in": 3600}

2. USS armazena em cache (TTL: 3300 segundos)

3. USS usa token em requisições ao DSS
   ├─> Authorization: Bearer JWT...
   └─> Resposta: 200 OK com dados

4. Quando cache expira (3300s) ou token vai expirar
   └─> Volta ao passo 1 (renovação automática)
```

## 📚 Documentação Criada

### 1. **FLUXO_AUTENTICACAO_USS_DSS.md**
Documentação técnica completa com:
- Diagrama de arquitetura
- Detalhes da implementação
- Estrutura de requisições HTTP
- Tratamento de erros
- Exemplo completo de uso
- Resumo em tabela

**Como usar:**
```bash
cat FLUXO_AUTENTICACAO_USS_DSS.md
```

### 2. **GUIA_INTEGRACAO_TOKEN_DSS.md**
Guia de integração prático com:
- Visão geral da arquitetura
- Componentes principais
- Passo-a-passo de integração
- Exemplos em views Django
- Exemplos em Celery tasks
- Troubleshooting

**Como usar:**
```bash
cat GUIA_INTEGRACAO_TOKEN_DSS.md
```

### 3. **exemplo_request_token.py**
Script executável com 6 exemplos práticos:

1. Autenticação básica
2. Cache de token
3. Decodificar JWT
4. Cliente DSS
5. Submeter OIR
6. Tratamento de erros

**Como executar:**
```bash
# Ativar ambiente
source venv/bin/activate

# Executar exemplos
python exemplo_request_token.py
```

### 4. **apps/dss_client/test_authentication_integration.py**
Testes automatizados com:
- Testes unitários da autenticação
- Testes do cliente DSS
- Testes de integração completa
- Validação de tokens
- 25+ casos de teste

**Como executar:**
```bash
# Via Django test runner
python manage.py test apps.dss_client.test_authentication_integration

# Via script direto
python apps/dss_client/test_authentication_integration.py
```

## 🚀 Como Usar

### Uso Básico

```python
from apps.dss_client.client import DSSClient

# Criar cliente com autenticação automática
client = DSSClient(
    intended_audience="core-service",
    scope="utm.strategic_coordination"
)

# Fazer requisições (token gerenciado automaticamente)
constraints = client.query_constraints()
print(f"Constraints: {constraints}")
```

### Em Views Django

```python
# apps/flight_plans/views.py
from rest_framework import viewsets
from apps.dss_client.client import DSSClient

class FlightPlanViewSet(viewsets.ModelViewSet):
    def perform_create(self, serializer):
        flight_plan = serializer.save()
        
        # Submeter ao DSS
        client = DSSClient(
            intended_audience="core-service",
            scope="utm.strategic_coordination"
        )
        
        result = client.submit_operational_intent_reference(
            oir_id=str(flight_plan.id),
            extents=flight_plan.get_extents(),
            uss_base_url="https://seu-uss.com"
        )
```

### Em Celery Tasks

```python
# apps/sync/tasks.py
from celery import shared_task
from apps.dss_client.client import DSSClient

@shared_task(bind=True, max_retries=3)
def sync_flight_plan_to_dss(self, flight_plan_id):
    try:
        client = DSSClient(
            intended_audience="core-service",
            scope="utm.strategic_coordination"
        )
        
        # Requisição ao DSS
        result = client.submit_operational_intent_reference(...)
        
    except Exception as e:
        # Retry com backoff
        raise self.retry(exc=e, countdown=2 ** self.request.retries)
```

## ⚙️ Configuração

### .env

```env
# Autenticação ICEA
ICEA_API_KEY=brutm
ICEA_AUTH_URL=https://api.sandbox.br-utm.org/token
DSS_BASE_URL=https://api.sandbox.br-utm.org

# Cache Django (para armazenar tokens)
CACHE_BACKEND=django.core.cache.backends.locmem.LocMemCache
```

### Django Settings

```python
# config/settings/base.py

# Já está configurado:
ICEA_API_KEY = env('ICEA_API_KEY', default='')
ICEA_AUTH_URL = env('ICEA_AUTH_URL', default='https://api.sandbox.br-utm.org/token')
DSS_BASE_URL = env('DSS_BASE_URL', default='https://api.sandbox.br-utm.org')

# Cache (para tokens)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}
```

## 🧪 Testes

### Teste Manual no Shell Django

```bash
python manage.py shell
```

```python
from apps.dss_client.client import DSSClient

# Teste 1: Criar cliente com autenticação
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
    uss_base_url="https://test-uss.com",
    state="Accepted"
)
print(f"OIR criada: {result['operational_intent_reference']['id']}")
```

### Teste Automatizado

```bash
# Executar os 6 exemplos práticos
python exemplo_request_token.py

# Executar testes unitários
python manage.py test apps.dss_client.test_authentication_integration

# Com verbose
python manage.py test apps.dss_client.test_authentication_integration -v 2
```

## 📊 Estrutura de Diretórios

```
/mnt/dados/projetos/uss/
├── FLUXO_AUTENTICACAO_USS_DSS.md          ← Documentação técnica
├── GUIA_INTEGRACAO_TOKEN_DSS.md           ← Guia de integração
├── exemplo_request_token.py               ← 6 exemplos práticos
├── apps/
│   └── dss_client/
│       ├── auth.py                        ← ICEAAuthenticator
│       ├── client.py                      ← DSSClient
│       ├── exceptions.py                  ← Exceções customizadas
│       ├── test_authentication_integration.py  ← Testes
│       └── ...
└── ...
```

## 🔑 Conceitos-Chave

### 1. **Token JWT (JSON Web Token)**
- Contém informações de autenticação e autorização
- Possui tempo de expiração (exp)
- Validado em cada requisição ao DSS

### 2. **Cache de Token**
- Armazena tokens para evitar múltiplas requisições ao AUTH
- TTL calculado dinamicamente baseado em expiração
- Margem de segurança de 5 minutos antes de expirar

### 3. **Bearer Token**
- Formato padrão: `Authorization: Bearer <token>`
- Enviado em todas as requisições ao DSS
- Validado pelo servidor DSS

### 4. **Intended Audience**
- Identifica o serviço alvo do token (ex: `core-service`)
- Parte da requisição ao AUTH
- Incluído no payload do JWT

### 5. **Scope**
- Define permissões do token (ex: `utm.strategic_coordination`)
- Parte da requisição ao AUTH
- Incluído no payload do JWT

## ✅ Checklist de Implementação

- [x] Classe `ICEAAuthenticator` implementada
- [x] Classe `DSSClient` implementada
- [x] Exceções customizadas criadas
- [x] Cache de token funcionando
- [x] Documentação técnica completa
- [x] Guia de integração prático
- [x] Exemplos de código executáveis
- [x] Testes automatizados (25+ casos)
- [x] Configuração no .env
- [x] Integração Django settings

## 🐛 Troubleshooting Rápido

### Erro: Token não é obtido
```bash
# Verificar configuração
echo $ICEA_AUTH_URL
echo $ICEA_API_KEY

# Testar conexão
curl https://api.sandbox.br-utm.org/token?apikey=brutm&intended_audience=core-service
```

### Erro: Acesso negado (403)
```python
# Verificar permissões da API Key
# Contactar ICEA para confirmar escopo 'utm.strategic_coordination'
```

### Erro: Token expirado
```python
# Não fazer nada! Token é renovado automaticamente.
# Se quiser forçar renovação:
from django.core.cache import cache
cache.delete("dss_token:core-service:utm.strategic_coordination")
```

## 📞 Suporte e Referências

- **BR-UTM Sandbox:** https://br-utm.org
- **ASTM F3548-22:** Padrão UAS Traffic Management
- **RFC 7519:** JWT Specification
- **InterUSS:** https://github.com/interuss/InterUSS-Platform

## 📝 Versão e Data

- **Versão:** 1.0
- **Data:** Março 2026
- **Compatibilidade:** Django 5.2+, Python 3.9+, ASTM F3548-22, BR-UTM Sandbox

---

## 🎓 Próximos Passos Recomendados

1. **Teste os exemplos:** `python exemplo_request_token.py`
2. **Leia a documentação técnica:** `FLUXO_AUTENTICACAO_USS_DSS.md`
3. **Estude o guia de integração:** `GUIA_INTEGRACAO_TOKEN_DSS.md`
4. **Execute os testes:** `python manage.py test apps.dss_client.test_authentication_integration`
5. **Integre no seu código:** Use `DSSClient` em views/tasks
6. **Monitore em produção:** Implemente logging de tokens

---

**Criado com ❤️ para o USS no BR-UTM Sandbox**
