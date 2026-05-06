import os
import sys
import django
import uuid
from datetime import datetime, timedelta, timezone

# Adiciona o diretório atual ao sys.path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

from apps.oir.models import OperationalIntent

# Dados básicos
oir_id = uuid.uuid4()
now = datetime.now(timezone.utc)
start = now + timedelta(minutes=10)
end = start + timedelta(hours=1)

extents = [{
    "volume": {
        "outline_polygon": {
            "vertices": [
                {"lat": -23.251, "lng": -45.861},
                {"lat": -23.252, "lng": -45.861},
                {"lat": -23.252, "lng": -45.859},
                {"lat": -23.251, "lng": -45.859},
            ]
        },
        "altitude_lower": {"value": 100, "reference": "W84", "units": "M"},
        "altitude_upper": {"value": 500, "reference": "W84", "units": "M"},
    },
    "time_start": {"value": start.isoformat().replace('+00:00', 'Z'), "format": "RFC3339"},
    "time_end": {"value": end.isoformat().replace('+00:00', 'Z'), "format": "RFC3339"},
}]

# Criar OIR
oir = OperationalIntent.objects.create(
    id=oir_id,
    dss_id=str(oir_id),
    state='Accepted',
    extents=extents,
    uss_base_url='http://localhost:8001'
)

print(f"Operational Intent criado: {oir_id}")
