# Passo a Passo da Implementação do USS

Este documento registra as ações tomadas durante a execução do roteiro de trabalho estabelecido no arquivo `planoUSS.md`. Focamos em estruturar as fundações para que o USS esteja em compliance com as normas ASTM F3548-22 e seja integrável à suíte InterUSS.

## Fase 0: Setup Inicial do Projeto
1. **Configuração de Dependências (`requirements.txt`)**: Listagem de todas as bibliotecas solicitadas, incluindo os wrappers para banco geoespacial (`psycopg2-binary`) e tarefas em background (`celery`).
2. **Containerização (`Dockerfile` e `docker-compose.yml`)**: Arquivos de imagem base com as bibliotecas system-level necessárias do GDAL/GEOS e contêineres para banco de dados PostGIS e in-memory data store Redis.
3. **Iniciando o Projeto Django e os Apps**: Configuração das variáveis de ambiente com `django-environ` nos módulos de `config/settings/base.py`, `development.py` e `production.py`. Injeção do app principal, dos conectores com serviços externos e API InterUSS.

## Fase 1: Modelagem do Domínio
- Criados os modelos espaciais de `FlightPlan` associados ao PostGIS (`gis_models.GeometryField(dim=3, srid=4326)`) em `apps/flight_plans/models.py`. 
- Modelagem das Intenções Operacionais com uma relação unívoca de pertencimento com um `FlightPlan`. 

## Fase 2: API ASTM F3548 (Core)
- Criados o `FlightPlanSerializer` e `OperationalIntentSerializer` em `apps/flight_plans/serializers.py`.
- Definido o controller principal: `FlightPlanViewSet` em `apps/flight_plans/views.py`. E registro nas rotas `apps/flight_plans/urls.py` ligado a `config/urls.py`.

## Fase 3: Motor de Conflito
- Criação base da lógica do PostGIS (`ST_Intersects`) no script utilitário `apps/flight_plans/conflict_engine.py`, onde as interseções espaço-temporais serão computadas.

## Fase 4 e Fase 6: Cliente DSS e Sincronização
- Montado o driver HTTP básico em `apps/dss_client/client.py` usando `requests` e preparado para autenticar seguindo o modelo do ICEA. 

  **Fluxo de Autenticação:**
  Para obtenção do token no ICEA, o trâmite a ser efetuado é o seguinte:
  ```text
  USS -> AUTH: GET /token?aud=core-service
  AUTH -> USS: JWT Token
  ```
  O método implementado (`authenticate_icea`) repassará parâmetros como `intended_audience`, `scope` e `apikey` para capturar e utilizar este JWT nas requisições.

- Criada a infraestrutura do Celery em `apps/sync/tasks.py` para injetar os planos no DSS de forma assíncrona com `exponential backoff` em caso de instabilidade da rede ou DSS fora do ar.
- Adicionado arquivo mestre de configuração de `celery` em `config/celery.py`.
## Fase 5: Interface de Teste InterUSS
- Implementação inicial de endpoints em `apps/test_interface/views.py` (`InjectFlightView`, `ClearStateView`, `StatusView`) mapeados para suas respectivas rotas para garantir que seja possível simular voos durante os testes inter-subsistemas baseados nas features do InterUSS.

Toda a arquitetura proposta no plano agora se encontra materializada como código e arquivos, aguardando agora as etapas de migrações no banco e integração mais pesada nas lógicas de processamento e endpoints.

---

### Como Testar a Autenticação (via Shell)

Para validar a integração com o sandbox do BR-UTM e o funcionamento do carregamento das chaves via `.env`, siga estes passos:

1. **Ativar Ambiente e Dependências:**
   ```bash
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Acessar o Shell do Django:**
   ```bash
   python manage.py shell
   ```

3. **Executar o Teste:**
   ```python
   from apps.dss_client.client import DSSClient
   from django.conf import settings

   # Inicializa o cliente com os endpoints da sandbox definidos no .env
   dss = DSSClient(base_url=settings.DSS_BASE_URL, token="")

   try:
       # Obtém o token JWT usando a API Key carregada do .env
       token = dss.authenticate_icea(
           intended_audience="utm.decea.mil.br",
           scope="utm.strategic_coordination"
       )
       print("Autenticado com sucesso!")
       print(f"Token: {token[:50]}...")
   except Exception as e:
       print(f"Erro na autenticação: {e}")
   ```

4. **Consultar Constraints no DSS (após autenticação):**
   ```python
   # Continuando a sessão do shell — token já obtido no passo anterior.
   # Fluxo:
   #   USS -> AUTH: GET /token?aud=core-service
   #   AUTH -> USS: JWT Token
   #   USS -> DSS: POST /constraint/query (Authorization: Bearer <JWT>)
   #   DSS -> USS: [] (lista vazia — sandbox sem constraints cadastradas)
   try:
       constraints = dss.query_constraints()
       print(f"Constraints recebidas: {constraints}")  # Esperado: []
   except Exception as e:
       print(f"Erro ao consultar constraints: {e}")
   ```

5. **Submeter Operational Intent Reference (OIR) e Checar Conflitos:**
   ```python
   # Continuando a sessão do shell
   import uuid
   from datetime import datetime, timedelta

   # 1. Gerar um ID único para a intenção
   oir_id = str(uuid.uuid4())

   # 2. Definir a área e tempo da operação (extents)
   now = datetime.utcnow()
   my_extents = {
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

   # 3. Enviar para o DSS
   try:
       print(f"Submetendo OIR ID: {oir_id}")
       # Note: Passamos os extents no padrão ASTM definido no client
       result = dss.submit_operational_intent_reference(
           oir_id=oir_id,
           extents=my_extents,
           uss_base_url="https://uss.minha-empresa.com",
           state="Accepted"
       )
       
       # 4. Verificar se há conflitos retornados na lista
       conflicts = result.get('conflicting_oirs', [])
       if not conflicts:
           print("✓ Sucesso: OIR aceita sem conflitos de outras USS!")
       else:
           print(f"⚠ Conflito detectado com {len(conflicts)} intenção(ões) prévia(s):")
           for oir in conflicts:
               print(f"  - ID Conflitante: {oir['id']} (USS: {oir['uss_base_url']})")

   except Exception as e:
       print(f"Erro no fluxo de OIR: {e}")
   ```
