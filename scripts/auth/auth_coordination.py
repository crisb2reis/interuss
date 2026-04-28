#!/usr/bin/env python3
from auth_base import run_auth
from apps.dss_client.auth import UTMAuthority

if __name__ == "__main__":
    # Script focado em Strategic Coordination (Coordenação Estratégica)
    run_auth("Strategic Coordination", UTMAuthority.STRATEGIC_COORDINATION)
