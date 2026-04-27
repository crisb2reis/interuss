"""
apps/validators — Camada de validação Pydantic para o projeto InterUSS/BR-UTM.

Estrutura:
  common/  — tipos base (Volume4D, Altitude, Time, LatLng, Geo, API)
  dss/     — schemas DSS: OIR, subscriptions, geozones ED-269, Remote ID
  uss/     — schemas USS: flight planning, OI details, constraints, RID, drone mapping
  tests/   — testes unitários pytest

Padrão: todas as funções públicas convertem PydanticValidationError
        em django.core.exceptions.ValidationError para compatibilidade Django.

Referências normativas:
  - ASTM F3548-21 (UTM)
  - ED-269 (geozones U-Space)
  - InterUSS Platform SCD test interface
"""
from pydantic import ValidationError as PydanticError, UUID4
from django.core.exceptions import ValidationError

# Schemas
from .common.schemas import (
    AltitudeSchema, TimeSchema, Volume4DSchema, LatLngPointSchema, 
    RadiusSchema, PolygonSchema, validate_url_https_no_slash
)
from .uss.schemas import (
    FlightTypeEnum, ExecutionStyleEnum, USSAvailabilityEnum,
    EntityOVNSchema, BasicInformationSchema, SubscriptionAdvancedSchema
)
from .dss.schemas import (
    OIRPayloadSchema, GeozoneSchema, AuthoritySchema, SubscriptionSchema
)

def _wrap_pydantic(schema_cls, data):
    try:
        if isinstance(data, list):
            return [schema_cls(**item).model_dump() for item in data]
        model = schema_cls(**data)
        return model.model_dump()
    except PydanticError as e:
        raise ValidationError(str(e))

# --- Common Validators ---

def validate_uuid4(value):
    from uuid import UUID
    try:
        val = UUID(value, version=4)
    except ValueError:
        raise ValidationError(f"Invalid UUID v4 format: {value}")
    if val.hex != value.replace('-', ''):
         raise ValidationError(f"Invalid UUID v4 format strictly matching: {value}")
    return value

def validate_altitude(data):
    return _wrap_pydantic(AltitudeSchema, data)

def validate_time_value(data):
    return _wrap_pydantic(TimeSchema, data)

def validate_volume4d(data):
    return _wrap_pydantic(Volume4DSchema, data)

def validate_uss_url(value):
    try:
        return validate_url_https_no_slash(value)
    except ValueError as e:
        raise ValidationError(str(e))

def validate_latitude(value):
    res = _wrap_pydantic(LatLngPointSchema, {"lat": value, "lng": 0})
    return res["lat"] if isinstance(res, dict) else res

def validate_longitude(value):
    res = _wrap_pydantic(LatLngPointSchema, {"lat": 0, "lng": value})
    return res["lng"] if isinstance(res, dict) else res

def validate_latlng_point(data):
    return _wrap_pydantic(LatLngPointSchema, data)

def validate_radius(data):
    return _wrap_pydantic(RadiusSchema, data)

def validate_polygon(vertices):
    res = _wrap_pydantic(PolygonSchema, {"vertices": vertices})
    return res["vertices"] if isinstance(res, dict) else res

# --- USS Validators ---

def validate_flight_plan_id(value):
    return validate_uuid4(value)

def validate_basic_information(data):
    return _wrap_pydantic(BasicInformationSchema, data)

def validate_execution_style(value):
    if value not in [e.value for e in ExecutionStyleEnum]:
         raise ValidationError(f"Invalid ExecutionStyle: {value}")
    return value

def validate_flight_type(value):
    if value not in [e.value for e in FlightTypeEnum]:
        raise ValidationError(f"Invalid FlightType: {value}")
    return value

def validate_entity_ovn(value):
    res = _wrap_pydantic(EntityOVNSchema, {"value": value})
    return res["value"] if isinstance(res, dict) else res

def validate_key(key_list):
    if not isinstance(key_list, list):
        raise ValidationError("Key must be a list.")
    return [validate_entity_ovn(k) for k in key_list]

def validate_uss_availability(value):
    if value not in [e.value for e in USSAvailabilityEnum]:
        raise ValidationError(f"Invalid availability: {value}")
    return value

def validate_subscription_url(value):
    return validate_uss_url(value)

def validate_implicit_subscription(value):
    if not isinstance(value, bool):
         raise ValidationError("implicit_subscription must be a boolean.")
    return value

def validate_dependent_operational_intents(value):
    if not isinstance(value, list):
         raise ValidationError("dependent_operational_intents must be a list of UUIDs.")
    return [validate_uuid4(v) for v in value]

def validate_notification_index(value):
    if not isinstance(value, int) or value < 0:
        raise ValidationError("notification_index must be a non-negative integer.")
    return value

# --- DSS Validators ---

def validate_oir_payload(data):
    return _wrap_pydantic(OIRPayloadSchema, data)

def validate_area_of_interest(data):
    return validate_volume4d(data)

def validate_new_subscription(data):
    return _wrap_pydantic(SubscriptionSchema, data)

def validate_identifier(value):
    dummy_auth = [{"name": "Auth", "email": "test@test.com", "purpose": "AUTHORIZATION"}]
    dummy_geom = [{"uomDimensions": "M", "horizontalProjection": {"type": "Polygon", "coordinates": [[[-1,-1], [-1,1], [1,1], [1,-1], [-1,-1]]]}}]
    return _wrap_pydantic(GeozoneSchema, {"identifier": value, "country": "BRA", "type": "COMMON", "restriction": "NO_RESTRICTION", "zoneAuthority": dummy_auth, "geometry": dummy_geom})["identifier"]

def validate_country(value):
    dummy_auth = [{"name": "Auth", "email": "test@test.com", "purpose": "AUTHORIZATION"}]
    dummy_geom = [{"uomDimensions": "M", "horizontalProjection": {"type": "Polygon", "coordinates": [[[-1,-1], [-1,1], [1,1], [1,-1], [-1,-1]]]}}]
    return _wrap_pydantic(GeozoneSchema, {"identifier": "ZONE", "country": value, "type": "COMMON", "restriction": "NO_RESTRICTION", "zoneAuthority": dummy_auth, "geometry": dummy_geom})["country"]

def validate_restriction(value):
    valid = ["COMMON", "CUSTOMIZED", "PROHIBITED", "REQ_AUTHORISATION", "CONDITIONAL", "NO_RESTRICTION"]
    if value not in valid:
        raise ValidationError(f"Invalid restriction: {value}. Valid options: {valid}")
    return value

def validate_authority(data):
    return _wrap_pydantic(AuthoritySchema, data)

def validate_entity_id(value):
    return validate_uuid4(value)

def validate_entity_version(value):
    if not isinstance(value, int) or value < 0 or value > 2147483647:
        raise ValidationError(f"EntityVersion {value} out of bit-32 range.")
    return value

def validate_internal_subscription_id(value):
    return validate_uuid4(value)

def validate_region(value):
    dummy_auth = [{"name": "Auth", "email": "test@test.com", "purpose": "AUTHORIZATION"}]
    dummy_geom = [{"uomDimensions": "M", "horizontalProjection": {"type": "Polygon", "coordinates": [[[-1,-1], [-1,1], [1,1], [1,-1], [-1,-1]]]}}]
    return _wrap_pydantic(GeozoneSchema, {"identifier": "Z", "country": "BRA", "type": "COMMON", "restriction": "NO_RESTRICTION", "region": value, "zoneAuthority": dummy_auth, "geometry": dummy_geom})["region"]

def validate_reason_list(value):
    dummy_auth = [{"name": "Auth", "email": "test@test.com", "purpose": "AUTHORIZATION"}]
    dummy_geom = [{"uomDimensions": "M", "horizontalProjection": {"type": "Polygon", "coordinates": [[[-1,-1], [-1,1], [1,1], [1,-1], [-1,-1]]]}}]
    valid_reasons = [] if not value else [v if v in ["AIR_TRAFFIC", "SENSITIVE", "PRIVACY", "POPULATION", "NATURE", "NOISE", "FOREIGN_TERRITORY", "EMERGENCY", "OTHER"] else "OTHER" for v in value]
    _wrap_pydantic(GeozoneSchema, {"identifier": "Z", "country": "BRA", "type": "COMMON", "restriction": "NO_RESTRICTION", "reason": valid_reasons, "zoneAuthority": dummy_auth, "geometry": dummy_geom})
    return value

def validate_interval_before(value):
    import re
    regex = r"^P(?:\d+D)?(?:T(?:\d+H)?(?:\d+M)?)?$"
    if not isinstance(value, str) or not re.match(regex, value) or value in ("P", "PT"):
        raise ValidationError(f"Interval before must be a valid ISO 8601 duration (PnnDTnnHnnM). Got: {value}")
    return value

# --- Geospatial Validators (Fase 2) ---

from .common.geospatial_schemas import (
    GeospatialMapHttpSourceSchema,
    GeospatialDataSourceStatusSchema,
    GeospatialDataSourceResponseSchema,
    ListGeospatialDataSourcesResponseSchema,
    GeospatialMapQueryReplySchema,
    GeospatialMapCheckResultSchema,
    StatusResponseSchema as GeospatialStatusResponseSchema,
)

from .common.geo_schemas import (
    PositionSchema,
    GeoZoneSchema as GeoZoneGenericSchema,
)


def validate_position(data):
    """Valida posição genérica conforme geo.py."""
    return _wrap_pydantic(PositionSchema, data)


def validate_geozone_generic(data):
    """Valida geozone conforme estrutura genérica de geo.py."""
    return _wrap_pydantic(GeoZoneGenericSchema, data)


def validate_geospatial_http_source(data):
    return _wrap_pydantic(GeospatialMapHttpSourceSchema, data)

def validate_geospatial_data_source_status(data):
    return _wrap_pydantic(GeospatialDataSourceStatusSchema, data)

def validate_geospatial_query_reply(data):
    return _wrap_pydantic(GeospatialMapQueryReplySchema, data)

# --- Flight Planning Validators (Fase 2) ---

from .uss.flight_planning_schemas import (
    UpsertFlightPlanRequestSchema,
    UpsertFlightPlanResponseSchema,
    DeleteFlightPlanResponseSchema,
    ClearAreaRequestSchema,
    ClearAreaOutcomeSchema,
    ClearAreaResponseSchema,
    UserNotificationSchema,
    QueryUserNotificationsResponseSchema,
    PlanningActivityResultEnum,
    FlightPlanStatusEnum,
    AdvisoryInclusionEnum,
)

def validate_upsert_flight_plan_request(data):
    return _wrap_pydantic(UpsertFlightPlanRequestSchema, data)

def validate_clear_area_request(data):
    return _wrap_pydantic(ClearAreaRequestSchema, data)

def validate_clear_area_outcome(data):
    return _wrap_pydantic(ClearAreaOutcomeSchema, data)

def validate_user_notification(data):
    return _wrap_pydantic(UserNotificationSchema, data)

def validate_planning_activity_result(value):
    if value not in [e.value for e in PlanningActivityResultEnum]:
        raise ValidationError(f"Invalid PlanningActivityResult: {value}")
    return value

def validate_flight_plan_status(value):
    if value not in [e.value for e in FlightPlanStatusEnum]:
        raise ValidationError(f"Invalid FlightPlanStatus: {value}")
    return value

def validate_advisory_inclusion(value):
    if value not in [e.value for e in AdvisoryInclusionEnum]:
        raise ValidationError(f"Invalid AdvisoryInclusion: {value}")
    return value

# --- Remote ID DSS Validators (Fase 3) ---

from .dss.remoteid_schemas import (
    IdentificationServiceAreaSchema,
    IdentificationServiceAreaFullSchema,
    RIDSubscriptionSchema,
    CreateISAParametersSchema,
    UpdateISAParametersSchema,
    PutISAResponseSchema,
    DeleteISAResponseSchema,
    GetISAResponseSchema,
    SearchISAResponseSchema,
    CreateRIDSubscriptionParametersSchema,
    PutRIDSubscriptionResponseSchema,
    DeleteRIDSubscriptionResponseSchema,
    GetRIDSubscriptionResponseSchema,
    SearchRIDSubscriptionsResponseSchema,
)

def validate_isa(data):
    return _wrap_pydantic(IdentificationServiceAreaSchema, data)

def validate_create_isa_parameters(data):
    return _wrap_pydantic(CreateISAParametersSchema, data)

def validate_rid_subscription(data):
    return _wrap_pydantic(RIDSubscriptionSchema, data)

def validate_create_rid_subscription(data):
    return _wrap_pydantic(CreateRIDSubscriptionParametersSchema, data)

# --- Remote ID USS Validators (Fase 3) ---

from .uss.remoteid_schemas import (
    RIDAircraftPositionSchema,
    RIDAircraftStateSchema,
    RIDFlightSchema,
    RIDFlightDetailsSchema,
    GetFlightsResponseSchema,
    GetFlightDetailsResponseSchema,
    PutIdentificationServiceAreaNotificationParametersSchema,
)

def validate_rid_aircraft_position(data):
    return _wrap_pydantic(RIDAircraftPositionSchema, data)

def validate_rid_flight(data):
    return _wrap_pydantic(RIDFlightSchema, data)

def validate_rid_flight_details(data):
    return _wrap_pydantic(RIDFlightDetailsSchema, data)

def validate_isa_notification(data):
    return _wrap_pydantic(PutIdentificationServiceAreaNotificationParametersSchema, data)

# --- Drone Mapping Validators (Fase 4) ---

from .uss.drone_mapping_schemas import (
    CreateDroneMappingRequestSchema,
    BulkCreateDroneMappingsRequestSchema,
    UpdateDroneMappingRequestSchema,
)

def validate_create_drone_mapping(data):
    return _wrap_pydantic(CreateDroneMappingRequestSchema, data)

def validate_bulk_create_drone_mappings(data):
    return _wrap_pydantic(BulkCreateDroneMappingsRequestSchema, data)

def validate_update_drone_mapping(data):
    return _wrap_pydantic(UpdateDroneMappingRequestSchema, data)

# --- Flight Strip Validators (Fase 4) ---

from .uss.flight_strip_schemas import (
    CreateFlightStripRequestSchema,
    UpdateFlightStripRequestSchema,
    SearchFlightStripsRequestSchema,
    FlightAreaEnum,
)

def validate_create_flight_strip(data):
    return _wrap_pydantic(CreateFlightStripRequestSchema, data)

def validate_update_flight_strip(data):
    return _wrap_pydantic(UpdateFlightStripRequestSchema, data)

def validate_search_flight_strips(data):
    return _wrap_pydantic(SearchFlightStripsRequestSchema, data)

def validate_flight_area(value):
    if value not in [e.value for e in FlightAreaEnum]:
        raise ValidationError(f"Invalid FlightArea: {value}. Valid: {[e.value for e in FlightAreaEnum]}")
    return value


# --- Airspace Validators (Fase 4) ---

from .common.airspace_schemas import AirspaceAllocationsSchema, AirspaceFlightsSchema


def validate_airspace_allocations(data):
    """Valida o payload completo de alocações de espaço aéreo (OIs + Constraints + ISAs)."""
    return _wrap_pydantic(AirspaceAllocationsSchema, data)


def validate_airspace_flights(data):
    """Valida a lista de voos RID associados a uma janela de espaço aéreo."""
    return _wrap_pydantic(AirspaceFlightsSchema, data)


# --- API Response Validators (Fase 4) ---

from .common.api_schemas import ApiResponseSchema


def validate_api_response(data):
    """Valida a estrutura genérica de resposta da API (message + data)."""
    return _wrap_pydantic(ApiResponseSchema, data)


# --- Telemetry Validators (Fase 3 — consolidação) ---

from .uss.telemetry_schemas import (
    VehicleTelemetrySchema,
    VelocitySchema,
    GetOperationalIntentTelemetryResponseSchema,
)


def validate_vehicle_telemetry(data):
    """Valida telemetria de veículo (posição + velocidade + timestamp). ASTM F3548-21 §A3.3."""
    return _wrap_pydantic(VehicleTelemetrySchema, data)


def validate_telemetry_response(data):
    """Valida resposta completa de telemetria de operational intent off-nominal."""
    return _wrap_pydantic(GetOperationalIntentTelemetryResponseSchema, data)
