# Plano de Teste: Fluxo de Autenticação e Envio de OIR Conflitante (USS_cristiano e USS_emanoel)

Este documento detalha o plano passo a passo para simular e testar o cenário onde duas entidades USS distintas (`USS_cristiano` e `USS_emanoel`) se autenticam e submetem Referências de Intenções Operacionais (OIR) projetando-se sobre o mesmo espaço geográfico e a mesma janela de tempo no DSS (Discovery and Synchronization Service).

---

## 1. Estrutura e Lógica do Teste

O principal intuito deste teste é validar dois comportamentos base:
1. O sucesso da autenticação e mapeamento do perímetro via um disparo regular (simulação livre de conflitos feitos pelo primeiro USS).
2. O sistema de interseção estratégica (Conflict Handling) devolvido pelo DSS, disparado quando um segundo USS envia um percurso de ocupação redundante no mesmo Espaço-Tempo que o USS primário.

### Extents da Operação (Compartilhado)
Para garantir que de fato existirá um cenário sobreposto (Overlap), as coordenadas usadas na intenção (OIR) do `USS_cristiano` serão replicadas nas intenções do `USS_emanoel`:

- **Área Geográfica (Polígono):**
  - Vérite 1: `lat`: -23.5505, `lng`: -46.6333
  - Vérite 2: `lat`: -23.5505, `lng`: -46.6233
  - Vérite 3: `lat`: -23.5405, `lng`: -46.6233
  - Vérite 4: `lat`: -23.5405, `lng`: -46.6333
- **Altitudes e Referencial:** De `50 M` inferior até `100 M` superior (`W84`).
- **Janela de Tempo (Timestamp):** Período futuro estático para conflito (Ex: `2026-05-15T12:00:00Z` abrindo, e `2026-05-15T13:00:00Z` finalizando a operação).

---

## 2. Passo a Passo do Fluxo Lógico

### Etapa A - Atuação como `USS_cristiano`

1. **Autenticação e Permissão (Token):**
   - Disparar requisição em direção à API de Auth com a finalidade de obter acesso restrito aos serviços utm.
   - *Scope:* `utm.strategic_coordination` 
   - *Intended Audience:* `utm.decea.mil.br`
   
2. **Definir Identidade da Requisição:**
   - Provisionar um UUID versão 4 exclusivo para este voo (Ex: *OIR_ID_CRISTIANO*).
   - Configurar o endpoint atrelado a este USS como algo específico: `https://uss.cristiano.local`.

3. **Submeter Operação ao DSS:**
   - Com o token válido no cabeçalho (*Bearer*), despachar o JSON de Extents num método PUT para o DSS.
   - **Resultado Esperado:** Reposta de sucesso (200 ou 201). O array de retorno `conflicting_oirs` deve retornar completamente vazio, atestando uma reserva de perímetro livre de vizinhos e conflitos.

### Etapa B - Atuação como `USS_emanoel`

1. **Autenticação (Novo Token):**
   - Obter um token de segurança de forma similar à Etapa A, utilizando as credenciais pertencentes ao contexto da operadora de Emanoel.
   
2. **Duplicação Tática (Criação do Conflito):**
   - Provisionar um segundo UUID diferente (*OIR_ID_EMANOEL*).
   - Utilizar as **MESMAS propriedades geométricas e temporais** (Latitude, Longitude e Tempo definidos no Início do plano).
   - Apontar o atributo auxiliar garantindo ser desta operadora: `https://uss.emanoel.local`.

3. **Submissão com Trato de Intersecção:**
   - O `USS_emanoel` efetua a injeção (`PUT`) contendo a sua intenção sobre o DSS.
   - **Resultado Esperado:** A resposta do servidor HTTP processará normalmente, porém no nó `conflicting_oirs` o DSS alertará o `USS_emanoel` de forma ativa sobre o mapeamento de rota que o `USS_cristiano` outorgou previamente, entregando os detalhes de contato via `uss_base_url`.  A partir daqui ocorre o tratamento *Peer-to-peer*.

---

## 3. Como Realizar o Fluxo Usando o Insomnia

Para automatizar ou viabilizar verificações pontuais, pode-se usar o **Insomnia**. É recomendado criar os chamados na sequência abaixo dentro da interface gráfica da plataforma.

### 3.1. Preparando o Ambiente (Environment Variables)
Crie um *Environment* (atalho `Ctrl+E` no topo da tela) chamado `USS-Sandbox` e defina variáveis estruturais caso utilize Docker/localhost:
```json
{
  "dss_base_url": "https://api.sandbox.br-utm.org", 
  "auth_url": "https://api.sandbox.br-utm.org/token",
  "audience": "utm.decea.mil.br",
  "scope": "utm.strategic_coordination"
}
```
*(Ajuste portas e contextos que batam com a arquitetura do momento em sua máquina)*.

### 3.2. Configurando o Request 1 (`Token Cristiano`)
A primeira chamada servirá para angariação do token.
- **Método**: `GET`
- **Url**: `{{ _.auth_url }}?intended_audience={{ _.audience }}&scope={{ _.scope }}`
- Ao ser devolvida uma String (O JWT Token), deixe-o salvo/copiado.

### 3.3. Configurando o Request 2 (`OIR Cristiano`)
Aqui despachamos a intenção genuinamente original.
- **Método**: `PUT`
- **Url**: `{{ _.dss_base_url }}/dss/v1/operational_intent_references/11111111-1111-4111-8111-111111111111`
  *(Repare que forçamos o UUID da rota no final da URL)*
- **Insomnia Headers:**
  - `Content-Type`: `application/json`
- **Insomnia Auth (Aba Auth -> Bearer Token):** Cole o TOKEN recolhido no Passo 3.2 do Cristiano no campo vazio de Bearer.
- **Body (JSON):**
```json
{
  "extents": [{
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
    "time_start": {"value": "2026-05-15T12:00:00Z", "format": "RFC3339"},
    "time_end": {"value": "2026-05-15T13:00:00Z", "format": "RFC3339"}
  }],
  "state": "Accepted",
  "uss_base_url": "https://uss-cristiano.local",
  "new_subscription": {
    "uss_base_url": "https://uss-cristiano.local",
    "notify_for_operational_intents": true
  }
}
```
> **Execute a Chamada**. O resultado JSON evidenciará que gravou sem problemas (*Conflitos virão vazios*).

### 3.4. Configurando o Request 3 (`Token Emanoel`)
- Você pode reutilizar o Request do `3.2` se for o mesmo endpoint de simulação, apenas copie o Token novamente, se simulando os cenários com a mesma permissão global, ou de fato modifique as credenciais da Aba Auth (Username/Keys) de obtenção caso operem num backend com divisões severas.

### 3.5. Configurando o Request 4 (`OIR Emanoel`)
Este é o Request que vai gerar a simulação da colisão.
- Pode **Duplicar** (Duplicate) o Request 2 (`OIR Cristiano`) no Insomnia para economizar tempo.
- **Método**: `PUT`
- **Url**: `{{ _.dss_base_url }}/dss/v1/operational_intent_references/22222222-2222-4222-8222-222222222222`
  *(Substitua o UUID 1111 na URL por um UUID totalmente novo 2222...)*
- **Aba Auth:** Lembre-se de substituir o Token aqui pelo token do `Emanoel` gerado na etapa 3.4.
- **Body (JSON):**  
Neste ponto reside a magia. Mantenha os contornos e o limite do espaço perfeitamente idênticos. Altere somentes as subscrições pertencentes de modo lógico para identificar de quem é o pedido atual!
```diff
-  "uss_base_url": "https://uss-cristiano.local",
+  "uss_base_url": "https://uss-emanoel.local",
   "new_subscription": {
-    "uss_base_url": "https://uss-cristiano.local",
+    "uss_base_url": "https://uss-emanoel.local",
     "notify_for_operational_intents": true
   }
```
> **Execute a Chamada e Valide a Resposta**. O DSS retornará Sucesso na indexação, mas trará em array JSON que de fato sua intenção esbarrou numa barreira existente construída pelo usuário da Etapa 3.3.

```json
{
  "operational_intent_reference": { 
     "id": "22222222-2222-4222-8222-222222222222", 
     ... 
  },
  "conflicting_oirs": [
    {
      "id": "11111111-1111-4111-8111-111111111111",
      "uss_base_url": "https://uss-cristiano.local",
      "version": 1,
      "state": "Accepted"
    }
  ]
}
```
