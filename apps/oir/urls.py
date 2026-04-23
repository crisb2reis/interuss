from django.urls import path

from . import views

app_name = "oir"

urlpatterns = [
    # Autenticação (diagnóstico)
    path("auth/token/", views.GetTokenView.as_view(), name="get-token"),

    # Consultas ao DSS — DEVEM vir antes da rota com <uuid:pk>
    path("oir/query_dss/", views.QueryDSSConstraintsView.as_view(), name="query-dss-constraints"),
    path("oir/search_dss/", views.SearchDSSOIRView.as_view(), name="search-dss-oirs"),

    # OIR CRUD
    path("oir/", views.OIRListCreateView.as_view(), name="oir-list-create"),
    path("oir/<uuid:pk>/", views.OIRDetailView.as_view(), name="oir-detail"),
]
