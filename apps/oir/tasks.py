from celery import shared_task
from django.utils.timezone import now
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

NONCONFORMING_TIMEOUT_SECONDS = 60

@shared_task(name="apps.oir.tasks.monitor_oir_conformance")
def monitor_oir_conformance():
    """
    Executa periodicamente para monitorar a conformidade das OIRs.
    - Se Activated e UA fora do volume -> Nonconforming.
    - Se Nonconforming e UA voltou ao volume -> Activated.
    - Se Nonconforming por mais de 60s -> Contingent.
    """
    from apps.oir.models import OperationalIntent
    from apps.oir.services import OIRStateTransitionService

    service = OIRStateTransitionService()

    # — Verifica OIRs Activated —
    activated_oirs = OperationalIntent.objects.filter(state="Activated")
    for oir in activated_oirs:
        try:
            if not service.check_conformance(oir):
                logger.warning(f"OIR {oir.id} saiu de conformidade. Movendo para Nonconforming.")
                service.transition_to(oir, "Nonconforming")
        except Exception as e:
            logger.error(f"Erro ao verificar conformidade da OIR {oir.id}: {e}")

    # — Verifica OIRs Nonconforming —
    nonconforming_oirs = OperationalIntent.objects.filter(state="Nonconforming")
    cutoff = now() - timedelta(seconds=NONCONFORMING_TIMEOUT_SECONDS)
    
    for oir in nonconforming_oirs:
        try:
            if service.check_conformance(oir):
                logger.info(f"OIR {oir.id} voltou à conformidade. Movendo para Activated.")
                service.transition_to(oir, "Activated")
            elif oir.nonconforming_since and oir.nonconforming_since <= cutoff:
                logger.error(f"OIR {oir.id} excedeu tempo em Nonconforming. Movendo para Contingent.")
                service.transition_to(oir, "Contingent")
        except Exception as e:
            logger.error(f"Erro ao verificar conformidade (NC) da OIR {oir.id}: {e}")
