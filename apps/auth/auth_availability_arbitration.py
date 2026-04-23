#!/usr/bin/env python3
"""Token para Arbitragem de Disponibilidade entre USSs."""
from apps.auth.auth_base import run_auth
from apps.dss_client.auth import UTMAuthority

if __name__ == "__main__":
    run_auth("Availability Arbitration", UTMAuthority.AVAILABILITY_ARBITRATION)
