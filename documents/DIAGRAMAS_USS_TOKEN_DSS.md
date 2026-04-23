# Fluxo Visual: USS → AUTH (Token) → DSS

## Diagrama 1: Sequência Completa

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          FLUXO DE AUTENTICAÇÃO DO USS                        │
└──────────────────────────────────────────────────────────────────────────────┘


  ┌─────────────────────────┐
  │   USS                   │
  │ (Seu Sistema Django)    │
  └───────────┬─────────────┘
              │
              │ Passo 1: Solicitar Token
              │ GET /token?
              │   intended_audience=core-service
              │   scope=utm.strategic_coordination  
              │   apikey=brutm
              │
    ┌─────────▼─────────┐
    │ ICEA (AUTH)       │  ◄─ Servidor de Autenticação
    │ BR-UTM            │     (api.sandbox.br-utm.org)
    │ /token endpoint   │
    └─────────┬─────────┘
              │
              │ Passo 2: Retorna JWT
              │ HTTP 200 OK
              │ {
              │   "access_token": "eyJhbGciOiJSUzI1...",
              │   "token_type": "Bearer",
              │   "expires_in": 3600
              │ }
              │
              ▼
  ┌─────────────────────────┐
  │ USS (Cache)             │  ◄─ Armazena token
  │ TTL: 3300 segundos      │     (até 5 min antes de expirar)
  └───────────┬─────────────┘
              │
              │ Passo 3: Usar Token em Requisições
              │ GET /dss/v1/constraints
              │ Authorization: Bearer eyJhbGciOiJSUzI1...
              │
              ▼
    ┌─────────────────────┐
    │ DSS                 │
    │ (Discovery Service) │  ◄─ api.sandbox.br-utm.org/dss
    │ Validar Bearer      │
    │ Processar requisição│
    └─────────┬───────────┘
              │
              │ Passo 4: Retorna Resposta
              │ HTTP 200 OK
              │ {
              │   "constraints": [...],
              │   "operational_intent_references": [...]
              │ }
              │
              ▼
  ┌─────────────────────────┐
  │ USS                     │
  │ Processa resposta       │
  └─────────────────────────┘


┌──────────────────────────────────────────────────────────────────────────────┐
│                      REGENERAÇÃO DE TOKEN (Automática)                       │
└──────────────────────────────────────────────────────────────────────────────┘

  Timeline:
  
  t=0:00  ┌─ Solicitação ao AUTH
          │ ├─ GET /token
          │ └─ ✓ Token obtido (exp: 3600s)
          │
  t=0:05  ├─ Token recuperado do cache
          │ └─ ✓ Usando token em cache
          │
  t=0:55  ├─ Verificação: Cache vai expirar?
          │ │ TTL = 3600 - 300 = 3300s
          │ │ Tempo passado: 3300s
          │ │ Resultado: SIM, vai expirar!
          │ │
          │ ├─ Nova solicitação ao AUTH (automática)
          │ │ ├─ GET /token
          │ │ └─ ✓ Novo token obtido
          │ │
          │ └─ Cache atualizado com novo TTL
          │
  t=1:50  ├─ Token recuperado do novo cache
          │ └─ ✓ Usando novo token
          │
  ...     └─ Ciclo continua indefinidamente
```

## Diagrama 2: Componentes e Fluxo de Dados

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            ARQUITETURA DO USS                               │
└─────────────────────────────────────────────────────────────────────────────┘


  ┌────────────────────────────────────────────────────────────┐
  │                    Sua View Django                         │
  │                                                             │
  │  def create_flight_plan(request):                          │
  │      client = DSSClient(                                   │
  │          intended_audience="core-service",                │
  │          scope="utm.strategic_coordination"               │
  │      )                                                     │
  │      result = client.submit_operational_intent_reference()│
  └────────┬────────────────────────────────────────────────────┘
           │
           │ Usa
           │
           ▼
  ┌────────────────────────────────────────────────────────────┐
  │              DSSClient (apps/dss_client/client.py)        │
  │                                                             │
  │  • Encapsula comunicação com DSS                           │
  │  • Gerencia requisições HTTP                               │
  │  • Valida respostas                                        │
  │  • Trata erros com exceções customizadas                   │
  │                                                             │
  │  Métodos principais:                                       │
  │  ├─ query_constraints()                                   │
  │  ├─ query_constraints_with_area()                        │
  │  ├─ submit_operational_intent_reference()                │
  │  ├─ get_operational_intent_reference()                   │
  │  └─ delete_operational_intent_reference()                │
  └────────┬────────────────────────────────────────────────────┘
           │
           │ Usa (na inicialização)
           │
           ▼
  ┌────────────────────────────────────────────────────────────┐
  │        ICEAAuthenticator (apps/dss_client/auth.py)        │
  │                                                             │
  │  get_token(intended_audience, scope)                      │
  │  ├─ Verifica cache                                        │
  │  ├─ Se válido: retorna do cache                           │
  │  └─ Se inválido: solicita novo token                      │
  │      ├─ GET /token (ao AUTH)                              │
  │      ├─ Valida expiração (JWT decode)                     │
  │      └─ Armazena em cache Django                          │
  └────────┬────────────────────────────────────────────────────┘
           │
           │ Armazena em
           │
           ▼
  ┌────────────────────────────────────────────────────────────┐
  │              Cache Django                                  │
  │                                                             │
  │  Key: "dss_token:core-service:utm.strategic_coordination" │
  │  Value: "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."        │
  │  TTL: 3300 segundos (= 3600 - 300 margin)                │
  └────────────────────────────────────────────────────────────┘
```

## Diagrama 3: Estados do Token

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                     CICLO DE VIDA DO TOKEN JWT                               │
└──────────────────────────────────────────────────────────────────────────────┘


                          ┌─────────────────────┐
                          │   Token Obtido      │
                          │ do Servidor AUTH    │
                          └──────────┬──────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    │                                 │
                    ▼                                 ▼
        ┌──────────────────────────┐    ┌──────────────────────────┐
        │     VÁLIDO               │    │   ARMAZENADO EM CACHE    │
        │ (exp > now + 5 min)      │────│ TTL = exp - now - margin │
        │                          │    │ Margem = 300 segundos    │
        └──────────────────────────┘    └──────────────────────────┘
                    │                                 │
                    │ (5 minutos antes de expirar)    │
                    │                                 │
                    ▼                                 ▼
        ┌──────────────────────────┐    ┌──────────────────────────┐
        │   PRESTES A EXPIRAR      │    │   CACHE EXPIROU          │
        │ (exp ≤ now + 5 min)      │────│ (TTL ≤ 0)                │
        └──────────────────────────┘    └──────────────────────────┘
                    │                                 │
                    │ (Quando detectado)              │ (Quando acessado)
                    │                                 │
                    └────────────────┬────────────────┘
                                     │
                                     ▼
                    ┌──────────────────────────────┐
                    │  RENOVAR TOKEN (AUTO)        │
                    │  GET /token novamente        │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │  NOVO TOKEN OBTIDO           │
                    │  Volta para VÁLIDO           │
                    └──────────────────────────────┘


LEGENDA:
  exp = Tempo de expiração do JWT (em segundos desde epoch)
  now = Tempo atual (em segundos desde epoch)
  margin = 300 segundos (5 minutos de margem de segurança)
```

## Diagrama 4: Tratamento de Erros

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                       TRATAMENTO DE ERROS NO USS                             │
└──────────────────────────────────────────────────────────────────────────────┘


Requisição HTTP ao DSS
       │
       ▼
┌─────────────────────────────┐
│ Verificar Status Code       │
└──────┬──────────────────────┘
       │
       ├──→ 200 OK
       │    └─→ ✓ Sucesso
       │        Retornar dados
       │
       ├──→ 400 Bad Request
       │    └─→ ✗ DSSValidationError
       │        Dados inválidos
       │
       ├──→ 401 Unauthorized
       │    └─→ ✗ DSSAuthenticationError
       │        Token inválido/expirado
       │        (Será renovado na próxima requisição)
       │
       ├──→ 403 Forbidden
       │    └─→ ✗ DSSAuthorizationError
       │        Sem permissão
       │        (Verificar API Key com ICEA)
       │
       ├──→ 404 Not Found
       │    └─→ ✗ DSSNotFoundError
       │        Recurso não encontrado
       │
       ├──→ 409 Conflict
       │    └─→ ✗ DSSConflictError
       │        OIR conflita com operação existente
       │        (Ajustar área/tempo da operação)
       │
       ├──→ 5xx Server Error
       │    └─→ ✗ DSSServerError
       │        Erro no servidor DSS
       │
       └──→ Timeout/Conexão perdida
            └─→ ✗ DSSConnectionError
                Tentar novamente com backoff exponencial


Padrão de Tratamento:

try:
    client = DSSClient(...)
    result = client.do_something()
except DSSAuthenticationError:
    # Token renovado automaticamente na próxima tentativa
    logger.warning("Token expirado")
except DSSAuthorizationError:
    # Problema com API Key
    logger.error("Sem permissão - verificar API Key")
except DSSConnectionError:
    # Implementar retry com backoff
    retry_with_backoff()
except Exception as e:
    # Erro genérico
    logger.exception(f"Erro: {e}")
```

## Diagrama 5: Requisição HTTP Completa

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    ESTRUTURA DE REQUISIÇÃO HTTP                              │
└──────────────────────────────────────────────────────────────────────────────┘


PASSO 1: Obter Token (GET Auth)
═════════════════════════════════════════════════════════════════════════════

REQUEST:
┌─────────────────────────────────────────────────────────────────────────────┐
│ GET /token?intended_audience=core-service&                                  │
│          scope=utm.strategic_coordination&                                  │
│          apikey=brutm HTTP/1.1                                              │
│ Host: api.sandbox.br-utm.org                                               │
│ User-Agent: Python-requests/2.31.0                                          │
│ Accept-Encoding: gzip, deflate                                              │
│ Connection: keep-alive                                                      │
└─────────────────────────────────────────────────────────────────────────────┘

RESPONSE:
┌─────────────────────────────────────────────────────────────────────────────┐
│ HTTP/1.1 200 OK                                                             │
│ Date: Thu, 13 Mar 2025 10:30:00 GMT                                         │
│ Content-Type: application/json                                              │
│ Content-Length: 856                                                         │
│ Connection: keep-alive                                                      │
│                                                                              │
│ {                                                                            │
│   "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",               │
│   "token_type": "Bearer",                                                   │
│   "expires_in": 3600                                                        │
│ }                                                                            │
└─────────────────────────────────────────────────────────────────────────────┘


PASSO 2: Usar Token no DSS
═════════════════════════════════════════════════════════════════════════════

REQUEST:
┌─────────────────────────────────────────────────────────────────────────────┐
│ GET /dss/v1/constraints HTTP/1.1                                            │
│ Host: api.sandbox.br-utm.org                                               │
│ Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...               │
│ Content-Type: application/json                                              │
│ User-Agent: Python-requests/2.31.0                                          │
│ Accept-Encoding: gzip, deflate                                              │
│ Connection: keep-alive                                                      │
└─────────────────────────────────────────────────────────────────────────────┘

RESPONSE:
┌─────────────────────────────────────────────────────────────────────────────┐
│ HTTP/1.1 200 OK                                                             │
│ Date: Thu, 13 Mar 2025 10:30:01 GMT                                         │
│ Content-Type: application/json                                              │
│ Content-Length: 42                                                          │
│ Connection: keep-alive                                                      │
│                                                                              │
│ {                                                                            │
│   "constraints": []                                                         │
│ }                                                                            │
└─────────────────────────────────────────────────────────────────────────────┘


PAYLOAD DO JWT DECODIFICADO:
═════════════════════════════════════════════════════════════════════════════

{
  "iss": "https://auth.sandbox.br-utm.org",      ◄─ Emissor
  "aud": "core-service",                         ◄─ Audience (para qual serviço?)
  "sub": "brutm-uss",                            ◄─ Subject (quem é o portador?)
  "scope": "utm.strategic_coordination",         ◄─ Escopo (permissões)
  "iat": 1710328200,                             ◄─ Emitido em (timestamp)
  "exp": 1710331800                              ◄─ Expira em (timestamp)
}
```

## Diagrama 6: Comparação - Com e Sem Cache

```
┌──────────────────────────────────────────────────────────────────────────────┐
│              IMPACTO DO CACHE DE TOKEN NA PERFORMANCE                        │
└──────────────────────────────────────────────────────────────────────────────┘


SEM CACHE (Requisição ao AUTH toda vez):
═════════════════════════════════════════════════════════════════════════════

USS Request 1: query_constraints()
    │
    ├─→ GET /token (ao AUTH)        ⏱ ~200ms
    ├─→ GET /dss/constraints        ⏱ ~150ms
    └─→ Total: ~350ms


USS Request 2: query_constraints()
    │
    ├─→ GET /token (ao AUTH)        ⏱ ~200ms  ◄─ Repetido!
    ├─→ GET /dss/constraints        ⏱ ~150ms
    └─→ Total: ~350ms


USS Request 3-10: ... (mesmo padrão)
    Total de requisições ao AUTH: 10
    Tempo economizado: 1.6 segundos (8 requisições × 200ms)


COM CACHE (Token armazenado localmente):
═════════════════════════════════════════════════════════════════════════════

USS Request 1: query_constraints()
    │
    ├─→ GET /token (ao AUTH)        ⏱ ~200ms
    ├─→ Armazenar em cache          ⏱ ~10ms
    ├─→ GET /dss/constraints        ⏱ ~150ms
    └─→ Total: ~360ms


USS Request 2-10: query_constraints()
    │
    ├─→ Recuperar token do cache    ⏱ ~1ms   ◄─ Do cache!
    ├─→ GET /dss/constraints        ⏱ ~150ms
    └─→ Total: ~151ms  (cada uma)


Total de requisições ao AUTH: 1  ◄─ Apenas 1!
Tempo total para 10 requisições:
  Com cache:    360 + 9×151 = 1719ms
  Sem cache:    10×350 = 3500ms
  ─────────────────────────────────
  Diferença:    1781ms economizados!
  Ganho:        203% mais rápido com cache!
```

---

**Notas Importantes:**

1. **Token é renovado automaticamente:** Você não precisa fazer nada! O sistema valida e renova quando necessário.

2. **Requisições são thread-safe:** Django cache é thread-safe, seguro para uso em aplicações multi-threaded.

3. **Cache persiste durante execução:** Enquanto o servidor Django estiver rodando, o cache mantém o token.

4. **Em produção:** Use Redis em vez de LocMemCache para melhor performance em múltiplos processos.

5. **Monitoramento:** Implemente logs para rastrear renovações de token.
