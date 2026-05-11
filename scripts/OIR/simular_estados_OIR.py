#!/usr/bin/env python3
import os
import sys
import json
import time
import requests
from datetime import datetime, timedelta

# Adicionar o diretório do projeto ao PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Configurar o Django (para ler settings)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django
django.setup()

from django.conf import settings

USS_BASE_URL = "http://localhost:8001" # Porta do container web no docker-compose

def create_oir():
    print("[*] Criando OIR...")
    payload = {
        "state": "Accepted",
        "uss_base_url": settings.USS_BASE_URL,
        "extents": [{
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
                "altitude_upper": {"value": 100, "units": "M", "reference": "W84"}
            },
            "time_start": {"value": (datetime.utcnow() + timedelta(minutes=1)).isoformat() + "Z", "format": "RFC3339"},
            "time_end": {"value": (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z", "format": "RFC3339"}
        }]
    }
    res = requests.post(f"{USS_BASE_URL}/api/oir/", json=payload)
    res.raise_for_status()
    data = res.json()
    print(f"[+] OIR criada: {data['id']} (Estado: {data['state']})")
    return data['id']

def transition_state(oir_id, state):
    print(f"[*] Transicionando para {state}...")
    res = requests.patch(f"{USS_BASE_URL}/api/oir/{oir_id}/state/", json={"state": state})
    res.raise_for_status()
    data = res.json()
    print(f"[+] Novo estado: {data['new_state']}")

def ingest_telemetry(oir_id, lat, lng):
    print(f"[*] Ingerindo telemetria ({lat}, {lng})...")
    # O Serializer local espera "isa_id"
    payload = {
        "isa_id": oir_id,
        "lat": lat,
        "lng": lng,
        "alt": 50,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    res = requests.post(f"{USS_BASE_URL}/api/uss/telemetry/", json=payload)
    res.raise_for_status()
    print("[+] Telemetria ingerida.")

def main():
    import sys
    
    # Coordenadas do ISA fornecido:
    # Lat: -23.2137 até -23.2186
    # Lng: -45.8772 até -45.8677
    
    LAT_INSIDE = -23.2160
    LNG_INSIDE = -45.8720
    
    LAT_OUTSIDE = -23.0000
    LNG_OUTSIDE = -45.0000

    try:
        # Se passar ID por argumento, usa ele. Senão, cria um novo.
        if len(sys.argv) > 1:
            oir_id = sys.argv[1]
            print(f"[*] Usando OIR/ISA existente: {oir_id}")
        else:
            oir_id = create_oir()
            # 2. Ativar (se for nova)
            transition_state(oir_id, "Activated")
        
        # 3. Telemetria DENTRO
        ingest_telemetry(oir_id, LAT_INSIDE, LNG_INSIDE)
        print("[*] Aguardando conformidade...")
        time.sleep(5)
        
        # 4. Telemetria FORA
        ingest_telemetry(oir_id, LAT_OUTSIDE, LNG_OUTSIDE)
        print(f"[*] UA FORA DO VOLUME ({LAT_OUTSIDE}, {LNG_OUTSIDE}).")
        print("[*] Aguardando detecção pelo Celery (pode levar até 15s)...")
        
        for i in range(12): # 1 minuto de polling
            time.sleep(5)
            res = requests.get(f"{USS_BASE_URL}/api/oir/{oir_id}/")
            state = res.json()['state']
            print(f"    - Estado atual: {state}")
            if state == "Nonconforming":
                print("[!] Detecção SUCESSO: Nonconforming detectado!")
                break
        
        if state == "Nonconforming":
            print("[*] Aguardando timeout de 60s para Contingent...")
            time.sleep(65)
            
            res = requests.get(f"{USS_BASE_URL}/api/oir/{oir_id}/")
            state = res.json()['state']
            print(f"[!] Estado final: {state}")
            if state == "Contingent":
                print("[SUCCESS] Ciclo completo realizado!")
            else:
                print("[FAILURE] Não chegou em Contingent (verifique se o Celery Beat está rodando).")
        else:
            print("[FAILURE] Não entrou em estado Nonconforming.")

    except Exception as e:
        print(f"[!] Erro: {e}")

if __name__ == "__main__":
    main()
