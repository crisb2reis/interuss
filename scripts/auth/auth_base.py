#!/usr/bin/env python3
import os
import sys
import jwt
import urllib3
from datetime import datetime

# Desabilitar avisos de SSL (Sandbox)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Adicionar o diretório do projeto ao PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configurar o Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django
django.setup()

from apps.dss_client.auth import ICEAAuthenticator
from django.conf import settings

def run_auth(scope_name, scope_value):
    print("\n" + "="*60)
    print(f"  USS AUTH: {scope_name}")
    print("="*60 + "\n")

    try:
        authenticator = ICEAAuthenticator()
        audience = "core-service"
        
        print(f"[*] Solicitando token...")
        print(f"[*] Audience: {audience}")
        print(f"[*] Scope:    {scope_value}")
        
        token = authenticator.get_token(
            intended_audience=audience,
            scope=scope_value
        )
        
        print("\n[+] Token obtido com sucesso!")
        print("-" * 60)
        print(f"JWT: {token}")
        print("-" * 60)
        
        payload = jwt.decode(token, options={"verify_signature": False})
        
        print("\nDetalhamento:")
        print(f"  - Subject (sub): {payload.get('sub')}")
        print(f"  - Escopo (scope): {payload.get('scope')}")
        
        exp_ts = payload.get('exp')
        if exp_ts:
            exp_date = datetime.fromtimestamp(exp_ts)
            print(f"  - Expira em:     {exp_date.strftime('%Y-%m-%d %H:%M:%S')}")
            
    except Exception as e:
        print(f"\n[!] ERRO NA AUTENTICAÇÃO: {str(e)}")
        sys.exit(1)
