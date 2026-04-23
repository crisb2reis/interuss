import logging
from datetime import datetime

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.views import APIView
from django.contrib.gis.geos import Polygon
from django.conf import settings

from .models import FlightPlan, OperationalIntent, State
from .serializers import (
    FlightPlanSerializer, 
    OperationalIntentSerializer,
    ASTMFlightPlanRequestSerializer,
    ASTMFlightPlanResponseSerializer
)
from .services import OperationalIntentService
from apps.dss_client.exceptions import (
    DSSConflictError,
    DSSNotFoundError,
    DSSValidationError,
    DSSConnectionError,
    DSSServerError,
)

logger = logging.getLogger(__name__)


def _dss_error_response(exc: Exception) -> Response:
    """Converte exceções DSS em respostas HTTP padronizadas."""
    if isinstance(exc, DSSConflictError):
        return Response(
            {
                "error": "conflito_detectado",
                "detail": str(exc),
                "conflicting_oirs": getattr(exc, "conflicting_references", []),
            },
            status=status.HTTP_409_CONFLICT,
        )
    if isinstance(exc, DSSValidationError):
        return Response({"error": "dados_invalidos", "detail": str(exc)}, status=400)
    if isinstance(exc, DSSNotFoundError):
        return Response({"error": "nao_encontrado", "detail": str(exc)}, status=404)
    if isinstance(exc, (DSSConnectionError, DSSServerError)):
        return Response({"error": "erro_dss", "detail": str(exc)}, status=502)
    return Response({"error": "erro_interno", "detail": str(exc)}, status=500)


class ASTMFlightPlanUpsertView(APIView):
    """
    PUT /api/flight_plans/{flight_plan_id}/
    Implementação do endpoint de Upsert de Plano de Voo (ASTM F3548-21).
    """

    def put(self, request, flight_plan_id):
        serializer = ASTMFlightPlanRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        body = data['flight_plan']
        info = body['basic_information']
        execution_style = data.get('execution_style', 'IfAllowed')

        # 1. Mapeamento de dados ASTM -> Interno
        # Extraímos o primeiro volume da lista 'area' para definir o volume principal
        area = info['area'][0]
        vertices = area['volume']['outline_polygon']['vertices']
        alt_z = area['volume'].get('altitude_upper', {}).get('value', 120)
        
        # Constrói Polígono 3D (Z)
        coords = [(v['lng'], v['lat'], alt_z) for v in vertices]
        # Fecha o polígono se necessário
        if coords[0] != coords[-1]:
            coords.append(coords[0])
        
        poly_z = Polygon(coords, srid=4326)

        # Datas
        start_time = datetime.fromisoformat(area['time_start']['value'].replace('Z', '+00:00'))
        end_time = datetime.fromisoformat(area['time_end']['value'].replace('Z', '+00:00'))

        # Mapeamento de estados
        # usage_state: Planned -> PLANNING, InUse -> ACCEPTED
        internal_state = State.PLANNING if info['usage_state'] == "Planned" else State.ACCEPTED

        # 2. Upsert (Create or Update)
        flight_plan, created = FlightPlan.objects.update_or_create(
            id=flight_plan_id,
            defaults={
                "state": internal_state,
                "start_time": start_time,
                "end_time": end_time,
                "volume": poly_z,
                "description": info.get('description', ''),
                "uss_base_url": settings.USS_BASE_URL,
                "astm_payload": request.data
            }
        )

        # 3. Sincronização com DSS
        planning_result = "Completed"
        notes = ""
        status_code = status.HTTP_200_OK if not created else status.HTTP_201_CREATED

        try:
            # Se for "DespiteConflict", injetamos essa lógica no service futuramente.
            # Por enquanto, tentamos criar ou atualizar.
            intent = OperationalIntent.objects.filter(flight_plan=flight_plan).first()
            
            if intent and intent.ovn:
                OperationalIntentService.update_operational_intent(str(flight_plan.id))
            else:
                OperationalIntentService.create_operational_intent(str(flight_plan.id))
                
        except DSSConflictError as exc:
            if execution_style == "IfAllowed":
                planning_result = "Rejected"
                notes = f"Conflito detectado: {str(exc)}"
                status_code = status.HTTP_409_CONFLICT
            else:
                # DespiteConflict - avisamos mas marcamos como Completed
                planning_result = "Completed"
                notes = f"Atenção: Voo planejado apesar de conflitos detectados. {str(exc)}"
        except Exception as exc:
            logger.error(f"Erro no DSS durante PUT ASTM: {str(exc)}")
            planning_result = "Failed"
            notes = str(exc)
            # ASTM costuma preferir 200 com Failed no body em alguns casos, 
            # mas vamos manter semântica HTTP onde apropriado.

        # 4. Resposta ASTM
        response_data = {
            "planning_result": planning_result,
            "notes": notes,
            "flight_plan_status": "Planned" if planning_result == "Completed" else "NotPlanned",
            "as_planned": body,
            "includes_advisories": "NoAdvisoriesOrConditions"
        }

        return Response(response_data, status=status_code)

    def get(self, request, flight_plan_id):
        """GET /api/flight_plans/{id}/ — Retorna dados internos do plano de voo."""
        try:
            flight_plan = FlightPlan.objects.get(id=flight_plan_id)
            return Response(FlightPlanSerializer(flight_plan).data)
        except FlightPlan.DoesNotExist:
            return Response({"error": "nao_encontrado"}, status=404)

    def delete(self, request, flight_plan_id):
        """DELETE /api/flight_plans/{id}/ — Remove do DSS e do USS."""
        try:
            success = OperationalIntentService.delete_operational_intent(flight_plan_id)
            if success:
                return Response(status=status.HTTP_204_NO_CONTENT)
            return Response({"error": "falha_ao_deletar"}, status=400)
        except Exception as exc:
            return _dss_error_response(exc)


class FlightPlanViewSet(viewsets.ModelViewSet):
    """
    ViewSet REST para FlightPlans (Interface Administrativa/Interna).
    """
    queryset = FlightPlan.objects.all()
    serializer_class = FlightPlanSerializer

    def create(self, request, *args, **kwargs):
        """Cria o FlightPlan localmente e o submete ao DSS automaticamente."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        flight_plan = serializer.save()

        try:
            intent, dss_result = OperationalIntentService.create_operational_intent(
                str(flight_plan.id)
            )
            return Response(
                {
                    "flight_plan": FlightPlanSerializer(flight_plan).data,
                    "operational_intent": {
                        "dss_id": intent.dss_id,
                        "ovn": intent.ovn,
                        "version": intent.version,
                        "subscription_id": intent.subscription_id,
                    },
                    "dss_subscribers": dss_result.get("subscribers", []),
                    "conflicting_oirs": dss_result.get("conflicting_oirs", []),
                },
                status=status.HTTP_201_CREATED,
            )
        except DSSConflictError as exc:
            return Response(
                {
                    "flight_plan": FlightPlanSerializer(flight_plan).data,
                    "error": "conflito_detectado",
                    "detail": str(exc),
                    "conflicting_oirs": getattr(exc, "conflicting_references", []),
                },
                status=status.HTTP_409_CONFLICT,
            )
        except Exception as exc:
            logger.exception("Erro ao submeter FlightPlan %s ao DSS", flight_plan.id)
            return _dss_error_response(exc)

    @action(detail=True, methods=["post"], url_path="submit")
    def submit(self, request, pk=None):
        flight_plan = self.get_object()
        try:
            existing = OperationalIntent.objects.filter(flight_plan=flight_plan).first()
            if existing and existing.ovn:
                intent, result = OperationalIntentService.update_operational_intent(str(flight_plan.id))
            else:
                intent, result = OperationalIntentService.create_operational_intent(str(flight_plan.id))

            return Response({
                "dss_id": intent.dss_id,
                "ovn": intent.ovn,
                "version": intent.version,
                "subscribers": result.get("subscribers", []),
                "conflicting_oirs": result.get("conflicting_oirs", []),
            })
        except Exception as exc:
            return _dss_error_response(exc)
