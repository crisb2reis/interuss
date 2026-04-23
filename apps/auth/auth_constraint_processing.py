#!/usr/bin/env python3
"""Token para Processamento de Constraints por outros USSs."""
from apps.auth.auth_base import run_auth
from apps.dss_client.auth import UTMAuthority

if __name__ == "__main__":
    run_auth("Constraint Processing", UTMAuthority.CONSTRAINT_PROCESSING)
