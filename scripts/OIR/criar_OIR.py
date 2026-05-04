#!/usr/bin/env python3
"""
Script de teste para o fluxo completo:
1. Criar FlightPlan no USS (Banco de dados local)
2. Autenticar no ICEA (via ICEAAuthenticator)
3. Criar OIR no DSS
4. Salvar referências (dss_id, ovn, subscription_id) no USS
"""

import os
import sys
import json
from datetime import datetime, timedelta
from django.contrib.gis.geos import Polygon

# Adicionar o diretório do projeto ao PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Configurar o Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django
django.setup()

from apps.flight_plans.models import FlightPlan, State
from apps.flight_plans.services import OperationalIntentService

def main():
    print("\n" + "="*60)
    print("  FLUXO COMPLETO: CRIAR OIR NO DSS E SALVAR NO USS")
    print("="*60 + "\n")

    from django.utils import timezone
    
    # 1. Criar um Plano de Voo Local
    # Uma pequena área em São Paulo com dimensão Z (altitude)
    # Formato: (lon, lat, alt)
    poly = Polygon((
        (-45.86100697775501, -23.251405929155823, 0.0),
        (-45.86100697775501, -23.252868169254455, 0.0),
        (-45.859250118309916, -23.252868169254455, 0.0),
        (-45.859250118309916, -23.251405929155823, 0.0),
        (-45.86100697775501, -23.251405929155823, 0.0)
    ))
    
    # now = timezone.now()
    # start = now + timedelta(hours=1)
    start = datetime(2026, 4, 30, 13, 50, 0)
    end = start + timedelta(minutes=30)

    print("[*] Criando Plano de Voo local...")
    fp = FlightPlan.objects.create(
        state=State.ACCEPTED,
        priority=1,
        start_time=start,
        end_time=end,
        volume=poly,
        uss_base_url="http://api.dev.br-utm.org/uss-cristiano"
    )
    print(f"[+] Plano de Voo criado: {fp.id}")

    # 2. Chamar o serviço de sincronização
    print(f"[*] Operação ASTM: PUT /dss/v1/operational_intent_references/{{entityid}}")
    print("\n[*] Iniciando sincronização com o DSS...")
    try:
        intent, dss_response = OperationalIntentService.create_operational_intent(fp.id)
        
        print("\n[+] SUCESSO! OIR registrada e salva localmente.")
        print("-" * 60)
        print(f"ID Local (OperationalIntent): {intent.id}")
        print(f"ID DSS (dss_id):             {intent.dss_id}")
        print(f"Versão no DSS:               {intent.version}")
        print(f"OVN:                         {intent.ovn}")
        print(f"Subscription ID:             {intent.subscription_id}")
        print("-" * 60)
        
        print("\nResposta Bruta do DSS (Resumo):")
        print(json.dumps(dss_response['operational_intent_reference'], indent=2))

    except Exception as e:
        print(f"\n[!] ERRO DURANTE O FLUXO: {str(e)}")
        # Se falhou mas o FlightPlan foi criado, podemos deletar para limpar o teste
        # fp.delete()
        sys.exit(1)

if __name__ == "__main__":
    main()
