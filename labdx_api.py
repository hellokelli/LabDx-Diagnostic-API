
import pandas as pd
import numpy as np
import xgboost as xgb
import shap
import json
import os
import re
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uuid
import time
from fuzzywuzzy import fuzz, process

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
        "synonyms": ["hgb", "hb", "hemoglobin", "haemoglobin", "blood hemoglobin"]
    },
    "mcv": {
        "loinc": "787-2",
        "synonyms": ["mcv", "mean corpuscular volume", "mean cell volume"]
    },
    "mch": {
        "loinc": "785-6",
        "synonyms": ["mch", "mean corpuscular hemoglobin", "mean cell hemoglobin"]
    },
    "rbc": {
        "loinc": "789-8",
        "synonyms": ["rbc", "red blood cell count", "red cell count", "erythrocyte count"]
    },
    "rdw": {
        "loinc": "788-0",
        "synonyms": ["rdw", "red cell distribution width", "rdw-cv"]
    },
    "platelets": {
        "loinc": "777-3",
        "synonyms": ["platelets", "plt", "platelet count", "thrombocyte count"]
    },
    "wbc": {
        "loinc": "6690-2",
        "synonyms": ["wbc", "white blood cell count", "leukocyte count"]
    }
}

RESOLVER_CACHE = {}

def resolve_test_name(raw_name: str) -> dict:
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
    birth_year: Optional[int] = None
    sex: Optional[str] = None
    pregnant: Optional[bool] = None
    medications: List[str] = []
    problems: List[str] = []

class LabResult(BaseModel):
    date: str
    test_name: str
    value: float
    unit: str
    loinc_code: Optional[str] = None

class DiagnoseRequest(BaseModel):
    patient_id: Optional[str] = None
    patient: PatientContext
    lab_history: List[LabResult]

class FeatureContribution(BaseModel):
    feature: str
    value: float
    shap: float

class Citation(BaseModel):
    reference: str
    doi: Optional[str] = None
    pmid: Optional[str] = None
    key_findings: Optional[str] = None

class Diagnosis(BaseModel):
    diagnosis: str
    icd10: str
    confidence: float
    confidence_interval_lower: Optional[float] = None
    confidence_interval_upper: Optional[float] = None
    supporting_labs: List[str]
    feature_contributions: List[FeatureContribution]
    citations: List[Citation]

class DiagnoseResponse(BaseModel):
    request_id: str
    processing_time_ms: int
    potential_diagnoses: List[Diagnosis]

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

    if "mcv" in features and "rbc" in features and features["rbc"] > 0:
        features["mentzer_index"] = features["mcv"] / features["rbc"]
    else:
        features["mentzer_index"] = 0

    default_features = {"hemoglobin": 13.0, "mcv": 90, "rdw": 13.5, "mentzer_index": 15}
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

            shap_vals = []
            for col in self.feature_names:
                if col == "hemoglobin" and hgb < 12:
                    shap_vals.append(0.25)
                elif col == "hemoglobin" and hgb >= 12:
                    shap_vals.append(-0.10)
                elif col == "mcv" and mcv < 80:
                    shap_vals.append(0.35)
                elif col == "mcv" and mcv >= 80:
                    shap_vals.append(-0.15)
                elif col == "mentzer_index" and mentzer < 13:
                    shap_vals.append(0.30)
                elif col == "mentzer_index" and mentzer >= 13:
                    shap_vals.append(-0.05)
                else:
                    shap_vals.append(0.0)

            return np.array([shap_vals])

        return np.zeros((1, len(self.feature_names)))

feature_names = ["hemoglobin", "mcv", "rdw", "mentzer_index"]

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

        score = 0.0
        if hgb < 12:
            score += 0.3
        if mcv < 80:
            score += 0.4
        if mentzer < 13:
            score += 0.3

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

app = FastAPI(title="LabDx Diagnostic API")

@app.get("/health")
def health_check():
    return {"status": "healthy", "model_loaded": True}

@app.post("/diagnose", response_model=DiagnoseResponse)
def diagnose(request: DiagnoseRequest):
    start_time = time.time()
    request_id = str(uuid.uuid4())[:8]

    try:
        resolved_labs = resolve_lab_results(request.lab_history)
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

@app.post("/diagnose/fhir", response_model=DiagnoseResponse)
def diagnose_from_fhir(bundle: FHIRBundle):
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
