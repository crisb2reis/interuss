# Guia Prático de Uso do DSSClient

## 1. Inicialização Básica

### Opção 1: Com Autenticação Automática (Recomendado)
```python
from apps.dss_client.client import DSSClient

client = DSSClient(
    intended_audience="dss.sandbox.br-utm.org",
    scope="utm.strategic_coordination",
    auto_authenticate=True
)
```

### Opção 2: Com Token Pré-existente
```python
client = DSSClient(
    base_url="https://dss.sandbox.br-utm.org/dss",
    token="eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
    auto_authenticate=False
)
```

### Opção 3: Autenticação Manual
```python
from apps.dss_client.auth import ICEAAuthenticator

authenticator = ICEAAuthenticator()
token = authenticator.get_token(
    intended_audience="dss.sandbox.br-utm.org",
    scope="utm.strategic_coordination"
)

client = DSSClient(token=token)
```

---

## 2. Consulta de Constraints

### 2.1 Query Simples (GET)
```python
try:
    response = client.query_constraints()
    print(f"Constraints encontradas: {len(response.get('constraints', []))}")
    
    for constraint in response.get('constraints', []):
        print(f"- ID: {constraint['id']}")
        print(f"  Tipo: {constraint.get('type', 'N/A')}")
        
except Exception as e:
    print(f"Erro: {e}")
```

### 2.2 Query com Área (POST)
```python
from apps.dss_client.exceptions import DSSValidationError

# Definir área de interesse
area = {
    "volume": {
        "outline_polygon": {
            "vertices": [
                {"lat": -23.5505, "lng": -46.6333},  # São Paulo
                {"lat": -23.5505, "lng": -46.5333},
                {"lat": -23.4505, "lng": -46.5333},
                {"lat": -23.4505, "lng": -46.6333}
            ]
        },
        "altitude_lower": {
            "value": 0,
            "reference": "W84",
            "units": "M"
        },
        "altitude_upper": {
            "value": 120,
            "reference": "W84",
            "units": "M"
        }
    },
    "time_start": {
        "value": "2024-06-01T10:00:00Z",
        "format": "RFC3339"
    },
    "time_end": {
        "value": "2024-06-01T12:00:00Z",
        "format": "RFC3339"
    }
}

try:
    response = client.query_constraints_with_area(area)
    
    constraints = response.get('constraints', [])
    print(f"Constraints na área: {len(constraints)}")
    
    for constraint in constraints:
        print(f"\nConstraint ID: {constraint['id']}")
        print(f"USS: {constraint.get('uss_base_url', 'N/A')}")
        
except DSSValidationError as e:
    print(f"Validação falhou: {e}")
except Exception as e:
    print(f"Erro: {e}")
```

---

## 3. Operational Intent References (OIR)

### 3.1 Submeter Nova OIR (Sem Conflito Esperado)
```python
import uuid
from apps.dss_client.exceptions import DSSConflictError

# Gerar ID único para a OIR
oir_id = str(uuid.uuid4())

# Definir extensões espaciais e temporais
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
        "altitude_lower": {"value": 30, "units": "M", "reference": "W84"},
        "altitude_upper": {"value": 100, "units": "M", "reference": "W84"}
    },
    "time_start": {"value": "2024-06-01T14:00:00Z", "format": "RFC3339"},
    "time_end": {"value": "2024-06-01T15:00:00Z", "format": "RFC3339"}
}

try:
    result = client.submit_operational_intent_reference(
        oir_id=oir_id,
        extents=extents,
        uss_base_url="https://uss.minha-empresa.com",
        state="Accepted"
    )
    
    # Verificar se há conflitos
    conflicting = result.get('conflicting_oirs', [])
    
    if not conflicting:
        print("✓ OIR criada com sucesso, sem conflitos!")
        print(f"  ID: {result['operational_intent_reference']['id']}")
        print(f"  Estado: {result['operational_intent_reference']['state']}")
    else:
        print(f"⚠ OIR criada, mas há {len(conflicting)} conflito(s):")
        for oir in conflicting:
            print(f"  - ID: {oir['id']}")
            print(f"    USS: {oir.get('uss_base_url', 'N/A')}")
            print(f"    Estado: {oir.get('state', 'N/A')}")
    
    # Assinantes notificados
    subscribers = result.get('subscribers', [])
    if subscribers:
        print(f"\n{len(subscribers)} assinante(s) notificado(s)")
        
except DSSConflictError as e:
    print(f"✗ Conflito ao criar OIR: {e}")
    print(f"  OIRs conflitantes: {len(e.conflicting_references)}")
    for ref in e.conflicting_references:
        print(f"  - {ref.get('id', 'N/A')}")
        
except Exception as e:
    print(f"✗ Erro: {e}")
```

### 3.2 Atualizar OIR Existente (com Key)
```python
# Primeiro, obter a OIR atual para pegar a key
existing_oir = client.get_operational_intent_reference(oir_id)
current_key = [existing_oir['operational_intent_reference']['ovn']]

# Atualizar com novos extents
new_extents = {
    "volume": {
        "outline_polygon": {
            "vertices": [
                {"lat": -23.5505, "lng": -46.6333},
                {"lat": -23.5505, "lng": -46.6133},  # Área expandida
                {"lat": -23.5305, "lng": -46.6133},
                {"lat": -23.5305, "lng": -46.6333}
            ]
        },
        "altitude_lower": {"value": 30, "units": "M"},
        "altitude_upper": {"value": 120, "units": "M"}  # Altitude aumentada
    },
    "time_start": {"value": "2024-06-01T14:00:00Z"},
    "time_end": {"value": "2024-06-01T16:00:00Z"}  # Tempo estendido
}

try:
    result = client.submit_operational_intent_reference(
        oir_id=oir_id,
        extents=new_extents,
        uss_base_url="https://uss.minha-empresa.com",
        state="Activated",  # Mudança de estado
        key=current_key
    )
    
    print("✓ OIR atualizada com sucesso")
    
except DSSConflictError as e:
    print(f"✗ Conflito na atualização: {e}")
```

### 3.3 Consultar OIR Específica
```python
from apps.dss_client.exceptions import DSSNotFoundError

try:
    response = client.get_operational_intent_reference(oir_id)
    
    oir = response['operational_intent_reference']
    print(f"OIR: {oir['id']}")
    print(f"Estado: {oir['state']}")
    print(f"USS: {oir['uss_base_url']}")
    print(f"OVN (versão): {oir['ovn']}")
    
except DSSNotFoundError:
    print(f"OIR {oir_id} não encontrada")
```

### 3.4 Deletar OIR
```python
try:
    # Obter key atual
    existing = client.get_operational_intent_reference(oir_id)
    key = [existing['operational_intent_reference']['ovn']]
    
    # Deletar
    response = client.delete_operational_intent_reference(
        oir_id=oir_id,
        key=key
    )
    
    print(f"✓ OIR {oir_id} removida com sucesso")
    
except DSSNotFoundError:
    print(f"OIR {oir_id} já foi removida ou não existe")
```

---

## 4. Fluxo Completo: Detecção e Resolução de Conflitos

```python
import uuid
from datetime import datetime, timedelta

def submit_operation_with_conflict_detection():
    """
    Fluxo completo: submeter operação e detectar/resolver conflitos
    """
    client = DSSClient(
        intended_audience="dss.sandbox.br-utm.org",
        scope="utm.strategic_coordination"
    )
    
    # 1. Definir minha operação
    my_oir_id = str(uuid.uuid4())
    
    now = datetime.utcnow()
    start_time = now + timedelta(hours=1)
    end_time = start_time + timedelta(hours=2)
    
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
            "altitude_lower": {"value": 50, "units": "M"},
            "altitude_upper": {"value": 100, "units": "M"}
        },
        "time_start": {"value": start_time.isoformat() + "Z"},
        "time_end": {"value": end_time.isoformat() + "Z"}
    }
    
    # 2. Submeter ao DSS
    try:
        result = client.submit_operational_intent_reference(
            oir_id=my_oir_id,
            extents=my_extents,
            uss_base_url="https://uss.minha-empresa.com",
            state="Accepted"
        )
        
        # 3. Analisar conflitos
        conflicts = result.get('conflicting_oirs', [])
        
        if not conflicts:
            print("✓ Operação aceita sem conflitos")
            return {
                'success': True,
                'oir_id': my_oir_id,
                'conflicts': []
            }
        
        # 4. Processar conflitos encontrados
        print(f"⚠ Detectados {len(conflicts)} conflito(s)")
        
        conflict_details = []
        for conflict in conflicts:
            print(f"\n  Conflito com OIR: {conflict['id']}")
            print(f"    USS: {conflict.get('uss_base_url', 'N/A')}")
            print(f"    Estado: {conflict.get('state', 'N/A')}")
            
            # Obter detalhes completos do conflito
            try:
                full_conflict = client.get_operational_intent_reference(
                    conflict['id']
                )
                conflict_details.append(full_conflict)
            except Exception as e:
                print(f"    Erro ao obter detalhes: {e}")
        
        # 5. Decisão de coordenação estratégica
        print("\n📋 Ação requerida:")
        print("  1. Coordenar com USS conflitantes")
        print("  2. Ajustar tempo/espaço da operação")
        print("  3. Cancelar se não houver solução")
        
        return {
            'success': True,
            'oir_id': my_oir_id,
            'conflicts': conflict_details,
            'action_required': True
        }
        
    except DSSConflictError as e:
        print(f"✗ Conflito crítico ao submeter: {e}")
        return {
            'success': False,
            'error': str(e),
            'conflicting_references': e.conflicting_references
        }
    
    except Exception as e:
        print(f"✗ Erro inesperado: {e}")
        return {
            'success': False,
            'error': str(e)
        }

# Executar
result = submit_operation_with_conflict_detection()
print(f"\nResultado final: {result}")
```

---

## 5. Tratamento de Erros

### 5.1 Hierarquia de Exceções
```python
from apps.dss_client.exceptions import (
    DSSException,
    DSSConnectionError,
    DSSAuthenticationError,
    DSSAuthorizationError,
    DSSNotFoundError,
    DSSConflictError,
    DSSValidationError,
    DSSServerError
)

def robust_dss_operation():
    client = DSSClient(
        intended_audience="dss.sandbox.br-utm.org",
        scope="utm.strategic_coordination"
    )
    
    try:
        result = client.query_constraints()
        return result
        
    except DSSAuthenticationError as e:
        # Token inválido ou expirado (401)
        print(f"Erro de autenticação: {e}")
        # Solução: renovar token
        
    except DSSAuthorizationError as e:
        # Sem permissão (403)
        print(f"Acesso negado: {e}")
        # Solução: verificar scopes/permissões
        
    except DSSNotFoundError as e:
        # Recurso não encontrado (404)
        print(f"Não encontrado: {e}")
        # Solução: verificar ID/endpoint
        
    except DSSConflictError as e:
        # Conflito (409)
        print(f"Conflito: {e}")
        print(f"Referências conflitantes: {e.conflicting_references}")
        # Solução: resolver conflitos
        
    except DSSValidationError as e:
        # Dados inválidos (400)
        print(f"Validação falhou: {e}")
        # Solução: corrigir dados de entrada
        
    except DSSServerError as e:
        # Erro do servidor DSS (5xx)
        print(f"Erro do servidor: {e}")
        # Solução: tentar novamente mais tarde
        
    except DSSConnectionError as e:
        # Outros erros de conexão
        print(f"Erro de conexão: {e}")
        # Solução: verificar rede/URL
        
    except DSSException as e:
        # Exceção base - captura qualquer erro DSS
        print(f"Erro DSS genérico: {e}")
```

---

## 6. Uso no Django Shell

```python
# Abrir Django shell
python manage.py shell

# Importar cliente
from apps.dss_client.client import DSSClient

# Inicializar
client = DSSClient(
    intended_audience="dss.sandbox.br-utm.org",
    scope="utm.strategic_coordination"
)

# Testar constraints
constraints = client.query_constraints()
print(f"Total: {len(constraints.get('constraints', []))}")

# Testar com área
area = {
    "volume": {
        "outline_polygon": {
            "vertices": [
                {"lat": -23.5505, "lng": -46.6333},
                {"lat": -23.5505, "lng": -46.5333},
                {"lat": -23.4505, "lng": -46.5333},
                {"lat": -23.4505, "lng": -46.6333}
            ]
        },
        "altitude_lower": {"value": 0, "units": "M"},
        "altitude_upper": {"value": 120, "units": "M"}
    }
}

result = client.query_constraints_with_area(area)
```

---

## 7. Configuração Recomendada (settings.py)

```python
# DSS Client Configuration
DSS_BASE_URL = env('DSS_BASE_URL', default='https://dss.sandbox.br-utm.org/dss')
ICEA_AUTH_URL = env('ICEA_AUTH_URL', default='https://api.sandbox.br-utm.org/token')
ICEA_API_KEY = env('ICEA_API_KEY')

# Defaults para autenticação
DSS_DEFAULT_AUDIENCE = 'dss.sandbox.br-utm.org'
DSS_DEFAULT_SCOPE = 'utm.strategic_coordination'

# Cache (use Redis em produção)
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Logging
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'apps.dss_client': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

---

## 8. Variáveis de Ambiente (.env)

```bash
# DSS Configuration
DSS_BASE_URL=https://dss.sandbox.br-utm.org/dss
ICEA_AUTH_URL=https://api.sandbox.br-utm.org/token
ICEA_API_KEY=your-api-key-here

# Redis (produção)
REDIS_URL=redis://localhost:6379/1
```
