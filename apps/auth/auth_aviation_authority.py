#!/usr/bin/env python3
"""Token para Autoridade de Aviação (regulador ICEA)."""
from apps.auth.auth_base import run_auth
from apps.dss_client.auth import UTMAuthority

if __name__ == "__main__":
    run_auth("Aviation Authority", UTMAuthority.AVIATION_AUTHORITY)
