#!/usr/bin/env python3
import requests
import sys
import uuid
import json

# URL base da nossa API local (ajuste se necessário)
BASE_URL = "http://api.dev.br-utm.org/uss-cristiano/api"

def update_and_activate(flight_plan_id):
    print(f"[*] Verificando existência do Flight Plan: {flight_plan_id}")
    
    # 1. Verificar se o ID existe via GET
    get_url = f"{BASE_URL}/flight_plans/{flight_plan_id}/"
    response = requests.get(get_url)
    
    if response.status_code != 200:
        print(f"[!] Erro: Plano de voo {flight_plan_id} não encontrado localmente (Status {response.status_code})")
        return

    flight_plan_data = response.json()
    print(f"[+] Plano encontrado. Estado atual: {flight_plan_data.get('state')}")

    # 2. Preparar payload para ativação
    # O backend salva o payload ASTM original em 'astm_payload'
    astm_payload = flight_plan_data.get('astm_payload')
    
    if not astm_payload:
        print("[!] Erro: Payload ASTM original não encontrado no registro local.")
        return

    # Mudar o estado para "InUse" para disparar a ativação (Activated) no DSS
    astm_payload['flight_plan']['basic_information']['usage_state'] = "InUse"
    astm_payload['flight_plan']['priority'] = 8

    print("[*] Enviando requisição de ativação (PUT)...")
    put_url = f"{BASE_URL}/flight_plans/{flight_plan_id}/"
    
    put_response = requests.put(put_url, json=astm_payload)
    
    if put_response.status_code in [200, 201]:
        result = put_response.json()
        print(f"\n[+] SUCESSO NA ATIVAÇÃO!")
        print(f"    Resultado: {result.get('planning_result')}")
        print(f"    Notas: {result.get('notes')}")
        
        # Verificar estado final
        check_res = requests.get(get_url).json()
        print(f"    Estado Final no USS: {check_res.get('state')}")
    else:
        print(f"\n[!] Falha na ativação.")
        print(f"    Status: {put_response.status_code}")
        print(f"    Detalhes: {put_response.text}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python atualizar_e_ativar_fp.py <flight_plan_id>")
        sys.exit(1)
        
    fp_id = sys.argv[1]
    try:
        uuid.UUID(fp_id)
    except ValueError:
        print(f"[!] Erro: '{fp_id}' não é um UUID válido.")
        sys.exit(1)
        
    update_and_activate(fp_id)
