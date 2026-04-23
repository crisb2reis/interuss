# Plano de Ajuste: Endpoints ASTM F3548-22 — DSSClient

## Diagnóstico — Diferenças entre Implementação Atual e Spec

| # | Situação | Implementação Atual | ASTM F3548 Correto |
|---|---|---|---|
| 1 | Criar OIR | `PUT /dss/v1/operational_intent_references/{id}` | `PUT /dss/v1/operational_intent_references/{entityid}` ✅ |
| 2 | **Atualizar OIR** | `PUT /dss/v1/operational_intent_references/{id}` | `PUT /dss/v1/operational_intent_references/{entityid}/{ovn}` ❌ |
| 3 | **Deletar OIR** | `DELETE /dss/v1/operational_intent_references/{id}?ovn=...` | `DELETE /dss/v1/operational_intent_references/{entityid}/{ovn}` ❌ |
| 4 | Buscar OIRs | (método ausente / path errado) | `POST /dss/v1/operational_intent_references/query` ❌ |
| 5 | Consultar OIR | `GET /dss/v1/operational_intent_references/{id}` | `GET /dss/v1/operational_intent_references/{entityid}` ✅ |
| 6 | **Constraints (list)** | `GET /dss/v1/constraints` | ❌ — não existe na spec |
| 7 | **Constraints (área)** | `POST /dss/v1/constraints/query` | `POST /dss/v1/constraint_references/query` ❌ |
| 8 | **Constraints (get)** | (ausente) | `GET /dss/v1/constraint_references/{entityid}` ❌ |

> **Resumo:** Os dois problemas críticos são: (a) a separação de **criar vs. atualizar** OIR via OVN na URL, e (b) o path de **constraint_references** que usa underscore, não "constraints".

---

## Mudanças a Fazer no `apps/dss_client/client.py`

### Mudança 1 — Separar `submit` em `create` e `update`

**Motivo:** A spec separa claramente criação (sem OVN) e atualização (com OVN na URL).

```python
# ANTES — um método só para criar e atualizar:
def submit_operational_intent_reference(self, oir_id, extents, uss_base_url, state, ...):
    path = f"/dss/v1/operational_intent_references/{oir_id}"
    self._request("PUT", path, json=payload)

# DEPOIS — dois métodos separados:

def create_operational_intent_reference(self, oir_id, extents, uss_base_url, state, ...):
    """Criação — PUT /dss/v1/operational_intent_references/{entityid}"""
    path = f"/dss/v1/operational_intent_references/{oir_id}"
    return self._request("PUT", path, json=payload)

def update_operational_intent_reference(self, oir_id, ovn, extents, uss_base_url, state, ...):
    """Atualização — PUT /dss/v1/operational_intent_references/{entityid}/{ovn}"""
    path = f"/dss/v1/operational_intent_references/{oir_id}/{ovn}"
    return self._request("PUT", path, json=payload)
```

### Mudança 2 — Corrigir DELETE para incluir OVN na URL

```python
# ANTES:
def delete_operational_intent_reference(self, oir_id, ovn=None):
    path = f"/dss/v1/operational_intent_references/{oir_id}"
    params = {"ovn": ovn} if ovn else None
    return self._request("DELETE", path, params=params)

# DEPOIS:
def delete_operational_intent_reference(self, oir_id, ovn):
    """DELETE /dss/v1/operational_intent_references/{entityid}/{ovn}"""
    if not ovn:
        raise DSSValidationError("ovn é obrigatório para deletar uma OIR.")
    path = f"/dss/v1/operational_intent_references/{oir_id}/{ovn}"
    return self._request("DELETE", path)
```

### Mudança 3 — Corrigir path de query de OIRs por área

```python
# ANTES:
def query_operational_intent_references(self, area):
    return self._request("POST", "/dss/v1/operational_intent_references/query", json={"area_of_interest": area})

# DEPOIS — path já está correto, mas garantir payload ASTM:
def query_operational_intent_references(self, area):
    """POST /dss/v1/operational_intent_references/query"""
    return self._request(
        "POST",
        "/dss/v1/operational_intent_references/query",
        json={"area_of_interest": area}
    )
```

### Mudança 4 — Corrigir paths de Constraint References

```python
# ANTES (errado):
def query_constraints(self):
    return self._request("GET", "/dss/v1/constraints")               # não existe na spec

def query_constraints_with_area(self, area):
    return self._request("POST", "/dss/v1/constraints/query", ...)   # path errado

# DEPOIS (correto segundo spec):
def query_constraint_references(self, area):
    """POST /dss/v1/constraint_references/query"""
    return self._request(
        "POST",
        "/dss/v1/constraint_references/query",
        json={"area_of_interest": area}
    )

def get_constraint_reference(self, constraint_id):
    """GET /dss/v1/constraint_references/{entityid}"""
    return self._request("GET", f"/dss/v1/constraint_references/{constraint_id}")
```

### Mudança 5 — Adicionar método `submit` como facade inteligente (cria ou atualiza)

Para não quebrar a view que usa `submit_operational_intent_reference`:

```python
def submit_operational_intent_reference(self, oir_id, extents, uss_base_url, state,
                                         ovn=None, subscription_id=None, key=None, new_subscription=None):
    """
    Facade: chama create (sem OVN) ou update (com OVN).
    - ovn=None  → cria  (PUT /.../{entityid})
    - ovn=str   → atualiza (PUT /.../{entityid}/{ovn})
    """
    if ovn:
        return self.update_operational_intent_reference(
            oir_id=oir_id, ovn=ovn, extents=extents,
            uss_base_url=uss_base_url, state=state,
            key=key, new_subscription=new_subscription
        )
    else:
        return self.create_operational_intent_reference(
            oir_id=oir_id, extents=extents,
            uss_base_url=uss_base_url, state=state,
            subscription_id=subscription_id, key=key,
            new_subscription=new_subscription
        )
```

---

## Mudanças na `apps/oir/views.py`

### `OIRDetailView.put` — passar o `ovn` atual para update

```python
# ANTES:
result = client.submit_operational_intent_reference(oir_id=str(oir.id), ...)

# DEPOIS — passa o OVN salvo localmente para usar o path correto:
result = client.submit_operational_intent_reference(
    oir_id=str(oir.id),
    ovn=oir.dss_ovn or None,   # ← se tiver OVN, usa update; senão, cria
    extents=data["extents"],
    uss_base_url=uss_base_url,
    state=data["state"],
)
```

### `OIRDetailView.delete` — garantir que OVN é obrigatório

```python
# ANTES:
client.delete_operational_intent_reference(oir_id=str(oir.id), ovn=oir.dss_ovn or None)

# DEPOIS:
if not oir.dss_ovn:
    return Response({"error": "OVN não disponível. OIR pode não ter sido enviada ao DSS."}, status=400)
client.delete_operational_intent_reference(oir_id=str(oir.id), ovn=oir.dss_ovn)
```

### `QueryDSSConstraintsView` — renomear método chamado

```python
# ANTES:
result = client.query_constraints_with_area(area)

# DEPOIS:
result = client.query_constraint_references(area)
```

---

## Resumo das Mudanças por Arquivo

| Arquivo | Mudanças |
|---------|---------|
| `apps/dss_client/client.py` | 5 mudanças: separar create/update OIR, fix DELETE, fix constraint paths, adding facade |
| `apps/oir/views.py` | 3 mudanças: PUT passa OVN, DELETE exige OVN, usa novo método de constraint |

---

## Checklist de Execução

- [ ] Alterar `client.py`: adicionar `create_operational_intent_reference`
- [ ] Alterar `client.py`: adicionar `update_operational_intent_reference`  
- [ ] Alterar `client.py`: atualizar `submit_operational_intent_reference` como facade
- [ ] Alterar `client.py`: corrigir `delete_operational_intent_reference` (OVN na URL)
- [ ] Alterar `client.py`: renomear `query_constraints_with_area` → `query_constraint_references` (path correto)
- [ ] Alterar `client.py`: renomear `query_constraints` → remover ou redirecionar
- [ ] Alterar `views.py`: PUT passa `ovn=oir.dss_ovn`
- [ ] Alterar `views.py`: DELETE verifica OVN antes de chamar DSS
- [ ] Alterar `views.py`: usar `query_constraint_references` no QueryDSSConstraintsView
- [ ] Testar todos os fluxos via Postman/curl

---

## Ordem de Execução

1. `client.py` — todas as mudanças (podem ser feitas juntas)
2. `views.py` — ajustes dependentes do novo client
3. Reiniciar servidor e testar

> **Nota:** O `submit_operational_intent_reference` será mantido como **facade** para compatibilidade. Ele decide automaticamente usar create ou update baseado na presença do OVN.
