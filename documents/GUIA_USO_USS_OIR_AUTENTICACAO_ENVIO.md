# Guia Definitivo: Autenticação e Gestão de OIR no USS

Este documento consolida as informações cruciais e o passo a passo para utilizar o USS (UAS Service Supplier) em processos de autenticação no DSS, envio de Referência de Intenção Operacional (OIR) e verificação de conflitos de OIR com intenções enviadas por outros USS.

---

## 1. Autenticação no DSS

A comunicação com o Discovery and Synchronization Service (DSS) exige um token JWT (Bearer Token). No projeto em questão, toda essa mecânica é gerenciada de forma transparente pelas classes `DSSClient` e `ICEAAuthenticator`. 

### Como a autenticação funciona:
- O módulo de autenticação faz uma requisição via `GET` para a URL de autenticação do ICEA (no endpoint `/token`).
- São fornecidos os parâmetros obrigatórios: `intended_audience` (ex: `utm.decea.mil.br`), `scope` (ex: `utm.strategic_coordination`) e sua devida `apikey`.
- Para evitar chamadas repetidas contínuas que poderiam causar congestionamento, o token JWT recebido é armazenado em memória via *System Cache*, sendo re-autenticado automaticamente à beira de expirar.

### Passo a Passo de Autenticação

Para se autenticar, há duas modalidades utilizando a interface `DSSClient`:

**Método de Teste Manual / Explicativo:**
```python
from apps.dss_client.client import DSSClient
from django.conf import settings

# 1. Instancie o cliente especificando uma base_url
dss = DSSClient(base_url=settings.DSS_BASE_URL, token="")

# 2. Obtenha o token consumindo o método authenticate_icea
token = dss.authenticate_icea(
    intended_audience="utm.decea.mil.br",
    scope="utm.strategic_coordination"
)
print(f"Sucesso. Bearer Token obtido: {token[:30]}...")
```

**Método Automático (Recomendado na Operação):**
```python
from apps.dss_client.client import DSSClient

# Instanciando o cliente ativando a flag 'auto_authenticate'. 
# O Client já fará o fetch do Token ou o trará do Cache nativo do Django sem requerer métodos extra.
dss = DSSClient(
    intended_audience="utm.decea.mil.br", 
    scope="utm.strategic_coordination", 
    auto_authenticate=True
)
```

---

## 2. Envio de OIR (Operational Intent Reference)

A Intent (ou Intenção Operacional) demonstra seu design de área e tempo para uma missão. O envio da Intenção ao DSS atrela-a geograficamente por meio dos atributos de contorno (os `extents`).

### Passo a Passo para Submissão

```python
import uuid
from datetime import datetime, timedelta
from apps.dss_client.client import DSSClient

# 1. Inicialize a camada do cliente com autônomia de Token
dss = DSSClient(
    intended_audience="utm.decea.mil.br",
    scope="utm.strategic_coordination",
    auto_authenticate=True
)

# 2. Defina os contornos delimitadores (Volume de Polígonos 3D e Tempo)
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

# 3. Dispare via PUT o encapsulamento do plano no DSS
oir_id = str(uuid.uuid4())

resultado = dss.submit_operational_intent_reference(
    oir_id=oir_id,
    extents=extents,
    uss_base_url="https://uss.suaempresa.com.br", # URL root onde seu app escuta as requisições
    state="Accepted"
)

# Confirma o identificador salvo no DSS
print(f"OIR armazenada com sucesso no DSS! ID: {resultado.get('operational_intent_reference', {}).get('id')}")
```

---

## 3. Verificando OIR em Outros USS (Tratamento de Conflito)

Sempre que incluímos ou atualizamos com modificações de extents na submissão de OIR para o DSS, o mesmo analisa o escopo demográfico contido ali com a banco de dados federados. A resposta HTTP a este envio contém um array listando intenções prévias estabelecidas por outras UTM/USS que disputam o mesmo *Espaço-Tempo*.

### Passo a Passo da Verificação de Conflito

Partindo da variável `resultado` capturada no momento do passo acima, avaliamos os itens sobrepostos para dar início à mitigação estratégica ponta a ponta (Peer-to-Peer):

```python
# 1. Recuperar o array de OIRs que competem pela mesma matriz tempo-geográfica
conflitos = resultado.get('conflicting_oirs', [])

if not conflitos:
    print("Voo seguro! Nenhuma outra USS foi identificada na malha desse plano.")
else:
    print(f"Alerta: Ocorreram {len(conflitos)} conflitos detectados em submissão.")
    
    # 2. Extrair dados para roteamento direto ao outro competidor inter-USS
    for oir_concorrente in conflitos:
        id_operacao = oir_concorrente.get('id')
        uss_dona = oir_concorrente.get('uss_base_url')
        
        print(f" >> Área reservada pelo ID: {id_operacao} controlado através de: {uss_dona}")
        
    # Observação Arquitetural:
    # A partir deste ponto, o processo normativo obriga o seu sistema 
    # a realizar uma conexão com a URL ('uss_base_url') do competidor 
    # para resolver as prioridades e ajustar detalhes da restrição tática.
```
