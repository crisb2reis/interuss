"""
Script para testar as integrações F3411 Remote ID recém implementadas:
1. Consultar ISAs no DSS (/api/isa/query_dss/)
2. Consultar voos no USS (/uss/flights)

Uso:
    python scripts/ISA/testar_dss_isa.py
"""
import sys
import os
import json
import requests
from datetime import datetime, timezone, timedelta

# Adiciona o diretório raiz ao path para importar apps
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

from django.conf import settings
from apps.dss_client.auth import ICEAAuthenticator

BASE_URL = "http://localhost:8001"

def get_token(scope: str) -> str:
    auth = ICEAAuthenticator()
    return auth.get_token(intended_audience="core-service", scope=scope)

def _get_headers(token: str) -> dict:
    api_key = getattr(settings, "ICEA_API_KEY", "brutm")
    return {
        "Authorization": f"Bearer {token}",
        "x-api-key": api_key,
    }

def print_section(title):
    print(f"\n{'='*70}\n  {title}\n{'='*70}")

def main():
    now = datetime.now(timezone.utc)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    
    # Bounding Box de São José dos Campos (onde normalmente criamos OIRs para teste)
    lat1, lng1 = -23.255, -45.865
    lat2, lng2 = -23.245, -45.855
    view_area = f"{lat1},{lng1},{lat2},{lng2}"
    
    token_dp = get_token("rid.display_provider")
    headers = _get_headers(token_dp)
    
    # ── 1. USS → DSS: GET /api/isa/query_dss/ ────────────────────────────────
    print_section(f"1. USS consulta DSS: GET /api/isa/query_dss/?area={view_area}")
    query_params = {
        "area": view_area,
        "earliest_time": now_iso,
        "latest_time": now_iso,
    }
    
    try:
        r_dss = requests.get(f"{BASE_URL}/api/isa/query_dss/", params=query_params, headers=headers)
        print(f"Status: {r_dss.status_code}")
        if r_dss.status_code == 200:
            dss_data = r_dss.json()
            areas = dss_data.get("service_areas", [])
            print(f"ISAs encontradas no DSS para a área: {len(areas)}")
            if areas:
                print(json.dumps(areas[0], indent=2))
                print("..." if len(areas) > 1 else "")
        else:
            print(f"Body: {r_dss.text}")
    except Exception as e:
        print(f"Erro ao consultar DSS: {e}")

    # ── 2. Display Provider → USS: GET /uss/flights ───────────────────────────
    print_section(f"2. Display Provider consulta USS: GET /uss/flights?view={view_area}&recent_positions_duration=60")
    flights_params = {
        "view": view_area,
        "recent_positions_duration": 60,
    }
    
    try:
        r_flights = requests.get(f"{BASE_URL}/uss/flights", params=flights_params, headers=headers)
        print(f"Status: {r_flights.status_code}")
        if r_flights.status_code == 200:
            print(json.dumps(r_flights.json(), indent=2))
        else:
            print(f"Body: {r_flights.text}")
    except Exception as e:
        print(f"Erro ao consultar voos: {e}")

if __name__ == "__main__":
    main()
