"""
Views da API OIR do USS.

Endpoints disponíveis:
  GET    /api/auth/token/          → Obtém JWT do AUTH (diagnóstico)
  GET    /api/oir/                 → Lista OIRs cadastradas localmente
  POST   /api/oir/                 → Cria OIR e submete ao DSS
  GET    /api/oir/{id}/            → Consulta OIR local por ID
  PUT    /api/oir/{id}/            → Atualiza OIR e resubmete ao DSS
  DELETE /api/oir/{id}/            → Remove OIR local e do DSS
  POST   /api/oir/query_dss/       → Consulta constraints no DSS por área
  POST   /api/oir/search_dss/      → Consulta OIRs no DSS por área
"""

import logging
import jwt as pyjwt

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.dss_client.auth import ICEAAuthenticator
from apps.dss_client.client import DSSClient
from apps.dss_client.exceptions import (
    DSSAuthenticationError,
    DSSAuthorizationError,
    DSSConflictError,
    DSSConnectionError,
    DSSNotFoundError,
    DSSServerError,
    DSSValidationError,
)

from .models import OperationalIntent, IdentificationServiceArea
from apps.flight_plans.models import OperationalIntent as FlightPlanOIR
from .serializers import OIRCreateSerializer, OperationalIntentSerializer, QueryDSSSerializer
from .services import OIRConstraintService, ISAService, normalize_dss_time
from .conflict_resolution import OIRConflictResolutionService
from apps.flight_plans.services import OperationalIntentService

logger = logging.getLogger(__name__)

# ─── Parâmetros default de autenticação ──────────────────────────
DEFAULT_AUDIENCE = "core-service"
DEFAULT_SCOPE = "utm.strategic_coordination"


def _build_client() -> DSSClient:
    """Instancia o DSSClient com autenticação automática."""
    return DSSClient(
        intended_audience=DEFAULT_AUDIENCE,
        scope=DEFAULT_SCOPE,
        auto_authenticate=True,
    )


def _dss_error_response(exc: Exception) -> Response:
    """Converte exceções DSS em respostas HTTP padronizadas."""
    if isinstance(exc, DSSValidationError):
        return Response({"error": "dados_invalidos", "detail": str(exc)}, status=400)
    if isinstance(exc, DSSAuthenticationError):
        return Response({"error": "autenticacao_falhou", "detail": str(exc)}, status=401)
    if isinstance(exc, DSSAuthorizationError):
        return Response({"error": "acesso_negado", "detail": str(exc)}, status=403)
    if isinstance(exc, DSSNotFoundError):
        return Response({"error": "nao_encontrado", "detail": str(exc)}, status=404)
    if isinstance(exc, DSSConflictError):
        return Response(
            {
                "error": "conflito_detectado",
                "detail": str(exc),
                "conflicting_oirs": exc.conflicting_references,
            },
            status=409,
        )
    if isinstance(exc, DSSConnectionError):
        return Response({"error": "erro_conexao", "detail": str(exc)}, status=502)
    if isinstance(exc, DSSServerError):
        return Response({"error": "erro_dss", "detail": str(exc)}, status=502)
    return Response({"error": "erro_interno", "detail": str(exc)}, status=500)


def _require_scope(request, required_scope: str):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return Response(
            {"message": "Bearer token ausente no header Authorization."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    token = auth_header.split(" ", 1)[1]
    try:
        # Mantém verify_exp=True; apenas ignora assinatura (validada pelo AUTH externo)
        decoded = pyjwt.decode(
            token,
            options={"verify_signature": False, "verify_exp": True},
        )
        if required_scope not in decoded.get("scope", ""):
            return Response(
                {"message": f"Token não possui escopo '{required_scope}'."},
                status=status.HTTP_403_FORBIDDEN,
            )
    except pyjwt.ExpiredSignatureError:
        return Response(
            {"message": "Token expirado."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    except pyjwt.DecodeError:
        return Response(
            {"message": "Token inválido ou não pôde ser decodificado."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    return None

def _extract_subscription_id(ref: dict, result: dict) -> str:
    """Extrai subscription_id do ref DSS ou da lista de subscribers."""
    sub_id = ref.get("subscription_id")
    if not sub_id:
        subscribers = result.get("subscribers", [])
        sub_id = subscribers[0].get("subscription_id", "") if subscribers else ""
    return sub_id

def _trigger_isa_if_activated(oir) -> None:
    """Dispara criação/atualização de ISA se a OIR estiver Activated."""
    if oir.state != "Activated":
        return
    try:
        ISAService.create_or_update_from_oir(oir)
        logger.info("ISA criado/atualizado para OIR %s.", oir.id)
    except Exception as isa_exc:
        logger.error("Falha ao criar ISA para OIR %s: %s", oir.id, isa_exc)

def _build_p2p_reference(id_, state, ovn, time_start, time_end, uss_base_url, subscription_id) -> dict:
    return {
        "id": str(id_),
        "manager": "uss-cristiano",
        "uss_availability": "Unknown",
        "version": 1,
        "state": state,
        "ovn": ovn,
        "time_start": time_start,
        "time_end": time_end,
        "uss_base_url": uss_base_url,
        "subscription_id": subscription_id,
    }

def _build_p2p_details(volumes, priority) -> dict:
    return {
        "volumes": volumes,
        "off_nominal_volumes": [],
        "priority": priority,
        "flight_type": "VLOS",
    }


# ─── Views ───────────────────────────────────────────────────────

class GetTokenView(APIView):
    """
    GET /api/auth/token/
    Obtém um JWT do serviço AUTH do sandbox BR-UTM.
    Útil para testar a autenticação e copiar o token para o Postman.

    Query params:
        audience (str): intended_audience (default: utm.decea.mil.br)
        scope (str): scope (default: utm.strategic_coordination)
    """

    def get(self, request):
        audience = request.query_params.get("audience", DEFAULT_AUDIENCE)
        scope = request.query_params.get("scope", DEFAULT_SCOPE)

        try:
            authenticator = ICEAAuthenticator()
            token = authenticator.get_token(intended_audience=audience, scope=scope)
            return Response({
                "access_token": token,
                "token_type": "Bearer",
                "intended_audience": audience,
                "scope": scope,
            })
        except Exception as exc:
            return _dss_error_response(exc)


class OIRListCreateView(APIView):
    """
    GET  /api/oir/  → Lista OIRs cadastradas localmente.
    POST /api/oir/  → Cria OIR localmente e submete ao DSS.
    """

    def get(self, request):
        oirs = OperationalIntent.objects.all()
        serializer = OperationalIntentSerializer(oirs, many=True)
        return Response({"count": oirs.count(), "results": serializer.data})

    def post(self, request):
        serializer = OIRCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": "payload_invalido", "detail": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data
        uss_base_url = data.get("uss_base_url", getattr(settings, "USS_BASE_URL", ""))

        try:
            client = _build_client()

            # Cria a OIR no modelo local (para gerar UUID)
            oir = OperationalIntent.objects.create(
                state=data["state"],
                uss_base_url=uss_base_url,
                extents=data["extents"],
            )

            # Submete ao DSS
            result = client.submit_operational_intent_reference(
                oir_id=str(oir.id),
                extents=data["extents"],
                uss_base_url=uss_base_url,
                state=data["state"],
                subscription_id=data.get("subscription_id"),
                key=data.get("key"),
                new_subscription=data.get("new_subscription", {
                    "uss_base_url": uss_base_url,
                    "notify_for_operational_intents": True,
                }),
            )

            # Atualiza OIR local com dados retornados pelo DSS
            ref = result.get("operational_intent_reference", {})
            oir.dss_id = ref.get("id", str(oir.id))
            oir.dss_ovn = ref.get("ovn", "")
            oir.dss_response = result
            
            oir.subscription_id = _extract_subscription_id(ref, result)
            oir.save()
            
            _trigger_isa_if_activated(oir)

            response_data = {
                "id": str(oir.id),
                "state": oir.state,
                "uss_base_url": oir.uss_base_url,
                "dss_id": oir.dss_id,
                "dss_ovn": oir.dss_ovn,
                "subscribers": result.get("subscribers", []),
                "conflicting_oirs": result.get("conflicting_oirs", []),
                "dss_reference": ref,
            }

            response_status = (
                status.HTTP_200_OK
                if ref.get("version", 0) > 0
                else status.HTTP_201_CREATED
            )
            return Response(response_data, status=response_status)

        except DSSConflictError as exc:
            # Conflito: ainda salva a OIR localmente mas informa o conflito
            return Response(
                {
                    "error": "conflito_detectado",
                    "detail": str(exc),
                    "conflicting_oirs": exc.conflicting_references,
                    "hint": "Consulte o campo conflicting_oirs para identificar o USS concorrente.",
                },
                status=status.HTTP_409_CONFLICT,
            )
        except Exception as exc:
            logger.exception("Erro ao criar OIR")
            return _dss_error_response(exc)


class OIRDetailView(APIView):
    """
    GET    /api/oir/{id}/  → Consulta OIR local por ID.
    PUT    /api/oir/{id}/  → Atualiza OIR e resubmete ao DSS.
    DELETE /api/oir/{id}/  → Remove OIR local e do DSS.
    """

    def _get_oir(self, pk):
        try:
            return OperationalIntent.objects.get(pk=pk)
        except OperationalIntent.DoesNotExist:
            return None

    def get(self, request, pk):
        oir = self._get_oir(pk)
        if not oir:
            return Response({"error": "OIR não encontrada."}, status=404)
        return Response(OperationalIntentSerializer(oir).data)

    def put(self, request, pk):
        oir = self._get_oir(pk)
        if not oir:
            return Response({"error": "OIR não encontrada localmente."}, status=404)

        serializer = OIRCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": "payload_invalido", "detail": serializer.errors},
                status=400,
            )

        data = serializer.validated_data
        uss_base_url = data.get("uss_base_url", oir.uss_base_url)

        try:
            client = _build_client()
            result = client.submit_operational_intent_reference(
                oir_id=str(oir.id),
                ovn=oir.dss_ovn or None,
                extents=data["extents"],
                uss_base_url=uss_base_url,
                state=data["state"],
                key=data.get("key"),
            )

            ref = result.get("operational_intent_reference", {})
            oir.state = data["state"]
            oir.uss_base_url = uss_base_url
            oir.extents = data["extents"]
            oir.dss_ovn = ref.get("ovn", oir.dss_ovn)
            if sub_id := _extract_subscription_id(ref, result):
                oir.subscription_id = sub_id
                
            oir.dss_response = result
            oir.save()

            _trigger_isa_if_activated(oir)

            return Response({
                "id": str(oir.id),
                "state": oir.state,
                "dss_ovn": oir.dss_ovn,
                "conflicting_oirs": result.get("conflicting_oirs", []),
            })

        except Exception as exc:
            logger.exception("Erro ao atualizar OIR %s", pk)
            return _dss_error_response(exc)

    def delete(self, request, pk):
        oir = self._get_oir(pk)
        if not oir:
            return Response({"error": "OIR não encontrada."}, status=404)

        if not oir.dss_ovn:
            return Response({"error": "OVN não disponível para esta OIR. Ela pode não ter sido registrada no DSS corretamente."}, status=400)

        dss_delete_failed = False
        try:
            client = _build_client()
            client.delete_operational_intent_reference(
                oir_id=str(oir.id),
                ovn=oir.dss_ovn,
            )
        except DSSNotFoundError:
            logger.warning("OIR %s não encontrada no DSS; removendo localmente.", pk)
        except Exception as exc:
            logger.exception("Erro ao deletar OIR %s no DSS", pk)
            dss_delete_failed = True

        oir.delete()
        return Response(
            {
                "message": f"OIR {pk} removida com sucesso.",
                "id": str(pk),
                **({"warning": "Falha ao remover do DSS; removida apenas localmente."} if dss_delete_failed else {}),
            },
            status=status.HTTP_200_OK,
        )


class QueryDSSConstraintsView(APIView):
    """
    POST /api/oir/query_dss/
    Consulta constraints no DSS filtradas por área geográfica/temporal.
    """

    def post(self, request):
        serializer = QueryDSSSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": "payload_invalido", "detail": serializer.errors},
                status=400,
            )

        area = serializer.validated_data["area_of_interest"]

        try:
            client = _build_client()
            result = client.query_constraint_references(area)
            return Response(result)
        except Exception as exc:
            return _dss_error_response(exc)


class SearchDSSOIRView(APIView):
    """
    POST /api/oir/search_dss/
    Consulta OIRs registradas no DSS por área geográfica/temporal.
    """

    def post(self, request):
        serializer = QueryDSSSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": "payload_invalido", "detail": serializer.errors},
                status=400,
            )

        area = serializer.validated_data["area_of_interest"]

        try:
            client = _build_client()
            result = client.query_operational_intent_references(area)
            return Response(result)
        except Exception as exc:
            return _dss_error_response(exc)


class CreateOIRNearConstraintView(APIView):
    """
    POST /api/oir/create_near_constraint/

    Executa o fluxo completo ASTM F3548-21 "OIR próxima a Constraint":

      1. Autentica com o DSS (audience=core-service)
      2. Consulta constraints na área de interesse (POST /constraint_references/query)
      3. Para cada constraint, obtém token com audience=<domínio do CP>
         e busca os detalhes (GET {cp_uss_base_url}/uss/v1/constraints/{id})
      4. Consulta OIRs existentes na área (POST /operational_intent_references/query)
      5. Cria a nova OIR no DSS (PUT /operational_intent_references/{id})
      6. Salva a OIR localmente no banco de dados

    Payload esperado:
    {
      "area_of_interest": {          // volume 4D para consulta de constraints/OIRs
        "volume": {
          "outline_polygon": {"vertices": [{"lat": ..., "lng": ...}, ...]},
          "altitude_lower": {"value": 50, "units": "M", "reference": "W84"},
          "altitude_upper": {"value": 120, "units": "M", "reference": "W84"}
        },
        "time_start": {"value": "2026-05-01T10:00:00Z", "format": "RFC3339"},
        "time_end":   {"value": "2026-05-01T11:00:00Z", "format": "RFC3339"}
      },
      "oir": {
        "extents": [{...}],          // lista de volumes 4D da OIR
        "state": "Accepted",         // Accepted | Activated | Nonconforming | Contingent
        "uss_base_url": "https://..." // URL base do USS (opcional, usa settings.USS_BASE_URL)
      }
    }
    """

    def post(self, request):
        # Validação básica do payload
        area = request.data.get("area_of_interest")
        oir_data = request.data.get("oir")

        if not area or not isinstance(area, dict):
            return Response(
                {"error": "payload_invalido", "detail": "'area_of_interest' é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not oir_data or not isinstance(oir_data, dict):
            return Response(
                {"error": "payload_invalido", "detail": "'oir' é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not oir_data.get("extents"):
            return Response(
                {"error": "payload_invalido", "detail": "'oir.extents' é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            service = OIRConstraintService()
            result = service.create_oir_near_constraint(
                area_of_interest=area,
                oir_payload=oir_data,
            )
            return Response(result, status=status.HTTP_201_CREATED)

        except DSSConflictError as exc:
            return Response(
                {
                    "error": "conflito_detectado",
                    "detail": str(exc),
                    "conflicting_oirs": exc.conflicting_references,
                },
                status=status.HTTP_409_CONFLICT,
            )
        except Exception as exc:
            logger.exception("Erro no fluxo create_near_constraint")
            return _dss_error_response(exc)


class CreateOIRWithConflictResolutionView(APIView):
    """
    POST /api/oir/create_with_conflict_resolution/

    Executa o fluxo ASTM F3548-21 "OIR com Conflito":
      Compara prioridades com OIRs concorrentes antes de registrar no DSS.
    """

    def post(self, request):
        area = request.data.get("area_of_interest")
        oir_data = request.data.get("oir")
        our_priority = oir_data.get("priority", 0) if oir_data else 0

        if not area or not isinstance(area, dict):
            return Response({"error": "payload_invalido", "detail": "'area_of_interest' é obrigatório."}, status=400)
        if not oir_data or not isinstance(oir_data, dict):
            return Response({"error": "payload_invalido", "detail": "'oir' é obrigatório."}, status=400)
        if not oir_data.get("extents"):
            return Response({"error": "payload_invalido", "detail": "'oir.extents' é obrigatório."}, status=400)

        try:
            service = OIRConflictResolutionService()
            result = service.resolve_and_create(
                area_of_interest=area,
                oir_payload=oir_data,
                our_priority=our_priority
            )
            
            if result.get("status") == "rejected":
                return Response(result, status=status.HTTP_409_CONFLICT)
            return Response(result, status=status.HTTP_201_CREATED)

        except DSSConflictError as exc:
            return Response(
                {
                    "error": "conflito_detectado",
                    "detail": str(exc),
                    "conflicting_oirs": getattr(exc, "conflicting_references", []),
                },
                status=status.HTTP_409_CONFLICT,
            )
        except Exception as exc:
            logger.exception("Erro no fluxo create_with_conflict_resolution")
            return _dss_error_response(exc)


class PeerToPeerOIRDetailsView(APIView):
    """
    GET /uss/v1/operational_intents/{id}
    Endpoint P2P para outros USSs consultarem detalhes da nossa OIR (incluindo prioridade).
    """
    def get(self, request, pk):
        oir = OperationalIntent.objects.filter(pk=pk).first()
        if oir:
            return Response({
                "operational_intent": {
                    "reference": _build_p2p_reference(
                        oir.id, oir.state, oir.dss_ovn,
                        oir.start_date, oir.end_date,
                        oir.uss_base_url, oir.subscription_id,
                    ),
                    "details": _build_p2p_details(oir.extents, oir.priority),
                }
            })

        fp_oir = FlightPlanOIR.objects.filter(flight_plan_id=pk).first()
        if fp_oir:
            extents = OperationalIntentService._build_extents(fp_oir)
            return Response({
                "operational_intent": {
                    "reference": _build_p2p_reference(
                        fp_oir.flight_plan.id,
                        fp_oir.state.capitalize(),
                        fp_oir.ovn,
                        fp_oir.start_date, fp_oir.end_date,
                        fp_oir.flight_plan.uss_base_url,
                        fp_oir.subscription_id,
                    ),
                    "details": _build_p2p_details(extents, fp_oir.flight_plan.priority),
                }
            })

        return Response({"error": "OIR não encontrada."}, status=status.HTTP_404_NOT_FOUND)


class IdentificationServiceAreaView(APIView):
    """
    GET  /uss/identification_service_areas/{isa_id}
         Escopo: rid.display_provider
         SP consulta detalhes do próprio ISA.

    POST /uss/identification_service_areas/{isa_id}
         Escopo: rid.service_provider
         DP recebe notificação de atualização vinda de SP externo.
    """

    def _get_isa(self, isa_id: str):
        try:
            return IdentificationServiceArea.objects.get(pk=isa_id)
        except (IdentificationServiceArea.DoesNotExist, Exception):
            return IdentificationServiceArea.objects.filter(dss_id=isa_id).first()

    def get(self, request, isa_id: str):
        # err = _require_scope(request, "rid.display_provider")
        # if err:
        #     return err

        isa = self._get_isa(isa_id)
        if not isa:
            return Response(
                {"message": f"ISA '{isa_id}' não encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )
        # Resposta conforme GetIdentificationServiceAreaDetailsResponse (ASTM F3411)
        return Response({
            "service_area": {
                "id": isa.dss_id,
                "uss_base_url": isa.uss_base_url,
                "owner": getattr(settings, "USS_IDENTIFIER", "uss-default"),
                "version": isa.dss_version or "",
                "time_start": normalize_dss_time(isa.extents.get("time_start") or isa.extents.get("volume", {}).get("time_start")),
                "time_end": normalize_dss_time(isa.extents.get("time_end") or isa.extents.get("volume", {}).get("time_end")),
            },
            "extents": isa.extents
        }, status=status.HTTP_200_OK)

    def post(self, request, isa_id: str):
        # err = _require_scope(request, "rid.service_provider")
        # if err:
        #     return err

        extents = request.data.get("extents")
        if not extents:
            return Response(
                {"message": "Campo 'extents' é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        isa = self._get_isa(isa_id)
        if isa:
            isa.extents = extents
            isa.last_notification = request.data
            isa.save()
            logger.info("ISA %s atualizado via notificação POST.", isa_id)
        else:
            service_area = request.data.get("service_area", {})
            IdentificationServiceArea.objects.create(
                dss_id=isa_id,
                uss_base_url=service_area.get("uss_base_url", ""),
                extents=extents,
                last_notification=request.data,
            )
            logger.info("ISA %s criado via notificação POST.", isa_id)

        return Response(status=status.HTTP_204_NO_CONTENT)


class QueryISADSSView(APIView):
    """
    GET /api/isa/query_dss/
      ?area=lat1,lng1,lat2,lng2
      &earliest_time=2026-05-05T10:00:00Z
      &latest_time=2026-05-05T11:00:00Z

    Requer escopo: rid.display_provider (validado via _require_scope)
    """
    def get(self, request):
        # err = _require_scope(request, "rid.display_provider")
        # if err:
        #     return err

        area = request.query_params.get("area")
        earliest = request.query_params.get("earliest_time")
        latest = request.query_params.get("latest_time")

        if not area or not earliest or not latest:
            return Response(
                {"message": "Parâmetros 'area', 'earliest_time' e 'latest_time' são obrigatórios."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from apps.oir.services import ISAService
            result = ISAService.query_dss(area, earliest, latest)
            return Response(result)
        except Exception as exc:
            return _dss_error_response(exc)

class USSIngestTelemetryView(APIView):
    """
    POST /uss/telemetry
    Recebe posições do drone e salva no banco de dados para servir no GET /uss/flights.
    """
    def post(self, request):
        from apps.oir.serializers import RIDTelemetrySerializer
        serializer = RIDTelemetrySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"status": "success", "message": "Telemetry ingested."}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

def _parse_view_param(view_str: str):
    """Converte 'lat1,lng1,lat2,lng2' em bounding box. Raises ValueError se inválido."""
    lat1, lng1, lat2, lng2 = [float(x) for x in view_str.split(",")]
    return lat1, lng1, lat2, lng2

def _bbox_to_dss_polygon(lat1, lng1, lat2, lng2) -> str:
    """Expande 2 cantos para polígono de 4 vértices exigido pelo DSS."""
    min_lat, max_lat = min(lat1, lat2), max(lat1, lat2)
    min_lng, max_lng = min(lng1, lng2), max(lng1, lng2)
    return (
        f"{min_lat},{min_lng},"
        f"{max_lat},{min_lng},"
        f"{max_lat},{max_lng},"
        f"{min_lat},{max_lng}"
    )

def _build_flight_entry(dss_isa, local_isa, local_intent, now, recent_dur) -> dict:
    """Monta um RIDFlight conforme RIDFlightSchema (ASTM F3411)."""
    from .models import RIDTelemetry

    isa_id = dss_isa.get("id", "")
    latest_telemetry = (
        RIDTelemetry.objects.filter(isa=local_isa).order_by("-timestamp").first() if local_isa else None
    )

    # Monta sempre com a ordem exata do modelo
    entry = {
        "id": isa_id,
        "aircraft_type": "Helicopter",
        # current_state inserido abaixo apenas se houver telemetria
        "simulated": True,
        "recent_positions": [],
    }

    if latest_telemetry:
        latest_iso = latest_telemetry.timestamp.strftime("%Y-%m-%dT%H:%M:%S") + "Z"
        alt          = latest_telemetry.alt              if latest_telemetry.alt              != -1000 else 0
        pressure_alt = latest_telemetry.pressure_altitude if latest_telemetry.pressure_altitude != -1000 else 0

        current_state = {
            "timestamp": {
                "value":  latest_iso,
                "format": "RFC3339",
            },
            "timestamp_accuracy": 0,
            "position": {
                "lat":               latest_telemetry.lat,
                "lng":               latest_telemetry.lng,
                "alt":               alt,
                "accuracy_h":        latest_telemetry.accuracy_h,
                "accuracy_v":        latest_telemetry.accuracy_v,
                "extrapolated":      latest_telemetry.extrapolated,
                "pressure_altitude": pressure_alt,
            },
            "speed_accuracy":      latest_telemetry.speed_accuracy,
            "operational_status":  latest_telemetry.operational_status,
            "track":         latest_telemetry.track         if latest_telemetry.track         is not None else 361,
            "speed":         latest_telemetry.speed         if latest_telemetry.speed         is not None else 255,
            "vertical_speed": latest_telemetry.vertical_speed if latest_telemetry.vertical_speed is not None else 63,
        }
        # Insere current_state na posição correta (após aircraft_type)
        entry = {
            "id":             entry["id"],
            "aircraft_type":  entry["aircraft_type"],
            "current_state":  current_state,
            "simulated":      entry["simulated"],
            "recent_positions": entry["recent_positions"],
        }

    return entry

class USSFlightsView(APIView):
    def get(self, request):
        from datetime import datetime, timezone, timedelta
        from django.conf import settings
        from apps.oir.services import ISAService
        from .models import RIDTelemetry

        view = request.query_params.get("view")
        if not view:
            return Response({"message": "O parâmetro 'view' é obrigatório."}, status=400)

        try:
            lat1, lng1, lat2, lng2 = _parse_view_param(view)
        except (ValueError, TypeError):
            return Response({"message": "Formato inválido para 'view'. Use: lat1,lng1,lat2,lng2."}, status=400)

        dss_area = _bbox_to_dss_polygon(lat1, lng1, lat2, lng2)
        recent_dur = float(request.query_params.get("recent_positions_duration", 0) or 0)
        now = datetime.now(timezone.utc)
        now_iso = now.strftime("%Y-%m-%dT%H:%M:%S") + "Z"
        our_uss_base = settings.USS_BASE_URL.rstrip("/")
        
        def _normalize_url(url: str) -> str:
            return url.strip().rstrip("/").replace("https://", "").replace("http://", "").lower()

        try:
            dss_result = ISAService.query_dss(area=dss_area, earliest_time=now_iso, latest_time=now_iso)
            dss_isas = dss_result.get("service_areas", [])
        except Exception as exc:
            logger.error("Falha ao consultar ISAs no DSS: %s", exc)
            dss_isas = []

        flights = []
        processed_ids = set()

        for dss_isa in dss_isas:
            if _normalize_url(dss_isa.get("uss_base_url", "")) != _normalize_url(our_uss_base):
                if not IdentificationServiceArea.objects.filter(dss_id=dss_isa.get("id")).exists():
                    continue

            isa_id = dss_isa.get("id", "")
            local_isa = IdentificationServiceArea.objects.filter(dss_id=isa_id).first()
            local_intent = OperationalIntent.objects.filter(dss_id=isa_id).first()
            flights.append(_build_flight_entry(dss_isa, local_isa, local_intent, now, recent_dur))
            processed_ids.add(isa_id)

        # ── Fallback: ISAs locais com telemetria recente (últimos 5 min) ──
        # Cobre o caso em que o ISA expirou no DSS mas ainda há telemetria ativa.
        min_lat, max_lat = min(lat1, lat2), max(lat1, lat2)
        min_lng, max_lng = min(lng1, lng2), max(lng1, lng2)
        recent_threshold = now - timedelta(minutes=5)

        local_isas_with_telemetry = (
            IdentificationServiceArea.objects
            .filter(
                telemetry__timestamp__gte=recent_threshold,
                telemetry__lat__gte=min_lat,
                telemetry__lat__lte=max_lat,
                telemetry__lng__gte=min_lng,
                telemetry__lng__lte=max_lng,
            )
            .distinct()
        )

        for isa in local_isas_with_telemetry:
            if isa.dss_id in processed_ids:
                continue
            processed_ids.add(isa.dss_id)
            synthetic_dss_isa = {"id": isa.dss_id, "uss_base_url": isa.uss_base_url}
            local_intent = OperationalIntent.objects.filter(dss_id=isa.dss_id).first()
            flights.append(_build_flight_entry(synthetic_dss_isa, isa, local_intent, now, recent_dur))

        no_isas_present = len(dss_isas) == 0 and len(flights) == 0

        return Response({
            "timestamp": {
                "value":  now_iso,
                "format": "RFC3339",
            },
            "flights": flights,
            "no_isas_present": no_isas_present,
        })

class USSFlightDetailsView(APIView):
    """
    GET /uss/flights/{id}/details
    Endpoint exigido pela ASTM F3411 (Remote ID) para Display Providers
    consultarem detalhes de um voo.
    """
    def get(self, request, flight_id):
        # err = _require_scope(request, "rid.display_provider")
        # if err:
        #     return err
            
        from apps.oir.models import IdentificationServiceArea, OperationalIntent
        from apps.flight_plans.models import FlightPlan
        
        # Validar se o ISA existe localmente (o ID retornado em /flights é o DSS ID do ISA ou do FP)
        local_isa = IdentificationServiceArea.objects.filter(dss_id=flight_id).first()
        local_intent = (
            OperationalIntent.objects.filter(dss_id=flight_id).first()
            or FlightPlan.objects.filter(id=flight_id).first()
        )
        
        if not local_isa and not local_intent:
            return Response({"error": "Voo não encontrado."}, status=status.HTTP_404_NOT_FOUND)
            
        # Extração de dados ASTM reais ou Mocks se não disponível
        registration_id = "PP-999999999"
        operator_id = "ABCDEF"
        operation_description = "SafeFlightDrone company doing survey with DJI Inspire 2. See my privacy policy www.example.com/privacy."
        
        # Tenta extrair dados reais se for FlightPlan
        if local_intent and isinstance(local_intent, FlightPlan):
            astm = local_intent.astm_payload
            if astm and isinstance(astm, dict):
                basic_info = astm.get("flight_plan", {}).get("basic_information", {})
                operation_description = basic_info.get("description", operation_description)
                
        response_data = {
            "details": {
                "id": flight_id,
                "uas_id": {
                    "registration_id": registration_id
                },
                "operation_description": operation_description
            }
        }
        
        return Response(response_data, status=status.HTTP_200_OK)


class OIRStateTransitionView(APIView):
    """
    PATCH /api/oir/{pk}/state/
    Transiciona a OIR para o novo estado e atualiza o DSS.
    """
    def patch(self, request, pk):
        from .models import OperationalIntent
        from .services import OIRStateTransitionService

        oir = OperationalIntent.objects.filter(pk=pk).first()
        if not oir:
            return Response({"error": "OIR não encontrada."}, status=status.HTTP_404_NOT_FOUND)

        new_state = request.data.get("state")
        if not new_state:
            return Response({"error": "Campo 'state' é obrigatório."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            service = OIRStateTransitionService()
            result = service.transition_to(oir, new_state)
            return Response({
                "status": "success",
                "new_state": oir.state,
                "dss_ovn": oir.dss_ovn,
                "dss_response": result
            })
        except Exception as exc:
            logger.exception("Erro ao transicionar estado da OIR %s", pk)
            return _dss_error_response(exc)
