from django.db.models import Q
from .models import FlightPlan

class ConflictEngine:
    def check_local_conflicts(self, start_time, end_time, geometry):
        """
        Detecta conflitos espaciais e temporais no banco local.
        """
        # Checagem temporal
        temporal_conflict = Q(start_time__lte=end_time) & Q(end_time__gte=start_time)
        
        # Checagem espacial usando ST_Intersects
        spatial_conflict = Q(volume__intersects=geometry)
        
        # Conflitos que satisfazem ambas as condicoes
        conflicts = FlightPlan.objects.filter(temporal_conflict & spatial_conflict)
        return conflicts
