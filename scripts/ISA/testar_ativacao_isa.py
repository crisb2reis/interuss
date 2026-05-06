import os
import sys
import django
import logging

# Adiciona o diretório raiz do projeto ao sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

# Configura logging para ver o que está acontecendo
logging.basicConfig(level=logging.INFO)

from apps.oir.models import OperationalIntent
from apps.oir.services import ISAService

# Pega o ID dos argumentos ou usa o padrão
if len(sys.argv) > 1:
    oir_id = sys.argv[1]
else:
    oir_id = "f88b436b-2b6b-40c8-8ee1-509820e12077"

oir = OperationalIntent.objects.get(id=oir_id)

print(f"Ativando OIR {oir_id}...")
oir.state = 'Activated'
oir.save()

# Disparar o serviço manualmente (como a view faria)
print("Chamando ISAService.create_or_update_from_oir(oir)...")
isa = ISAService.create_or_update_from_oir(oir)

print(f"ISA ID: {isa.id}")
print(f"DSS ID: {isa.dss_id}")
print(f"DSS Version: {isa.dss_version}")
