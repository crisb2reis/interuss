#!/usr/bin/env python3
import sys
import uuid
import copy
import requests

BASE_URL = "http://localhost:8001/api"
TIMEOUT  = 10  # segundos

# Constantes de domínio
USAGE_STATE_IN_USE = "InUse"
ACTIVATION_PRIORITY = 8


def fetch_flight_plan(flight_plan_id: str) -> dict | None:
    """Busca o plano de voo pelo ID. Retorna o dict ou None se não encontrado."""
    url = f"{BASE_URL}/flight_plans/{flight_plan_id}/"
    try:
        resp = requests.get(url, timeout=TIMEOUT)
    except requests.RequestException as e:
        print(f"[!] Erro de rede ao buscar plano: {e}")
        return None

    if resp.status_code != 200:
        print(f"[!] Plano {flight_plan_id} não encontrado (HTTP {resp.status_code})")
        return None

    return resp.json()


def build_activation_payload(flight_plan_data: dict) -> dict | None:
    """Monta o payload de ativação a partir dos dados do plano. Retorna None se inválido."""
    astm_payload = flight_plan_data.get("astm_payload")
    if not astm_payload:
        print("[!] Payload ASTM original ausente no registro local.")
        return None

    # Trabalha em cópia para não mutar o objeto original
    payload = copy.deepcopy(astm_payload)
    payload["flight_plan"]["basic_information"]["usage_state"] = USAGE_STATE_IN_USE
    payload["flight_plan"]["priority"] = ACTIVATION_PRIORITY
    return payload


def activate_flight_plan(flight_plan_id: str, payload: dict) -> bool:
    """Envia o PUT de ativação. Retorna True se bem-sucedido."""
    url = f"{BASE_URL}/flight_plans/{flight_plan_id}/"
    print(f"[*] Operação ASTM: PUT /dss/v1/operational_intent_references/{{entityid}}/{{ovn}}")
    print("[*] Enviando requisição de ativação...")

    try:
        resp = requests.put(url, json=payload, timeout=TIMEOUT)
    except requests.RequestException as e:
        print(f"[!] Erro de rede ao ativar plano: {e}")
        return False

    if resp.status_code in (200, 201):
        result = resp.json()
        print(f"\n[+] ATIVAÇÃO BEM-SUCEDIDA")
        print(f"    Resultado : {result.get('planning_result')}")
        print(f"    Notas     : {result.get('notes')}")
        return True

    print(f"\n[!] Falha na ativação (HTTP {resp.status_code})")
    print(f"    Detalhes: {resp.text}")
    return False


def verify_final_state(flight_plan_id: str) -> None:
    """Consulta e exibe o estado final do plano no USS."""
    url = f"{BASE_URL}/flight_plans/{flight_plan_id}/"
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        state = resp.json().get("state", "desconhecido")
        print(f"    Estado final no USS: {state}")
    except (requests.RequestException, ValueError) as e:
        print(f"[!] Não foi possível verificar o estado final: {e}")


def update_and_activate(flight_plan_id: str) -> None:
    print(f"[*] Verificando Flight Plan: {flight_plan_id}")

    plan = fetch_flight_plan(flight_plan_id)
    if plan is None:
        return

    print(f"[+] Plano encontrado. Estado atual: {plan.get('state')}")

    payload = build_activation_payload(plan)
    if payload is None:
        return

    success = activate_flight_plan(flight_plan_id, payload)
    if success:
        verify_final_state(flight_plan_id)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python atualizar_e_ativar_fp.py <flight_plan_id>")
        sys.exit(1)

    fp_id = sys.argv[1]
    try:
        uuid.UUID(fp_id)
    except ValueError:
        print(f"[!] '{fp_id}' não é um UUID válido.")
        sys.exit(1)

    update_and_activate(fp_id)