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

from .models import OperationalIntent
from apps.flight_plans.models import OperationalIntent as FlightPlanOIR
from .serializers import OIRCreateSerializer, OperationalIntentSerializer, QueryDSSSerializer
from .services import OIRConstraintService
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
            
            subscribers = result.get("subscribers", [])
            oir.subscription_id = subscribers[0].get("subscription_id", "") if subscribers else ""
            
            oir.save()

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
            oir.dss_response = result
            oir.save()

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
            # Remove localmente mesmo se o DSS falhar
            pass

        oir.delete()
        return Response(
            {"message": f"OIR {pk} removida com sucesso.", "id": str(pk)},
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
        # 1. Tenta buscar no modelo de OIRs avulsas (app oir)
        oir = OperationalIntent.objects.filter(pk=pk).first()
        
        if oir:
            # Resposta para OIR do app 'oir'
            response_data = {
                "operational_intent": {
                    "reference": {
                        "id": str(oir.id),
                        "manager": "uss-cristiano",
                        "uss_availability": "Unknown",
                        "version": 1,
                        "state": oir.state,
                        "ovn": oir.dss_ovn,
                        "time_start": oir.start_date,
                        "time_end": oir.end_date,
                        "uss_base_url": oir.uss_base_url,
                        "subscription_id": oir.subscription_id
                    },
                    "details": {
                        "volumes": oir.extents,
                        "off_nominal_volumes": [],
                        "priority": oir.priority,
                        "flight_type": "VLOS"
                    },
                }
            }
            return Response(response_data, status=status.HTTP_200_OK)

        # 2. Tenta buscar no modelo de Planos de Voo (app flight_plans)
        fp_oir = FlightPlanOIR.objects.filter(flight_plan_id=pk).first()
        if fp_oir:
            # Constrói os extents ASTM a partir do modelo FlightPlan
            extents = OperationalIntentService._build_extents(fp_oir)
            
            response_data = {
                "operational_intent": {
                    "reference": {
                        "id": str(fp_oir.flight_plan.id),
                        "manager": "uss-cristiano",
                        "uss_availability": "Unknown",
                        "version": 1,
                        "state": fp_oir.state.capitalize(), # ASTM usa CamelCase (Accepted)
                        "ovn": fp_oir.ovn,
                        "time_start": fp_oir.start_date,
                        "time_end": fp_oir.end_date,
                        "uss_base_url": fp_oir.flight_plan.uss_base_url,
                        "subscription_id": fp_oir.subscription_id
                    },
                    "details": {
                        "volumes": extents,
                        "off_nominal_volumes": [],
                        "priority": fp_oir.flight_plan.priority,
                        "flight_type": "VLOS"
                    }
                }
            }
            return Response(response_data, status=status.HTTP_200_OK)

        return Response({"error": "OIR não encontrada."}, status=status.HTTP_404_NOT_FOUND)
