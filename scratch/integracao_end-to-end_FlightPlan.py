#!/usr/bin/env python3
import requests
import uuid
import json
from datetime import datetime, timedelta

# BASE_URL apontando para o Kong Gateway local
BASE_URL = "http://localhost:8001/api"
API_KEY = "brutm"

def create_flight_plan():
    flight_plan_id = str(uuid.uuid4())
    print(f"[*] Gerando novo Flight Plan ID: {flight_plan_id}")

    now = datetime.utcnow()
    start = now + timedelta(minutes=15)
    end = start + timedelta(minutes=45)

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
                                    {"lat": -23.251, "lng": -45.861},
                                    {"lat": -23.252, "lng": -45.861},
                                    {"lat": -23.252, "lng": -45.859},
                                    {"lat": -23.251, "lng": -45.859}
                                ]
                            },
                            "altitude_lower": {"value": 0, "units": "M", "reference": "W84"},
                            "altitude_upper": {"value": 120, "units": "M", "reference": "W84"}
                        },
                        "time_start": {"value": start.strftime("%Y-%m-%dT%H:%M:%SZ"), "format": "RFC3339"},
                        "time_end": {"value": end.strftime("%Y-%m-%dT%H:%M:%SZ"), "format": "RFC3339"}
                    }
                ],
                "description": "Teste de criacao para validacao ISA Step 3"
            },
            "uas": "Drone-ISA-Test",
            "operator": "Operator-ISA"
        },
        "execution_style": "IfAllowed"
    }

    url = f"{BASE_URL}/flight_plans/{flight_plan_id}/"
    headers = {"x-api-key": API_KEY}
    
    print(f"[*] Enviando requisição PUT para {url}...")
    response = requests.put(url, json=payload, headers=headers)
    
    if response.status_code in [200, 201]:
        print(f"[+] SUCESSO! Plano de voo criado: {flight_plan_id}")
        return flight_plan_id
    else:
        print(f"[!] Erro na criação: {response.status_code}")
        print(response.text)
        return None

if __name__ == "__main__":
    create_flight_plan()
