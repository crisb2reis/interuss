#!/usr/bin/env python3
"""
auth_base.py — Função base reutilizada por todos os scripts de autenticação do USS.

Uso:
    from apps.auth.auth_base import run_auth
    from apps.dss_client.auth import UTMAuthority

    run_auth("Strategic Coordination", UTMAuthority.STRATEGIC_COORDINATION)

Execute a partir da raiz do projeto:
    python3 -m apps.auth.auth_strategic_coordination
"""
import os
import sys
from datetime import datetime
import jwt
import urllib3

# Desabilitar avisos de SSL (Sandbox)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Garante que a raiz do projeto está no PYTHONPATH
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Configura o Django antes de importar modelos/settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")

import django
django.setup()

from apps.dss_client.auth import ICEAAuthenticator  # noqa: E402


def run_auth(scope_name: str, scope_value: str, audience: str = "core-service") -> str:
    """
    Solicita um JWT para o AUTH do sandbox BR-UTM e imprime os detalhes na tela.

    Args:
        scope_name:  Nome legível do escopo (usado no log).
        scope_value: Valor do escopo ASTM (ex: "utm.strategic_coordination").
        audience:    intended_audience do token (padrão: "core-service").

    Returns:
        O token JWT obtido (string).
    """
    print("\n" + "=" * 60)
    print(f"  USS AUTH: {scope_name}")
    print("=" * 60 + "\n")

    try:
        authenticator = ICEAAuthenticator()

        print(f"[*] Solicitando token...")
        print(f"[*] Audience: {audience}")
        print(f"[*] Scope:    {scope_value}")

        token = authenticator.get_token(
            intended_audience=audience,
            scope=scope_value,
        )

        print("\n[+] Token obtido com sucesso!")
        print("-" * 60)
        print(f"JWT: {token}")
        print("-" * 60)

        payload = jwt.decode(token, options={"verify_signature": False})

        print("\nDetalhamento:")
        print(f"  - Subject  (sub):   {payload.get('sub')}")
        print(f"  - Audience (aud):   {payload.get('aud')}")
        print(f"  - Escopo   (scope): {payload.get('scope')}")

        exp_ts = payload.get("exp")
        if exp_ts:
            exp_date = datetime.fromtimestamp(exp_ts)
            print(f"  - Expira em:        {exp_date.strftime('%Y-%m-%d %H:%M:%S')}")

        return token

    except Exception as exc:
        print(f"\n[!] ERRO NA AUTENTICAÇÃO: {exc}")
        sys.exit(1)
