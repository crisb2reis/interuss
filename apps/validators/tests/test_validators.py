import pytest
from django.core.exceptions import ValidationError
from apps.validators import (
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
    validate_reason_list, validate_authority, validate_interval_before
)

# --- COMMON TESTS ---

def test_validate_altitude_advanced():
    # Válido (-8000..100000, W84)
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
    valid_vol = {
        "volume": {
            "outline_polygon": {"vertices": [{"lat": 0, "lng": 0}, {"lat": 0, "lng": 1}, {"lat": 1, "lng": 1}]},
            "altitude_lower": {"value": 10, "units": "M", "reference": "W84"},
            "altitude_upper": {"value": 20, "units": "M", "reference": "W84"}
        },
        "time_start": {"value": "2026-04-24T12:00:00Z", "format": "RFC3339"},
        "time_end": {"value": "2026-04-24T13:00:00Z", "format": "RFC3339"}
    }
    validate_volume4d(valid_vol)
    # Erro: altitudes invertidas
    invalid_vol = valid_vol.copy()
    invalid_vol["volume"]["altitude_lower"]["value"] = 30
    with pytest.raises(ValidationError):
        validate_volume4d(invalid_vol)

def test_coordinates():
    assert validate_latitude(45) == 45.0
    with pytest.raises(ValidationError):
        validate_latitude(91)
    assert validate_longitude(120) == 120.0
    with pytest.raises(ValidationError):
        validate_longitude(-181)

# --- USS TESTS ---

def test_flight_type():
    validate_flight_type("VLOS")
    validate_flight_type("BVLOS")
    with pytest.raises(ValidationError):
        validate_flight_type("LOS")

def test_entity_ovn():
    validate_entity_ovn("a"*16)
    with pytest.raises(ValidationError):
        validate_entity_ovn("small")

def test_subscription_url_advanced():
    validate_subscription_url("https://uss.example.com/utm")
    with pytest.raises(ValidationError):
        validate_subscription_url("https://uss.example.com/utm/")

# --- DSS TESTS ---

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
        validate_authority({"name": "DECEA"}) # Sem contato

def test_interval_before():
    validate_interval_before("P1D")
    validate_interval_before("PT1H30M")
    with pytest.raises(ValidationError):
        validate_interval_before("1 day")
