#!/usr/bin/env python3
"""
Ativa um Flight Plan existente (state=ACCEPTED) e verifica o ISA
(Identification Service Area) criado automaticamente.

Fluxo:
  1. GET  /api/flight_plans/{id}/ → confirma existência e estado atual
  2. PUT  /api/flight_plans/{id}/ → ativa o plano (usage_state=InUse)
  3. GET  /uss/identification_service_areas/{id}
         (escopo rid.display_provider) → verifica o ISA resultante

Uso:
    python scripts/ISA/atualizar_e_ativar_isa.py <flight_plan_id>

Dica:
    O flight_plan_id deve estar em estado ACCEPTED (Planned) para ser ativado.
"""

import json
import sys
import os
import uuid
import requests

# ── Configuração do Django (para ICEAAuthenticator) ───────────────
# IMPORTANTE: usar 'config.settings.base' — 'config.settings' aponta
# para __init__.py vazio e não carrega as variáveis de ambiente.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

from django.conf import settings
from apps.dss_client.auth import ICEAAuthenticator

# ── URLs ──────────────────────────────────────────────────────────
API_BASE_URL = "http://localhost:8001/api"
USS_BASE_URL = "http://localhost:8001"


# ── Helpers ───────────────────────────────────────────────────────

def get_token(scope: str) -> str:
    auth = ICEAAuthenticator()
    return auth.get_token(intended_audience="core-service", scope=scope)


def _api_headers() -> dict:
    """Headers para endpoints da API interna (/api/*) via Kong Gateway."""
    api_key = getattr(settings, "ICEA_API_KEY", "brutm")
    return {"x-api-key": api_key}


def _isa_headers(token: str) -> dict:
    """Headers para endpoints ISA (exigem JWT + x-api-key via Kong)."""
    api_key = getattr(settings, "ICEA_API_KEY", "brutm")
    return {
        "Authorization": f"Bearer {token}",
        "x-api-key": api_key,
    }


def print_section(title: str):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")


# ── Passos ────────────────────────────────────────────────────────

def step1_verificar_flight_plan(fp_id: str) -> dict | None:
    """Verifica existência do Flight Plan e retorna os dados locais."""
    print_section(f"1. Verificando Flight Plan: {fp_id}")

    url = f"{API_BASE_URL}/flight_plans/{fp_id}/"
    r = requests.get(url, headers=_api_headers())

    if r.status_code != 200:
        print(f"[!] Flight Plan não encontrado (HTTP {r.status_code}): {r.text}")
        return None

    data = r.json()
    state = data.get("state")
    print(f"[+] Encontrado. Estado atual: {state}")

    if state == "ACTIVATED":
        print("[~] Plano já está ACTIVATED — pulando ativação e consultando ISA.")

    return data


def step2_ativar_flight_plan(fp_id: str, fp_data: dict) -> bool:
    """Envia PUT para ativar o Flight Plan no DSS."""
    print_section(f"2. Ativando Flight Plan via DSS: {fp_id}")

    astm_payload = fp_data.get("astm_payload")
    if not astm_payload:
        print("[!] Erro: 'astm_payload' ausente no registro local. "
              "O plano foi criado antes desta funcionalidade ser implementada?")
        return False

    # Transição de estado: Planned → InUse (ativa a OIR no DSS)
    astm_payload["flight_plan"]["basic_information"]["usage_state"] = "InUse"
    astm_payload["flight_plan"]["priority"] = 8

    print(f"[*] ASTM: PUT /dss/v1/operational_intent_references/{{entityid}}/{{ovn}}")

    url = f"{API_BASE_URL}/flight_plans/{fp_id}/"
    r = requests.put(url, json=astm_payload, headers=_api_headers())

    if r.status_code in [200, 201]:
        result = r.json()
        print(f"[+] Ativação concluída!")
        print(f"    planning_result : {result.get('planning_result')}")
        if result.get("notes"):
            print(f"    notes           : {result.get('notes')}")
        return True
    else:
        print(f"[!] Falha na ativação (HTTP {r.status_code}):")
        print(f"    {r.text}")
        return False


def step3_verificar_isa(fp_id: str) -> None:
    """Consulta o ISA gerado automaticamente via endpoint ASTM F3411."""
    print_section(f"3. Consultando ISA: /uss/identification_service_areas/{fp_id}")

    try:
        token = get_token("rid.display_provider")
    except Exception as e:
        print(f"[!] Erro ao obter token rid.display_provider: {e}")
        return

    url = f"{USS_BASE_URL}/uss/identification_service_areas/{fp_id}"
    r = requests.get(url, headers=_isa_headers(token))

    print(f"    HTTP Status: {r.status_code}")

    if r.status_code == 200:
        isa_data = r.json()
        extents = isa_data.get("extents", {})
        volume = extents.get("volume", {})
        alt_lower = extents.get("altitude_lower") or volume.get("altitude_lower", {})
        alt_upper = extents.get("altitude_upper") or volume.get("altitude_upper", {})

        print(f"\n[+] ISA encontrado e válido!")
        print(f"    time_start : {extents.get('time_start', {}).get('value', 'N/A')}")
        print(f"    time_end   : {extents.get('time_end',   {}).get('value', 'N/A')}")
        print(f"    alt_lower  : {alt_lower.get('value', 'N/A')} {alt_lower.get('units', '')}")
        print(f"    alt_upper  : {alt_upper.get('value', 'N/A')} {alt_upper.get('units', '')}")

        vertices = volume.get("outline_polygon", {}).get("vertices", [])
        print(f"    vértices   : {len(vertices)} pontos")

        print(f"\n[~] ISA completo (JSON):")
        print(json.dumps(isa_data, indent=2))

    elif r.status_code == 404:
        print(f"\n[!] ISA não encontrado para o ID '{fp_id}'.")
        print("    Possíveis causas:")
        print("    - A ativação não disparou o gatilho ISA (verifique os logs do Django).")
        print("    - O ID passado não é o mesmo que o 'dss_id' no ISA.")
    else:
        print(f"\n[!] Resposta inesperada: {r.text}")


# ── Ponto de entrada ──────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Uso: python scripts/ISA/atualizar_e_ativar_isa.py <flight_plan_id>")
        print("Dica: flight_plan_id deve estar em estado ACCEPTED (Planned).")
        sys.exit(1)

    fp_id = sys.argv[1]
    try:
        uuid.UUID(fp_id)
    except ValueError:
        print(f"[!] Erro: '{fp_id}' não é um UUID válido.")
        sys.exit(1)

    # 1. Verificar existência
    fp_data = step1_verificar_flight_plan(fp_id)
    if fp_data is None:
        sys.exit(1)

    # 2. Ativar (somente se ainda não está ACTIVATED)
    if fp_data.get("state") != "ACTIVATED":
        success = step2_ativar_flight_plan(fp_id, fp_data)
        if not success:
            sys.exit(1)
    else:
        print("[~] Pulando Passo 2 — plano já ativado.")

    # 3. Verificar ISA resultante
    step3_verificar_isa(fp_id)

    print(f"\n{'='*60}")
    print("  Concluído.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
