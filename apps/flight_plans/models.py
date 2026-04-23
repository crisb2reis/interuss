import uuid
from django.db import models
from django.contrib.gis.db import models as gis_models

class State(models.TextChoices):
    ACCEPTED = 'ACCEPTED', 'Accepted'
    ACTIVATED = 'ACTIVATED', 'Activated'
    NONCONFORMING = 'NONCONFORMING', 'Nonconforming'
    CONTINGENT = 'CONTINGENT', 'Contingent'
    PLANNING = 'PLANNING', 'Planning'

class FlightPlan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    state = models.CharField(max_length=20, choices=State.choices, default=State.PLANNING)
    priority = models.IntegerField(default=0)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    volume = gis_models.GeometryField(dim=3, srid=4326)  # Volume 3D (lon,lat,alt)
    uss_base_url = models.URLField()
    
    # [ASTM] Dados extras
    description = models.TextField(blank=True, default="")
    astm_payload = models.JSONField(null=True, blank=True)

class OperationalIntent(models.Model):
    flight_plan = models.OneToOneField(FlightPlan, on_delete=models.CASCADE, related_name='operational_intent')
    dss_id = models.CharField(max_length=255, blank=True)
    version = models.IntegerField(default=0)
    state = models.CharField(max_length=20, choices=State.choices)
    
    # [NOVO] Mantém controle da versão Opaque providenciada pelo DSS
    ovn = models.CharField(max_length=255, blank=True, null=True)
    
    # [NOVO] ID da subscrição associada no DSS
    subscription_id = models.CharField(max_length=255, blank=True, null=True)

class OperationalIntentConflict(models.Model):
    """
    Registra hard-conflicts 409 vindos do DSS.
    Isto é útil para que as rotinas de coordenação estratégica saibam com quem devem falar.
    """
    my_intent = models.ForeignKey(OperationalIntent, on_delete=models.CASCADE, related_name='conflicts')
    
    # ID da OIR de propriedade de outra USS que está cruzando a nossa área
    conflict_dss_id = models.CharField(max_length=255)
    
    # Base URL da USS conflitante para orquestrarmos uma comunicação peer-to-peer (ASTM)
    conflict_uss_base_url = models.URLField()
    
    # Estado da intenção que está causando o conflito
    conflict_state = models.CharField(max_length=50, blank=True, null=True)
    
    detected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Previne salvar o mesmo conflito infinitas vezes na base
        unique_together = ('my_intent', 'conflict_dss_id')
