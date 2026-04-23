#!/usr/bin/env python3
"""Token para Coordenação Estratégica (OIR / gestão de intenções operacionais)."""
from apps.auth.auth_base import run_auth
from apps.dss_client.auth import UTMAuthority

if __name__ == "__main__":
    run_auth("Strategic Coordination", UTMAuthority.STRATEGIC_COORDINATION)
