# Plano de Implementação — USS (UAS Service Supplier)

Implementação de um USS compatível com **ASTM F3548-22** e a **suíte de testes InterUSS**, capaz de receber intenções de voo, detectar conflitos (local + DSS), publicar no DSS e manter consistência com outros USSs.

---

## Stack Tecnológica

| Camada | Tecnologia | Justificativa |
|---|---|---|
| Framework | **Django + DRF** | Maturidade, ORM robusto, ecossistema |
| Banco de dados | **PostgreSQL + PostGIS** | Suporte geoespacial nativo (`ST_Intersects`) |
| Serialização / Validação | **Pydantic** (dentro do DRF) | Parsing estrito de payloads ASTM |
| Tarefas assíncronas | **Celery + Redis** | Retry com backoff para chamadas DSS |
| Autenticação | **OAuth2 / JWT** (via `python-jose`) | Requisito ASTM F3548 e produção |
| Containerização | **Docker Compose** | Desenvolvimento e testes locais |
| Testes | **pytest-django** | Cobertura unitária e de integração |

---

## Autenticação (Montreal/ICEA)

### Obter Token
A URL base para autenticação é: `https://api.sandbox.br-utm.org/token`

A requisição deve conter as seguintes query strings:

| Campo | Descrição | Exemplo |
|---|---|---|
| `intended_audience` | USS de destino da mensagem (Domínio do provedor) | `"utm.decea.mil.br"` |
| `scope` | Escopo da requisição (conforme definido no OpenAPI) | `utm.strategic_coordination` |
| `apikey` | Chave recebida do ICEA (opcionalmente enviada no Header) | `xxxxxx` |

---

### Validar Autenticação de outro USS
Ao receber uma requisição de outro USS, é necessário validar o token fornecido. O payload do token contém:

| Campo | Descrição | Exemplo |
|---|---|---|
| `aud` | Domínio do seu provedor | `"utm.provider1.com"` |
| `exp` | Timestamp epoch de expiração | `1719777868` |
| `iss` | Nome do provedor emissor | `ICEA` |
| `scope` | Escopo autorizado (pode conter múltiplos separados por espaço) | `utm.strategic_coordination` |
| `sub` | Nome do provedor origem da requisição (não deve ser validado) | `"USS1"` |

#### Passos para Verificação:
1. **Verificar assinatura**: Validar utilizando a chave pública do ICEA.
2. **Verificar validade**: O campo `exp` não deve ser menor que o horário atual.
3. **Verificar audiência**: O campo `aud` deve ser o nome do seu provedor.
4. **Verificar escopo**: Validar se o `scope` contém o valor necessário para o endpoint.

### Chave Pública Eco-UTM
Referência: [Wiki DECEA](https://servicos2.decea.mil.br/br-utm/wiki/link/199#bkmrk-chave-publica-eco-ut)

**Chave:** `xxxxxx`

---

## Estrutura do Projeto

```
uss/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── manage.py
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   └── urls.py
├── apps/
│   ├── flight_plans/        # Fase 1 + 2 + 3
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── conflict_engine.py
│   ├── dss_client/          # Fase 4
│   │   ├── client.py
│   │   └── exceptions.py
│   ├── test_interface/      # Fase 5
│   │   ├── views.py
│   │   └── urls.py
│   └── sync/                # Fase 6
│       ├── tasks.py
│       └── cache.py
└── tests/
    ├── test_models.py
    ├── test_conflict_engine.py
    ├── test_dss_client.py
    └── test_api.py
```

---

## Fase 1 — Modelagem do Domínio

### Objetivo
Representar corretamente o conceito de **Operational Intent** com suporte a dados geoespaciais.

### Modelos Principais

```python
class FlightPlan(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4)
    state       = models.CharField(max_length=20, choices=State.choices, default=State.PLANNING)
    priority    = models.IntegerField(default=0)
    start_time  = models.DateTimeField()
    end_time    = models.DateTimeField()
    volume      = gis_models.GeometryField(dim=3, srid=4326)  # Volume 3D (lon,lat,alt)
    uss_base_url = models.URLField()

class OperationalIntent(models.Model):
    flight_plan  = models.OneToOneField(FlightPlan, on_delete=models.CASCADE)
    dss_id       = models.CharField(max_length=255, blank=True)
    version      = models.IntegerField(default=0)
    state        = models.CharField(max_length=20, choices=State.choices)
```

---

## Fase 2 — API ASTM F3548 (Core)

### Objetivo
Implementar a interface REST que o ecossistema espera.

- **PUT `/flight_plans/{id}`**: Criar ou atualizar intenção.
- **GET `/flight_plans/{id}`**: Consultar intenção.
- **DELETE `/flight_plans/{id}`**: Remover intenção.

**Fluxo interno:** Validar payload → Checar conflitos locais → Consultar DSS → Decidir (Accept/Reject) → Publicar no DSS → Retornar resposta padrão ASTM.

---

## Fase 3 — Motor de Conflito

### Objetivo
Detectar conflitos espaciais e temporais corretamente.

- **Espaço**: Usar `ST_Intersects` do PostGIS.
- **Tempo**: Validar sobreposição de janelas `(start_a <= end_b) AND (end_a >= start_b)`.
- **Global**: Integrar dados retornados pelo DSS para conflitos com outros USSs.

---

## Fase 4 — Cliente DSS (Integração)

### Objetivo
Fazer o USS interagir com o Discovery and Synchronization Service.

**Operações obrigatórias:**
- `create_operational_intent_reference`
- `update_operational_intent_reference`
- `query_operational_intent_references`
- `delete_operational_intent_reference`

---

## Fase 5 — Interface de Teste (InterUSS)

### Objetivo
Permitir que o test driver oficial controle seu USS.

**Endpoints necessários:**
- `POST /inject_flight`
- `DELETE /clear_state`
- `GET /status`

---

## Fase 6 — Sincronização e Consistência

### Objetivo
Garantir que o estado local não divirja do DSS.

- **Resiliência**: Retry com backoff exponencial para falhas no DSS.
- **Sincronia**: Reconciliação periódica de OIRs (Operational Intent References).

---

## Fase 7 — Suíte de Testes InterUSS

### Objetivo
Passar no onboarding oficial.

- Executar cenários de conflito entre múltiplos USSs.
- Validar prioridade de voo e consistência de dados.

---

## Fase 8 — Produção

### Requisitos
- HTTPS obrigatório.
- Autenticação OAuth2 padrão ASTM F3548.
- Alta disponibilidade e monitoramento.
