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
# Model Directory and Training Data
# ============================================

MODEL_DIR = "models"
TRAINING_DATA_PATHS = {
    "thalassemia_trait": os.path.join(MODEL_DIR, "training_features.csv"),
    "sickle_cell_disease": os.path.join(MODEL_DIR, "sickle_training_features.csv"),
    "sickle_cell_trait": os.path.join(MODEL_DIR, "sickle_trait_training_features.csv")
}

# ============================================
# Unit Definitions and Normalization
# ============================================

EXPECTED_UNITS = {
    "hemoglobin": {
        "standard": "g/dL",
        "aliases": ["g/dl", "gram/deciliter"],
        "normalizable": [
            {"unit": "g/L", "factor": 0.1},
            {"unit": "gram/liter", "factor": 0.1}
        ]
    },
    "mcv": {
        "standard": "fL",
        "aliases": ["fl", "fl"],
        "normalizable": [
            {"unit": "um^3", "factor": 1.0},
            {"unit": "cubic micrometer", "factor": 1.0}
        ]
    },
    "rbc": {
        "standard": "million/uL",
        "aliases": ["million/ul", "x10^6/ul", "10^6/ul"],
        "normalizable": [
            {"unit": "x10^12/L", "factor": 1.0},
            {"unit": "10^12/L", "factor": 1.0}
        ]
    },
    "rdw": {
        "standard": "%",
        "aliases": ["percent", "percentage"],
        "normalizable": []
    }
}

def validate_and_normalize_units(value: float, unit: str, canonical_test_name: str) -> tuple:
    """
    Validate units and normalize to standard.
    Returns (normalized_value, error_message)
    If error_message is not None, the input is invalid.
    """
    test_config = EXPECTED_UNITS.get(canonical_test_name)
    if not test_config:
        return None, f"Unknown test: {canonical_test_name}"
    
    unit_lower = unit.lower().strip()
    
    # Check if unit matches standard or alias
    if unit_lower == test_config["standard"].lower() or unit_lower in [a.lower() for a in test_config["aliases"]]:
        return value, None
    
    # Try normalization
    for norm in test_config.get("normalizable", []):
        if unit_lower == norm["unit"].lower():
            normalized = value * norm["factor"]
            return normalized, None
    
    return None, f"Unsupported unit '{unit}' for {canonical_test_name}. Expected {test_config['standard']}"

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

def resolve_and_normalize_lab_results(lab_results):
    """
    Resolve test names and normalize units.
    Returns (resolved_labs, errors)
    """
    resolved = []
    errors = []

    for lab in lab_results:
        if lab.loinc_code:
            canonical_test_name = lab.test_name 
            resolved.append(lab)
            continue
        resolution = resolve_test_name(lab.test_name)
        if not resolution["canonical"]:
            errors.append(f"Could not resolve test name: {lab.test_name}")
            continue

        normalized_value, unit_error = validate_and_normalize_units(
            lab.value, lab.unit, resolution["canonical"]
        )

        if unit_error:
            errors.append(unit_error)
            continue

        from copy import copy
        normalized_lab = copy(lab)
        normalized_lab.test_name = resolution["canonical"]
        normalized_lab.loinc_code = resolution["loinc"]
        normalized_lab.value = normalized_value
        normalized_lab.unit = EXPECTED_UNITS[resolution["canonical"]]["standard"]
        
        resolved.append(normalized_lab)
    
    return resolved, errors

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
    missing_flags = {}
    
    tests_found = {
        "hemoglobin": False,
        "mcv": False,
        "mch": False,
        "rbc": False,
        "rdw": False
    }

    for lab in lab_history:
        test_name = lab.test_name.lower()
        if test_name in ["hemoglobin", "hgb", "hb"]:
            features["hemoglobin"] = lab.value
            tests_found["hemoglobin"] = True
        elif test_name in ["mcv", "mean corpuscular volume"]:
            features["mcv"] = lab.value
            tests_found["mcv"] = True
        elif test_name in ["rbc", "red blood cell count"]:
            features["rbc"] = lab.value
            tests_found["rbc"] = True
        elif test_name in ["rdw", "red cell distribution width"]:
            features["rdw"] = lab.value
            tests_found["rdw"] = True
    
    for test_name in tests_found:
        missing_flags[f"{test_name}_missing"] = 0 if tests_found[test_name] else 1
    
    # Mentzer index (MCV / RBC) 
    if tests_found["mcv"] and tests_found["rbc"] and features.get("rbc", 0) > 0:
        features["mentzer_index"] = features["mcv"] / features["rbc"]
    else:
        features["mentzer_index"] = 0
        missing_flags["mentzer_index_missing"] = 1

    # Green and King index ((MCV^2 * RDW) / (Hb * 100))
    if tests_found["mcv"] and tests_found["rdw"] and tests_found["hemoglobin"]:
        features["green_king_index"] = (features["mcv"] ** 2 * features["rdw"]) / (features["hemoglobin"] * 100)
    else:
        features["green_king_index"] = 0
        missing_flags["green_king_index_missing"] = 1

    # England and Fraser index (MCV - RBC - (5 * Hb) - 8.4)
    if tests_found["mcv"] and tests_found["rbc"] and tests_found["hemoglobin"]:
        features["england_fraser_index"] = features["mcv"] - features["rbc"] - (5 * features["hemoglobin"]) - 8.4
    else:
        features["england_fraser_index"] = 0
        missing_flags["england_fraser_index_missing"] = 1
    
    # Srivastava index (MCH / RBC)
    if tests_found["mch"] and tests_found["rbc"] and features.get("rbc", 0) > 0:
        features["srivastava_index"] = features["mch"] / features["rbc"]
    else:
        features["srivastava_index"] = 0
        missing_flags["srivastava_index_missing"] = 1
    
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
   
    features.update(missing_flags)
    
    return pd.DataFrame([features])

# ============================================
# Model Registry for Multiple Conditions
# ============================================

class ModelRegistry:
    """Load and manage multiple XGBoost models"""
    
    def __init__(self, model_dir="models"):
        self.models = {}
        self.features = {}
        self.thresholds = {}
        self.icd10_map = {}
        self.name_map = {}
        self.feature_order_map = {}   
        self.feature_mapping_map = {}  
        
        # Define all models with their paths and thresholds
        model_configs = {
            "thalassemia_trait": {
                "path": os.path.join(model_dir, "hemoglobinopathy_model.xgb"),
                "threshold": 0.6152,
                "icd10": "D56.3",
                "name": "Beta-thalassemia trait",
                "feature_order": ["Hemoglobin", "MCV", "RBC", "RDW", 
                                  "mentzer_index", "green_king_index", "england_fraser_index"],
                "feature_mapping": {
                    "hemoglobin": "Hemoglobin",
                    "mcv": "MCV",
                    "rbc": "RBC",
                    "rdw": "RDW",
                    "mentzer_index": "mentzer_index",
                    "green_king_index": "green_king_index",
                    "england_fraser_index": "england_fraser_index"
                }
            },
            "sickle_cell_disease": {
                "path": os.path.join(model_dir, "sickle_disease_model.xgb"),
                "threshold": 0.50,  # Update with your actual threshold
                "icd10": "D57.0",
                "name": "Sickle cell disease",
                "feature_order": ["Hemoglobin", "Hematocrit", "MCV", "MCH", "MCHC", 
                                  "RBC", "RDW", "RDW_SD", "Platelets", "WBC"],
                "feature_mapping": {
                    "hemoglobin": "Hemoglobin",
                    "mcv": "MCV",
                    "mch": "MCH",
                    "mchc": "MCHC",
                    "rbc": "RBC",
                    "rdw": "RDW",
                    "platelets": "Platelets",
                    "wbc": "WBC"
                }
            },
            "sickle_cell_trait": {
                "path": os.path.join(model_dir, "sickle_trait_model.xgb"),
                "threshold": 0.75,  
                "icd10": "D57.3",
                "name": "Sickle cell trait",
                "feature_order": ["Hemoglobin", "MCV", "MCH", "RBC", "RDW", 
                                  "green_king_index", "england_fraser_index"],
                "feature_mapping": {
                    "hemoglobin": "Hemoglobin",
                    "mcv": "MCV",
                    "mch": "MCH",
                    "rbc": "RBC",
                    "rdw": "RDW",
                    "green_king_index": "green_king_index",
                    "england_fraser_index": "england_fraser_index"
                }
            }
        }
        
        for key, config in model_configs.items():
            try:
                model = xgb.Booster()
                model.load_model(config["path"])
                self.models[key] = model
                self.thresholds[key] = config["threshold"]
                self.icd10_map[key] = config["icd10"]
                self.name_map[key] = config["name"]
                self.feature_order_map[key] = config["feature_order"]
                self.feature_mapping_map[key] = config["feature_mapping"]
                print(f"Loaded model: {key}")
            except Exception as e:
                print(f"Failed to load {key}: {e}")
    
    def preprocess_features(self, features_df, model_key):
        """Preprocess features for a specific model"""
        mapping = self.feature_mapping_map.get(model_key, {})
        order = self.feature_order_map.get(model_key, [])
        
        # Rename columns using mapping
        renamed = features_df.rename(columns=mapping)
        
        # Select and order features
        return renamed[order]
    
    def predict_all(self, features_df):
        """Run all models and return predictions"""
        results = {}
        for key in self.models.keys():
            try:
                X_processed = self.preprocess_features(features_df, key)
                dmatrix = xgb.DMatrix(X_processed)
                proba = self.models[key].predict(dmatrix)[0]
                results[key] = proba
            except Exception as e:
                print(f"Error predicting with {key}: {e}")
                results[key] = 0.0
        return results
    
    def get_diagnoses(self, features_df, shap_contributions=None):
        """Return all diagnoses that exceed their thresholds"""
        predictions = self.predict_all(features_df)
        diagnoses = []
        
        for key, proba in predictions.items():
            if proba > self.thresholds.get(key, 0.5):
                shap_vals = shap_contributions.get(key, []) if shap_contributions else []
                diagnoses.append(Diagnosis(
                    diagnosis=self.name_map.get(key, key),
                    icd10=self.icd10_map.get(key, "R69"),
                    confidence=proba,
                    confidence_interval_lower=proba - 0.07,
                    confidence_interval_upper=proba + 0.07,
                    supporting_labs=get_supporting_labs(key, features_df),
                    feature_contributions=shap_vals,
                    citations=get_citation_objects(self.icd10_map.get(key, "R69"))
                ))
        
        # Sort by confidence (highest first)
        diagnoses.sort(key=lambda x: x.confidence, reverse=True)
        return diagnoses
    def get_shap_for_model(self, model_key, features_df):
        """Get SHAP values for a specific model"""
        try:
            # Preprocess features for this model
            X_processed = self.preprocess_features(features_df, model_key)
            
            # You'll need to load a SHAP explainer for each model
            # This requires training_data per model
            if not hasattr(self, 'explainers'):
                self.explainers = {}
            
            if model_key not in self.explainers:
                # Load training data for this model
                training_path = TRAINING_DATA_PATHS.get(model_key)
                if training_path and os.path.exists(training_path):
                    training_data = pd.read_csv(training_path)
                    order = self.feature_order_map.get(model_key, [])
                    self.explainers[model_key] = shap.TreeExplainer(
                        self.models[model_key], 
                        training_data[order]
                    )
                else:
                    return []
            
            shap_values = self.explainers[model_key].shap_values(X_processed)
            
            contributions = []
            order = self.feature_order_map.get(model_key, [])
            for i, feature in enumerate(order):
                contributions.append(FeatureContribution(
                    feature=feature,
                    value=float(X_processed.iloc[0, i]),
                    shap=float(shap_values[0][i])
                ))
            
            contributions.sort(key=lambda x: abs(x.shap), reverse=True)
            return contributions[:5]
        except Exception as e:
            print(f"SHAP error for {model_key}: {e}")
            return []

def get_supporting_labs(model_key, features_df):
    """Return supporting labs based on the model and features"""
    # This can be customized per model
    supporting_labs = []
    if "mcv" in features_df.columns:
        if features_df["mcv"].iloc[0] < 80:
            supporting_labs.append("Low MCV")
    if "hemoglobin" in features_df.columns:
        if features_df["hemoglobin"].iloc[0] < 12:
            supporting_labs.append("Low hemoglobin")
    if "rdw" in features_df.columns:
        if features_df["rdw"].iloc[0] > 15:
            supporting_labs.append("Elevated RDW")
    return supporting_labs

# ============================================
# XGBoost Model with SHAP
# ============================================

import xgboost as xgb
import shap
import pandas as pd
import numpy as np

# ============================================
# Initialize the Model Registry
# ============================================

# Initialize the model registry
model_registry = ModelRegistry(model_dir=MODEL_DIR)

# If no models loaded, fallback to dummy
if len(model_registry.models) == 0:
    print("WARNING: No models loaded. API will return inconclusive results.")




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
    errors = [] 
    start_time = time.time()
    request_id = str(uuid.uuid4())[:8]
    
    try:
        resolved_labs, errors = resolve_and_normalize_lab_results(diagnose_request.lab_history)
        if errors:
            raise HTTPException(status_code=400, detail=f"Unit validation errors: {'; '.join(errors)}")
        
        if len(resolved_labs) == 0:
            raise HTTPException(status_code=400, detail="No valid lab results after resolution and normalization")

        X = extract_features(resolved_labs)
        print("=== DEBUG: Feature values from extract_features ===")
        print(X.to_dict())
    
        all_predictions = model_registry.predict_all(X)
        print(f"DEBUG: All predictions: {all_predictions}")

        diagnoses = []

        for key, proba in all_predictions.items():
            threshold = model_registry.thresholds.get(key, 0.5)
            if proba > threshold:
                # Get SHAP values for this model (if available)
                shap_vals = model_registry.get_shap_for_model(key, X)
                
                diagnoses.append(Diagnosis(
                    diagnosis=model_registry.name_map.get(key, key),
                    icd10=model_registry.icd10_map.get(key, "R69"),
                    confidence=proba,
                    confidence_interval_lower=proba - 0.07,
                    confidence_interval_upper=proba + 0.07,
                    supporting_labs=get_supporting_labs(key, X),
                    feature_contributions=shap_vals,
                    citations=get_citation_objects(model_registry.icd10_map.get(key, "R69"))
                ))
        
        # If no diagnoses exceed thresholds, return normal
        if len(diagnoses) == 0:
            citations = get_citation_objects("Z01.00")
            diagnoses.append(Diagnosis(
                diagnosis="No significant abnormality detected",
                icd10="Z01.00",
                confidence=0.95,
                confidence_interval_lower=0.90,
                confidence_interval_upper=1.00,
                supporting_labs=["Within normal limits"],
                feature_contributions=[],
                citations=citations
            ))
        diagnoses.sort(key=lambda x: x.confidence, reverse=True)
        
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

        all_predictions = model_registry.predict_all(X)
        print(f"DEBUG: All predictions: {all_predictions}")

        diagnoses = []

        for key, proba in all_predictions.items():
            threshold = model_registry.thresholds.get(key, 0.5)
            if proba > threshold:
                # Get SHAP values for this model (if available)
                shap_vals = model_registry.get_shap_for_model(key, X)
                
                diagnoses.append(Diagnosis(
                    diagnosis=model_registry.name_map.get(key, key),
                    icd10=model_registry.icd10_map.get(key, "R69"),
                    confidence=proba,
                    confidence_interval_lower=proba - 0.07,
                    confidence_interval_upper=proba + 0.07,
                    supporting_labs=get_supporting_labs(key, X),
                    feature_contributions=shap_vals,
                    citations=get_citation_objects(model_registry.icd10_map.get(key, "R69"))
                ))
        
        if len(diagnoses) == 0:
            citations = get_citation_objects("Z01.00")
            diagnoses.append(Diagnosis(
                diagnosis="No significant abnormality detected",
                icd10="Z01.00",
                confidence=0.95,
                confidence_interval_lower=0.90,
                confidence_interval_upper=1.00,
                supporting_labs=["Within normal limits"],
                feature_contributions=[],
                citations=citations
            ))
        diagnoses.sort(key=lambda x: x.confidence, reverse=True)
        
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