#!/usr/bin/env python3
import requests
import uuid
import json
from datetime import datetime, timedelta

BASE_URL = "http://api.sandbox.br-utm.org/uss-cristiano/api"

def create_flight_plan():
    flight_plan_id = str(uuid.uuid4())
    print(f"[*] Gerando novo Flight Plan ID: {flight_plan_id}")

    # now = datetime.utcnow()
    # start = now + timedelta(minutes=15)
    start = datetime(2026, 4, 30, 13, 5, 0)
    end = start + timedelta(minutes=30)

    payload = {
        "flight_plan": {
            "basic_information": {
                "usage_state": "Planned",
                "uas_state": "Nominal",
                "area": [
                    {
                        "volume": {
                            "outline_polygon": {
                                "vertices": [
                                    {"lat": -23.251405929155823, "lng": -45.86100697775501},
                                    {"lat": -23.252868169254455, "lng": -45.86100697775501},
                                    {"lat": -23.252868169254455, "lng": -45.859250118309916},
                                    {"lat": -23.251405929155823, "lng": -45.859250118309916}
                                ]
                            },
                            "altitude_lower": {"value": 0, "units": "M", "reference": "W84"},
                            "altitude_upper": {"value": 120, "units": "M", "reference": "W84"}
                        },
                        "time_start": {"value": start.strftime("%Y-%m-%dT%H:%M:%SZ"), "format": "RFC3339"},
                        "time_end": {"value": end.strftime("%Y-%m-%dT%H:%M:%SZ"), "format": "RFC3339"}
                    }
                ],
                "description": "Teste de criacao via API para posterior ativacao"
            },
            "uas": "Drone-Test-01",
            "operator": "Operator-Cristiano"
        },
        "execution_style": "IfAllowed"
    }

    url = f"{BASE_URL}/flight_plans/{flight_plan_id}/"
    print(f"[*] Operação ASTM: PUT /dss/v1/operational_intent_references/{{entityid}}")
    print(f"[*] Enviando requisição PUT (Upsert) para {url}...")
    
    response = requests.put(url, json=payload)
    
    if response.status_code in [200, 201]:
        print(f"[+] SUCESSO! Plano de voo criado.")
        print(f"    ID: {flight_plan_id}")
        print(f"    Resultado: {response.json().get('planning_result')}")
        print(f"\n[DEBUG] JSON ENVIADO À API:")
        print(json.dumps(payload, indent=2))
        return flight_plan_id
    else:
        print(f"[!] Erro na criação: {response.status_code}")
        print(response.text)
        return None

if __name__ == "__main__":
    create_flight_plan()
