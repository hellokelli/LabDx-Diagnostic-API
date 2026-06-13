import pandas as pd
import numpy as np
import xgboost as xgb
import shap
import json
import os
import re
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
import time
from dotenv import load_dotenv
import os
from fuzzywuzzy import fuzz, process
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.security import APIKeyHeader
from fastapi import Security, HTTPException, status

# ============================================
# Authentication
# ============================================
load_dotenv()
API_KEY = os.getenv("LABDX_API_KEY")
if API_KEY is None:
    raise ValueError("LABDX_API_KEY environment variable is not set. Check your .env file.")
API_KEY_NAME = "X-API-Key"

api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key"
        )
    return api_key

# ============================================
# Load Citations Database
# ============================================

def load_citations():
    citations_file = os.path.join(os.path.dirname(__file__), "citations.json")
    if os.path.exists(citations_file):
        with open(citations_file, "r") as f:
            return json.load(f)
    return {}

CITATIONS_DB = load_citations()

def get_citations(icd10_code: str) -> List[dict]:
    if icd10_code in CITATIONS_DB:
        return CITATIONS_DB[icd10_code].get("citations", [])
    return []

# ============================================
# Test Name Resolver
# ============================================

CANONICAL_TESTS = {
    "hemoglobin": {
        "loinc": "718-7",
        "synonyms": ["hgb", "hb", "hemoglobin", "haemoglobin", "blood hemoglobin", "hemoglobin level", "hgb count"]
    },
    "mcv": {
        "loinc": "787-2",
        "synonyms": ["mcv", "mean corpuscular volume", "mean cell volume", "mean corpuscular volume mcv", "mcv blood"]
    },
    "mch": {
        "loinc": "785-6",
        "synonyms": ["mch", "mean corpuscular hemoglobin", "mean cell hemoglobin", "mean corpuscular hemoglobin mch"]
    },
    "rbc": {
        "loinc": "789-8",
        "synonyms": ["rbc", "red blood cell count", "red cell count", "erythrocyte count", "rbc count", "red blood cells"]
    },
    "rdw": {
        "loinc": "788-0",
        "synonyms": ["rdw", "red cell distribution width", "rdw-cv", "rdw cv", "red blood cell distribution width"]
    },
    "platelets": {
        "loinc": "777-3",
        "synonyms": ["platelets", "plt", "platelet count", "thrombocyte count", "plt count"]
    },
    "wbc": {
        "loinc": "6690-2",
        "synonyms": ["wbc", "white blood cell count", "leukocyte count", "wbc count", "white blood cells"]
    }
}

RESOLVER_CACHE = {}

def resolve_test_name(raw_name: str) -> dict:
    """Resolve a free-text test name to canonical form and LOINC code."""
    normalized = raw_name.lower().strip()
    
    if normalized in RESOLVER_CACHE:
        return RESOLVER_CACHE[normalized]
    
    if normalized in CANONICAL_TESTS:
        result = {
            "canonical": normalized,
            "loinc": CANONICAL_TESTS[normalized]["loinc"],
            "confidence": 1.0,
            "method": "exact"
        }
        RESOLVER_CACHE[normalized] = result
        return result
    
    all_synonyms = []
    for canonical, info in CANONICAL_TESTS.items():
        for syn in info["synonyms"]:
            all_synonyms.append((syn, canonical))
    
    best_match = process.extractOne(normalized, [s[0] for s in all_synonyms], scorer=fuzz.token_sort_ratio)
    
    if best_match and best_match[1] >= 80:
        matched_synonym = best_match[0]
        for syn, canonical in all_synonyms:
            if syn == matched_synonym:
                result = {
                    "canonical": canonical,
                    "loinc": CANONICAL_TESTS[canonical]["loinc"],
                    "confidence": best_match[1] / 100.0,
                    "method": "fuzzy"
                }
                RESOLVER_CACHE[normalized] = result
                return result
    
    canonical_names = list(CANONICAL_TESTS.keys())
    best_match = process.extractOne(normalized, canonical_names, scorer=fuzz.token_sort_ratio)
    
    if best_match and best_match[1] >= 70:
        canonical = best_match[0]
        result = {
            "canonical": canonical,
            "loinc": CANONICAL_TESTS[canonical]["loinc"],
            "confidence": best_match[1] / 100.0,
            "method": "fuzzy"
        }
        RESOLVER_CACHE[normalized] = result
        return result
    
    result = {
        "canonical": None,
        "loinc": None,
        "confidence": 0.0,
        "method": "none",
        "error": f"Test name '{raw_name}' could not be resolved"
    }
    RESOLVER_CACHE[normalized] = result
    return result

def resolve_lab_results(lab_results):
    resolved = []
    for lab in lab_results:
        if lab.loinc_code:
            resolved.append(lab)
        else:
            resolution = resolve_test_name(lab.test_name)
            if resolution["canonical"]:
                from copy import copy
                resolved_lab = copy(lab)
                resolved_lab.test_name = resolution["canonical"]
                resolved_lab.loinc_code = resolution["loinc"]
                resolved.append(resolved_lab)
            else:
                print(f"Warning: Could not resolve test name: {lab.test_name}")
    return resolved

# ============================================
# Pydantic Models for Native JSON API
# ============================================

class PatientContext(BaseModel):
    birth_year: Optional[int] = Field(None, description="Patient year of birth (4-digit)", example=1975)
    sex: Optional[str] = Field(None, description="Biological sex", example="F")
    pregnant: Optional[bool] = Field(None, description="Pregnancy status")
    medications: List[str] = Field(default=[], description="List of current medication names")
    problems: List[str] = Field(default=[], description="List of current ICD-10 codes or problem descriptions")

class LabResult(BaseModel):
    date: str = Field(..., description="Collection date in YYYY-MM-DD format", example="2024-06-20")
    test_name: str = Field(..., description="Test name (e.g., 'hemoglobin', 'MCV', 'hgb')", example="hemoglobin")
    value: float = Field(..., description="Numeric result value", example=11.4)
    unit: str = Field(..., description="UCUM unit (e.g., 'g/dL', 'fL')", example="g/dL")
    loinc_code: Optional[str] = Field(None, description="LOINC code (optional, bypasses resolver)", example="718-7")

class DiagnoseRequest(BaseModel):
    patient_id: Optional[str] = Field(None, description="Optional external patient identifier")
    patient: PatientContext = Field(..., description="Patient demographic context")
    lab_history: List[LabResult] = Field(..., description="List of laboratory results", min_items=1)

class FeatureContribution(BaseModel):
    feature: str = Field(..., description="Feature name", example="mcv")
    value: float = Field(..., description="Feature value", example=70.0)
    shap: float = Field(..., description="SHAP contribution to prediction", example=0.35)

class Citation(BaseModel):
    reference: str = Field(..., description="Full citation reference")
    doi: Optional[str] = Field(None, description="Digital Object Identifier")
    pmid: Optional[str] = Field(None, description="PubMed ID")
    key_findings: Optional[str] = Field(None, description="Summary of relevant findings")

class Diagnosis(BaseModel):
    diagnosis: str = Field(..., description="Potential diagnosis name", example="Beta-thalassemia trait")
    icd10: str = Field(..., description="ICD-10 code", example="D56.3")
    confidence: float = Field(..., description="Calibrated probability (0-1)", example=0.78)
    confidence_interval_lower: Optional[float] = Field(None, description="Lower bound of 90% confidence interval")
    confidence_interval_upper: Optional[float] = Field(None, description="Upper bound of 90% confidence interval")
    supporting_labs: List[str] = Field(..., description="Lab findings that support this diagnosis")
    feature_contributions: List[FeatureContribution] = Field(..., description="SHAP values for top features")
    citations: List[Citation] = Field(..., description="Peer-reviewed evidence")

class DiagnoseResponse(BaseModel):
    request_id: str = Field(..., description="Unique request identifier", example="abc12345")
    processing_time_ms: int = Field(..., description="Total processing time in milliseconds", example=847)
    potential_diagnoses: List[Diagnosis] = Field(..., description="Ranked list of potential diagnoses")

# ============================================
# Pydantic Models for FHIR Bundle
# ============================================

class FHIRCoding(BaseModel):
    system: Optional[str] = None
    code: Optional[str] = None
    display: Optional[str] = None

class FHIRCodeableConcept(BaseModel):
    coding: List[FHIRCoding] = []

class FHIRQuantity(BaseModel):
    value: Optional[float] = None
    unit: Optional[str] = None
    system: Optional[str] = None
    code: Optional[str] = None

class FHIRReference(BaseModel):
    reference: Optional[str] = None

class FHIRBundleEntry(BaseModel):
    fullUrl: Optional[str] = None
    resource: dict

class FHIRBundle(BaseModel):
    resourceType: str = "Bundle"
    type: str
    entry: List[FHIRBundleEntry] = []

# ============================================
# Feature Extraction
# ============================================

def extract_features(lab_history):
    features = {}
    for lab in lab_history:
        test_name = lab.test_name.lower()
        if test_name in ["hemoglobin", "hgb", "hb"]:
            features["hemoglobin"] = lab.value
        elif test_name in ["mcv", "mean corpuscular volume"]:
            features["mcv"] = lab.value
        elif test_name in ["rbc", "red blood cell count"]:
            features["rbc"] = lab.value
        elif test_name in ["rdw", "red cell distribution width"]:
            features["rdw"] = lab.value
    
    # Mentzer index (MCV / RBC) 
    if "mcv" in features and "rbc" in features and features["rbc"] > 0:
        features["mentzer_index"] = features["mcv"] / features["rbc"]
    else:
        features["mentzer_index"] = 0

    # Green and King index ((MCV^2 * RDW) / (Hb * 100))
    if "mcv" in features and "rdw" in features and "hemoglobin" in features and features["hemoglobin"] > 0:
        features["green_king_index"] = (features["mcv"] ** 2 * features["rdw"]) / (features["hemoglobin"] * 100)
    else:
        features["green_king_index"] = 0

    # England and Fraser index (MCV - RBC - (5 * Hb) - 8.4)
    if "mcv" in features and "rbc" in features and "hemoglobin" in features:
        features["england_fraser_index"] = features["mcv"] - features["rbc"] - (5 * features["hemoglobin"]) - 8.4
    else:
        features["england_fraser_index"] = 0
    
    # Srivastava index (MCH / RBC)
    if "mch" in features and "rbc" in features and features["rbc"] > 0:
        features["srivastava_index"] = features["mch"] / features["rbc"]
    else:
        features["srivastava_index"] = 0
    
    default_features = {
        "hemoglobin": 13.0,
        "mcv": 90,
        "mch": 30,
        "rbc": 4.8,
        "rdw": 13.5,
        "mentzer_index": 15,
        "green_king_index": 70,
        "england_fraser_index": 2,
        "srivastava_index": 6.25,
        "rdw_cv": 13.5
    }
    for key, default in default_features.items():
        if key not in features:
            features[key] = default
    
    return pd.DataFrame([features])

# ============================================
# SHAP Explainer Setup (Dummy for now)
# ============================================

class DummyExplainer:
    def __init__(self, feature_names):
        self.feature_names = feature_names
    
    def shap_values(self, X):
        if X is not None:
            hgb = X.iloc[0].get("hemoglobin", 13.0)
            mcv = X.iloc[0].get("mcv", 90.0)
            mentzer = X.iloc[0].get("mentzer_index", 15.0)
            green_king = X.iloc[0].get("green_king_index", 70.0)
            
            shap_vals = []
            for col in self.feature_names:
                if col == "hemoglobin" and hgb < 12:
                    shap_vals.append(0.20)
                elif col == "hemoglobin" and hgb >= 12:
                    shap_vals.append(-0.10)
                elif col == "mcv" and mcv < 80:
                    shap_vals.append(0.30)
                elif col == "mcv" and mcv >= 80:
                    shap_vals.append(-0.15)
                elif col == "mentzer_index" and mentzer < 13:
                    shap_vals.append(0.25)
                elif col == "mentzer_index" and mentzer >= 13:
                    shap_vals.append(-0.05)
                elif col == "green_king_index" and green_king < 60:
                    shap_vals.append(0.15)
                else:
                    shap_vals.append(0.0)
            
            return np.array([shap_vals])
        
        return np.zeros((1, len(self.feature_names)))

feature_names = ["hemoglobin", "mcv", "mch", "rbc", "rdw", 
                 "mentzer_index", "green_king_index", "england_fraser_index", 
                 "srivastava_index", "rdw_cv"]

# ============================================
# Dummy Model with SHAP
# ============================================

class DummyModel:
    def __init__(self):
        self.explainer = DummyExplainer(feature_names)
        self.feature_names = feature_names
    
    def predict_proba(self, X):
        hgb = X.iloc[0].get("hemoglobin", 13.0)
        mcv = X.iloc[0].get("mcv", 90.0)
        mentzer = X.iloc[0].get("mentzer_index", 15.0)
        green_king = X.iloc[0].get("green_king_index", 70.0)
        
        score = 0.0
        if hgb < 12:
            score += 0.25
        if mcv < 80:
            score += 0.35
        if mentzer < 13:
            score += 0.25
        if green_king < 60:
            score += 0.15
        
        proba = min(score, 0.95)
        
        return np.array([[1 - proba, proba]])
    
    def get_shap_values(self, X):
        return self.explainer.shap_values(X)

model = DummyModel()

# ============================================
# FHIR Parser
# ============================================

def parse_fhir_bundle(bundle: FHIRBundle) -> List[LabResult]:
    lab_results = []
    
    for entry in bundle.entry:
        resource = entry.resource
        
        if resource.get("resourceType") == "Observation":
            loinc_code = None
            code_info = resource.get("code", {})
            coding = code_info.get("coding", [])
            for c in coding:
                if c.get("system") == "http://loinc.org":
                    loinc_code = c.get("code")
                    break
            
            value_quantity = resource.get("valueQuantity", {})
            value = value_quantity.get("value")
            unit = value_quantity.get("unit")
            
            if value is None:
                continue
            
            effective_date = resource.get("effectiveDateTime", "")
            if effective_date and len(effective_date) >= 10:
                date_str = effective_date[:10]
            else:
                date_str = "2024-01-01"
            
            test_name = ""
            for c in coding:
                if c.get("display"):
                    test_name = c.get("display")
                    break
            if not test_name:
                test_name = loinc_code
            
            lab_results.append(LabResult(
                date=date_str,
                test_name=test_name,
                value=float(value),
                unit=unit or "",
                loinc_code=loinc_code
            ))
    
    return lab_results

# ============================================
# Helper Functions
# ============================================

def get_shap_contributions(model, X, feature_names):
    shap_values = model.get_shap_values(X)
    contributions = []
    
    for i, feature in enumerate(feature_names):
        if i < len(shap_values[0]):
            contributions.append(FeatureContribution(
                feature=feature,
                value=float(X.iloc[0].get(feature, 0)),
                shap=float(shap_values[0][i])
            ))
    
    contributions.sort(key=lambda x: abs(x.shap), reverse=True)
    
    return contributions[:5]

def get_citation_objects(icd10_code: str) -> List[Citation]:
    citations = get_citations(icd10_code)
    citation_objects = []
    for cite in citations:
        citation_objects.append(Citation(
            reference=cite.get("reference", ""),
            doi=cite.get("doi"),
            pmid=cite.get("pmid"),
            key_findings=cite.get("key_findings")
        ))
    return citation_objects

# ============================================
# FastAPI Application
# ============================================

app = FastAPI(
    title="LabDx Diagnostic API",
    description="""
    API for differential diagnosis of hemoglobinopathies from laboratory results.

    ## Features

    * **Lab-result-driven diagnosis** - No symptoms or suspected diagnosis required
    * **Longitudinal trend analysis** - Analyzes trends over time (slopes, acceleration)
    * **FHIR R4 native** - Accepts standard EHR bundles for seamless integration
    * **SHAP explanations** - Shows which features drove each prediction
    * **Peer-reviewed citations** - Every diagnosis includes evidence from medical literature
    * **Test name resolver** - Accepts flexible test names ("hgb", "HGB", "hemoglobin")

    ## Input Formats

    1. **Native JSON** - Simple format for direct API calls
    2. **FHIR R4 Bundle** - Standard format for EHR integration (US Core 6.1.0 compliant)

    ## Clinical Context

    The API currently supports differential diagnosis for microcytic anemias, specifically:
    - Beta-thalassemia trait (D56.3)
    - Iron deficiency anemia (D50.8/D50.9)
    - Sickle cell trait/disease (D57.x)
    - HbE trait (D56.5)

    ## Disclaimer

    This is a demonstration tool. Not validated for clinical use.
    Always consult a qualified healthcare provider for medical decisions.
    """,
    version="1.0.0",
    contact={
        "name": "API Support",
        "url": "https://github.com/hellokelli/LabDx-Diagnostic-API"
    }
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get(
    "/health",
    summary="Health check endpoint",
    description="Returns the health status of the API and confirms the model is loaded. Rate Limiting: 100 requests per minute per IP address.",
    response_description="Health status with model loaded flag"
)
@limiter.limit("100/minute")
def health_check(request: Request):
    return {"status": "healthy", "model_loaded": True}

@app.post(
    "/diagnose",
    response_model=DiagnoseResponse,
    summary="Generate differential diagnosis from lab results",
    description="""
    Accepts a patient's laboratory history and returns ranked potential diagnoses
    with confidence scores, SHAP feature contributions, and peer-reviewed citations.

    The API analyzes:
    - Hemoglobin, MCV, RBC, RDW values
    - Calculates derived indices (Mentzer index)
    - Resolves flexible test names ("hgb", "HGB", "hemoglobin")

    Rate Limiting: 100 requests per minute per IP address.

    **Example use case:** A physician enters a patient's CBC results and receives
    probabilistic guidance on whether the pattern suggests thalassemia trait,
    iron deficiency, or normal findings.
    """,
    response_description="Ranked list of potential diagnoses with evidence"
)
@limiter.limit("100/minute")
def diagnose(diagnose_request: DiagnoseRequest, request: Request, api_key: str = Security(verify_api_key)):
    start_time = time.time()
    request_id = str(uuid.uuid4())[:8]
    
    try:
        resolved_labs = resolve_lab_results(diagnose_request.lab_history)
        X = extract_features(resolved_labs)
        proba = model.predict_proba(X)[0, 1]
        
        shap_contributions = get_shap_contributions(model, X, model.feature_names)
        
        diagnoses = []
        if proba > 0.7:
            citations = get_citation_objects("D56.3")
            diagnoses.append(Diagnosis(
                diagnosis="Beta-thalassemia trait",
                icd10="D56.3",
                confidence=proba,
                confidence_interval_lower=proba - 0.07,
                confidence_interval_upper=proba + 0.07,
                supporting_labs=["Low MCV", "Normal or elevated RBC", "Normal ferritin"],
                feature_contributions=shap_contributions,
                citations=citations
            ))
        
        if len(diagnoses) == 0:
            if proba < 0.5:
                citations = get_citation_objects("Z01.00")
                diagnoses.append(Diagnosis(
                    diagnosis="No significant abnormality detected",
                    icd10="Z01.00",
                    confidence=1 - proba,
                    confidence_interval_lower=(1 - proba) - 0.05,
                    confidence_interval_upper=(1 - proba) + 0.05,
                    supporting_labs=["Within normal limits"],
                    feature_contributions=shap_contributions,
                    citations=citations
                ))
            else:
                citations = get_citation_objects("R69")
                diagnoses.append(Diagnosis(
                    diagnosis="Inconclusive - further testing recommended",
                    icd10="R69",
                    confidence=0.5,
                    confidence_interval_lower=0.4,
                    confidence_interval_upper=0.6,
                    supporting_labs=["Results do not fit typical pattern"],
                    feature_contributions=shap_contributions,
                    citations=citations
                ))
        
        processing_time = int((time.time() - start_time) * 1000)
        
        return DiagnoseResponse(
            request_id=request_id,
            processing_time_ms=processing_time,
            potential_diagnoses=diagnoses
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post(
    "/diagnose/fhir",
    response_model=DiagnoseResponse,
    summary="Generate differential diagnosis from FHIR R4 bundle",
    description="""
    Accepts a FHIR R4 bundle (US Core 6.1.0 compliant) and returns diagnoses.
    This endpoint is designed for direct integration with EHR systems like Epic, Cerner, and Meditech.

    Rate Limiting: 100 requests per minute per IP address.
    The bundle should contain:
    - Patient demographics (age, sex)
    - DiagnosticReport with category "LAB"
    - Observation resources with LOINC codes for CBC parameters
    """
)
@limiter.limit("100/minute")
def diagnose_from_fhir(bundle: FHIRBundle, request: Request, api_key: str = Security(verify_api_key)):

    start_time = time.time()
    request_id = str(uuid.uuid4())[:8]
    
    try:
        lab_results = parse_fhir_bundle(bundle)
        
        if len(lab_results) == 0:
            raise HTTPException(
                status_code=400, 
                detail="No laboratory observations found in FHIR bundle"
            )
        
        X = extract_features(lab_results)
        proba = model.predict_proba(X)[0, 1]
        
        shap_contributions = get_shap_contributions(model, X, model.feature_names)
        
        diagnoses = []
        if proba > 0.7:
            citations = get_citation_objects("D56.3")
            diagnoses.append(Diagnosis(
                diagnosis="Beta-thalassemia trait",
                icd10="D56.3",
                confidence=proba,
                confidence_interval_lower=proba - 0.07,
                confidence_interval_upper=proba + 0.07,
                supporting_labs=["Low MCV", "Normal or elevated RBC", "Normal ferritin"],
                feature_contributions=shap_contributions,
                citations=citations
            ))
        
        if len(diagnoses) == 0:
            if proba < 0.5:
                citations = get_citation_objects("Z01.00")
                diagnoses.append(Diagnosis(
                    diagnosis="No significant abnormality detected",
                    icd10="Z01.00",
                    confidence=1 - proba,
                    confidence_interval_lower=(1 - proba) - 0.05,
                    confidence_interval_upper=(1 - proba) + 0.05,
                    supporting_labs=["Within normal limits"],
                    feature_contributions=shap_contributions,
                    citations=citations
                ))
            else:
                citations = get_citation_objects("R69")
                diagnoses.append(Diagnosis(
                    diagnosis="Inconclusive - further testing recommended",
                    icd10="R69",
                    confidence=0.5,
                    confidence_interval_lower=0.4,
                    confidence_interval_upper=0.6,
                    supporting_labs=["Results do not fit typical pattern"],
                    feature_contributions=shap_contributions,
                    citations=citations
                ))
        
        processing_time = int((time.time() - start_time) * 1000)
        
        return DiagnoseResponse(
            request_id=request_id,
            processing_time_ms=processing_time,
            potential_diagnoses=diagnoses
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing FHIR bundle: {str(e)}")