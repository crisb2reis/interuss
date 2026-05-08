"""
OIRConstraintService — Orquestra o fluxo ASTM F3548-21:
"OIR próxima a Constraint"

Sequência implementada:
  1. USS → AUTH: GET /token?aud=core-service          (token para o DSS)
  2. USS → DSS:  POST /constraint_references/query     (constraints na área)
  3. USS → AUTH: GET /token?aud=<domínio do CP>        (token para cada CP)
  4. USS → CP:   GET /uss/v1/constraints/{id}          (detalhes da constraint)
  5. USS → DSS:  POST /operational_intent_references/query  (OIRs existentes)
  6. USS → DSS:  PUT  /operational_intent_references/{id}   (criar nova OIR)
  7. Salva OIR localmente no modelo OperationalIntent
"""
from apps.oir.models import IdentificationServiceArea
import logging
import urllib.parse
import uuid
import requests
from typing import Any, Optional

from django.conf import settings

from apps.dss_client.client import DSSClient
from apps.dss_client.exceptions import DSSConnectionError, DSSNotFoundError, DSSConflictError
from .models import OperationalIntent

logger = logging.getLogger(__name__)


# ─── Helpers compartilhados (candidatos a utils.py) ──────────────

def extract_subscription_id(ref: dict, result: dict) -> str:
    """Extrai subscription_id do ref DSS ou da lista de subscribers."""
    sub_id = ref.get("subscription_id")
    if not sub_id:
        subscribers = result.get("subscribers", [])
        sub_id = subscribers[0].get("subscription_id", "") if subscribers else ""
    return sub_id


def normalize_dss_time(time_field: Any) -> Optional[str]:
    """
    Normaliza o campo de tempo do DSS que pode vir como string RFC3339
    ou como objeto {'value': '...', 'format': 'RFC3339'}.
    Retorna a string do timestamp.
    """
    if not time_field:
        return None
    if isinstance(time_field, str):
        return time_field
    if isinstance(time_field, dict):
        return time_field.get("value")
    return str(time_field)


def _build_dss_oir_payload(
    oir_id: str,
    extents: list,
    uss_base_url: str,
    state: str,
    ovns: list,
) -> dict:
    """Monta o payload base para criação de OIR no DSS."""
    return dict(
        oir_id=oir_id,
        extents=extents,
        uss_base_url=uss_base_url,
        state=state,
        key=ovns or None,
        new_subscription={
            "uss_base_url": uss_base_url,
            "notify_for_operational_intents": True,
            "notify_for_constraints": True,
        },
    )


# ─── OIRConstraintService ─────────────────────────────────────────

class OIRConstraintService:
    DSS_AUDIENCE = "core-service"
    DSS_SCOPE    = "utm.strategic_coordination"

    def create_oir_near_constraint(
        self,
        area_of_interest: dict,
        oir_payload: dict,
    ) -> dict:
        uss_base_url = oir_payload.get("uss_base_url", getattr(settings, "USS_BASE_URL", ""))
        state        = oir_payload.get("state", "Accepted")
        extents      = oir_payload["extents"]

        # Etapa 2: Consultar constraints
        client_constraints = self._build_dss_client(scope="utm.constraint_processing")
        logger.info("[OIR-Constraint] Etapa 2/6: Consultando constraints no DSS...")
        logger.debug("[ASTM] POST /dss/v1/constraint_references/query")

        constraint_result = client_constraints.query_constraint_references(area_of_interest)
        constraint_refs   = constraint_result.get("constraint_references", [])
        logger.info("[OIR-Constraint] %d constraint(s) encontrada(s).", len(constraint_refs))

        # Etapas 3 & 4: Buscar detalhes de cada constraint no CP
        constraint_details = []
        for ref in constraint_refs:
            detail = self._fetch_constraint_detail(
                client_constraints,
                ref.get("id", ""),
                ref.get("uss_base_url", ""),
            )
            if detail:
                constraint_details.append(detail)

        # Etapa 5: Consultar OIRs existentes na área
        client_oir = self._build_dss_client(scope="utm.strategic_coordination")
        logger.info("[OIR-Constraint] Etapa 5/6: Consultando OIRs existentes...")
        logger.debug("[ASTM] POST /dss/v1/operational_intent_references/query")

        oir_query_result = client_oir.query_operational_intent_references(area_of_interest)
        existing_oirs    = oir_query_result.get("operational_intent_references", [])
        logger.info("[OIR-Constraint] %d OIR(s) encontrada(s).", len(existing_oirs))

        # Coletar OVNs de constraints + OIRs existentes
        ovns = [r["ovn"] for r in constraint_refs + existing_oirs if r.get("ovn")]
        if ovns:
            logger.info("[OIR-Constraint] %d OVN(s) coletados para campo 'key'.", len(ovns))

        # Etapa 6: Criar OIR no DSS (com retry em caso de 409)
        new_oir_id = str(uuid.uuid4())
        logger.info("[OIR-Constraint] Etapa 6/6: Criando OIR %s...", new_oir_id)
        logger.debug("[ASTM] PUT /dss/v1/operational_intent_references/%s", new_oir_id)

        dss_result = self._create_oir_with_retry(
            client_constraints=client_constraints,
            client_oir=client_oir,
            new_oir_id=new_oir_id,
            extents=extents,
            uss_base_url=uss_base_url,
            state=state,
            ovns=ovns,
            constraint_refs=constraint_refs,
            constraint_details=constraint_details,
        )

        # Etapa 7: Salvar localmente
        ref_dss = dss_result.get("operational_intent_reference", {})
        oir = OperationalIntent.objects.create(
            id=new_oir_id,
            state=state,
            uss_base_url=uss_base_url,
            extents=extents,
            dss_id=ref_dss.get("id", new_oir_id),
            dss_ovn=ref_dss.get("ovn", ""),
            subscription_id=extract_subscription_id(ref_dss, dss_result),
            dss_response=dss_result,
        )
        logger.info("[OIR-Constraint] OIR %s salva. dss_id=%s ovn=%s.", oir.id, oir.dss_id, oir.dss_ovn)

        return {
            "constraints_found":      constraint_refs,
            "constraint_details":     constraint_details,
            "existing_oirs_in_area":  existing_oirs,
            "oir_created": {
                "local_id":        str(oir.id),
                "dss_id":          oir.dss_id,
                "dss_ovn":         oir.dss_ovn,
                "state":           oir.state,
                "uss_base_url":    oir.uss_base_url,
                "subscribers":     dss_result.get("subscribers", []),
                "conflicting_oirs": dss_result.get("conflicting_oirs", []),
            },
        }

    # ─── Helpers privados ────────────────────────────────────────

    def _build_dss_client(self, scope: str = None) -> DSSClient:
        return DSSClient(
            intended_audience=self.DSS_AUDIENCE,
            scope=scope or self.DSS_SCOPE,
            auto_authenticate=True,
        )

    def _fetch_constraint_detail(
        self,
        client: DSSClient,
        constraint_id: str,
        cp_uss_base_url: str,
        source: str = "initial_query",
    ) -> dict | None:
        """Busca detalhes de uma constraint no CP. Retorna None se dados insuficientes."""
        if not constraint_id or not cp_uss_base_url:
            return None

        cp_audience = urllib.parse.urlparse(cp_uss_base_url).netloc or cp_uss_base_url
        logger.info(
            "[OIR-Constraint] [Etapa 3&4] Buscando constraint %s | audience=%s",
            constraint_id, cp_audience,
        )
        logger.debug("[ASTM] [P2P] GET %s/uss/v1/constraints/%s", cp_uss_base_url, constraint_id)

        base = {"id": constraint_id, "uss_base_url": cp_uss_base_url,
                "cp_audience": cp_audience, "source": source}
        try:
            details = client.get_constraint_details_from_provider(
                constraint_id=constraint_id,
                cp_uss_base_url=cp_uss_base_url,
            )
            logger.info("[OIR-Constraint] Constraint %s obtida com sucesso.", constraint_id)
            return {**base, "details": details}
        except DSSNotFoundError:
            logger.warning("[OIR-Constraint] Constraint %s não encontrada no CP.", constraint_id)
            return {**base, "details": None, "error": "não encontrada no CP"}
        except Exception as exc:
            logger.error("[OIR-Constraint] Erro ao buscar constraint %s: %s", constraint_id, exc)
            return {**base, "details": None, "error": str(exc)}

    def _create_oir_with_retry(
        self,
        client_constraints: DSSClient,
        client_oir: DSSClient,
        new_oir_id: str,
        extents: list,
        uss_base_url: str,
        state: str,
        ovns: list,
        constraint_refs: list,
        constraint_details: list,
    ) -> dict:
        """Tenta criar a OIR no DSS; em caso de 409 atualiza OVNs e tenta novamente."""
        payload = _build_dss_oir_payload(new_oir_id, extents, uss_base_url, state, ovns)

        try:
            return client_oir.create_operational_intent_reference(**payload)

        except DSSConflictError as exc:
            logger.warning("[OIR-Constraint] Conflito 409. Coletando referências faltantes...")
            missing_refs = getattr(exc, "conflicting_references", [])

            for ref in missing_refs:
                # Adiciona OVN faltante
                if ref.get("ovn") and ref["ovn"] not in ovns:
                    ovns.append(ref["ovn"])

                # Busca detalhes da constraint faltante (etapas 3&4 do diagrama ASTM)
                m_id, m_url = ref.get("id", ""), ref.get("uss_base_url", "")
                if m_id and m_url and not any(d["id"] == m_id for d in constraint_details):
                    detail = self._fetch_constraint_detail(
                        client_constraints, m_id, m_url, source="409_conflict"
                    )
                    if detail:
                        constraint_details.append(detail)

                if m_id and not any(r.get("id") == m_id for r in constraint_refs):
                    constraint_refs.append(ref)

            if not ovns:
                raise  # preserva traceback original

            logger.info("[OIR-Constraint] Re-tentando com %d OVN(s)...", len(ovns))
            payload = _build_dss_oir_payload(new_oir_id, extents, uss_base_url, state, ovns)
            return client_oir.create_operational_intent_reference(**payload)


# ─── ISAService ───────────────────────────────────────────────────

class ISAService:

    @staticmethod
    def create_or_update_from_oir(oir: "OperationalIntent") -> "IdentificationServiceArea":
        from .models import IdentificationServiceArea

        extents_list = oir.extents if isinstance(oir.extents, list) else [oir.extents]
        isa_extents  = extents_list[0] if extents_list else {}

        isa, created = IdentificationServiceArea.objects.update_or_create(
            operational_intent=oir,
            defaults={
                "dss_id":       oir.dss_id,
                "uss_base_url": oir.uss_base_url,
                "extents":      isa_extents,
            },
        )
        logger.info("ISA %s %s a partir da OIR %s.", isa.id, "criado" if created else "atualizado", oir.id)

        try:
            dss_result  = ISAService.register_in_dss(isa)
            isa.refresh_from_db()  # garante dss_version atualizado em memória
            subscribers = dss_result.get("subscribers", [])
            logger.info(
                "ISA %s registrado no DSS. version=%s subscribers=%d",
                isa.dss_id,
                dss_result.get("service_area", {}).get("version"),
                len(subscribers),
            )
            if subscribers:
                ISAService.notify_subscribers(isa, subscribers)
        except Exception as exc:
            logger.warning("Falha ao registrar ISA no DSS F3411: %s", exc)

        return isa

    @staticmethod
    def notify_subscribers(isa: "IdentificationServiceArea", subscribers: list) -> None:
        if not subscribers:
            return

        try:
            token   = ISAService._build_rid_client("rid.service_provider").token
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            payload = {
                "service_area": {
                    "id":          isa.dss_id,
                    "uss_base_url": isa.uss_base_url,
                    "version":     isa.dss_version or "",
                },
                "extents":       isa.extents,
                "subscriptions": [],
            }

            for subscriber in subscribers:
                sub_url = subscriber.get("uss_base_url", "").rstrip("/")
                if not sub_url:
                    continue
                notify_url = f"{sub_url}/uss/identification_service_areas/{isa.dss_id}"
                try:
                    r = requests.post(notify_url, json=payload, headers=headers, timeout=10)
                    logger.info("Subscriber %s notificado: HTTP %s", sub_url, r.status_code)
                except Exception as exc:
                    logger.warning("Falha ao notificar subscriber %s: %s", sub_url, exc)

        except Exception as exc:
            logger.error("Falha ao preparar notificações: %s", exc)

    @staticmethod
    def _build_rid_client(scope: str) -> DSSClient:
        return DSSClient(intended_audience="core-service", scope=scope, auto_authenticate=True)

    @staticmethod
    def query_dss(area: str, earliest_time: str, latest_time: str) -> dict:
        client = ISAService._build_rid_client("rid.display_provider")
        return client.query_identification_service_areas(
            area=area, earliest_time=earliest_time, latest_time=latest_time
        )

    @staticmethod
    def register_in_dss(isa: "IdentificationServiceArea") -> dict:
        client = ISAService._build_rid_client("rid.service_provider")
        result = client.create_identification_service_area(
            isa_id=str(isa.dss_id),
            extents=isa.extents,
            uss_base_url=isa.uss_base_url,
        )
        version = result.get("service_area", {}).get("version")
        if version:
            from .models import IdentificationServiceArea
            IdentificationServiceArea.objects.filter(pk=isa.pk).update(dss_version=version)
        return result