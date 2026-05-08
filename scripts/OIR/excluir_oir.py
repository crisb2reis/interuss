#!/usr/bin/env python3
import sys
import uuid
import requests

BASE_URL = "http://localhost:8001/api"
TIMEOUT = 10  # segundos


def delete_flight_plan(flight_plan_id: str) -> None:
    """Envia um DELETE para excluir o Operational Intent (OIR) e o Flight Plan associado."""
    url = f"{BASE_URL}/flight_plans/{flight_plan_id}/"
    print(f"[*] Operação ASTM: DELETE {url}")
    print(f"[*] Solicitando exclusão do Flight Plan / OIR: {flight_plan_id}...")

    try:
        resp = requests.delete(url, timeout=TIMEOUT)
    except requests.RequestException as e:
        print(f"[!] Erro de rede ao tentar excluir o plano: {e}")
        return

    if resp.status_code == 200:
        print(f"\n[+] EXCLUSÃO BEM-SUCEDIDA (HTTP 200)")
        try:
            result = resp.json()
            print(f"    Resultado : {result.get('planning_result')}")
            print(f"    Notas     : {result.get('notes')}")
        except ValueError:
            pass
    elif resp.status_code == 404:
        print(f"\n[!] Falha na exclusão: Plano não encontrado (HTTP 404)")
        try:
            print(f"    Detalhes: {resp.json()}")
        except ValueError:
            pass
    elif resp.status_code == 409:
        print(f"\n[!] Falha na exclusão: Conflito (HTTP 409)")
        try:
            print(f"    Detalhes: {resp.json()}")
        except ValueError:
            pass
    else:
        print(f"\n[!] Falha na exclusão (HTTP {resp.status_code})")
        print(f"    Detalhes: {resp.text}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python excluir_oir.py <flight_plan_id>")
        sys.exit(1)

    fp_id = sys.argv[1]
    
    # Valida se é um UUID
    try:
        uuid.UUID(fp_id)
    except ValueError:
        print(f"[!] '{fp_id}' não é um UUID válido.")
        sys.exit(1)

    delete_flight_plan(fp_id)
