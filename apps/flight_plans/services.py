import logging
from django.conf import settings
from .models import FlightPlan, OperationalIntent, State
from apps.dss_client.client import DSSClient
from apps.dss_client.auth import UTMAuthority
from apps.dss_client.exceptions import DSSConflictError, DSSNotFoundError

from apps.oir.models import IdentificationServiceArea, OperationalIntent as OirAppIntent
from apps.oir.services import ISAService
from .utils import extract_subscription_id

logger = logging.getLogger(__name__)


class OperationalIntentService:
    """
    Orquestra a criação e atualização de Intenções Operacionais no USS e no DSS.
    Em conformidade com ASTM F3548-22.
    """

    # Configurações de janela de tempo para consultas ao DSS (em minutos)
    DSS_QUERY_BUFFER_START = 15
    DSS_QUERY_BUFFER_END = 15
    
    # Placeholder de Subscription que deve ser ignorado
    PLACEHOLDER_SUB = "00000000-0000-4000-8000-000000000000"

    @staticmethod
    def _build_client(scope: str = UTMAuthority.STRATEGIC_COORDINATION) -> DSSClient:
        """Instancia o DSSClient autenticado para o escopo solicitado."""
        return DSSClient(
            intended_audience="core-service",
            scope=scope,
            auto_authenticate=True,
        )

    @staticmethod
    def _build_extents(intent: OperationalIntent, buffer_minutes_start=0, buffer_minutes_end=0) -> list:
        """
        Converte o volume PostGIS em payload de extents para o DSS.
        Opcionalmente adiciona um buffer temporal em minutos para consultas.
        """
        from datetime import timedelta
        
        start_time = intent.flight_plan.start_time - timedelta(minutes=buffer_minutes_start)
        end_time = intent.flight_plan.end_time + timedelta(minutes=buffer_minutes_end)
        
        coords = intent.flight_plan.volume.coords[0][:-1]
        
        # Extrai altitudes do payload ASTM original salvo, ou usa default se não existir
        alt_lower = {"value": 0, "reference": "W84", "units": "M"}
        alt_upper = {"value": 120, "reference": "W84", "units": "M"}
        try:
            if intent.flight_plan.astm_payload:
                area = intent.flight_plan.astm_payload.get("flight_plan", {}).get("basic_information", {}).get("area", [{}])[0]
                vol = area.get("volume", {})
                if "altitude_lower" in vol:
                    alt_lower = vol["altitude_lower"]
                if "altitude_upper" in vol:
                    alt_upper = vol["altitude_upper"]
        except Exception:
            pass

        return [{
            "volume": {
                "outline_polygon": {
                    "vertices": [{"lat": v[1], "lng": v[0]} for v in coords]
                },
                "altitude_lower": alt_lower,
                "altitude_upper": alt_upper,
            },
            "time_start": {
                "value": start_time.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + "Z",
                "format": "RFC3339",
            },
            "time_end": {
                "value": end_time.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + "Z",
                "format": "RFC3339",
            },
        }]

    @staticmethod
    def _submit_to_dss_with_retry(
        client_coord: DSSClient,
        oir_id: str,
        extents_real: list,
        state: str,
        keys: list,
        ovn: str = None,
        subscription_id: str = None,
        new_subscription: dict = None,
    ) -> dict:
        """
        Encapsula a chamada DSS (Create/Update), protegendo as chaves contra mutação silenciosa
        e contornando loops de retentativa 409 quando as chaves não são renovadas.
        """
        keys_local = list(keys)

        def _make_call(payload_com_chaves):
            if ovn:
                print(f"[*] [ASTM] PUT /dss/v1/operational_intent_references/{oir_id}/{ovn}")
                return client_coord.update_operational_intent_reference(**payload_com_chaves)
            else:
                print(f"[*] [ASTM] PUT /dss/v1/operational_intent_references/{oir_id}")
                return client_coord.create_operational_intent_reference(**payload_com_chaves)

        payload_base = {
            "oir_id": oir_id,
            "extents": extents_real,
            "uss_base_url": settings.USS_BASE_URL,
            "state": state,
        }
        
        if ovn:
            payload_base["ovn"] = ovn
            payload_base["subscription_id"] = subscription_id
            payload_base["new_subscription"] = new_subscription

        payload_base["key"] = keys_local

        try:
            return _make_call(payload_base)
        except DSSConflictError as exc:
            logger.info("Conflito 409 detectado. Coletando OVNs faltantes...")
            keys_before = set(keys_local)

            for ref in exc.conflicting_references:
                missing_ovn = ref.get("ovn")
                if missing_ovn and missing_ovn not in keys_local:
                    keys_local.append(missing_ovn)

            # Evita o loop infinito (quando o 409 não fornece novas chaves ou já temos todas)
            if not (set(keys_local) - keys_before):
                raise exc
            
            logger.info("Re-tentando submissão DSS com novas chaves adquiridas...")
            payload_com_novas_chaves = payload_base.copy()
            payload_com_novas_chaves["key"] = keys_local
            return _make_call(payload_com_novas_chaves)

    @staticmethod
    def create_operational_intent(flight_plan_id: str):
        """
        Registra um FlightPlan existente no DSS como OIR.
        1. Consulta vizinhos com buffers temporários configuráveis.
        2. Tenta submissão e realiza retry automático se houver conflito 409.
        """
        fp: FlightPlan = FlightPlan.objects.get(pk=flight_plan_id)

        intent, _ = OperationalIntent.objects.get_or_create(
            flight_plan=fp,
            defaults={"state": fp.state},
        )
        if intent.state != fp.state:
            intent.state = fp.state
            intent.save()

        client_coord = OperationalIntentService._build_client(scope=UTMAuthority.STRATEGIC_COORDINATION)
        client_constraint = OperationalIntentService._build_client(scope=UTMAuthority.CONSTRAINT_PROCESSING)
        
        area_query = OperationalIntentService._build_extents(
            intent, 
            buffer_minutes_start=OperationalIntentService.DSS_QUERY_BUFFER_START,
            buffer_minutes_end=OperationalIntentService.DSS_QUERY_BUFFER_END
        )[0]
        
        extents_real = OperationalIntentService._build_extents(intent)

        # 1. Coleta de OVNs (Chaves)
        keys = []
        try:
            print(f"[*] [ASTM] POST /dss/v1/operational_intent_references/query")
            neighbor_result = client_coord.query_operational_intent_references(area_query)
            for oir in neighbor_result.get("operational_intent_references", []):
                if oir.get("id") != str(fp.id) and oir.get("ovn"):
                    keys.append(oir["ovn"])
            
            print(f"[*] [ASTM] POST /dss/v1/constraint_references/query")
            constraint_result = client_constraint.query_constraint_references(area_query)
            for con in constraint_result.get("constraint_references", []):
                if con.get("ovn"):
                    keys.append(con["ovn"])
        except Exception as exc:
            logger.warning("Falha na coleta inicial de chaves: %s", exc)

        # 2. Submissão com Retry Automático
        result = OperationalIntentService._submit_to_dss_with_retry(
            client_coord=client_coord,
            oir_id=str(fp.id),
            extents_real=extents_real,
            state=intent.state.capitalize(),
            keys=keys,
        )

        # 3. Persiste resposta
        dss_ref = result.get("operational_intent_reference", {})
        intent.dss_id = dss_ref.get("id", "")
        intent.version = dss_ref.get("version", 0)
        intent.ovn = dss_ref.get("ovn", "")
        intent.subscription_id = extract_subscription_id(dss_ref, result)
        intent.save()

        logger.info("OIR sincronizada (Create). DSS ID: %s | OVN: %s", intent.dss_id, intent.ovn)
        return intent, result

    @staticmethod
    def update_operational_intent(flight_plan_id: str):
        """
        Atualiza uma OIR já registrada no DSS usando o OVN corrente.
        Implementa retry automático para tratar conflitos de OVN/Chaves (409).
        """
        intent = OperationalIntent.objects.get(flight_plan_id=flight_plan_id)
        fp = intent.flight_plan

        if intent.state != fp.state:
            intent.state = fp.state
            intent.save()

        if not intent.ovn:
            raise ValueError("OVN não disponível — crie a OIR primeiro.")

        client_coord = OperationalIntentService._build_client(scope=UTMAuthority.STRATEGIC_COORDINATION)
        client_constraint = OperationalIntentService._build_client(scope=UTMAuthority.CONSTRAINT_PROCESSING)

        area_query = OperationalIntentService._build_extents(
            intent, 
            buffer_minutes_start=OperationalIntentService.DSS_QUERY_BUFFER_START,
            buffer_minutes_end=OperationalIntentService.DSS_QUERY_BUFFER_END
        )[0]
        
        extents_real = OperationalIntentService._build_extents(intent)

        new_subscription = None
        if intent.state == State.ACTIVATED:
            new_subscription = {
                "uss_base_url": settings.USS_BASE_URL,
                "notify_for_operational_intents": True,
                "notify_for_constraints": True,
            }

        # 1. Coleta de OVNs (chaves)
        keys = []
        try:
            print(f"[*] [ASTM] POST /dss/v1/operational_intent_references/query")
            neighbors = client_coord.query_operational_intent_references(area_query)
            for oir in neighbors.get("operational_intent_references", []):
                if oir.get("id") != str(intent.flight_plan.id) and oir.get("ovn"):
                    keys.append(oir["ovn"])
            
            print(f"[*] [ASTM] POST /dss/v1/constraint_references/query")
            constraints = client_constraint.query_constraint_references(area_query)
            for con in constraints.get("constraint_references", []):
                if con.get("ovn"):
                    keys.append(con["ovn"])
        except Exception as exc:
            logger.warning("Falha na coleta inicial de chaves para update: %s", exc)

        sub_id = intent.subscription_id if intent.subscription_id != OperationalIntentService.PLACEHOLDER_SUB else None

        # 2. Submissão com Retry Automático
        result = OperationalIntentService._submit_to_dss_with_retry(
            client_coord=client_coord,
            oir_id=str(intent.flight_plan.id),
            extents_real=extents_real,
            state=intent.state.capitalize(),
            keys=keys,
            ovn=intent.ovn,
            subscription_id=sub_id,
            new_subscription=new_subscription,
        )

        dss_ref = result.get("operational_intent_reference", {})
        intent.version = dss_ref.get("version", intent.version)
        intent.ovn = dss_ref.get("ovn", intent.ovn)
        intent.save()

        # ── Gatilho ISA ao ativar via FlightPlan ─────────────────────────
        if intent.state == State.ACTIVATED:
            try:
                oir_instance = OirAppIntent.objects.filter(id=intent.flight_plan.id).first()
                if oir_instance:
                    oir_instance.state = "Activated"
                    oir_instance.dss_ovn = intent.ovn
                    oir_instance.dss_response = result
                    oir_instance.save()
                    ISAService.create_or_update_from_oir(oir_instance)
                    logger.info("ISA criado/atualizado e estado sincronizado para OIR %s.", oir_instance.id)
                else:
                    extents_isa = extents_real[0] if isinstance(extents_real, list) and len(extents_real) > 0 else {}
                    IdentificationServiceArea.objects.update_or_create(
                        dss_id=str(intent.dss_id),
                        defaults={
                            "uss_base_url": settings.USS_BASE_URL,
                            "extents": extents_isa,
                        },
                    )
            except Exception as isa_exc:
                logger.error("Falha ao criar ISA (FlightPlan %s): %s", intent.flight_plan_id, isa_exc)

        logger.info("OIR atualizada (Update). DSS ID: %s | OVN: %s", intent.dss_id, intent.ovn)
        return intent, result

    @staticmethod
    def delete_operational_intent(flight_plan_id: str) -> dict:
        """
        Remove uma OIR do DSS e o plano de voo local.
        Retorna um dicionário para que a view possa compor a resposta ASTM F3548-21.
        """
        res = {
            "found": False,
            "dss_success": False,
            "dss_notes": "Flight plan deleted successfully"
        }

        try:
            fp = FlightPlan.objects.get(id=flight_plan_id)
            res["found"] = True
            intent = getattr(fp, 'operational_intent', None)
        except FlightPlan.DoesNotExist:
            return res

        if intent and intent.ovn and intent.dss_id:
            client = OperationalIntentService._build_client()
            try:
                print(f"[*] [ASTM] DELETE /dss/v1/operational_intent_references/{intent.dss_id}/{intent.ovn}")
                client.delete_operational_intent_reference(
                    oir_id=intent.dss_id,
                    ovn=intent.ovn,
                )
                res["dss_success"] = True
            except DSSNotFoundError:
                res["dss_success"] = True # Já não existe no DSS
                res["dss_notes"] = "Operational intent not found in DSS, removed locally"
            except Exception as exc:
                res["dss_success"] = False
                res["dss_notes"] = f"DSS was unreachable or returned error: {str(exc)}"
                logger.error("Erro ao deletar no DSS: %s", exc)
        
        # Remove localmente (CASCADE remove a OperationalIntent)
        fp.delete()
        return res
