import pytest
from django.core.exceptions import ValidationError
from apps.validators import (
    # Common (existentes)
    validate_uuid4, validate_altitude, validate_time_value,
    validate_volume4d, validate_uss_url, validate_flight_plan_id,
    validate_basic_information, validate_execution_style,
    validate_oir_payload, validate_new_subscription,
    validate_latitude, validate_longitude, validate_latlng_point,
    validate_radius, validate_polygon, validate_flight_type,
    validate_entity_ovn, validate_key, validate_subscription_url,
    validate_implicit_subscription, validate_dependent_operational_intents,
    validate_notification_index, validate_uss_availability,
    validate_entity_id, validate_entity_version, validate_identifier,
    validate_country, validate_restriction, validate_region,
    validate_reason_list, validate_authority, validate_interval_before,
    # Geospatial (Fase 2)
    validate_geospatial_http_source,
    validate_geospatial_data_source_status,
    validate_geospatial_query_reply,
    # Flight Planning (Fase 2)
    validate_upsert_flight_plan_request,
    validate_clear_area_request,
    validate_clear_area_outcome,
    validate_user_notification,
    validate_planning_activity_result,
    validate_flight_plan_status,
    validate_advisory_inclusion,
    # RID DSS (Fase 3)
    validate_isa,
    validate_create_isa_parameters,
    validate_rid_subscription,
    validate_create_rid_subscription,
    # RID USS (Fase 3)
    validate_rid_aircraft_position,
    validate_rid_flight,
    validate_rid_flight_details,
    # Drone Mapping (Fase 4)
    validate_create_drone_mapping,
    validate_bulk_create_drone_mappings,
    validate_update_drone_mapping,
    # Flight Strips (Fase 4)
    validate_create_flight_strip,
    validate_update_flight_strip,
    validate_search_flight_strips,
    validate_flight_area,
    # Geo (Fase 4.5)
    validate_position,
    validate_geozone_generic,
)


# =====================================================================
# HELPERS
# =====================================================================

VALID_VOLUME4D = {
    "volume": {
        "outline_polygon": {
            "vertices": [
                {"lat": -15.0, "lng": -47.0},
                {"lat": -15.1, "lng": -47.0},
                {"lat": -15.1, "lng": -47.1},
            ]
        },
        "altitude_lower": {"value": 0, "units": "M", "reference": "W84"},
        "altitude_upper": {"value": 120, "units": "M", "reference": "W84"},
    },
    "time_start": {"value": "2026-05-01T10:00:00Z", "format": "RFC3339"},
    "time_end":   {"value": "2026-05-01T11:00:00Z", "format": "RFC3339"},
}

VALID_TIME = {"value": "2026-05-01T10:00:00Z", "format": "RFC3339"}


# =====================================================================
# FASE 1 — COMMON (Existentes)
# =====================================================================

def test_validate_altitude_advanced():
    validate_altitude({"value": -100, "units": "M", "reference": "W84"})
    with pytest.raises(ValidationError):
        validate_altitude({"value": -9000, "units": "M", "reference": "W84"})
    with pytest.raises(ValidationError):
        validate_altitude({"value": 100, "units": "M", "reference": "SFC"})


def test_validate_time_utc_only():
    validate_time_value({"value": "2026-04-24T12:00:00Z", "format": "RFC3339"})
    with pytest.raises(ValidationError):
        validate_time_value({"value": "2026-04-24T12:00:00+03:00", "format": "RFC3339"})


def test_validate_volume4d_advanced():
    validate_volume4d(VALID_VOLUME4D)
    # Altitudes invertidas
    bad = {
        "volume": {
            "outline_polygon": {
                "vertices": [
                    {"lat": 0, "lng": 0}, {"lat": 0, "lng": 1}, {"lat": 1, "lng": 1}
                ]
            },
            "altitude_lower": {"value": 50, "units": "M", "reference": "W84"},
            "altitude_upper": {"value": 20, "units": "M", "reference": "W84"},
        },
        "time_start": {"value": "2026-04-24T12:00:00Z", "format": "RFC3339"},
        "time_end":   {"value": "2026-04-24T13:00:00Z", "format": "RFC3339"},
    }
    with pytest.raises(ValidationError):
        validate_volume4d(bad)


def test_coordinates():
    assert validate_latitude(45) == 45.0
    with pytest.raises(ValidationError):
        validate_latitude(91)
    assert validate_longitude(120) == 120.0
    with pytest.raises(ValidationError):
        validate_longitude(-181)


# =====================================================================
# FASE 1 — USS (Existentes)
# =====================================================================

def test_flight_type():
    validate_flight_type("VLOS")
    validate_flight_type("BVLOS")
    with pytest.raises(ValidationError):
        validate_flight_type("LOS")


def test_entity_ovn():
    validate_entity_ovn("a" * 16)
    with pytest.raises(ValidationError):
        validate_entity_ovn("small")


def test_subscription_url_advanced():
    validate_subscription_url("https://uss.example.com/utm")
    with pytest.raises(ValidationError):
        validate_subscription_url("https://uss.example.com/utm/")


# =====================================================================
# FASE 1 — DSS (Existentes)
# =====================================================================

def test_geozone_ed269():
    validate_identifier("ZONE001")
    with pytest.raises(ValidationError):
        validate_identifier("TOOLONGID")
    validate_country("BRA")
    with pytest.raises(ValidationError):
        validate_country("BR")
    validate_restriction("PROHIBITED")


def test_authority_advanced():
    auth = {"name": "DECEA", "email": "contato@decea.gov.br"}
    validate_authority(auth)
    with pytest.raises(ValidationError):
        validate_authority({"name": "DECEA"})  # Sem contato


def test_interval_before():
    validate_interval_before("P1D")
    validate_interval_before("PT1H30M")
    with pytest.raises(ValidationError):
        validate_interval_before("1 day")


# =====================================================================
# FASE 1 — CodeZoneTypeEnum (bug fix: todos os 6 valores devem ser aceitos)
# =====================================================================

def test_geozone_type_all_values():
    """Valida os 6 tipos de zona ED-269 (corrigido na Fase 1)."""
    types = ["COMMON", "CUSTOMIZED", "PROHIBITED", "REQ_AUTHORISATION", "CONDITIONAL", "NO_RESTRICTION"]
    dummy_auth = [{"name": "DECEA", "email": "a@b.com"}]
    dummy_geom = [{"uomDimensions": "M", "horizontalProjection": {"type": "Polygon", "coordinates": [[[-1,-1], [-1,1], [1,1], [1,-1], [-1,-1]]]}}]
    for t in types:
        from apps.validators.dss.schemas import GeozoneSchema
        GeozoneSchema(**{"identifier": "Z", "country": "BRA", "type": t, "restriction": "NO_RESTRICTION", "zoneAuthority": dummy_auth, "geometry": dummy_geom})


# =====================================================================
# FASE 2 — Geospatial
# =====================================================================

def test_validate_geospatial_http_source_valid():
    data = {
        "https_source": {
            "url": "https://caa.example.com/geozones.json",
            "format": "ED-269"
        }
    }
    result = validate_geospatial_http_source(data)
    assert result is not None


def test_validate_geospatial_http_source_invalid_format():
    data = {
        "https_source": {
            "url": "https://caa.example.com/geozones.json",
            "format": "UNKNOWN_FORMAT"
        }
    }
    with pytest.raises(ValidationError):
        validate_geospatial_http_source(data)


def test_validate_geospatial_data_source_status():
    validate_geospatial_data_source_status({"id": "abc123", "status": "Ready"})
    validate_geospatial_data_source_status({"id": "abc123", "status": "Error", "message": "Failed to load"})


def test_validate_geospatial_query_reply():
    data = {"results": [{"features_selection_outcome": "Present"}]}
    result = validate_geospatial_query_reply(data)
    assert result["results"][0]["features_selection_outcome"] == "Present"


# =====================================================================
# FASE 2 — Flight Planning
# =====================================================================

def test_validate_upsert_flight_plan_request_valid():
    data = {
        "flight_plan": {"basic_information": {"usage_state": "Planned"}},
        "execution_style": "IfAllowed",
        "request_id": "req-001",
    }
    result = validate_upsert_flight_plan_request(data)
    assert result is not None


def test_validate_upsert_flight_plan_invalid_execution_style():
    data = {
        "flight_plan": {},
        "execution_style": "INVALID",
        "request_id": "req-002",
    }
    with pytest.raises(ValidationError):
        validate_upsert_flight_plan_request(data)


def test_validate_clear_area_request():
    data = {
        "request_id": "clear-001",
        "extent": {"volume": {}, "time_start": "2026-01-01T00:00:00Z", "time_end": "2026-01-01T01:00:00Z"}
    }
    result = validate_clear_area_request(data)
    assert result["request_id"] == "clear-001"


def test_validate_clear_area_outcome():
    validate_clear_area_outcome({"success": True})
    validate_clear_area_outcome({"success": False, "message": "No flights found"})


def test_validate_planning_activity_result_enum():
    validate_planning_activity_result("Completed")
    validate_planning_activity_result("Rejected")
    validate_planning_activity_result("Failed")
    validate_planning_activity_result("NotSupported")
    with pytest.raises(ValidationError):
        validate_planning_activity_result("Unknown")


def test_validate_flight_plan_status_enum():
    validate_flight_plan_status("NotPlanned")
    validate_flight_plan_status("Planned")
    validate_flight_plan_status("Closed")
    with pytest.raises(ValidationError):
        validate_flight_plan_status("Active")


def test_validate_advisory_inclusion_enum():
    validate_advisory_inclusion("Unknown")
    validate_advisory_inclusion("None")
    with pytest.raises(ValidationError):
        validate_advisory_inclusion("SomeAdvisory")


# =====================================================================
# FASE 3 — Remote ID (DSS)
# =====================================================================

def test_validate_isa_valid():
    data = {
        "uss_base_url": "https://uss.example.com/rid",
        "owner": "uss_owner",
        "time_start": VALID_TIME,
        "time_end": {"value": "2026-05-01T12:00:00Z", "format": "RFC3339"},
        "version": "1",
        "id": "isa-abc123",
    }
    result = validate_isa(data)
    assert result["id"] == "isa-abc123"


def test_validate_isa_invalid_url():
    data = {
        "uss_base_url": "http://uss.example.com/rid",  # HTTP sem S
        "owner": "uss_owner",
        "time_start": VALID_TIME,
        "time_end": {"value": "2026-05-01T12:00:00Z", "format": "RFC3339"},
        "version": "1",
        "id": "isa-abc123",
    }
    with pytest.raises(ValidationError):
        validate_isa(data)


def test_validate_create_isa_parameters():
    data = {
        "extents": VALID_VOLUME4D,
        "uss_base_url": "https://uss.example.com/rid",
    }
    result = validate_create_isa_parameters(data)
    assert result is not None


def test_validate_rid_subscription_valid():
    data = {
        "id": "sub-001",
        "uss_base_url": "https://uss.example.com/rid",
        "owner": "owner",
        "version": "1",
    }
    result = validate_rid_subscription(data)
    assert result["id"] == "sub-001"


# =====================================================================
# FASE 3 — Remote ID (USS)
# =====================================================================

def test_validate_rid_aircraft_position_valid():
    data = {
        "lat": -15.7801,
        "lng": -47.9292,
        "alt": 120.0,
        "accuracy_h": "HA10m",
        "accuracy_v": "VA3m",
    }
    result = validate_rid_aircraft_position(data)
    assert result["lat"] == -15.7801


def test_validate_rid_aircraft_position_invalid_lat():
    data = {"lat": 95.0, "lng": -47.9}
    with pytest.raises(ValidationError):
        validate_rid_aircraft_position(data)


def test_validate_rid_aircraft_position_invalid_lng():
    data = {"lat": -15.0, "lng": 200.0}
    with pytest.raises(ValidationError):
        validate_rid_aircraft_position(data)


def test_validate_rid_flight_valid():
    data = {
        "id": "flight-001",
        "aircraft_type": "Helicopter",
    }
    result = validate_rid_flight(data)
    assert result["id"] == "flight-001"


def test_validate_rid_flight_invalid_aircraft_type():
    data = {
        "id": "flight-002",
        "aircraft_type": "FlyingCar",  # Não existe no UAType enum
    }
    with pytest.raises(ValidationError):
        validate_rid_flight(data)


def test_validate_rid_flight_details():
    data = {"id": "flight-001"}
    result = validate_rid_flight_details(data)
    assert result["id"] == "flight-001"


# =====================================================================
# FASE 4 — Drone Mapping
# =====================================================================

def test_validate_create_drone_mapping_valid():
    data = {
        "id": "drone-alpha",
        "serial_number": "SN12345678",
        "sisant": "SISANT001",
    }
    result = validate_create_drone_mapping(data)
    assert result["id"] == "drone-alpha"


def test_validate_create_drone_mapping_missing_serial():
    with pytest.raises(ValidationError):
        validate_create_drone_mapping({"id": "drone-beta", "sisant": "S01"})


def test_validate_bulk_create_drone_mappings():
    data = {
        "mappings": [
            {"id": "d1", "serial_number": "SN001", "sisant": "SA001"},
            {"id": "d2", "serial_number": "SN002", "sisant": "SA002"},
        ]
    }
    result = validate_bulk_create_drone_mappings(data)
    assert len(result["mappings"]) == 2


def test_validate_update_drone_mapping_partial():
    data = {"serial_number": "SN_UPDATED"}
    result = validate_update_drone_mapping(data)
    assert result["serial_number"] == "SN_UPDATED"


# =====================================================================
# FASE 4 — Flight Strips
# =====================================================================

def test_validate_create_flight_strip_valid():
    data = {
        "name": "Strip Alpha",
        "flight_area": "green",
        "height": 120,
        "takeoff_time": "08:30",
        "landing_time": "09:00",
    }
    result = validate_create_flight_strip(data)
    assert result["name"] == "Strip Alpha"


def test_validate_create_flight_strip_name_too_long():
    with pytest.raises(ValidationError):
        validate_create_flight_strip({
            "name": "A" * 21,  # > 20 chars
            "flight_area": "green",
        })


def test_validate_create_flight_strip_invalid_area():
    with pytest.raises(ValidationError):
        validate_create_flight_strip({
            "name": "Strip Beta",
            "flight_area": "black",  # Não existe
        })


def test_validate_create_flight_strip_invalid_time_format():
    with pytest.raises(ValidationError):
        validate_create_flight_strip({
            "name": "Strip C",
            "flight_area": "red",
            "takeoff_time": "25:00",  # Hora inválida
        })


def test_validate_update_flight_strip_partial():
    data = {"flight_area": "blue", "active": False}
    result = validate_update_flight_strip(data)
    assert result["flight_area"] == "blue"


def test_validate_search_flight_strips():
    data = {"flight_area": "yellow", "limit": 50, "offset": 0}
    result = validate_search_flight_strips(data)
    assert result["limit"] == 50


def test_validate_flight_area_valid():
    for area in ["red", "yellow", "orange", "green", "blue", "purple"]:
        validate_flight_area(area)


def test_validate_flight_area_invalid():
    with pytest.raises(ValidationError):
        validate_flight_area("black")


# =====================================================================
# FASE 4.5 — Geo
# =====================================================================

def test_validate_position_valid():
    data = {
        "longitude": -47.9,
        "latitude": -15.8,
        "accuracy_h": "HA10m",
        "accuracy_v": "VA3m",
    }
    result = validate_position(data)
    assert result["longitude"] == -47.9


def test_validate_geozone_generic_valid():
    data = {
        "identifier": "GEO01",
        "country": "BRA",
        "zone_authority": [{"name": "DECEA"}],
        "type": "COMMON",
        "restriction": "PROHIBITED",
    }
    result = validate_geozone_generic(data)
    assert result["identifier"] == "GEO01"

