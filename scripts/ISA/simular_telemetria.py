import os
import sys
import django
import requests
from datetime import datetime, timezone
import json

# Adiciona a raiz do projeto ao sys.path (2 níveis acima de scripts/ISA/)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

from apps.oir.models import IdentificationServiceArea

def simular(isa_id_str):
    try:
        isa = IdentificationServiceArea.objects.get(id=isa_id_str)
    except IdentificationServiceArea.DoesNotExist:
        try:
            # Tenta buscar pelo dss_id que é igual ao OIR id normalmente
            isa = IdentificationServiceArea.objects.get(dss_id=isa_id_str)
        except IdentificationServiceArea.DoesNotExist:
            print(f"ISA não encontrado para: {isa_id_str}")
            return

    # Usaremos o dss_id como id de voo na url? Não, a ingestão usa a chave primária local do ISA
    payload = {
        "isa_id": str(isa.id),
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "lat": -23.2515,
        "lng": -45.8605,
        "alt": 150.0,
        "pressure_altitude": 150.0,
        "operational_status": "Airborne",
        "speed": 5.0,
        "track": 90.0,
        "accuracy_h": "HA10m",
        "accuracy_v": "VA10m",
        "speed_accuracy": "SA3mps"
    }

    url = "http://localhost:8001/uss/telemetry/"
    
    print(f"Enviando telemetria para {url}...")
    print(json.dumps(payload, indent=2))
    
    resp = requests.post(url, json=payload)
    print(f"Status: {resp.status_code}")
    print(f"Resposta: {resp.text}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/ISA/simular_telemetria.py <ISA_ID_ou_OIR_ID>")
        sys.exit(1)
    simular(sys.argv[1])
