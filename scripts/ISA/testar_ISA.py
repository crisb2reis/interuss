"""
Testa os endpoints ISA:
  1. Ativa uma OIR existente → ISA deve ser criado automaticamente
  2. GET  /uss/identification_service_areas/{id}  (rid.display_provider)
  3. POST /uss/identification_service_areas/{id}  (rid.service_provider)

Uso:
    python scripts/ISA/testar_ISA.py <isa_id>
"""
import json
import sys
import os
import requests

# Adiciona o diretório raiz ao path para importar apps
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Configuração do Django para usar o ICEAAuthenticator
# IMPORTANTE: usar 'config.settings.base' — 'config.settings' aponta para __init__.py vazio
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

from django.conf import settings
from apps.dss_client.auth import ICEAAuthenticator

# Apontando para o Docker local para evitar autenticação do Gateway remoto
BASE_URL = "http://localhost:8001"

def get_token(scope: str) -> str:
    auth = ICEAAuthenticator()
    return auth.get_token(intended_audience="core-service", scope=scope)


def _get_headers(token: str) -> dict:
    """
    Monta os headers completos para requisições via Kong API Gateway.
    O Kong exige 'x-api-key' além do 'Authorization: Bearer' JWT.
    """
    api_key = getattr(settings, "ICEA_API_KEY", "brutm")
    return {
        "Authorization": f"Bearer {token}",
        "x-api-key": api_key,
    }

def print_section(title):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")

def main():
    # ── Pega ISA ID da linha de comando ou usa placeholder ────────
    isa_id = sys.argv[1] if len(sys.argv) > 1 else None
    if not isa_id:
        print("Uso: python scripts/ISA/testar_ISA.py <isa_id>")
        print("Dica: isa_id = dss_id de uma OIR ativada.")
        sys.exit(1)

    # ── 1. GET com escopo rid.display_provider ────────────────────
    print_section(f"1. GET /uss/identification_service_areas/{isa_id}")
    try:
        token_dp = get_token("rid.display_provider")
        r = requests.get(
            f"{BASE_URL}/uss/identification_service_areas/{isa_id}",
            headers=_get_headers(token_dp),
        )
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            print(json.dumps(r.json(), indent=2))
        else:
            print(f"Body: {r.text}")
    except Exception as e:
        print(f"Erro no GET: {e}")

    # ── 2. POST com escopo rid.service_provider ───────────────────
    print_section(f"2. POST /uss/identification_service_areas/{isa_id}")
    try:
        token_sp = get_token("rid.service_provider")
        payload = {
            "extents": {
                "volume": {
                    "outline_polygon": {
                        "vertices": [
                            {"lat": -23.251405929155823, "lng": -45.86100697775501},
                            {"lat": -23.252868169254455, "lng": -45.86100697775501},
                            {"lat": -23.252868169254455, "lng": -45.859250118309916},
                            {"lat": -23.251405929155823, "lng": -45.859250118309916},
                        ]
                    },
                    "altitude_lower": {"value": 600.0,   "reference": "W84", "units": "M"},
                    "altitude_upper": {"value": 7000.0, "reference": "W84", "units": "M"},
                },
                "time_start": {"value": "2026-05-10T10:00:00Z", "format": "RFC3339"},
                "time_end":   {"value": "2026-05-10T11:00:00Z", "format": "RFC3339"},
            },
            "service_area": {
                "id": isa_id,
                "uss_base_url": BASE_URL,
            },
            "subscriptions": [],
        }
        r = requests.post(
            f"{BASE_URL}/uss/identification_service_areas/{isa_id}",
            json=payload,
            headers=_get_headers(token_sp),
        )
        print(f"Status: {r.status_code}")
        if r.status_code != 204:
            print(f"Body: {r.text}")
        else:
            print("(204 No Content — OK)")
    except Exception as e:
        print(f"Erro no POST: {e}")

if __name__ == "__main__":
    main()
