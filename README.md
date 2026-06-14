[![Run Unit Tests](https://github.com/hellokelli/LabDx-Diagnostic-API/actions/workflows/test.yml/badge.svg)](https://github.com/hellokelli/LabDx-Diagnostic-API/actions/workflows/test.yml)
# LabDx: Diagnostic API for Hemoglobinopathy Detection

LabDx is a proof-of-concept diagnostic API that analyzes longitudinal laboratory results and returns a ranked differential diagnosis with confidence scores, SHAP feature attribution, and peer-reviewed citations. This repository demonstrates the architecture, feature engineering pipeline, and public data training examples for a hemoglobinopathy detection model.

**Important Disclaimer:** This is a demonstration project only. The model shown here is trained on public NHANES data with proxy labels and is **not validated for clinical use**. Proprietary model weights and MIMIC-IV data are not included in this repository.

---

## Problem Statement

Physicians have more laboratory data than ever, yet diagnostic delays remain common. Medical errors account for 251,000 deaths annually. Existing clinical decision support tools require symptoms or suspected diagnoses as input. None work from laboratory data alone or analyze longitudinal trends.

This API addresses that gap by synthesizing existing lab data to reveal diagnostic patterns, temporal trends, and anomalies that do not match common conditions.

---

## Vision: Connecting Disconnected Dots

"No one is talking. The giant is suffering. And no one even notices, because they are all too busy managing their own small piece of the rope." -Jonathan Swift

Healthcare  has become entrapped in the twine of isolated specialists. Much like Swift's giant, the rheumatologists have ensnared the hands in a treatment that pulls at the stomach, while the head is restricted by the neurologist that can't see the feet.

Finding a physician that is multi-disciplinary is extremely rare, and even then, it is difficult for one person to know all the ways the body is connected.

This project is motivated by a lifetime of experiencing the healthcare disconnect. From being misdiagnosed with leukemia at 7, chronic pain that started at 14, unexplained recurrent miscarriages at 37, to the final long overdue diagnosis at 42. Healthcare has failed many, but maybe it doesn't have to fail our future?

This API starts with hemoglobinopathies. However, the architecture is designed to build and recognize patterns across specialties and to see the signals hidden in the noise and weave the dots that so often go unconnected.

---

## What This API Does

| Feature | Description |
|---------|-------------|
| Lab-result-driven diagnosis | No symptoms or suspected diagnosis required |
| Longitudinal trend analysis | Calculates slopes, acceleration, and variability over 3-12 months |
| Transparent predictions | SHAP values show why each diagnosis was suggested |
| Rare disease flagging | Anomaly detection identifies unrecognized patterns |
| FHIR native | Accepts FHIR R4 bundles for EHR integration |
| Evidence-cited | Every diagnosis includes peer-reviewed citations |

---

## Target Conditions (Pilot Scope)

| Condition | Prevalence | Key Lab Markers |
|-----------|------------|-----------------|
| Beta-thalassemia trait | 1-20% globally | Low MCV, normal/elevated RBC, normal ferritin |
| Iron deficiency anemia | 5-10% | Low MCV, low ferritin, high RDW |
| Sickle cell trait/disease | 1-40% endemic | Low Hb, HbS on electrophoresis |
| HbE trait | 10-60% SE Asia | Low MCV, low MCH, HbE peak |

---

## Technical Architecture

```mermaid
graph TD
    A[Client Request] --> B[API Gateway]

    subgraph "API Gateway Layer"
        B --> B1[Authentication]
        B --> B2[Rate Limiting]
    end

    B --> C[Test Name Resolver]

    subgraph "Processing Layer"
        C --> C1{In Cache?}
        C1 -->|Yes| D[Feature Pipeline]
        C1 -->|No| C2[Fuzzy Match]
        C2 --> D
    end

    subgraph "Feature Pipeline"
        D --> D1[Temporal Aggregates]
        D1 --> D2[Derived Indices]
        D2 --> E
    end

    subgraph "Prediction Engine"
        E[XGBoost + Anomaly Detection]
    end

    E --> F[Post-Processing]

    subgraph "Post-Processing"
        F --> F1[Calibration]
        F1 --> F2[SHAP Values]
        F2 --> F3[Citation Lookup]
    end

    F3 --> G[JSON Response]
    G --> H[Client]
```
---
## Authentication

The API uses API key authentication. All requests to protected endpoints must include the API key in the request header.

### Getting an API Key

For demonstration purposes, the API key is stored in a `.env` file. To run the API locally:

1. Create a `.env` file in the project root
2. Add your API key: `LABDX_API_KEY=your-api-key-here`
3. The API will load the key automatically using `python-dotenv`

### Making Authenticated Requests

Include the API key in the `X-API-Key` header for all requests.
---

## Unit Tests

This project includes unit tests for the test name resolver, feature extraction, citation lookup, and API endpoints.

### Install Development Dependencies

```bash
pip install -r requirements-dev.txt
```
### Run All Tests

```bash
pytest test_labdx.py -v
```
