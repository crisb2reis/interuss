#!/usr/bin/env python3
"""Token para Gerenciamento de Constraints (restrições de espaço aéreo)."""
from apps.auth.auth_base import run_auth
from apps.dss_client.auth import UTMAuthority

if __name__ == "__main__":
    run_auth("Constraint Management", UTMAuthority.CONSTRAINT_MANAGEMENT)
