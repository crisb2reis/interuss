#!/usr/bin/env python3
"""
Script de teste para o fluxo completo ASTM F3548-21:
"OIR com Conflito e Deconflição por Prioridade"
"""

import os
import sys
import json
from datetime import datetime, timedelta

# Adicionar o diretório do projeto ao PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Configurar o Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django
django.setup()

from apps.oir.conflict_resolution import OIRConflictResolutionService


def main():
    print("\n" + "=" * 65)
    print("  FLUXO: OIR COM CONFLITO E DECONFLIÇÃO (ASTM F3548-21)")
    print("=" * 65 + "\n")

    # now = datetime.utcnow()
    # start = now + timedelta(hours=1)

    # Ajuste do horário para 14:00:00Z (UTC) do dia 28 de Abril de 2026
    start = datetime(2026, 4, 28, 18, 47, 0)
    end = start + timedelta(minutes=30)

    area_of_interest = {
        "volume": {
            "outline_polygon": {
                "vertices": [
                    {"lat": -23.409038292043147, "lng": -45.98052417963366},
                    {"lat": -23.409710788866886, "lng": -45.97979246585125},
                    {"lat": -23.408980318021133, "lng": -45.96893459452031},
                    {"lat": -23.40842376612441, "lng": -45.969754618586796},
                ]
            },
            "altitude_lower": {"value": 0, "units": "M", "reference": "W84"},
            "altitude_upper": {"value": 500, "units": "M", "reference": "W84"},
        },
        "time_start": {"value": start.strftime("%Y-%m-%dT%H:%M:%SZ"), "format": "RFC3339"},
        "time_end":   {"value": end.strftime("%Y-%m-%dT%H:%M:%SZ"),   "format": "RFC3339"},
    }

    oir_payload = {
        "extents": [area_of_interest],
        "state": "Accepted",
    }

    our_priority = 9

    print("[*] Iniciando fluxo via OIRConflictResolutionService...")
    print(f"[*] Nossa Prioridade: {our_priority}")

    print("\n[+] DETALHES DO VOO:")
    print(f"    Horário de Início (UTC): {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"    Horário de Término (UTC): {end.strftime('%Y-%m-%d %H:%M:%S')}")
    print("    Polígono (Lat/Lng):")
    for idx, vertex in enumerate(area_of_interest["volume"]["outline_polygon"]["vertices"], 1):
        print(f"      - Vértice {idx}: Lat {vertex['lat']}, Lng {vertex['lng']}")
    print("-" * 65)

    try:
        service = OIRConflictResolutionService()
        result = service.resolve_and_create(
            area_of_interest=area_of_interest,
            oir_payload=oir_payload,
            our_priority=our_priority,
        )

        status = result.get("status")
        
        print("\n[+] RESULTADO DA RESOLUÇÃO DE CONFLITO:")
        print(f"    Status: {status.upper()}")
        print(f"    Motivo: {result.get('reason')}")

        conflicting = result.get("conflicting_oirs", [])
        if conflicting:
            print(f"\n    OIRs encontradas na área ({len(conflicting)}):")
            for c in conflicting:
                print(f"      • ID: {c.get('id')}")
                print(f"        USS: {c.get('uss_base_url')}")
                print(f"        Prioridade do concorrente: {c.get('priority')}")
        else:
            print("\n    [✓] Nenhuma OIR encontrada na área.")

        if status == "created":
            oir = result.get("oir_created", {})
            print(f"\n[+] OIR CRIADA NO DSS:")
            print(f"    Local ID : {oir.get('local_id')}")
            print(f"    DSS ID   : {oir.get('dss_id')}")
            print(f"    DSS OVN  : {oir.get('dss_ovn')}")
            print(f"    Prioridade registrada : {oir.get('priority')}")
            
            # Print do JSON enviado (simulado, pois o service recebe os objetos)
            sent_json = {
                "area_of_interest": area_of_interest,
                "oir": oir_payload
            }
            print(f"\n[DEBUG] JSON ENVIADO AO SERVIÇO:")
            print(json.dumps(sent_json, indent=2))

    except Exception as e:
        print(f"\n[!] ERRO DURANTE O FLUXO: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
