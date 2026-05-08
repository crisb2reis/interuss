from django.conf import settings
from apps.oir.services import ISAService
from datetime import datetime, timezone
import json

now = datetime.now(timezone.utc).isoformat()
res = ISAService.query_dss('-23.3,-45.9,-23.1,-45.9,-23.1,-45.7,-23.3,-45.7', now, now)
our_uss_base = settings.USS_BASE_URL.rstrip('/')
print(f"OUR BASE: '{our_uss_base}'")

isas = res.get('service_areas', [])
for isa in isas:
    base = isa.get('uss_base_url', '').rstrip('/')
    match = (base == our_uss_base)
    print(f"ISA ID: {isa.get('id')} | BASE: '{base}' | MATCH: {match}")
