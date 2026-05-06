import uuid

from django.db import models


class OperationalIntent(models.Model):
    """
    Representa uma Operational Intent Reference (OIR) registrada neste USS.
    Armazenada localmente após submissão bem-sucedida ao DSS.
    """

    class State(models.TextChoices):
        ACCEPTED = "Accepted", "Accepted"
        ACTIVATED = "Activated", "Activated"
        NONCONFORMING = "Nonconforming", "Nonconforming"
        CONTINGENT = "Contingent", "Contingent"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    state = models.CharField(
        max_length=20,
        choices=State.choices,
        default=State.ACCEPTED,
    )
    uss_base_url = models.URLField(
        help_text="URL base da USS responsável por esta OIR."
    )
    priority = models.IntegerField(
        default=0,
        help_text="Prioridade da operação. Valores maiores = maior prioridade."
    )
    # Dados retornados pelo DSS após submissão
    dss_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="ID da OIR conforme registrado no DSS.",
    )
    dss_ovn = models.CharField(
        max_length=255,
        blank=True,
        help_text="OVN (Operational Version Number) retornado pelo DSS.",
    )
    # Extents no formato ASTM (lista de volumes 4D)
    extents = models.JSONField(
        help_text="Lista de volumes 4D — [{'volume': {...}, 'time_start': {...}, 'time_end': {...}}]"
    )
    # [ASTM] ID da subscrição associada no DSS
    subscription_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="ID da subscrição DSS associada a esta OIR.",
    )
    # Resposta completa do DSS (para debug/auditoria)
    dss_response = models.JSONField(
        null=True,
        blank=True,
        help_text="Resposta completa recebida do DSS na última submissão.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Operational Intent"
        verbose_name_plural = "Operational Intents"

    def __str__(self):
        return f"OIR {self.id} [{self.state}] — {self.uss_base_url}"

    @property
    def start_date(self):
        """Retorna o time_start do primeiro volume no formato string."""
        if self.extents and isinstance(self.extents, list) and len(self.extents) > 0:
            return self.extents[0].get("time_start", {})
        return None

    @property
    def end_date(self):
        """Retorna o time_end do primeiro volume no formato string."""
        if self.extents and isinstance(self.extents, list) and len(self.extents) > 0:
            return self.extents[0].get("time_end", {})
        return None


class IdentificationServiceArea(models.Model):
    """
    Representa uma Identification Service Area (ISA) no ASTM F3411 Remote ID.
    O ISA é associado a um volume 4D onde os voos serão identificados.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # FK opcional para vincular a uma OIR ativada no ASTM F3548
    operational_intent = models.ForeignKey(
        OperationalIntent,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="isas"
    )

    # ID no DSS (geralmente espelha o da OIR, mas tecnicamente são entidades distintas)
    dss_id = models.CharField(max_length=255, unique=True)

    # Versão retornada pelo DSS ao registrar (necessária para DELETE)
    dss_version = models.CharField(max_length=255, blank=True, null=True)

    uss_base_url = models.URLField()

    # Volume 4D do ISA. Diferente da OIR (que é uma lista de volumes), o ISA é um único Volume4D
    extents = models.JSONField(help_text="Volume 4D (ASTM F3411) do ISA")

    # Última notificação POST recebida de SP externo (auditoria)
    last_notification = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Identification Service Area"

    def __str__(self):
        return f"ISA {self.id} [OIR={self.operational_intent_id}]"

class RIDTelemetry(models.Model):
    """
    Armazena posições de aeronaves para servir ao GET /uss/flights.
    Cada registro representa uma leitura de posição do UAS.
    Retidos por NetUasInAreaWindow (60s padrão ASTM).
    """
    isa = models.ForeignKey(
        IdentificationServiceArea,
        on_delete=models.CASCADE,
        related_name="telemetry"
    )
    # Timestamp da posição (vindo do UAS ou gerado no recebimento)
    timestamp = models.DateTimeField()
    # Posição geográfica
    lat = models.FloatField()
    lng = models.FloatField()
    alt = models.FloatField(default=-1000)
    pressure_altitude = models.FloatField(default=-1000)
    # Acurácias
    accuracy_h = models.CharField(max_length=20, default="HAUnknown")
    accuracy_v = models.CharField(max_length=20, default="VAUnknown")
    # Movimento
    track = models.FloatField(default=361)   # 361 = desconhecido
    speed = models.FloatField(default=255)   # 255 = desconhecido
    speed_accuracy = models.CharField(max_length=20, default="SAUnknown")
    vertical_speed = models.FloatField(default=63)  # 63 = desconhecido
    # Status operacional
    operational_status = models.CharField(max_length=50, default="Undeclared")
    extrapolated = models.BooleanField(default=False)
    # Altura relativa (opcional)
    height_distance = models.FloatField(default=0)
    height_reference = models.CharField(max_length=20, default="GroundLevel")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "RID Telemetry"

    def __str__(self):
        return f"Telemetry ISA={self.isa_id} @ {self.timestamp}"
