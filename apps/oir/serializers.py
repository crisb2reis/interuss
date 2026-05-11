"""
Serializers para a API OIR do USS.

Valida payloads no padrão ASTM F3548-22.
"""

from rest_framework import serializers

from .models import OperationalIntent
from apps.validators import validate_oir_payload, validate_area_of_interest
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError


class ExtentVolumePolygonSerializer(serializers.Serializer):
    vertices = serializers.ListField(
        child=serializers.DictField(),
        min_length=3,
    )


class ExtentVolumeSerializer(serializers.Serializer):
    outline_polygon = ExtentVolumePolygonSerializer()
    altitude_lower = serializers.DictField(required=False)
    altitude_upper = serializers.DictField(required=False)


class ExtentSerializer(serializers.Serializer):
    volume = ExtentVolumeSerializer()
    time_start = serializers.DictField()
    time_end = serializers.DictField()


class OIRCreateSerializer(serializers.Serializer):
    """Payload enviado pelo Postman para criar uma OIR."""

    extents = serializers.ListField(
        child=ExtentSerializer(),
        min_length=1,
        help_text="Lista de volumes 4D (obrigatório, mínimo 1 elemento).",
    )
    uss_base_url = serializers.URLField(
        help_text="URL pública desta USS, registrada no DSS.",
    )
    state = serializers.ChoiceField(
        choices=["Accepted", "Activated", "Nonconforming", "Contingent"],
        default="Accepted",
    )
    # Campos opcionais
    subscription_id = serializers.CharField(required=False, allow_blank=True)
    key = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="Lista de OVNs conhecidos (para detecção de conflito).",
    )
    new_subscription = serializers.DictField(
        required=False,
        help_text="Parâmetros para criar nova subscrição no DSS.",
    )

    def validate(self, data):
        try:
            validate_oir_payload(data)
        except DjangoValidationError as e:
            raise ValidationError(detail=e.message if hasattr(e, 'message') else str(e))
        return data


class OperationalIntentSerializer(serializers.ModelSerializer):
    """Serializer de leitura do model OperationalIntent."""

    class Meta:
        model = OperationalIntent
        fields = [
            "id",
            "state",
            "uss_base_url",
            "dss_id",
            "dss_ovn",
            "extents",
            "dss_response",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "dss_id", "dss_ovn", "dss_response", "created_at", "updated_at"]


class QueryDSSSerializer(serializers.Serializer):
    """Payload para consultar constraints/OIRs por área no DSS."""

    area_of_interest = ExtentSerializer(
        help_text="Área de interesse para filtrar constraints no DSS.",
    )

    def validate(self, data):
        try:
            if 'area_of_interest' in data:
                validate_area_of_interest(data['area_of_interest'])
        except DjangoValidationError as e:
            raise ValidationError(detail=e.message if hasattr(e, 'message') else str(e))
        return data

class RIDTelemetrySerializer(serializers.ModelSerializer):
    """Serializer para ingestão de telemetria via POST /uss/telemetry."""
    isa_id = serializers.UUIDField(write_only=True)

    class Meta:
        from .models import RIDTelemetry
        model = RIDTelemetry
        fields = [
            "isa_id", "timestamp", "lat", "lng", "alt", "pressure_altitude",
            "accuracy_h", "accuracy_v", "track", "speed", "speed_accuracy",
            "vertical_speed", "operational_status", "extrapolated",
            "height_distance", "height_reference"
        ]

    def create(self, validated_data):
        isa_id = validated_data.pop("isa_id")
        from .models import IdentificationServiceArea
        from django.db.models import Q
        
        # Tenta buscar pelo ID primário ou pelo DSS ID
        isa = IdentificationServiceArea.objects.filter(
            Q(id=isa_id) | Q(dss_id=str(isa_id))
        ).first()
        
        if not isa:
            raise serializers.ValidationError({"isa_id": f"ISA com ID {isa_id} não encontrado localmente."})
            
        validated_data["isa"] = isa
        return super().create(validated_data)
