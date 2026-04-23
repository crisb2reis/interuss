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
from .serializers import OIRCreateSerializer, OperationalIntentSerializer, QueryDSSSerializer

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
