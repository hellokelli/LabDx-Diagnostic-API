![Static Badge](https://img.shields.io/badge/coverage-87%25-green)
![Static Badge](https://img.shields.io/badge/docs-85%25-green)

# 🔬 LabDx: Diagnostic API for Hemoglobinopathy Detection

LabDx is a proof-of-concept diagnostic API that analyzes longitudinal laboratory results and returns a ranked differential diagnosis with confidence scores, SHAP feature attribution, and peer-reviewed citations. This repository demonstrates the architecture, feature engineering pipeline, and public data training examples for a hemoglobinopathy detection model.

**Important Disclaimer:** This is a demonstration project only. The model shown here is trained on public NHANES data with proxy labels and is **not validated for clinical use**. Proprietary model weights and MIMIC-IV data are not included in this repository.

---

## 🚩 Problem Statement

Physicians have more laboratory data than ever, yet diagnostic delays remain common. Medical errors account for 251,000 deaths annually. Existing clinical decision support tools require symptoms or suspected diagnoses as input. None work from laboratory data alone or analyze longitudinal trends.

This API addresses that gap by synthesizing existing lab data to reveal diagnostic patterns, temporal trends, and anomalies that do not match common conditions.

---

## 🎯 Vision: Connecting Disconnected Dots

"No one is talking. The giant is suffering. And no one even notices, because they are all too busy managing their own small piece of the rope." -Jonathan Swift

Healthcare  has become entrapped in the twine of isolated specialists. Much like Swift's giant, the rheumatologists have ensnared the hands in a treatment that pulls at the stomach, while the head is restricted by the neurologist that can't see the feet.

Finding a physician that is multi-disciplinary is extremely rare, and even then, it is difficult for one person to know all the ways the body is connected.

This project is motivated by a lifetime of experiencing the healthcare disconnect. From being misdiagnosed with leukemia at 7, chronic pain that started at 14, unexplained recurrent miscarriages at 37, to the final long overdue diagnosis at 42. Healthcare has failed many, but maybe it doesn't have to fail our future?

This API starts with hemoglobinopathies. However, the architecture is designed to build and recognize patterns across specialties and to see the signals hidden in the noise and weave the dots that so often go unconnected.

---

## 🧩 What This API Does

| Feature | Description |
|---------|-------------|
| Lab-result-driven diagnosis | No symptoms or suspected diagnosis required |
| Transparent predictions | SHAP values show why each diagnosis was suggested |
| FHIR native | Accepts FHIR R4 bundles for EHR integration |
| Evidence-cited | Every diagnosis includes peer-reviewed citations |

---

## 🧬 Target Conditions (Pilot Scope)

| Condition | Prevalence | Key Lab Markers |
|-----------|------------|-----------------|
| Beta-thalassemia trait | 1-6% globally | Low MCV, normal/elevated RBC, normal ferritin |
| Sickle cell disease | <1% | Low RBC, low Hb, high RDW, high WBW |
| Sickle cell trait | 1-5% endemic | Slightly low MCV |


---

## Success Metrics (Pilot)

The pilot phase targets hemoglobinopathies (beta-thalassemia trait, sickle cell disease/trait). Success is defined by the following quantifiable metrics:

### Model Performance

| Metric | Target | Measurement |
|--------|--------|-------------|
| AUC (common conditions) | >0.90 | Area under ROC curve  |
| AUC (rare variants) | >0.85 | Area under ROC curve  |
| Calibration slope | 0.8 - 1.2 | Calibration curve slope (ideal = 1.0) |
| Calibration intercept | <0.1 | Calibration curve intercept (ideal = 0) |
| Sensitivity | >90% | |
| Specificity | >95% | |
| External validation drop | <15% | Performance drop from internal to external validation |
| Net benefit at 10% threshold | >0.02 | Decision curve analysis net benefit |

### Go/No-Go Decision

Proceed to Phase 2 (expansion to additional hematologic conditions) only if ALL model performance metrics meet or exceed minimum acceptable thresholds. See [Roadmap](docs/roadmap.md)

If metrics not met, publish negative results and pivot to alternative architecture or different initial condition.

## 🏗 Technical Architecture

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
        D --> D1[Extract CBC Parameters]
        D1 --> D2[Apply Defaults for Missing Values]
        D2 --> E
    end

    subgraph "Prediction Engine"
        E[Three Independent XGBoost Models Thalassemia SCD SCT]
    end

    E --> F[Post-Processing]

    subgraph "Post-Processing"
        F --> F1[SHAP Values]
        F1 --> F2[Citation Lookup]
    end

    F2 --> G[JSON Response]
    G --> H[Client]
```
---
## 🔐 Authentication

The API uses API key authentication. All requests to protected endpoints must include the API key in the request header.

### Getting an API Key

For demonstration purposes, the API key is stored in a `.env` file. To run the API locally:

1. Create a `.env` file in the project root
2. Add your API key: `LABDX_API_KEY=your-api-key-here`
3. The API will load the key automatically using `python-dotenv`

### Making Authenticated Requests

Include the API key in the `X-API-Key` header for all requests.
---

## 🥽 Unit Tests

This project includes unit tests for the test name resolver, feature extraction, citation lookup, and API endpoints.

### Install Development Dependencies

```bash
pip install -r requirements-dev.txt
```
### Run All Tests

```bash
pytest test_labdx.py -v
```
## Model Performance (MIMIC-IV Validation)

### Beta-Thalassemia Trait

| Metric | Value |
|--------|-------|
| AUC | 0.9792 |
| 95% CI | 0.9341 – 0.9938 |
| Sensitivity | 93.41% |
| Specificity | 99.38% |
| Optimal Threshold | 0.3054 |
| Training set size | 3,587 patients (362 cases, 3,225 controls) |
| Test set size | 898 patients (91 cases, 807 controls) |

### Sickle Cell Disease

| Metric | Value |
|--------|-------|
| AUC | 0.9706 |
| 95% CI | 0.9568 – 0.9845 |
| Sensitivity | 90.81% |
| Specificity | 99.88% |
| Optimal Threshold | 0.7508 |
| Training set size | 4,313 patients (1,088 cases, 3,225 controls) |
| Test set size | 1,079 patients (272 cases, 807 controls) |

### Sickle Cell Trait

| Metric | Value |
|--------|-------|
| AUC | 0.9582 |
| 95% CI | 0.9364 – 0.9799 |
| Sensitivity | 86.96% |
| Specificity | 97.99% |
| Optimal Threshold | 0.4042 |
| Training set size | 3,774 patients (549 cases, 3,225 controls) |
| Test set size | 945 patients (138 cases, 807 controls) |