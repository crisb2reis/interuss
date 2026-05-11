from django.urls import path

from . import views

app_name = "oir"

urlpatterns = [
    # Autenticação (diagnóstico)
    path("auth/token/", views.GetTokenView.as_view(), name="get-token"),

    # Consultas ao DSS — DEVEM vir antes da rota com <uuid:pk>
    path("oir/query_dss/", views.QueryDSSConstraintsView.as_view(), name="query-dss-constraints"),
    path("oir/search_dss/", views.SearchDSSOIRView.as_view(), name="search-dss-oirs"),

    # Fluxo completo: OIR próxima a Constraint (ASTM F3548-21)
    path("oir/create_near_constraint/", views.CreateOIRNearConstraintView.as_view(), name="create-oir-near-constraint"),
    path("oir/create_with_conflict_resolution/", views.CreateOIRWithConflictResolutionView.as_view(), name="create-oir-conflict-resolution"),

    # OIR CRUD
    path("oir/", views.OIRListCreateView.as_view(), name="oir-list-create"),
    path("oir/<uuid:pk>/", views.OIRDetailView.as_view(), name="oir-detail"),
    path("oir/<uuid:pk>/state/", views.OIRStateTransitionView.as_view(), name="oir-state-transition"),
    path("isa/query_dss/", views.QueryISADSSView.as_view(), name="isa-query-dss"),
    path("isa/<str:isa_id>/", views.IdentificationServiceAreaView.as_view(), name="isa-detail"),
    path("uss/telemetry/", views.USSIngestTelemetryView.as_view(), name="uss-telemetry"),
]
