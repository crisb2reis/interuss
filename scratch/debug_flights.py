
import os, sys, django
from datetime import datetime, timezone

PROJECT_ROOT = "/mnt/dados/projetos/interuss"
sys.path.insert(0, PROJECT_ROOT)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

from rest_framework.test import APIRequestFactory
from apps.oir.views import USSFlightsView
from apps.dss_client.auth import ICEAAuthenticator

factory = APIRequestFactory()
view = USSFlightsView.as_view()

# Obtém token
auth = ICEAAuthenticator()
token = auth.get_token(intended_audience="core-service", scope="rid.display_provider")

# Faz o request
# Coordenadas aproximadas de SJC/ICEA conforme o print do usuário
# lat1,lng1,lat2,lng2
view_coords = "-23.22,-45.88,-23.21,-45.86"
request = factory.get(f'/uss/flights?view={view_coords}', HTTP_AUTHORIZATION=f'Bearer {token}')
response = view(request)

print(f"Status Code: {response.status_code}")
import json
print(json.dumps(response.data, indent=2))
