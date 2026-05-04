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

    # Configurações de janela de tempo para consultas ao DSS (em minutos)
    DSS_QUERY_BUFFER_START = 15
    DSS_QUERY_BUFFER_END = 15
    
    # Placeholder de Subscription que deve ser ignorado
    PLACEHOLDER_SUB = "00000000-0000-4000-8000-000000000000"

    @staticmethod
    def _build_client(scope: str = UTMAuthority.STRATEGIC_COORDINATION) -> DSSClient:
        """Instancia o DSSClient com o token do escopo solicitado."""
        authenticator = ICEAAuthenticator()
        token = authenticator.get_token(
            intended_audience="core-service",
            scope=scope,
        )
        return DSSClient(token=token)

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
        return [{
            "volume": {
                "outline_polygon": {
                    "vertices": [{"lat": v[1], "lng": v[0]} for v in coords]
                },
                "altitude_lower": {"value": 0, "reference": "W84", "units": "M"},
                "altitude_upper": {"value": 120, "reference": "W84", "units": "M"},
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

        # Clients separados por scope
        client_coord = OperationalIntentService._build_client(scope=UTMAuthority.STRATEGIC_COORDINATION)
        client_constraint = OperationalIntentService._build_client(scope=UTMAuthority.CONSTRAINT_PROCESSING)
        
        # Área de consulta com buffer temporal
        area_query = OperationalIntentService._build_extents(
            intent, 
            buffer_minutes_start=OperationalIntentService.DSS_QUERY_BUFFER_START,
            buffer_minutes_end=OperationalIntentService.DSS_QUERY_BUFFER_END
        )[0]
        
        # Extents reais para submissão (sem buffer)
        extents_real = OperationalIntentService._build_extents(intent)

        # 1. Coleta de OVNs (Chaves)
        keys = []
        try:
            # OIRs vizinhas
            print(f"[*] [ASTM] POST /dss/v1/operational_intent_references/query")
            neighbor_result = client_coord.query_operational_intent_references(area_query)
            for oir in neighbor_result.get("operational_intent_references", []):
                if oir.get("id") != str(fp.id) and oir.get("ovn"):
                    keys.append(oir["ovn"])
            
            # Constraints vizinhas
            print(f"[*] [ASTM] POST /dss/v1/constraint_references/query")
            constraint_result = client_constraint.query_constraint_references(area_query)
            for con in constraint_result.get("constraint_references", []):
                if con.get("ovn"):
                    keys.append(con["ovn"])
        except Exception as exc:
            logger.warning("Falha na coleta inicial de chaves: %s", exc)

        # 2. Submissão com Retry Automático
        try:
            print(f"[*] [ASTM] PUT /dss/v1/operational_intent_references/{fp.id}")
            result = client_coord.create_operational_intent_reference(
                oir_id=str(fp.id),
                extents=extents_real,
                uss_base_url=settings.USS_BASE_URL,
                state=intent.state.capitalize(),
                key=keys,
            )
        except DSSConflictError as exc:
            logger.info("Conflito 409 no Create. Realizando retry com OVNs faltantes...")
            for ref in exc.conflicting_references:
                ovn = ref.get("ovn")
                if ovn and ovn not in keys:
                    keys.append(ovn)
            
            if not keys: raise exc
            
            result = client_coord.create_operational_intent_reference(
                oir_id=str(fp.id),
                extents=extents_real,
                uss_base_url=settings.USS_BASE_URL,
                state=intent.state.capitalize(),
                key=keys,
            )

        # 3. Persiste resposta
        dss_ref = result.get("operational_intent_reference", {})
        intent.dss_id = dss_ref.get("id", "")
        intent.version = dss_ref.get("version", 0)
        intent.ovn = dss_ref.get("ovn", "")
        intent.subscription_id = dss_ref.get("subscription_id", "")
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

        # Clients separados por scope
        client_coord = OperationalIntentService._build_client(scope=UTMAuthority.STRATEGIC_COORDINATION)
        client_constraint = OperationalIntentService._build_client(scope=UTMAuthority.CONSTRAINT_PROCESSING)

        # Área de consulta com buffer temporal
        area_query = OperationalIntentService._build_extents(
            intent, 
            buffer_minutes_start=OperationalIntentService.DSS_QUERY_BUFFER_START,
            buffer_minutes_end=OperationalIntentService.DSS_QUERY_BUFFER_END
        )[0]
        
        # Extents reais para submissão
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
            # OIRs vizinhas
            print(f"[*] [ASTM] POST /dss/v1/operational_intent_references/query")
            neighbors = client_coord.query_operational_intent_references(area_query)
            for oir in neighbors.get("operational_intent_references", []):
                if oir.get("id") != str(intent.flight_plan.id) and oir.get("ovn"):
                    keys.append(oir["ovn"])
            
            # Constraints vizinhas
            print(f"[*] [ASTM] POST /dss/v1/constraint_references/query")
            constraints = client_constraint.query_constraint_references(area_query)
            for con in constraints.get("constraint_references", []):
                if con.get("ovn"):
                    keys.append(con["ovn"])
        except Exception as exc:
            logger.warning("Falha na coleta inicial de chaves para update: %s", exc)

        # Limpeza de Subscription ID (não enviar placeholder)
        sub_id = intent.subscription_id if intent.subscription_id != OperationalIntentService.PLACEHOLDER_SUB else None

        # 2. Submissão com Retry Automático
        try:
            print(f"[*] [ASTM] PUT /dss/v1/operational_intent_references/{intent.flight_plan.id}/{intent.ovn}")
            result = client_coord.update_operational_intent_reference(
                oir_id=str(intent.flight_plan.id),
                ovn=intent.ovn,
                extents=extents_real,
                uss_base_url=settings.USS_BASE_URL,
                state=intent.state.capitalize(),
                subscription_id=sub_id,
                new_subscription=new_subscription,
                key=keys,
            )
        except DSSConflictError as exc:
            logger.info("Conflito 409 no Update. Realizando retry com OVNs faltantes...")
            for ref in exc.conflicting_references:
                ovn = ref.get("ovn")
                if ovn and ovn not in keys:
                    keys.append(ovn)
            
            if not keys: raise exc
            
            result = client_coord.update_operational_intent_reference(
                oir_id=str(intent.flight_plan.id),
                ovn=intent.ovn,
                extents=extents_real,
                uss_base_url=settings.USS_BASE_URL,
                state=intent.state.capitalize(),
                subscription_id=sub_id,
                new_subscription=new_subscription,
                key=keys,
            )

        dss_ref = result.get("operational_intent_reference", {})
        intent.version = dss_ref.get("version", intent.version)
        intent.ovn = dss_ref.get("ovn", intent.ovn)
        intent.save()

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
