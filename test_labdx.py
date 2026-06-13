import pytest
import os
import json
from fastapi.testclient import TestClient
from labdx_api import app, resolve_test_name, extract_features, get_citations
from dotenv import load_dotenv

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

# Test 5: Feature extraction - Mentzer index
def test_mentzer_index():
    from labdx_api import LabResult
    labs = [
        LabResult(date="2024-01-01", test_name="MCV", value=70, unit="fL"),
        LabResult(date="2024-01-01", test_name="RBC", value=5.2, unit="million/uL")
    ]
    df = extract_features(labs)
    assert df["mentzer_index"].iloc[0] == 70 / 5.2  # ~13.46

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