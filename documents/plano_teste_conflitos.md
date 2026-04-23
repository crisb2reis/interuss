# Plano de Teste: Detecção de Conflitos com OIRs Sobrepostas

## Objetivo
Criar cenários de teste que gerem conflitos intencionais ao submeter OIRs com coordenadas sobrepostas, validando a detecção de conflitos do DSS e a recuperação dos IDs das USS conflitantes.

---

## Conceitos de Sobreposição

### Tipos de Conflito
1. **Sobreposição Espacial Total** - Área completamente dentro de outra
2. **Sobreposição Espacial Parcial** - Áreas que se cruzam
3. **Sobreposição Temporal Total** - Mesmo período de tempo
4. **Sobreposição Temporal Parcial** - Períodos que se cruzam
5. **Sobreposição Vertical** - Mesma altitude ou faixas que se cruzam
6. **Sobreposição 4D Completa** - Espaço + Tempo + Altitude

---

## Área de Referência Base (São Paulo - Região Central)

### OIR Base (Primeira Operação)
```python
BASE_OIR = {
    "id": "oir-base-001",
    "area": {
        "vertices": [
            {"lat": -23.5505, "lng": -46.6333},  # Ponto Noroeste
            {"lat": -23.5505, "lng": -46.6233},  # Ponto Nordeste
            {"lat": -23.5605, "lng": -46.6233},  # Ponto Sudeste
            {"lat": -23.5605, "lng": -46.6333}   # Ponto Sudoeste
        ]
    },
    "altitude": {
        "lower": 50,   # metros
        "upper": 100   # metros
    },
    "time": {
        "start": "2024-06-15T14:00:00Z",
        "end": "2024-06-15T16:00:00Z"
    },
    "uss_base_url": "https://uss-alpha.example.com"
}
```

**Características:**
- Área: ~1.1 km² (aproximadamente 1000m x 1100m)
- Altitude: 50m - 100m AGL
- Duração: 2 horas (14:00 - 16:00)
- Localização: Centro de São Paulo (Av. Paulista região)

---

## Cenário 1: Sobreposição Espacial Total (Mesma Área)

### Descrição
Segunda USS tenta operar na **mesma área exata** com horários e altitudes sobrepostos.

### OIR Conflitante 1A - Sobreposição 100%
```python
CONFLICT_1A_TOTAL_OVERLAP = {
    "id": "oir-conflict-1a",
    "area": {
        "vertices": [
            {"lat": -23.5505, "lng": -46.6333},  # IDÊNTICO à base
            {"lat": -23.5505, "lng": -46.6233},
            {"lat": -23.5605, "lng": -46.6233},
            {"lat": -23.5605, "lng": -46.6333}
        ]
    },
    "altitude": {
        "lower": 60,   # Sobrepõe 60-100m
        "upper": 110   # Estende para 110m
    },
    "time": {
        "start": "2024-06-15T14:30:00Z",  # Começa 30min depois
        "end": "2024-06-15T17:00:00Z"     # Termina 1h depois
    },
    "uss_base_url": "https://uss-beta.example.com"
}
```

**Resultado Esperado:**
- ✅ Conflito detectado
- 📍 Sobreposição espacial: 100%
- ⏱️ Sobreposição temporal: 1h30min (14:30-16:00)
- 📏 Sobreposição vertical: 40m (60-100m)

---

## Cenário 2: Sobreposição Espacial Parcial (Interseção)

### OIR Conflitante 2A - Interseção 50% (Leste)
```python
CONFLICT_2A_PARTIAL_EAST = {
    "id": "oir-conflict-2a",
    "area": {
        "vertices": [
            {"lat": -23.5505, "lng": -46.6283},  # Deslocado 500m leste
            {"lat": -23.5505, "lng": -46.6183},
            {"lat": -23.5605, "lng": -46.6183},
            {"lat": -23.5605, "lng": -46.6283}
        ]
    },
    "altitude": {
        "lower": 50,
        "upper": 100
    },
    "time": {
        "start": "2024-06-15T14:00:00Z",  # Horário idêntico
        "end": "2024-06-15T16:00:00Z"
    },
    "uss_base_url": "https://uss-gamma.example.com"
}
```

**Resultado Esperado:**
- ✅ Conflito detectado
- 📍 Sobreposição espacial: ~50% (metade leste da área base)
- ⏱️ Sobreposição temporal: 100%
- 📏 Sobreposição vertical: 100%

### OIR Conflitante 2B - Interseção 25% (Canto Nordeste)
```python
CONFLICT_2B_CORNER_NE = {
    "id": "oir-conflict-2b",
    "area": {
        "vertices": [
            {"lat": -23.5455, "lng": -46.6283},  # Desloca norte e leste
            {"lat": -23.5455, "lng": -46.6183},
            {"lat": -23.5555, "lng": -46.6183},
            {"lat": -23.5555, "lng": -46.6283}
        ]
    },
    "altitude": {
        "lower": 75,   # Sobrepõe apenas 75-100m
        "upper": 120
    },
    "time": {
        "start": "2024-06-15T15:00:00Z",  # Sobrepõe última hora
        "end": "2024-06-15T17:00:00Z"
    },
    "uss_base_url": "https://uss-delta.example.com"
}
```

**Resultado Esperado:**
- ✅ Conflito detectado
- 📍 Sobreposição espacial: ~25% (canto nordeste)
- ⏱️ Sobreposição temporal: 1h (15:00-16:00)
- 📏 Sobreposição vertical: 25m (75-100m)

---

## Cenário 3: Sobreposição Temporal Apenas (Áreas Diferentes)

### OIR Não-Conflitante 3A - Área Adjacente (Sul)
```python
NO_CONFLICT_3A_ADJACENT_SOUTH = {
    "id": "oir-no-conflict-3a",
    "area": {
        "vertices": [
            {"lat": -23.5605, "lng": -46.6333},  # Começa onde base termina
            {"lat": -23.5605, "lng": -46.6233},
            {"lat": -23.5705, "lng": -46.6233},
            {"lat": -23.5705, "lng": -46.6333}
        ]
    },
    "altitude": {
        "lower": 50,
        "upper": 100
    },
    "time": {
        "start": "2024-06-15T14:00:00Z",  # Mesmo horário
        "end": "2024-06-15T16:00:00Z"
    },
    "uss_base_url": "https://uss-epsilon.example.com"
}
```

**Resultado Esperado:**
- ❌ SEM conflito (áreas adjacentes, não sobrepostas)
- 📍 Sobreposição espacial: 0% (fronteira compartilhada apenas)
- ⏱️ Sobreposição temporal: 100%
- 📏 Sobreposição vertical: 100%

---

## Cenário 4: Sobreposição Vertical Apenas (Diferentes Altitudes)

### OIR Não-Conflitante 4A - Mesma Área, Altitude Superior
```python
NO_CONFLICT_4A_ALTITUDE_ABOVE = {
    "id": "oir-no-conflict-4a",
    "area": {
        "vertices": [
            {"lat": -23.5505, "lng": -46.6333},  # Mesma área
            {"lat": -23.5505, "lng": -46.6233},
            {"lat": -23.5605, "lng": -46.6233},
            {"lat": -23.5605, "lng": -46.6333}
        ]
    },
    "altitude": {
        "lower": 100,  # Começa onde base termina
        "upper": 150
    },
    "time": {
        "start": "2024-06-15T14:00:00Z",
        "end": "2024-06-15T16:00:00Z"
    },
    "uss_base_url": "https://uss-zeta.example.com"
}
```

**Resultado Esperado:**
- ❌ SEM conflito (altitudes separadas)
- 📍 Sobreposição espacial: 100%
- ⏱️ Sobreposição temporal: 100%
- 📏 Sobreposição vertical: 0% (camadas separadas)

### OIR Conflitante 4B - Mesma Área, Altitude Sobreposta
```python
CONFLICT_4B_ALTITUDE_OVERLAP = {
    "id": "oir-conflict-4b",
    "area": {
        "vertices": [
            {"lat": -23.5505, "lng": -46.6333},  # Mesma área
            {"lat": -23.5505, "lng": -46.6233},
            {"lat": -23.5605, "lng": -46.6233},
            {"lat": -23.5605, "lng": -46.6333}
        ]
    },
    "altitude": {
        "lower": 90,   # Sobrepõe 90-100m da base
        "upper": 140
    },
    "time": {
        "start": "2024-06-15T14:00:00Z",
        "end": "2024-06-15T16:00:00Z"
    },
    "uss_base_url": "https://uss-eta.example.com"
}
```

**Resultado Esperado:**
- ✅ Conflito detectado
- 📍 Sobreposição espacial: 100%
- ⏱️ Sobreposição temporal: 100%
- 📏 Sobreposição vertical: 10m (90-100m)

---

## Cenário 5: Múltiplos Conflitos Simultâneos

### Teste de Stress - 3 USS Conflitantes
```python
MULTI_CONFLICT_SCENARIO = [
    {
        "id": "oir-multi-1",
        "area": {
            "vertices": [
                {"lat": -23.5505, "lng": -46.6333},
                {"lat": -23.5505, "lng": -46.6233},
                {"lat": -23.5605, "lng": -46.6233},
                {"lat": -23.5605, "lng": -46.6333}
            ]
        },
        "altitude": {"lower": 50, "upper": 75},
        "time": {
            "start": "2024-06-15T14:00:00Z",
            "end": "2024-06-15T15:00:00Z"
        },
        "uss_base_url": "https://uss-theta.example.com"
    },
    {
        "id": "oir-multi-2",
        "area": {
            "vertices": [
                {"lat": -23.5505, "lng": -46.6333},
                {"lat": -23.5505, "lng": -46.6233},
                {"lat": -23.5605, "lng": -46.6233},
                {"lat": -23.5605, "lng": -46.6333}
            ]
        },
        "altitude": {"lower": 70, "upper": 95},  # Sobrepõe theta 70-75m
        "time": {
            "start": "2024-06-15T14:30:00Z",     # Sobrepõe theta 14:30-15:00
            "end": "2024-06-15T16:00:00Z"
        },
        "uss_base_url": "https://uss-iota.example.com"
    },
    {
        "id": "oir-multi-3",
        "area": {
            "vertices": [
                {"lat": -23.5555, "lng": -46.6283},  # Sobrepõe parcialmente
                {"lat": -23.5555, "lng": -46.6183},
                {"lat": -23.5655, "lng": -46.6183},
                {"lat": -23.5655, "lng": -46.6283}
            ]
        },
        "altitude": {"lower": 50, "upper": 100},
        "time": {
            "start": "2024-06-15T14:00:00Z",
            "end": "2024-06-15T16:00:00Z"
        },
        "uss_base_url": "https://uss-kappa.example.com"
    }
]
```

**Resultado Esperado:**
- ✅ 3 conflitos detectados ao submeter nova OIR na mesma área/tempo
- 📋 Lista retornada deve conter IDs: `oir-multi-1`, `oir-multi-2`, `oir-multi-3`

---

## Cenário 6: Casos Extremos (Edge Cases)

### 6A - Toque de Fronteira (Sem Sobreposição)
```python
EDGE_6A_BOUNDARY_TOUCH = {
    "id": "oir-edge-6a",
    "area": {
        "vertices": [
            {"lat": -23.5505, "lng": -46.6233},  # Lat idêntica à fronteira leste
            {"lat": -23.5505, "lng": -46.6133},
            {"lat": -23.5605, "lng": -46.6133},
            {"lat": -23.5605, "lng": -46.6233}
        ]
    },
    "altitude": {"lower": 50, "upper": 100},
    "time": {
        "start": "2024-06-15T14:00:00Z",
        "end": "2024-06-15T16:00:00Z"
    },
    "uss_base_url": "https://uss-lambda.example.com"
}
```

**Resultado Esperado:**
- ❌ SEM conflito (depende da implementação do DSS)
- 📝 Nota: Alguns DSS consideram toque de fronteira como não-conflito

### 6B - Ponto Interno (Vértice Compartilhado)
```python
EDGE_6B_VERTEX_SHARED = {
    "id": "oir-edge-6b",
    "area": {
        "vertices": [
            {"lat": -23.5605, "lng": -46.6333},  # Vértice sudoeste da base
            {"lat": -23.5605, "lng": -46.6233},
            {"lat": -23.5705, "lng": -46.6233},
            {"lat": -23.5705, "lng": -46.6333}
        ]
    },
    "altitude": {"lower": 50, "upper": 100},
    "time": {
        "start": "2024-06-15T14:00:00Z",
        "end": "2024-06-15T16:00:00Z"
    },
    "uss_base_url": "https://uss-mu.example.com"
}
```

**Resultado Esperado:**
- ❌ SEM conflito (compartilham apenas 1 vértice)

### 6C - Área Envolvente (Contém a Base Completamente)
```python
EDGE_6C_ENCOMPASSING = {
    "id": "oir-edge-6c",
    "area": {
        "vertices": [
            {"lat": -23.5455, "lng": -46.6383},  # Engloba completamente a base
            {"lat": -23.5455, "lng": -46.6183},
            {"lat": -23.5655, "lng": -46.6183},
            {"lat": -23.5655, "lng": -46.6383}
        ]
    },
    "altitude": {"lower": 40, "upper": 110},  # Engloba verticalmente
    "time": {
        "start": "2024-06-15T13:00:00Z",      # Engloba temporalmente
        "end": "2024-06-15T17:00:00Z"
    },
    "uss_base_url": "https://uss-nu.example.com"
}
```

**Resultado Esperado:**
- ✅ Conflito detectado
- 📍 Sobreposição espacial: 100% (base completamente dentro)
- ⏱️ Sobreposição temporal: 100%
- 📏 Sobreposição vertical: 100%

---

## Implementação de Teste em Python

### Script de Teste Completo
```python
import uuid
from datetime import datetime, timedelta
from apps.dss_client.client import DSSClient
from apps.dss_client.exceptions import DSSConflictError

class ConflictTestRunner:
    """
    Executor de testes de conflito para validação do DSS
    """
    
    def __init__(self):
        self.client = DSSClient(
            intended_audience="dss.sandbox.br-utm.org",
            scope="utm.strategic_coordination"
        )
        self.test_results = []
    
    def create_extents(self, vertices, altitude_lower, altitude_upper, 
                       time_start, time_end):
        """
        Helper para criar extents no formato ASTM
        """
        return {
            "volume": {
                "outline_polygon": {
                    "vertices": vertices
                },
                "altitude_lower": {
                    "value": altitude_lower,
                    "reference": "W84",
                    "units": "M"
                },
                "altitude_upper": {
                    "value": altitude_upper,
                    "reference": "W84",
                    "units": "M"
                }
            },
            "time_start": {
                "value": time_start,
                "format": "RFC3339"
            },
            "time_end": {
                "value": time_end,
                "format": "RFC3339"
            }
        }
    
    def submit_base_oir(self):
        """
        Submete a OIR base (primeira operação)
        """
        print("\n" + "="*80)
        print("📍 SUBMETENDO OIR BASE")
        print("="*80)
        
        base_vertices = [
            {"lat": -23.5505, "lng": -46.6333},
            {"lat": -23.5505, "lng": -46.6233},
            {"lat": -23.5605, "lng": -46.6233},
            {"lat": -23.5605, "lng": -46.6333}
        ]
        
        base_extents = self.create_extents(
            vertices=base_vertices,
            altitude_lower=50,
            altitude_upper=100,
            time_start="2024-06-15T14:00:00Z",
            time_end="2024-06-15T16:00:00Z"
        )
        
        base_id = str(uuid.uuid4())
        
        try:
            result = self.client.submit_operational_intent_reference(
                oir_id=base_id,
                extents=base_extents,
                uss_base_url="https://uss-alpha.example.com",
                state="Accepted"
            )
            
            print(f"✅ OIR Base criada: {base_id}")
            print(f"   USS: https://uss-alpha.example.com")
            print(f"   Área: Centro SP (~1.1km²)")
            print(f"   Altitude: 50-100m")
            print(f"   Tempo: 14:00-16:00 UTC")
            
            return base_id, result
            
        except Exception as e:
            print(f"❌ Erro ao criar OIR base: {e}")
            return None, None
    
    def test_scenario_1_total_overlap(self):
        """
        Cenário 1: Sobreposição espacial total
        """
        print("\n" + "="*80)
        print("🧪 CENÁRIO 1: Sobreposição Espacial Total (100%)")
        print("="*80)
        
        vertices = [
            {"lat": -23.5505, "lng": -46.6333},  # IDÊNTICO
            {"lat": -23.5505, "lng": -46.6233},
            {"lat": -23.5605, "lng": -46.6233},
            {"lat": -23.5605, "lng": -46.6333}
        ]
        
        extents = self.create_extents(
            vertices=vertices,
            altitude_lower=60,
            altitude_upper=110,
            time_start="2024-06-15T14:30:00Z",
            time_end="2024-06-15T17:00:00Z"
        )
        
        return self._execute_test(
            scenario_name="1A - Total Overlap",
            extents=extents,
            uss_url="https://uss-beta.example.com",
            expected_conflict=True
        )
    
    def test_scenario_2_partial_east(self):
        """
        Cenário 2A: Sobreposição parcial (50% leste)
        """
        print("\n" + "="*80)
        print("🧪 CENÁRIO 2A: Sobreposição Parcial Leste (50%)")
        print("="*80)
        
        vertices = [
            {"lat": -23.5505, "lng": -46.6283},  # Deslocado leste
            {"lat": -23.5505, "lng": -46.6183},
            {"lat": -23.5605, "lng": -46.6183},
            {"lat": -23.5605, "lng": -46.6283}
        ]
        
        extents = self.create_extents(
            vertices=vertices,
            altitude_lower=50,
            altitude_upper=100,
            time_start="2024-06-15T14:00:00Z",
            time_end="2024-06-15T16:00:00Z"
        )
        
        return self._execute_test(
            scenario_name="2A - Partial East",
            extents=extents,
            uss_url="https://uss-gamma.example.com",
            expected_conflict=True
        )
    
    def test_scenario_2_corner_ne(self):
        """
        Cenário 2B: Sobreposição canto nordeste (25%)
        """
        print("\n" + "="*80)
        print("🧪 CENÁRIO 2B: Sobreposição Canto Nordeste (25%)")
        print("="*80)
        
        vertices = [
            {"lat": -23.5455, "lng": -46.6283},
            {"lat": -23.5455, "lng": -46.6183},
            {"lat": -23.5555, "lng": -46.6183},
            {"lat": -23.5555, "lng": -46.6283}
        ]
        
        extents = self.create_extents(
            vertices=vertices,
            altitude_lower=75,
            altitude_upper=120,
            time_start="2024-06-15T15:00:00Z",
            time_end="2024-06-15T17:00:00Z"
        )
        
        return self._execute_test(
            scenario_name="2B - Corner NE",
            extents=extents,
            uss_url="https://uss-delta.example.com",
            expected_conflict=True
        )
    
    def test_scenario_3_adjacent_south(self):
        """
        Cenário 3A: Área adjacente (SEM conflito esperado)
        """
        print("\n" + "="*80)
        print("🧪 CENÁRIO 3A: Área Adjacente Sul (SEM Conflito)")
        print("="*80)
        
        vertices = [
            {"lat": -23.5605, "lng": -46.6333},  # Sul da base
            {"lat": -23.5605, "lng": -46.6233},
            {"lat": -23.5705, "lng": -46.6233},
            {"lat": -23.5705, "lng": -46.6333}
        ]
        
        extents = self.create_extents(
            vertices=vertices,
            altitude_lower=50,
            altitude_upper=100,
            time_start="2024-06-15T14:00:00Z",
            time_end="2024-06-15T16:00:00Z"
        )
        
        return self._execute_test(
            scenario_name="3A - Adjacent South",
            extents=extents,
            uss_url="https://uss-epsilon.example.com",
            expected_conflict=False
        )
    
    def test_scenario_4_altitude_above(self):
        """
        Cenário 4A: Mesma área, altitude superior (SEM conflito)
        """
        print("\n" + "="*80)
        print("🧪 CENÁRIO 4A: Altitude Superior (SEM Conflito)")
        print("="*80)
        
        vertices = [
            {"lat": -23.5505, "lng": -46.6333},  # Mesma área
            {"lat": -23.5505, "lng": -46.6233},
            {"lat": -23.5605, "lng": -46.6233},
            {"lat": -23.5605, "lng": -46.6333}
        ]
        
        extents = self.create_extents(
            vertices=vertices,
            altitude_lower=100,  # Acima da base
            altitude_upper=150,
            time_start="2024-06-15T14:00:00Z",
            time_end="2024-06-15T16:00:00Z"
        )
        
        return self._execute_test(
            scenario_name="4A - Altitude Above",
            extents=extents,
            uss_url="https://uss-zeta.example.com",
            expected_conflict=False
        )
    
    def test_scenario_4_altitude_overlap(self):
        """
        Cenário 4B: Mesma área, altitude sobreposta
        """
        print("\n" + "="*80)
        print("🧪 CENÁRIO 4B: Altitude Sobreposta")
        print("="*80)
        
        vertices = [
            {"lat": -23.5505, "lng": -46.6333},
            {"lat": -23.5505, "lng": -46.6233},
            {"lat": -23.5605, "lng": -46.6233},
            {"lat": -23.5605, "lng": -46.6333}
        ]
        
        extents = self.create_extents(
            vertices=vertices,
            altitude_lower=90,   # Sobrepõe 90-100m
            altitude_upper=140,
            time_start="2024-06-15T14:00:00Z",
            time_end="2024-06-15T16:00:00Z"
        )
        
        return self._execute_test(
            scenario_name="4B - Altitude Overlap",
            extents=extents,
            uss_url="https://uss-eta.example.com",
            expected_conflict=True
        )
    
    def test_scenario_6_encompassing(self):
        """
        Cenário 6C: Área envolvente (contém base completamente)
        """
        print("\n" + "="*80)
        print("🧪 CENÁRIO 6C: Área Envolvente (Contém Base)")
        print("="*80)
        
        vertices = [
            {"lat": -23.5455, "lng": -46.6383},  # Maior que base
            {"lat": -23.5455, "lng": -46.6183},
            {"lat": -23.5655, "lng": -46.6183},
            {"lat": -23.5655, "lng": -46.6383}
        ]
        
        extents = self.create_extents(
            vertices=vertices,
            altitude_lower=40,
            altitude_upper=110,
            time_start="2024-06-15T13:00:00Z",
            time_end="2024-06-15T17:00:00Z"
        )
        
        return self._execute_test(
            scenario_name="6C - Encompassing",
            extents=extents,
            uss_url="https://uss-nu.example.com",
            expected_conflict=True
        )
    
    def _execute_test(self, scenario_name, extents, uss_url, expected_conflict):
        """
        Executa um teste individual e registra resultados
        """
        test_id = str(uuid.uuid4())
        
        try:
            result = self.client.submit_operational_intent_reference(
                oir_id=test_id,
                extents=extents,
                uss_base_url=uss_url,
                state="Accepted"
            )
            
            conflicts = result.get('conflicting_oirs', [])
            has_conflict = len(conflicts) > 0
            
            # Validar expectativa
            test_passed = (has_conflict == expected_conflict)
            
            # Registrar resultado
            test_result = {
                "scenario": scenario_name,
                "oir_id": test_id,
                "expected_conflict": expected_conflict,
                "actual_conflict": has_conflict,
                "conflict_count": len(conflicts),
                "conflicting_uss_ids": [c.get('id') for c in conflicts],
                "conflicting_uss_urls": [c.get('uss_base_url') for c in conflicts],
                "passed": test_passed
            }
            
            self.test_results.append(test_result)
            
            # Print resultado
            status = "✅ PASSOU" if test_passed else "❌ FALHOU"
            print(f"\n{status}")
            print(f"   OIR ID: {test_id}")
            print(f"   USS: {uss_url}")
            print(f"   Conflito Esperado: {expected_conflict}")
            print(f"   Conflito Detectado: {has_conflict}")
            
            if has_conflict:
                print(f"\n   🔴 CONFLITOS DETECTADOS ({len(conflicts)}):")
                for i, conflict in enumerate(conflicts, 1):
                    print(f"      {i}. ID: {conflict.get('id')}")
                    print(f"         USS: {conflict.get('uss_base_url')}")
                    print(f"         Estado: {conflict.get('state')}")
            
            return test_result
            
        except DSSConflictError as e:
            print(f"   ⚠️  Erro de conflito (409): {e}")
            print(f"   Referências conflitantes: {e.conflicting_references}")
            
            test_result = {
                "scenario": scenario_name,
                "oir_id": test_id,
                "expected_conflict": expected_conflict,
                "actual_conflict": True,
                "conflict_count": len(e.conflicting_references),
                "error": str(e),
                "passed": expected_conflict  # Se esperávamos conflito, 409 é sucesso
            }
            
            self.test_results.append(test_result)
            return test_result
            
        except Exception as e:
            print(f"   ❌ Erro inesperado: {e}")
            
            test_result = {
                "scenario": scenario_name,
                "oir_id": test_id,
                "expected_conflict": expected_conflict,
                "error": str(e),
                "passed": False
            }
            
            self.test_results.append(test_result)
            return test_result
    
    def run_all_tests(self):
        """
        Executa toda a suíte de testes
        """
        print("\n" + "="*80)
        print("🚀 INICIANDO SUÍTE DE TESTES DE CONFLITO DSS")
        print("="*80)
        
        # 1. Criar OIR base
        base_id, base_result = self.submit_base_oir()
        
        if not base_id:
            print("\n❌ Falha ao criar OIR base. Abortando testes.")
            return
        
        # 2. Executar cenários de teste
        self.test_scenario_1_total_overlap()
        self.test_scenario_2_partial_east()
        self.test_scenario_2_corner_ne()
        self.test_scenario_3_adjacent_south()
        self.test_scenario_4_altitude_above()
        self.test_scenario_4_altitude_overlap()
        self.test_scenario_6_encompassing()
        
        # 3. Relatório final
        self.print_summary()
    
    def print_summary(self):
        """
        Imprime resumo dos testes
        """
        print("\n" + "="*80)
        print("📊 RESUMO DOS TESTES")
        print("="*80)
        
        total = len(self.test_results)
        passed = sum(1 for t in self.test_results if t.get('passed', False))
        failed = total - passed
        
        print(f"\nTotal de Testes: {total}")
        print(f"✅ Passou: {passed}")
        print(f"❌ Falhou: {failed}")
        print(f"Taxa de Sucesso: {(passed/total*100):.1f}%")
        
        print("\n📋 DETALHES POR CENÁRIO:")
        print("-" * 80)
        
        for test in self.test_results:
            status = "✅" if test.get('passed') else "❌"
            scenario = test.get('scenario', 'N/A')
            conflict_count = test.get('conflict_count', 0)
            
            print(f"\n{status} {scenario}")
            print(f"   Conflitos: {conflict_count}")
            
            if test.get('conflicting_uss_ids'):
                print(f"   USS IDs Conflitantes:")
                for uss_id in test['conflicting_uss_ids']:
                    print(f"      - {uss_id}")


# Executar testes
if __name__ == "__main__":
    runner = ConflictTestRunner()
    runner.run_all_tests()
```

---

## Execução dos Testes

### Via Django Shell
```bash
python manage.py shell
```

```python
from apps.dss_client.tests.conflict_tests import ConflictTestRunner

runner = ConflictTestRunner()
runner.run_all_tests()
```

### Via Script Python
```bash
python apps/dss_client/tests/run_conflict_tests.py
```

---

## Estrutura de Resposta Esperada do DSS

### Resposta com Conflitos
```json
{
  "operational_intent_reference": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "manager": "https://uss-beta.example.com",
    "uss_availability": "Unknown",
    "version": 1,
    "state": "Accepted",
    "ovn": "abc123def456",
    "time_start": {"value": "2024-06-15T14:30:00Z"},
    "time_end": {"value": "2024-06-15T17:00:00Z"},
    "uss_base_url": "https://uss-beta.example.com"
  },
  "subscribers": [
    {
      "uss_base_url": "https://uss-alpha.example.com",
      "subscriptions": [
        {
          "subscription_id": "sub-12345",
          "notification_index": 0
        }
      ]
    }
  ],
  "operational_intent_references": [
    {
      "id": "oir-base-001",
      "manager": "https://uss-alpha.example.com",
      "uss_availability": "Unknown",
      "version": 1,
      "state": "Accepted",
      "ovn": "xyz789ghi012",
      "time_start": {"value": "2024-06-15T14:00:00Z"},
      "time_end": {"value": "2024-06-15T16:00:00Z"},
      "uss_base_url": "https://uss-alpha.example.com"
    }
  ]
}
```

### Extração de IDs das USS Conflitantes
```python
# Do resultado acima:
conflicting_oirs = response.get('operational_intent_references', [])

for oir in conflicting_oirs:
    print(f"USS Conflitante:")
    print(f"  ID da OIR: {oir['id']}")
    print(f"  URL da USS: {oir['uss_base_url']}")
    print(f"  Estado: {oir['state']}")
    print(f"  OVN: {oir['ovn']}")
```

---

## Matriz de Testes Esperados

| Cenário | Sobreposição Espacial | Sobreposição Temporal | Sobreposição Vertical | Conflito? |
|---------|----------------------|----------------------|----------------------|-----------|
| 1A - Total | 100% | Parcial (1h30) | Parcial (40m) | ✅ SIM |
| 2A - Parcial Leste | 50% | 100% | 100% | ✅ SIM |
| 2B - Canto NE | 25% | Parcial (1h) | Parcial (25m) | ✅ SIM |
| 3A - Adjacente Sul | 0% (adjacente) | 100% | 100% | ❌ NÃO |
| 4A - Altitude Acima | 100% | 100% | 0% (separado) | ❌ NÃO |
| 4B - Altitude Sobreposta | 100% | 100% | Parcial (10m) | ✅ SIM |
| 6C - Envolvente | 100% (contida) | 100% | 100% | ✅ SIM |

---

## Checklist de Validação

- [ ] OIR base submetida com sucesso
- [ ] Cenário 1A detecta conflito (sobreposição total)
- [ ] Cenário 2A detecta conflito (sobreposição parcial 50%)
- [ ] Cenário 2B detecta conflito (sobreposição canto 25%)
- [ ] Cenário 3A NÃO detecta conflito (áreas adjacentes)
- [ ] Cenário 4A NÃO detecta conflito (altitudes separadas)
- [ ] Cenário 4B detecta conflito (altitudes sobrepostas)
- [ ] Cenário 6C detecta conflito (área envolvente)
- [ ] IDs das USS conflitantes são retornados corretamente
- [ ] URLs das USS conflitantes são retornados
- [ ] OVN (versão) de cada OIR está presente
- [ ] Estados das OIRs conflitantes são retornados

---

## Notas Importantes

### Comportamento do DSS
1. **Detecção 4D**: O DSS deve detectar sobreposição em todas as 4 dimensões (lat, lng, altitude, tempo)
2. **Retorno de Vizinhos**: Mesmo sem conflito estrito, o DSS pode retornar OIRs "próximas"
3. **OVN para Versionamento**: Sempre obtenha o OVN atual antes de atualizar uma OIR

### Coordenação Estratégica
Ao receber conflitos:
1. Contactar as USS retornadas via `uss_base_url`
2. Negociar alterações de tempo/espaço/altitude
3. Re-submeter com parâmetros ajustados
4. Usar `key` com OVNs conhecidos para sincronização

### Debugging
Se um teste falhar:
```python
# Verificar OIR no DSS
oir_details = client.get_operational_intent_reference(oir_id)
print(json.dumps(oir_details, indent=2))

# Consultar área
area = {...}  # área de teste
constraints = client.query_constraints_with_area(area)
print(f"OIRs na área: {len(constraints.get('constraints', []))}")
```
