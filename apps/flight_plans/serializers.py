from rest_framework import serializers
from .models import FlightPlan, OperationalIntent, State
from django.contrib.gis.geos import Polygon, MultiPolygon, Point

class FlightPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlightPlan
        fields = '__all__'

class OperationalIntentSerializer(serializers.ModelSerializer):
    flight_plan = FlightPlanSerializer()

    class Meta:
        model = OperationalIntent
        fields = '__all__'

    def create(self, validated_data):
        flight_plan_data = validated_data.pop('flight_plan')
        flight_plan = FlightPlan.objects.create(**flight_plan_data)
        operational_intent = OperationalIntent.objects.create(flight_plan=flight_plan, **validated_data)
        return operational_intent

# ─── ASTM F3548-21 SERIALIZERS ──────────────────────────────────

class ASTMBasicInformationSerializer(serializers.Serializer):
    usage_state = serializers.ChoiceField(choices=["Planned", "InUse", "Closed"])
    uas_state = serializers.CharField(required=False, allow_blank=True, default="")
    area = serializers.ListField(child=serializers.DictField(), min_length=1)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    utm_id = serializers.UUIDField(required=False, allow_null=True)
    specific_session_id = serializers.CharField(required=False, allow_blank=True, default="")

class ASTMFlightPlanBodySerializer(serializers.Serializer):
    basic_information = ASTMBasicInformationSerializer()
    uas = serializers.CharField(required=False, allow_blank=True, default="")
    operator = serializers.CharField(required=False, allow_blank=True, default="")
    telemetry = serializers.CharField(required=False, allow_blank=True, default="")
    astm_f3548_21 = serializers.CharField(required=False, allow_blank=True, default="")
    uspace_flight_authorisation = serializers.CharField(required=False, allow_blank=True, default="")
    rpas_operating_rules_2_6 = serializers.CharField(required=False, allow_blank=True, default="")
    additional_information = serializers.DictField(required=False, default=dict)

class ASTMFlightPlanRequestSerializer(serializers.Serializer):
    flight_plan = ASTMFlightPlanBodySerializer()
    execution_style = serializers.ChoiceField(
        choices=["IfAllowed", "DespiteConflict"],
        default="IfAllowed"
    )
    request_id = serializers.CharField(required=False, allow_blank=True, default="")

class ASTMFlightPlanResponseSerializer(serializers.Serializer):
    planning_result = serializers.CharField()
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    flight_plan_status = serializers.CharField()
    as_planned = ASTMFlightPlanBodySerializer()
    includes_advisories = serializers.CharField(default="NoAdvisoriesOrConditions")
