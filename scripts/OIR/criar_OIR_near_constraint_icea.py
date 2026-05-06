#!/usr/bin/env python3
"""
Script de teste para o fluxo ASTM F3548-21: "OIR próxima a Constraint"
Cenário: ICEA (Coordenadas e Horários Específicos)

Sequência executada:
  1. USS → AUTH: GET /token?aud=core-service
  2. USS → DSS:  POST /constraint_references/query     (constraints na área)
  3. USS → AUTH: GET /token?aud=<domínio do CP>         (token para cada CP)
  4. USS → CP:   GET /uss/v1/constraints/{id}           (detalhes da constraint)
  5. USS → DSS:  POST /operational_intent_references/query
  6. USS → DSS:  PUT  /operational_intent_references/{id}
"""

import os
import sys
import json
import urllib.parse

# Adicionar o diretório do projeto ao PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Configurar o Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django
django.setup()

from django.conf import settings
from apps.oir.services import OIRConstraintService


def main():
    print("\n" + "=" * 65)
    print("  FLUXO: OIR PRÓXIMA A CONSTRAINT - CENÁRIO ICEA")
    print("=" * 65 + "\n")

    # ── Parâmetros fornecidos pelo usuário ────────────────────────────────
    
    # Horários fixos conforme solicitado
    from datetime import timedelta
    from django.utils import timezone
    now = timezone.now()
    start_dt = now + timedelta(minutes=3)
    end_dt = now + timedelta(minutes=40)
    time_start = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    time_end = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Vértices do polígono 
    vertices = [
        {"lat": -23.213767186500263, "lng": -45.877224550908124},
        {"lat": -23.218601668979545, "lng": -45.877224550908124},
        {"lat": -23.218601668979545, "lng": -45.8677017825556},
        {"lat": -23.213767186500263, "lng": -45.8677017825556}
    ]

    # Área de Interesse (AOI)
    area_of_interest = {
        "volume": {
            "outline_polygon": {
                "vertices": vertices
            },
            "altitude_lower": {"value": 600, "reference": "W84", "units": "M"},
            "altitude_upper": {"value": 700, "reference": "W84", "units": "M"}
        },
        "time_start": {"format": "RFC3339", "value": time_start},
        "time_end": {"format": "RFC3339", "value": time_end}
    }

    # Dados da OIR (usando a mesma área para o teste de overlap/near constraint)
    oir_payload = {
        "extents": [
            {
                "volume": {
                    "outline_polygon": {
                        "vertices": vertices
                    },
                    "altitude_lower": {"value": 600, "units": "M", "reference": "W84"},
                    "altitude_upper": {"value": 700, "units": "M", "reference": "W84"},
                },
                "time_start": {"value": time_start, "format": "RFC3339"},
                "time_end":   {"value": time_end,   "format": "RFC3339"},
            }
        ],
        "state": "Accepted",
    }

    print(f"[*] Operação ASTM: PUT /dss/v1/operational_intent_references/{{entityid}}")
    print("[*] Iniciando fluxo via OIRConstraintService...")
    print(f"Cenário: ICEA (São José dos Campos)")
    print(f"Horário: {time_start} até {time_end}")

    try:
        service = OIRConstraintService()
        result = service.create_oir_near_constraint(
            area_of_interest=area_of_interest,
            oir_payload=oir_payload,
        )

        # ── Resultados ───────────────────────────────────────────────────
        print("\n[+] FLUXO CONCLUÍDO COM SUCESSO!")
        print("-" * 65)

        constraints = result["constraints_found"]
        print(f"\n[2] Constraints encontradas no DSS: {len(constraints)}")
        for c in constraints:
            print(f"    • ID: {c.get('id')} | CP: {c.get('uss_base_url')}")

        details = result["constraint_details"]
        print(f"\n[3/4] Detalhes coletados nos CPs: {len(details)}")
        for d in details:
            status_str = "OK" if d["details"] else f"ERRO: {d.get('error', '?')}"
            print(f"    • {d['id']} → {status_str}")

        existing = result["existing_oirs_in_area"]
        print(f"\n[5] OIRs existentes na área: {len(existing)}")
        for o in existing:
            print(f"    • ID: {o.get('id')} | USS: {o.get('uss_base_url')}")

        oir = result["oir_created"]
        dss_domain = urllib.parse.urlparse(settings.DSS_BASE_URL).netloc

        print(f"\n[6] OIR criada no DSS:")
        print(f"    DSS Domain: {dss_domain}")
        print(f"    OVN       : {oir['dss_ovn']}")
        
        if constraints:
            print(f"    Restrições Reconhecidas ({len(constraints)}):")
            for c in constraints:
                print(f"      • ID: {c.get('id')}")
                print(f"        CP: {c.get('uss_base_url')}")
        else:
            print("    Restrições Reconhecidas: Nenhuma")

        print(f"    Local ID  : {oir['local_id']}")
        print(f"    DSS ID    : {oir['dss_id']}")
        print(f"    Estado    : {oir['state']}")
        print(f"    USS URL   : {oir['uss_base_url']}")
        print(f"    Subscribers: {len(oir.get('subscribers', []))}")

        conflitos = oir.get("conflicting_oirs", [])
        if conflitos:
            print(f"\n    [!] {len(conflitos)} OIR(s) conflitante(s) detectada(s):")
            for cf in conflitos:
                print(f"        - {cf.get('id')} (USS: {cf.get('uss_base_url')})")
        else:
            print("\n    [✓] Sem conflitos com outras OIRs na área.")

        # ─── CRIAR FLIGHT PLAN LOCALMENTE PARA A UI E ATIVAÇÃO ───
        from apps.flight_plans.models import FlightPlan, State, OperationalIntent
        from django.contrib.gis.geos import Polygon
        
        poly = Polygon((
            (vertices[0]["lng"], vertices[0]["lat"], 0.0),
            (vertices[1]["lng"], vertices[1]["lat"], 0.0),
            (vertices[2]["lng"], vertices[2]["lat"], 0.0),
            (vertices[3]["lng"], vertices[3]["lat"], 0.0),
            (vertices[0]["lng"], vertices[0]["lat"], 0.0),
        ))

        astm_payload = {
            "flight_plan": {
                "basic_information": {
                    "usage_state": "Planned",
                    "uas_state": "Nominal",
                    "area": [oir_payload["extents"][0]],
                }
            }
        }
        
        fp = FlightPlan.objects.create(
            id=oir['dss_id'],
            state=State.ACCEPTED,
            priority=1,
            start_time=start_dt,
            end_time=end_dt,
            volume=poly,
            uss_base_url=settings.USS_BASE_URL,
            astm_payload=astm_payload
        )
        
        sub_id = ""
        if oir.get('subscribers'):
            sub_id = oir['subscribers'][0].get('subscription_id', '')
            
        OperationalIntent.objects.create(
            flight_plan=fp,
            dss_id=oir['dss_id'],
            version=1,
            state=State.ACCEPTED,
            ovn=oir['dss_ovn'],
            subscription_id=sub_id
        )
        
        print(f"\n    [+] FlightPlan local associado (UI) salvo com ID: {oir['dss_id']}")

        print("\n" + "=" * 65)
        print("  FLUXO CONCLUÍDO!")
        print("=" * 65 + "\n")

    except Exception as e:
        print(f"\n[!] ERRO DURANTE O FLUXO: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
