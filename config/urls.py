"""
Roteamento raiz do USS.
"""

from django.contrib import admin
from django.urls import include, path
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def health_check(request):
    """GET / — Health check do USS."""
    return Response({
        "status": "ok",
        "service": "USS — UAS Service Supplier",
        "version": "1.0.0",
        "endpoints": {
            "token":           "/api/auth/token/",
            "oir_list":        "/api/oir/",
            "oir_detail":      "/api/oir/{id}/",
            "query_dss":       "/api/oir/query_dss/",
            "search_dss":      "/api/oir/search_dss/",
            "flight_plans":    "/api/flight_plans/",
            "admin":           "/admin/",
        },
    })


urlpatterns = [
    path("", health_check, name="health-check"),
    path("admin/", admin.site.urls),
    path("api/", include("apps.oir.urls", namespace="oir")),
    path("api/", include("apps.flight_plans.urls")),
]
