# LabDx Data Dictionary

# LabDx Data Dictionary

This document defines all features currently implemented in the LabDx diagnostic API (Version 1.0). Features are derived from CBC parameters and derived indices. Temporal features, missing indicators, and several derived indices are on the roadmap for future versions.

## Patient Demographics

| Field | Type | Description | Source | Example |
|-------|------|-------------|--------|---------|
| patient_id | string | Unique patient identifier (optional) | Client | P001234 |
| birth_year | integer | Patient year of birth (4-digit) | Client | 1975 |
| age_years | integer | Calculated age at lab collection | Derived | 49 |
| sex | string | Biological sex (M, F, other) | Client | F |

**Note:** Pregnancy status, medications, and problems are accepted in the request but not currently used in feature extraction. They are reserved for future versions.

## CBC Parameters (Extracted)

| Feature | LOINC Code | Unit | Description | Implemented |
|---------|------------|------|-------------|-------------|
| hemoglobin | 718-7 | g/dL | Hemoglobin concentration | Yes |
| mcv | 787-2 | fL | Mean corpuscular volume | Yes |
| rbc | 789-8 | million/uL | Red blood cell count | Yes |
| rdw | 788-0 | % | Red cell distribution width | Yes |

**Not yet implemented:** MCH, MCHC, platelet count, WBC count. These are on the roadmap.

| Feature | LOINC Code | Unit | Description | Normal Range (Adult) |
|---------|------------|------|-------------|----------------------|
| mch | 785-6 | pg | Mean corpuscular hemoglobin | 27-33 |
| mchc | 786-4 | g/dL | Mean corpuscular hemoglobin concentration | 32-36 |
| platelet_count | 777-3 | thousand/uL | Platelet count | 150-450 |
| wbc_count | 6690-2 | thousand/uL | White blood cell count | 4.5-11.0 |

## Derived Indices 

| Feature | Formula | Clinical Threshold | Description |
|---------|---------|-------------------|-------------|
| mentzer_index | MCV / RBC | <13 suggests thalassemia trait | Distinguishes thalassemia from iron deficiency |
| green_king_index | (MCV² × RDW) / (Hb × 100) | Elevated in iron deficiency | Alternative iron deficiency indicator |
| england_fraser_index | MCV - RBC - (5 × Hb) - 8.4 | >0 suggests thalassemia trait | Alternative thalassemia indicator |
| srivastava_index | MCH / RBC | <3.7 suggests thalassemia trait | Another thalassemia indicator |

## Derived Index Example Calculation

For a patient with MCV = 70 fL and RBC = 5.2 million/uL:

mentzer_index = 70 / 5.2 = 13.46

Result = 13.46 (borderline, indeterminate)

## Unit Normalization

The API accepts and normalizes the following units:

| Test | Standard Unit | Accepted Units | Conversion |
|------|---------------|----------------|------------|
| Hemoglobin | g/dL | g/dL, g/L | g/L → divide by 10 |
| MCV | fL | fL, um³ | No conversion needed |
| RBC | million/uL | million/uL, x10¹²/L | No conversion needed |
| RDW | % | %, percent | No conversion needed |

Unsupported units return an error.

## Clinical Context Features

| Feature | Status | Description |
|---------|--------|-------------|
| age_years | Implemented | Derived from birth_year |
| sex_numeric | Implemented | Converted from sex (0=Male, 1=Female) |
| pregnancy_status | Not implemented | Reserved for future version |
| medication_effect | Not implemented | Reserved for future version |

## Target Labels (Diagnosis Codes)

These are the ICD-10 codes used as ground truth labels for model training. Current model uses a dummy model; real training pending MIMIC-IV access.

| Condition | ICD-10 Code | Description |
|-----------|-------------|-------------|
| Beta-thalassemia trait | D56.3 | Carrier state for beta-thalassemia |
| Iron deficiency anemia | D50.8, D50.9 | Anemia due to insufficient iron stores |
| Sickle cell trait | D57.3 | Carrier state for sickle cell |
| Sickle cell disease | D57.0, D57.1, D57.2 | Active sickle cell disease |
| HbE trait | D56.5 | Carrier state for hemoglobin E |
| Healthy control | N/A | No hemoglobinopathy or significant anemia |

## Current Feature Vector

The current feature vector include the following:

| Feature | Description |
|---------|-------------|
| hemoglobin | Hemoglobin value in g/dL |
| mcv | Mean corpuscular volume in fL |
| mch | Mean corpuscular hemoglobin in pg (if available) |
| rbc | Red blood cell count in million/uL |
| rdw | Red cell distribution width in % |
| mentzer_index | MCV / RBC |
| green_king_index | (MCV² × RDW) / (Hb × 100) |
| england_fraser_index | MCV - RBC - (5 × Hb) - 8.4 |
| srivastava_index | MCH / RBC (0 if MCH missing) |
| age_years | Age in years |
| sex_numeric | 0=Male, 1=Female |

## Roadmap Features (Not Yet Implemented)

The following features are planned for future versions:

| Category | Features | Target Version |
|----------|----------|----------------|
| CBC Parameters | MCH, MCHC, platelets, WBC | v2.0 |
| Derived Indices | Green & King, England & Fraser, Srivastava | v2.0 |
| Temporal Slopes | 3-month, 6-month, 12-month slopes for Hb, MCV | v2.0 |
| Temporal Variability | Standard deviation, coefficient of variation | v2.0 |
| Missing Indicators | Binary flags per lab per timepoint | v2.0 |
| Pregnancy status | Boolean flag | v2.0 |
| Medication effects | Binary flags for common medications | v3.0 |

## Data Quality Rules

| Rule | Description | Action |
|------|-------------|--------|
| Missing values | XGBoost handles missing values natively | Leave as NA, do not impute |
| Outliers | Values beyond 3 standard deviations | Flag but do not remove automatically |
| Negative values | Biologically impossible | Treat as missing |
| Zero values | Zero for hemoglobin is incompatible with life | Treat as missing |
| Unit validation | Units must match accepted list | Reject request if unsupported |

## Normalization Approach

Features are currently used raw (not normalized). Age-adjusted and sex-adjusted normalization is planned for future versions.

## Missing Data Indicators

Binary flags indicating whether a specific lab value was available at a given timepoint. These help the model distinguish between a normal value and a missing value.

| Feature | Format | Description |
|---------|--------|-------------|
| hgb_missing | 0 or 1 | 1 if hemoglobin was not measured |
| mcv_missing | 0 or 1 | 1 if MCV was not measured |
| rbc_missing | 0 or 1 | 1 if RBC count was not measured |
| rdw_missing | 0 or 1 | 1 if RDW was not measured |

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-06-01 | Initial implementation: 7 features (Hb, MCV, RBC, RDW, Mentzer index, age, sex) |
| 1.1 | 2026-06-13 | Added unit normalization (g/L → g/dL) |
| 2.0 | Planned | Add remaining CBC parameters, derived indices, temporal features |


---
# Yet to be implemented:


## Temporal Features

These features capture changes in lab values over time. They require at least two measurements separated by at least 30 days. Patients with only one measurement receive null values for slope features.

### Hemoglobin Trend Features

| Feature | Description | Calculation | Clinical Significance |
|---------|-------------|-------------|----------------------|
| hgb_baseline | First recorded hemoglobin | Minimum date value | Baseline status before any intervention |
| hgb_current | Most recent hemoglobin | Maximum date value | Current status for decision making |
| hgb_slope_3m | Slope over 3 months | Linear regression over last 90 days | Rapid decline suggests acute blood loss |
| hgb_slope_6m | Slope over 6 months | Linear regression over last 180 days | Moderate decline suggests chronic disease |
| hgb_slope_12m | Slope over 12 months | Linear regression over last 365 days | Slow decline suggests indolent condition |
| hgb_acceleration | Change in slope | Second derivative of trend | Accelerating decline is clinically concerning |
| hgb_variability | Coefficient of variation | Standard deviation divided by mean times 100 | High variability suggests lab error or intermittent issue |

### MCV Trend Features

| Feature | Description | Clinical Significance |
|---------|-------------|----------------------|
| mcv_baseline | First recorded MCV | Baseline status for macrocytic/microcytic evaluation |
| mcv_current | Most recent MCV | Current status for treatment monitoring |
| mcv_slope_6m | Slope over 6 months | Increasing MCV suggests B12 or folate deficiency |
| mcv_slope_12m | Slope over 12 months | Decreasing MCV suggests iron deficiency or thalassemia |

## Feature Vector Format

The final feature vector passed to XGBoost is a fixed-length numeric array with approximately 30 to 50 features depending on data availability.

### Example Feature Vector (30 features)

`[12.1, 70, 23.5, 4.8, 13.5, 250, 7.2, 13.46, 0, 49, 0, 0, -0.12, -0.08, -0.05, 2.1, 1.8, 0.9, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0]`

### Feature Index Mapping

| Index | Feature | Index | Feature |
|-------|---------|-------|---------|
| 0 | hgb_current | 15 | hgb_slope_3m |
| 1 | mcv_current | 16 | hgb_slope_6m |
| 2 | mch_current | 17 | hgb_slope_12m |
| 3 | rbc_current | 18 | mcv_slope_6m |
| 4 | rdw_current | 19 | mentzer_index |
| 5 | platelet_current | 20 | green_king_index |
| 6 | wbc_current | 21 | england_fraser_index |
| 7 | mentzer_index | 22 | age_years |
| 8 | green_king_index | 23 | sex_numeric |
| 9 | england_fraser_index | 24 | pregnancy_status |
| 10 | hgb_baseline | 25 | medication_effect |
| 11 | mcv_baseline | 26 | hgb_missing |
| 12 | rbc_baseline | 27 | mcv_missing |
| 13 | rdw_baseline | 28 | rbc_missing |
| 14 | platelet_baseline | 29 | rdw_missing |