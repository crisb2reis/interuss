import os
import sys
import django
import uuid

# Obtém o diretório raiz do projeto (dois níveis acima de scripts/ISA)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

from apps.oir.models import OperationalIntent
from apps.oir.services import ISAService

if len(sys.argv) < 2:
    print("Uso: python3 ativar_ISA.py <oir_id>")
    sys.exit(1)

oir_id_str = sys.argv[1]
try:
    oir_id = uuid.UUID(oir_id_str)
except ValueError:
    print(f"[!] '{oir_id_str}' não é um UUID válido.")
    sys.exit(1)

try:
    oir = OperationalIntent.objects.get(id=oir_id)
except OperationalIntent.DoesNotExist:
    print(f"[!] OperationalIntent com ID {oir_id} não encontrado no banco local.")
    sys.exit(1)

print(f"Operational Intent encontrado: {oir_id}")
print("Ativando e registrando ISA...")

try:
    oir.state = 'Activated'
    
    # Atualiza o time_start para o presente para evitar erro 400 (time_start in the past) no DSS
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    now_str = now.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + "Z"
    
    if isinstance(oir.extents, list) and len(oir.extents) > 0:
        if "time_start" in oir.extents[0]:
            oir.extents[0]["time_start"]["value"] = now_str
            
    oir.save()
    isa = ISAService.create_or_update_from_oir(oir)
    print(f"[+] ISA registrado no DSS com ID: {isa.dss_id}")
    print(f"[+] Vá verificar a interface BR-UTM!")
except Exception as e:
    print(f"[!] Erro ao ativar/registrar ISA: {e}")

