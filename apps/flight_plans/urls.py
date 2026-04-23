from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FlightPlanViewSet, ASTMFlightPlanUpsertView

router = DefaultRouter()
router.register(r'flight_plans', FlightPlanViewSet, basename='flight_plans')

urlpatterns = [
    # Endpoint ASTM PUT explicito (Upsert)
    path('flight_plans/<uuid:flight_plan_id>/', ASTMFlightPlanUpsertView.as_view(), name='astm-fp-upsert'),
    
    # Endpoints administrativos do ViewSet
    path('', include(router.urls)),
]
