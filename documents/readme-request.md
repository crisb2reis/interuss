# Guia de Testes Práticos no Insomnia (ASTM F3548)

Este documento foi criado para ajudar QA, engenheiros e operadores a validar os endpoints do Discovery and Synchronization Service (DSS) do sandbox BR-UTM via ferramentas de clientes REST como o **Insomnia** ou **Postman**.

Nós simularemos uma conversa entre a sua USS (você enviando chamadas via Insomnia) e a rede UTM.

---

## Passo 1: Configurando o `Environment` no Insomnia
No seu Insomnia (ou Postman), crie um ambiente de variáveis (_Environment_) e adicione as seguintes chaves. Isso evitará que você precise copiar e colar links o tempo inteiro.

```json
{
  "dss_url": "https://dss.sandbox.br-utm.org/dss",
  "auth_url": "https://api.sandbox.br-utm.org/token",
  "apikey": "brutm",
  "my_uss_url": "https://uss.minha-empresa.com",
  "beta_uss_url": "https://uss.concorrente-beta.com",
  "token": ""
}
```

---

## Passo 2: Obter o JWT de Acesso (AUTH)

Toda conexão na rede UTM exige autorização com *audience* específica.

*   **Método:** `GET`
*   **URL:** `{{auth_url}}?intended_audience=core-service&scope=utm.strategic_coordination&apikey={{apikey}}`

**Ação Pós-Request:**
1. Envie a requisição.
2. O servidor retornará um JSON contendo a chave `access_token`.
3. Copie o valor do token e cole na variável de environment chamada `"token"`.

---

## Passo 3: Consultar Constraints (Opcional)

Garante que você está autenticado e inspeciona se há alguma restrição geopolítica (Constraints) dentro daquela área espacial.

*   **Método:** `POST`
*   **URL:** `{{dss_url}}/dss/v1/constraints/query`
*   **Header Customizado:**
    *   `Authorization`: `Bearer {{token}}`
    *   `Content-Type`: `application/json`

**Body (JSON):**
```json
{
    "area_of_interest": {
        "volume": {
            "outline_polygon": {
                "vertices": [
                    {"lat": -23.5505, "lng": -46.6333},
                    {"lat": -23.5505, "lng": -46.6233},
                    {"lat": -23.5605, "lng": -46.6233},
                    {"lat": -23.5605, "lng": -46.6333}
                ]
            },
            "altitude_lower": {"value": 50, "units": "M", "reference": "W84"},
            "altitude_upper": {"value": 100, "units": "M", "reference": "W84"}
        },
        "time_start": {"value": "2026-06-15T14:00:00Z", "format": "RFC3339"},
        "time_end": {"value": "2026-06-15T16:00:00Z", "format": "RFC3339"}
    }
}
```

**Resultado Esperado:** 
Status `200 OK`. Você deverá receber uma lista (vazia ou não) de constraints.

---

## Passo 4: Submeter sua Operational Intent Reference (OIR)

Agora sim, iremos enviar o seu voo para reservar o espaço no DSS UTM.
Lembre-se: os "intentions" são inseridos baseados no ID estrito fornecido na URL (UUID).

*   **Método:** `PUT`
*   **URL:** `{{dss_url}}/dss/v1/operational_intent_references/550e8400-e29b-41d4-a716-446655440000` *(Substitua o UUID por algum gerado aleatoriamente se quiser).*
*   **Header Customizado:**
    *   `Authorization`: `Bearer {{token}}`
    *   `Content-Type`: `application/json`

**Body (JSON):**
```json
{
    "extents": [
        {
            "volume": {
                "outline_polygon": {
                    "vertices": [
                        {"lat": -23.5505, "lng": -46.6333},
                        {"lat": -23.5505, "lng": -46.6233},
                        {"lat": -23.5605, "lng": -46.6233},
                        {"lat": -23.5605, "lng": -46.6333}
                    ]
                },
                "altitude_lower": {"value": 50, "units": "M", "reference": "W84"},
                "altitude_upper": {"value": 100, "units": "M", "reference": "W84"}
            },
            "time_start": {"value": "2026-06-15T14:00:00Z", "format": "RFC3339"},
            "time_end": {"value": "2026-06-15T16:00:00Z", "format": "RFC3339"}
        }
    ],
    "uss_base_url": "{{my_uss_url}}",
    "state": "Accepted"
}
```

**Resultado Esperado:**
Status `201 Created` ou `200 OK`. 
O DSS irá retornar o `operational_intent_reference` de sucesso e o respectivo token criptografado dele: `ovn`!

---

## Passo 5: Simulando um Conflito (Choque Aéreo - erro 409)

E se algum drone "Concorrente" for tentar ocupar o mesmíssimo espaço que nós reservamos no passo 4? O Insomnia vai estourar um erro bloqueante de `409 Conflict`. Veja na prática!

No seu Insomnia, você vai simular um **segundo operador de UTM**.

*   **Método:** `PUT`
*   **URL:** `{{dss_url}}/dss/v1/operational_intent_references/a93b4588-43d7-4632-9c3f-912da6f23f0g` *(Use OBRIGATORIAMENTE um UUID novo e DIFERENTE da requisição do passo 4)*
*   **Header Customizado:**
    *   `Authorization`: `Bearer {{token}}`
    *   `Content-Type`: `application/json`

**Body (JSON):** *(Perceba que enviaremos NO MESMO LUGAR, mas alterando apenas o a url de quem enviou)*
```json
{
    "extents": [
        {
            "volume": {
                "outline_polygon": {
                    "vertices": [
                        {"lat": -23.5505, "lng": -46.6333},
                        {"lat": -23.5505, "lng": -46.6233},
                        {"lat": -23.5605, "lng": -46.6233},
                        {"lat": -23.5605, "lng": -46.6333}
                    ]
                },
                "altitude_lower": {"value": 50, "units": "M", "reference": "W84"},
                "altitude_upper": {"value": 100, "units": "M", "reference": "W84"}
            },
            "time_start": {"value": "2026-06-15T14:00:00Z", "format": "RFC3339"},
            "time_end": {"value": "2026-06-15T16:00:00Z", "format": "RFC3339"}
        }
    ],
    "uss_base_url": "{{beta_uss_url}}",
    "state": "Accepted"
}
```

**Resultado Esperado (Conflito):**
Você NÃO conseguirá registrar (O DSS recusa)!
Status: `409 Conflict`.

O DSS te informará **com quem e por que** sua rota vai bater. A resposta em JSON vai se parecer com:
```json
{
    "message": "Current OVNs not provided for one or more OperationalIntents or Constraints",
    "missing_operational_intents": [
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "manager": "brutm",
            "state": "Accepted",
            "uss_base_url": "https://uss.minha-empresa.com",
            ...
        }
    ]
}
```
*   **Atenção:** Como QA, valide se a lista `missing_operational_intents` contém os dados da "sua" USS do Passo 4. Repare que o campo `id` e `uss_base_url` listados lá embaixo demonstram o oponente blindando a zona de conflito, seguindo os estritórios da rede InterUSS ASTM UTM F3548-22!
