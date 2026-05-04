#!/usr/bin/env python3
"""
Script de teste para o fluxo completo ASTM F3548-21:
"OIR próxima a Constraint"

Sequência executada:
  1. USS → AUTH: GET /token?aud=core-service
  2. USS → DSS:  POST /constraint_references/query     (constraints na área)
  3. USS → AUTH: GET /token?aud=<domínio do CP>         (token para cada CP)
  4. USS → CP:   GET /uss/v1/constraints/{id}           (detalhes da constraint)
  5. USS → DSS:  POST /operational_intent_references/query
  6. USS → DSS:  PUT  /operational_intent_references/{id}  → Sucesso
"""

import os
import sys
import json
import urllib.parse
from datetime import datetime, timedelta

# Adicionar o diretório do projeto ao PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Configurar o Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django
django.setup()

from django.utils import timezone
from django.conf import settings
from apps.oir.services import OIRConstraintService


def main():
    print("\n" + "=" * 65)
    print("  FLUXO: OIR PRÓXIMA A CONSTRAINT (ASTM F3548-21)")
    print("=" * 65 + "\n")

    # Define o horário do voo: iniciando em 1 hora e durando 30 minutos.
    now = datetime.utcnow()
    start = now + timedelta(hours=1)
    end = start + timedelta(minutes=30)

    # ── Área de interesse (São Paulo) ────────────────────────────────────
    area_of_interest = {
        "volume": {
            "outline_polygon": {
                "vertices": [
                    {"lat": -23.209038292043147, "lng": -45.87052417963366},
                    {"lat": -23.209710788866886, "lng": -45.86979246585125},
                    {"lat": -23.208980318021133, "lng": -45.86893459452031},
                    {"lat": -23.20842376612441, "lng": -45.869754618586796},
                ]
            },
            "altitude_lower": {"value": 600,   "units": "M", "reference": "W84"},
            "altitude_upper": {"value": 700, "units": "M", "reference": "W84"},
        },
        "time_start": {"value": start.strftime("%Y-%m-%dT%H:%M:%SZ"), "format": "RFC3339"},
        "time_end":   {"value": end.strftime("%Y-%m-%dT%H:%M:%SZ"),   "format": "RFC3339"},
    }

    # ── Dados da OIR a criar ─────────────────────────────────────────────
    oir_payload = {
        "extents": [
            {
                "volume": {
                    "outline_polygon": {
                        "vertices": [
                            {"lat": -23.5505, "lng": -47.6333},
                            {"lat": -23.5505, "lng": -47.6233},
                            {"lat": -23.5405, "lng": -47.6233},
                            {"lat": -23.5405, "lng": -47.6333},
                        ]
                    },
                    "altitude_lower": {"value": 0,   "units": "M", "reference": "W84"},
                    "altitude_upper": {"value": 500, "units": "M", "reference": "W84"},
                },
                "time_start": {"value": start.strftime("%Y-%m-%dT%H:%M:%SZ"), "format": "RFC3339"},
                "time_end":   {"value": end.strftime("%Y-%m-%dT%H:%M:%SZ"),   "format": "RFC3339"},
            }
        ],
        "state": "Accepted",
    }

    print(f"[*] Operação ASTM: PUT /dss/v1/operational_intent_references/{{entityid}}")
    print("[*] Iniciando fluxo via OIRConstraintService...")
    print("Área: São José dos Campos")

    try:
        service = OIRConstraintService()
        result = service.create_oir_near_constraint(
            area_of_interest=area_of_interest,
            oir_payload=oir_payload,
        )

        # ── Resultados ───────────────────────────────────────────────────
        print("\n[+] FLUXO CONCLUÍDO COM SUCESSO!")
        print("-" * 65)

        # ── [2] Constraints encontradas no DSS ──────────────────────────
        # Mostra as referências de restrições de espaço aéreo encontradas.
        constraints = result["constraints_found"]
        print(f"\n[2] Constraints encontradas no DSS: {len(constraints)}")
        for c in constraints:
            print(f"    • ID: {c.get('id')} | CP: {c.get('uss_base_url')}")

        # ── [3/4] Detalhes coletados nos CPs ────────────────────────────
        # Mostra o resultado da comunicação USS-to-USS com os Constraint Providers.
        details = result["constraint_details"]
        print(f"\n[3/4] Detalhes coletados nos CPs: {len(details)}")
        for d in details:
            status_str = "OK" if d["details"] else f"ERRO: {d.get('error', '?')}"
            print(f"    • {d['id']} → {status_str}")

        # ── [5] OIRs existentes na área ─────────────────────────────────
        # Mostra outros planos de voo de outros USSs que sobrepõem nossa área.
        existing = result["existing_oirs_in_area"]
        print(f"\n[5] OIRs existentes na área: {len(existing)}")
        for o in existing:
            print(f"    • ID: {o.get('id')} | USS: {o.get('uss_base_url')}")

        # ── [6] OIR criada no DSS ───────────────────────────────────────
        # Confirmação de que nossa intenção operacional foi registrada com sucesso.
        oir = result["oir_created"]
        dss_domain = urllib.parse.urlparse(settings.DSS_BASE_URL).netloc

        print(f"\n[6] OIR criada no DSS:")
        print(f"    DSS Domain: {dss_domain}")
        print(f"    OVN       : {oir['dss_ovn']}")
        
        # Agrupa as constraints reconhecidas de forma mais clara
        constraints = result.get("constraints_found", [])
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

        # Mostra se houve conflito direto (overlap) com outras intenções operacionais.
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
        
        oir_verts = oir_payload["extents"][0]["volume"]["outline_polygon"]["vertices"]
        poly = Polygon((
            (oir_verts[0]["lng"], oir_verts[0]["lat"], 0.0),
            (oir_verts[1]["lng"], oir_verts[1]["lat"], 0.0),
            (oir_verts[2]["lng"], oir_verts[2]["lat"], 0.0),
            (oir_verts[3]["lng"], oir_verts[3]["lat"], 0.0),
            (oir_verts[0]["lng"], oir_verts[0]["lat"], 0.0),
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
            start_time=start,
            end_time=end,
            volume=poly,
            uss_base_url=getattr(settings, "USS_BASE_URL", "http://api.dev.br-utm.org"),
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
