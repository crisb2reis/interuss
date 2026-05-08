
import os, sys, django, requests
from datetime import datetime, timezone

PROJECT_ROOT = "/mnt/dados/projetos/interuss"
sys.path.insert(0, PROJECT_ROOT)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

from apps.oir.models import IdentificationServiceArea, RIDTelemetry

# Busca o ISA ativo
isa = IdentificationServiceArea.objects.first()
if not isa:
    print("Nenhum ISA encontrado.")
    sys.exit(1)

print(f"Inserindo telemetria para ISA: {isa.dss_id} (UUID: {isa.id})")

payload = {
    "isa_id": str(isa.id),
    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "lat": -23.21388,
    "lng": -45.87701,
    "alt": 650.0,
    "pressure_altitude": 650.0,
    "operational_status": "Airborne",
    "speed": 5.0,
    "track": 118.9,
    "accuracy_h": "HA10m",
    "accuracy_v": "VA10m",
    "speed_accuracy": "SA3mps",
}

# Ingerindo via API
url = "http://localhost:8001/uss/telemetry/"
try:
    resp = requests.post(url, json=payload)
    print(f"Status Ingestão: {resp.status_code}")
    print(resp.json())
except Exception as e:
    print(f"Erro ao chamar API local: {e}")

# Verifica se salvou no DB
t = RIDTelemetry.objects.filter(isa=isa).order_by("-timestamp").first()
print(f"Telemetria mais nova no DB: {t.timestamp if t else 'Nenhum'}")
