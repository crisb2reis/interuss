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
