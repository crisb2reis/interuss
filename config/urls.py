"""
Roteamento raiz do USS.
"""

from django.contrib import admin
from django.urls import include, path, reverse
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.oir.views import PeerToPeerOIRDetailsView, IdentificationServiceAreaView, USSFlightsView, USSIngestTelemetryView, USSFlightDetailsView


@api_view(["GET"])
def health_check(request):
    """GET / — Health check do USS."""
    return Response({
        "status": "ok",
        "service": "USS — UAS Service Supplier",
        "version": "1.0.0",
        "endpoints": {
            "token":           reverse("oir:get-token"),
            "oir_list":        reverse("oir:oir-list-create"),
            "oir_detail":      reverse("oir:oir-detail", kwargs={"pk": "00000000-0000-0000-0000-000000000000"}).replace("00000000-0000-0000-0000-000000000000", "{id}"),
            "query_dss":       reverse("oir:query-dss-constraints"),
            "search_dss":      reverse("oir:search-dss-oirs"),
            "flight_plans":    reverse("flight_plans-list"),
            "admin":           reverse("admin:index"),
        },
    })


urlpatterns = [
    path("", health_check, name="health-check"),
    path("admin/", admin.site.urls),
    path("api/", include("apps.oir.urls", namespace="oir")),
    path("api/", include("apps.flight_plans.urls")),
    
    # Endpoint Peer-to-Peer ASTM F3548-21
    path("uss/v1/operational_intents/<uuid:pk>", PeerToPeerOIRDetailsView.as_view(), name="p2p-oir-details"),

    # ISA — Identification Service Area (ASTM F3411 — Remote ID)
    path(
        "uss/identification_service_areas/<str:isa_id>",
        IdentificationServiceAreaView.as_view(),
        name="isa-detail-astm",
    ),
    path("uss/flights", USSFlightsView.as_view(), name="uss-flights"),
    path("uss/flights/<str:flight_id>/details", USSFlightDetailsView.as_view(), name="uss-flight-details"),
    path("uss/telemetry/", USSIngestTelemetryView.as_view(), name="uss-telemetry"),
]
