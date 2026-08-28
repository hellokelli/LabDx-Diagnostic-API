import pytest
import os
import json
from fastapi.testclient import TestClient
from labdx_api import app, resolve_test_name, extract_features, get_citations
from dotenv import load_dotenv
import pandas as pd
import time

load_dotenv()
API_KEY = os.getenv("LABDX_API_KEY", "test-key-for-ci")

client = TestClient(app)

AUTH_HEADERS = {"X-API-Key": API_KEY}

# Test 1: Health check
def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

# Test 2: Test name resolver - exact match
def test_resolve_exact_match():
    result = resolve_test_name("hemoglobin")
    assert result["canonical"] == "hemoglobin"
    assert result["loinc"] == "718-7"
    assert result["confidence"] == 1.0

# Test 3: Test name resolver - fuzzy match
def test_resolve_fuzzy_match():
    result = resolve_test_name("hgb")
    assert result["canonical"] == "hemoglobin"
    assert result["loinc"] == "718-7"

# Test 4: Test name resolver - unknown
def test_resolve_unknown():
    result = resolve_test_name("xyz")
    assert result["canonical"] is None
    assert result["confidence"] == 0.0

# Test 6: Citation lookup
def test_citation_lookup():
    citations = get_citations("D56.3")
    assert len(citations) > 0
    assert "Taher" in citations[0]["reference"]

# Test 7: Diagnose endpoint
def test_diagnose_endpoint():
    request = {
        "patient": {"birth_year": 1975, "sex": "F"},
        "lab_history": [
            {"date": "2024-06-20", "test_name": "hemoglobin", "value": 11.4, "unit": "g/dL"},
            {"date": "2024-06-20", "test_name": "MCV", "value": 70, "unit": "fL"}
        ]
    }
    response = client.post("/diagnose", json=request, headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert "potential_diagnoses" in data
    assert len(data["potential_diagnoses"]) > 0

# Test 8: Diagnose endpoint without auth (should fail)
def test_diagnose_endpoint_no_auth():
    request = {
        "patient": {"birth_year": 1975, "sex": "F"},
        "lab_history": [
            {"date": "2024-06-20", "test_name": "hemoglobin", "value": 11.4, "unit": "g/dL"}
        ]
    }
    response = client.post("/diagnose", json=request)  # No headers
    assert response.status_code == 403
    assert "Invalid API Key" in response.text

# Test 9: Diagnose endpoint with wrong auth (should fail)
def test_diagnose_endpoint_wrong_auth():
    request = {
        "patient": {"birth_year": 1975, "sex": "F"},
        "lab_history": [
            {"date": "2024-06-20", "test_name": "hemoglobin", "value": 11.4, "unit": "g/dL"}
        ]
    }
    wrong_headers = {"X-API-Key": "wrong-key"}
    response = client.post("/diagnose", json=request, headers=wrong_headers)
    assert response.status_code == 403

# Test 10: FHIR endpoint with auth
def test_fhir_endpoint():
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Observation",
                    "code": {"coding": [{"system": "http://loinc.org", "code": "718-7"}]},
                    "valueQuantity": {"value": 11.4, "unit": "g/dL"},
                    "effectiveDateTime": "2024-06-20"
                }
            }
        ]
    }
    response = client.post("/diagnose/fhir", json=bundle, headers=AUTH_HEADERS)
    assert response.status_code == 200

# Test 11: Test unit normalization for hbg
def test_unit_normalization_hemoglobin():
    from labdx_api import validate_and_normalize_units
    
    # g/dL is standard, no change
    val, err = validate_and_normalize_units(11.4, "g/dL", "hemoglobin")
    assert err is None
    assert val == 11.4
    
    # g/L converts to g/dL
    val, err = validate_and_normalize_units(114, "g/L", "hemoglobin")
    assert err is None
    assert val == 11.4
    
    # Unsupported unit
    val, err = validate_and_normalize_units(11.4, "mg/dL", "hemoglobin")
    assert err is not None

# Test 12: Test unit normalization for mcv
def test_unit_normalization_mcv():
    from labdx_api import validate_and_normalize_units
    
    val, err = validate_and_normalize_units(70, "fL", "mcv")
    assert err is None
    assert val == 70
    
    val, err = validate_and_normalize_units(70, "um^3", "mcv")
    assert err is None
    assert val == 70

#Test 13: Test FHIR parser when value is None
def test_fhir_parse_missing_value():
    from labdx_api import parse_fhir_bundle, FHIRBundle
    
    bundle = FHIRBundle(
        type="collection",
        entry=[{
            "resource": {
                "resourceType": "Observation",
                "code": {"coding": [{"system": "http://loinc.org", "code": "718-7"}]},
                "valueQuantity": {"value": None, "unit": "g/dL"},
                "effectiveDateTime": "2024-06-20"
            }
        }]
    )
    results = parse_fhir_bundle(bundle)
    assert len(results) == 0  # Should skip None values

#Test 14: Test FHIR parser with missing effectiveDateTime
def test_fhir_parse_missing_date():
    from labdx_api import parse_fhir_bundle, FHIRBundle
    
    bundle = FHIRBundle(
        type="collection",
        entry=[{
            "resource": {
                "resourceType": "Observation",
                "code": {"coding": [{"system": "http://loinc.org", "code": "718-7"}]},
                "valueQuantity": {"value": 11.4, "unit": "g/dL"},
                "effectiveDateTime": ""
            }
        }]
    )
    results = parse_fhir_bundle(bundle)
    # Should use default date "2024-01-01"
    assert len(results) == 1
    assert results[0].date == "2024-01-01"

#Test 15: Test unit validation with unknown test
def test_unit_normalization_unknown_test():
    from labdx_api import validate_and_normalize_units
    
    val, err = validate_and_normalize_units(10.5, "g/dL", "unknown_test")
    assert err is not None
    assert "Unknown test" in err

#Test 16: Test unit validation with unsupported unit
def test_unit_normalization_unsupported_unit():
    from labdx_api import validate_and_normalize_units
    
    val, err = validate_and_normalize_units(10.5, "mg/dL", "hemoglobin")
    assert err is not None
    assert "Unsupported unit" in err

#Test 17: Test diagnose endpoint with no valid lab results
def test_diagnose_endpoint_no_labs():
    request = {
        "patient": {"birth_year": 1975, "sex": "F"},
        "lab_history": [
            {"date": "2024-06-20", "test_name": "unknown_test", "value": 10.5, "unit": "g/dL"}
        ]
    }
    response = client.post("/diagnose", json=request, headers=AUTH_HEADERS)
    assert response.status_code == 500

#Test 18: Test FHIR endpoint with empty bundle
def test_fhir_endpoint_empty_bundle():   
    bundle = {"resourceType": "Bundle", "type": "collection", "entry": []}
    response = client.post("/diagnose/fhir", json=bundle, headers=AUTH_HEADERS)
    assert response.status_code == 400

#Test 19: Test ModelRegistry with missing moodel file
def test_model_registry_missing_model():
    from labdx_api import ModelRegistry
    
    registry = ModelRegistry(model_dir="/non/existent/path")
    # Should still initialize but with no models
    assert len(registry.models) == 0

#Test 20: Test predict_all when no models are loaded
def test_predict_all_with_no_models():
    from labdx_api import ModelRegistry
    
    registry = ModelRegistry(model_dir="/non/existent/path")
    features = pd.DataFrame({"hemoglobin": [13.0], "mcv": [90]})
    results = registry.predict_all(features)
    assert results == {}  # No models, no predictions

# Test 21: Rate limiting
def test_rate_limiting():
    """Test that rate limiting returns 429 after too many requests"""
    request = {
        "patient": {"birth_year": 1975, "sex": "F"},
        "lab_history": [
            {"date": "2024-06-20", "test_name": "hemoglobin", "value": 11.4, "unit": "g/dL"}
        ]
    }
    # Make 101 requests in quick succession
    for i in range(101):
        response = client.post("/diagnose", json=request, headers=AUTH_HEADERS)
        if i >= 100:
            assert response.status_code == 429
            break

# Test 22: Test name resolver - case insensitivity
def test_resolve_case_insensitive():
    result = resolve_test_name("HEMOGLOBIN")
    assert result["canonical"] == "hemoglobin"
    
    result = resolve_test_name("Hb")
    assert result["canonical"] == "hemoglobin"

# Test 23: Test name resolver - with spaces
def test_resolve_with_spaces():
    result = resolve_test_name("  hemoglobin  ")
    assert result["canonical"] == "hemoglobin"

# Test 24: Test name resolver - synonyms
def test_resolve_synonyms():
    result = resolve_test_name("mean corpuscular volume")
    assert result["canonical"] == "mcv"

# Test 25: Feature extraction with all CBC parameters
def test_extract_features_all_params():
    from labdx_api import LabResult
    labs = [
        LabResult(date="2024-01-01", test_name="hemoglobin", value=13.0, unit="g/dL"),
        LabResult(date="2024-01-01", test_name="MCV", value=90, unit="fL"),
        LabResult(date="2024-01-01", test_name="MCH", value=30, unit="pg"),
        LabResult(date="2024-01-01", test_name="RBC", value=4.8, unit="million/uL"),
        LabResult(date="2024-01-01", test_name="RDW", value=13.5, unit="%"),
        LabResult(date="2024-01-01", test_name="hematocrit", value=45, unit="%"),
        LabResult(date="2024-01-01", test_name="platelets", value=200, unit="thousand/uL"),
        LabResult(date="2024-01-01", test_name="WBC", value=10, unit="thousand/uL"),
        LabResult(date="2024-01-01", test_name="MCHC", value=32, unit="g/dL")
    ]
    df = extract_features(labs)
    assert df["hemoglobin"].iloc[0] == 13.0
    assert df["mcv"].iloc[0] == 90
    assert df["mch"].iloc[0] == 30
    assert df["rbc"].iloc[0] == 4.8
    assert df["rdw"].iloc[0] == 13.5
    assert df["hematocrit"].iloc[0] == 45
    assert df["platelets"].iloc[0] == 200
    assert df["wbc"].iloc[0] == 10
    assert df["mchc"].iloc[0] == 32

# Test 26: Feature extraction with defaults
def test_extract_features_defaults():
    from labdx_api import LabResult
    labs = [
        LabResult(date="2024-01-01", test_name="hemoglobin", value=13.0, unit="g/dL")
    ]
    df = extract_features(labs)
    # Missing parameters should use defaults
    assert df["mcv"].iloc[0] == 90
    assert df["mch"].iloc[0] == 30
    assert df["rbc"].iloc[0] == 4.8


# Test 28: Resolve and normalize integration
def test_resolve_and_normalize():
    from labdx_api import LabResult, resolve_and_normalize_lab_results
    labs = [
        LabResult(date="2024-01-01", test_name="hgb", value=114, unit="g/L"),
        LabResult(date="2024-01-01", test_name="mcv", value=70, unit="fL")
    ]
    resolved, errors = resolve_and_normalize_lab_results(labs)
    assert len(errors) == 0
    assert len(resolved) == 2
    # Hemoglobin should be normalized from g/L to g/dL
    assert resolved[0].value == 11.4
    assert resolved[0].unit == "g/dL"

# Test 29: Invalid JSON
def test_invalid_json():
    response = client.post("/diagnose", data="not json", headers=AUTH_HEADERS)
    assert response.status_code == 422

# Test 30: Missing required fields
def test_missing_required_fields():
    request = {
        "patient": {"birth_year": 1975},
        # Missing lab_history
    }
    response = client.post("/diagnose", json=request, headers=AUTH_HEADERS)
    assert response.status_code == 422

# Test 31: Empty lab history
def test_empty_lab_history():
    request = {
        "patient": {"birth_year": 1975, "sex": "F"},
        "lab_history": []
    }
    response = client.post("/diagnose", json=request, headers=AUTH_HEADERS)
    assert response.status_code == 422

# Test 32: FHIR endpoint with malformed bundle
def test_fhir_malformed_bundle():
    bundle = {"not": "valid"}
    response = client.post("/diagnose/fhir", json=bundle, headers=AUTH_HEADERS)
    assert response.status_code == 422

# Test 33: Citation lookup with unknown code
def test_citation_lookup_unknown():
    citations = get_citations("XXXXX")
    assert citations == []