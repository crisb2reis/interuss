import logging
from django.conf import settings
from .models import FlightPlan, OperationalIntent, State
from apps.dss_client.client import DSSClient
from apps.dss_client.auth import ICEAAuthenticator, UTMAuthority
from apps.dss_client.exceptions import DSSConflictError, DSSNotFoundError

logger = logging.getLogger(__name__)


class OperationalIntentService:
    """
    Orquestra a criação e atualização de Intenções Operacionais no USS e no DSS.
    Em conformidade com ASTM F3548-22.
    """

    @staticmethod
    def _build_client() -> DSSClient:
        """Instancia o DSSClient com token de coordenação estratégica."""
        authenticator = ICEAAuthenticator()
        token = authenticator.get_token(
            intended_audience="core-service",
            scope=UTMAuthority.STRATEGIC_COORDINATION,
        )
        return DSSClient(token=token)

    @staticmethod
    def _build_extents(intent: OperationalIntent) -> list:
        """Converte o volume PostGIS em payload de extents para o DSS."""
        coords = intent.flight_plan.volume.coords[0][:-1]  # Exclui vértice duplicado
        return [{
            "volume": {
                "outline_polygon": {
                    "vertices": [{"lat": v[1], "lng": v[0]} for v in coords]
                },
                "altitude_lower": {"value": 0, "reference": "W84", "units": "M"},
                "altitude_upper": {"value": 120, "reference": "W84", "units": "M"},
            },
            "time_start": {
                "value": intent.flight_plan.start_time.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + "Z",
                "format": "RFC3339",
            },
            "time_end": {
                "value": intent.flight_plan.end_time.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + "Z",
                "format": "RFC3339",
            },
        }]

    @staticmethod
    def create_operational_intent(flight_plan_id: str):
        """
        Registra um FlightPlan existente no DSS como OIR.

        1. Consulta constraints na área (ASTM § 4.3.1)
        2. Faz discovery das OIRs vizinhas para coletar OVNs (chaves)
        3. Submete a nova OIR ao DSS (create — sem OVN)
        4. Persiste a resposta local (dss_id, ovn, subscription_id)

        Returns:
            (intent, result_dict)
        Raises:
            DSSConflictError: se o DSS reportar conflito 409
        """
        fp: FlightPlan = FlightPlan.objects.get(pk=flight_plan_id)

        intent, _ = OperationalIntent.objects.get_or_create(
            flight_plan=fp,
            defaults={"state": State.ACCEPTED},
        )

        client = OperationalIntentService._build_client()
        extents = OperationalIntentService._build_extents(intent)
        area = extents[0]  # Usa o primerio extent como área de interesse

        # 1. Consulta constraints
        try:
            constraints = client.query_constraint_references(area)
            if constraints.get("constraint_references"):
                logger.warning(
                    "Constraints encontradas na área do FlightPlan %s: %d",
                    flight_plan_id, len(constraints["constraint_references"]),
                )
        except Exception as exc:
            logger.warning("Falha ao consultar constraints: %s", exc)

        # 2. Discovery de OIRs vizinhas — coleta OVNs
        keys = []
        try:
            neighbor_result = client.query_operational_intent_references(area)
            for oir in neighbor_result.get("operational_intent_references", []):
                if oir.get("ovn"):
                    keys.append(oir["ovn"])
            if keys:
                logger.info(
                    "%d OIRs vizinhas encontradas. Adicionando chaves ao payload.", len(keys)
                )
        except Exception as exc:
            logger.warning("Falha ao consultar OIRs vizinhas: %s", exc)

        # 3. Submissão ao DSS (create — sem OVN na URL)
        result = client.create_operational_intent_reference(
            oir_id=str(fp.id),
            extents=extents,
            uss_base_url=settings.USS_BASE_URL,
            state="Accepted",
            key=keys,
        )

        # 4. Persiste resposta
        dss_ref = result.get("operational_intent_reference", {})
        intent.dss_id = dss_ref.get("id", "")
        intent.version = dss_ref.get("version", 0)
        intent.ovn = dss_ref.get("ovn", "")
        intent.subscription_id = dss_ref.get("subscription_id", "")
        intent.save()

        logger.info("OIR sincronizada com sucesso. DSS ID: %s | OVN: %s", intent.dss_id, intent.ovn)
        return intent, result

    @staticmethod
    def update_operational_intent(flight_plan_id: str):
        """
        Atualiza uma OIR já registrada no DSS usando o OVN corrente.
        PUT /dss/v1/operational_intent_references/{entityid}/{ovn}
        """
        intent = OperationalIntent.objects.get(flight_plan_id=flight_plan_id)

        if not intent.ovn:
            raise ValueError("OVN não disponível — crie a OIR primeiro.")

        client = OperationalIntentService._build_client()
        extents = OperationalIntentService._build_extents(intent)

        result = client.update_operational_intent_reference(
            oir_id=str(intent.flight_plan.id),
            ovn=intent.ovn,
            extents=extents,
            uss_base_url=settings.USS_BASE_URL,
            state=intent.state.capitalize(),
        )

        dss_ref = result.get("operational_intent_reference", {})
        intent.version = dss_ref.get("version", intent.version)
        intent.ovn = dss_ref.get("ovn", intent.ovn)
        intent.save()

        logger.info("OIR atualizada. DSS ID: %s | OVN: %s", intent.dss_id, intent.ovn)
        return intent, result

    @staticmethod
    def delete_operational_intent(flight_plan_id: str) -> bool:
        """
        Remove uma OIR do DSS.
        DELETE /dss/v1/operational_intent_references/{entityid}/{ovn}
        """
        try:
            intent = OperationalIntent.objects.get(flight_plan_id=flight_plan_id)
        except OperationalIntent.DoesNotExist:
            logger.warning("OperationalIntent para FlightPlan %s não encontrada.", flight_plan_id)
            return False

        if intent.ovn:
            client = OperationalIntentService._build_client()
            try:
                client.delete_operational_intent_reference(
                    oir_id=str(intent.flight_plan.id),
                    ovn=intent.ovn,
                )
            except DSSNotFoundError:
                logger.warning("OIR %s não encontrada no DSS; removendo apenas localmente.", intent.dss_id)

        intent.delete()
        return True
