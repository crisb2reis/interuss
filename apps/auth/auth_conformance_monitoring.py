#!/usr/bin/env python3
"""Token para Monitoramento de Conformidade (Situational Awareness)."""
from apps.auth.auth_base import run_auth
from apps.dss_client.auth import UTMAuthority

if __name__ == "__main__":
    run_auth("Conformance Monitoring", UTMAuthority.CONFORMANCE_MONITORING_SA)
