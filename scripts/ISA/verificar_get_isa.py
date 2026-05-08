import os
import sys
import django
import json

# Obtém o diretório raiz do projeto
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

from apps.dss_client.client import DSSClient

def verificar_get_isa(isa_id):
    print(f"[*] Consultando ISA {isa_id} no DSS...")
    
    # Escopo rid.display_provider é necessário para GET ISA
    client = DSSClient(intended_audience="core-service", scope="rid.display_provider")
    
    try:
        result = client.get_identification_service_area(isa_id)
        print("[+] Resposta do DSS recebida com sucesso!")
        print(json.dumps(result, indent=2))
        
        service_area = result.get("service_area", {})
        time_start = service_area.get("time_start")
        time_end = service_area.get("time_end")
        
        print("-" * 40)
        print(f"ID: {service_area.get('id')}")
        print(f"Owner: {service_area.get('owner')}")
        print(f"Version: {service_area.get('version')}")
        print(f"Time Start (Raw): {time_start}")
        print(f"Time End (Raw): {time_end}")
        
    except Exception as e:
        print(f"[!] Erro ao consultar ISA: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 verificar_get_isa.py <isa_id>")
        sys.exit(1)
    
    verificar_get_isa(sys.argv[1])
