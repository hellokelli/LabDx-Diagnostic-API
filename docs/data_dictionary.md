# LabDx Data Dictionary

This document defines all features used in the LabDx diagnostic API. Features are derived from CBC parameters, temporal trends, and derived indices.

## Patient Demographics

| Field | Type | Description | Source | Example |
|-------|------|-------------|--------|---------|
| patient_id | string | Unique patient identifier | EHR | P001234 |
| birth_year | integer | Patient year of birth (4-digit) | EHR | 1975 |
| age_years | integer | Calculated age at lab collection | Derived | 49 |
| sex | string | Biological sex (M, F, other) | EHR | F |
| pregnant | boolean | Pregnancy status | EHR | false |

## CBC Parameters (Raw Values)

| Feature | LOINC Code | Unit | Description | Normal Range (Adult) |
|---------|------------|------|-------------|----------------------|
| hemoglobin | 718-7 | g/dL | Hemoglobin concentration | Female: 12.0-16.0, Male: 13.5-17.5 |
| mcv | 787-2 | fL | Mean corpuscular volume | 80-100 |
| mch | 785-6 | pg | Mean corpuscular hemoglobin | 27-33 |
| mchc | 786-4 | g/dL | Mean corpuscular hemoglobin concentration | 32-36 |
| rbc_count | 789-8 | million/uL | Red blood cell count | Female: 4.2-5.4, Male: 4.7-6.1 |
| rdw | 788-0 | percent | Red cell distribution width | 11.5-14.5 |
| platelet_count | 777-3 | thousand/uL | Platelet count | 150-450 |
| wbc_count | 6690-2 | thousand/uL | White blood cell count | 4.5-11.0 |

## Derived Indices

These calculated indices help distinguish between different types of anemia.

| Feature | Formula | Clinical Threshold | Description |
|---------|---------|-------------------|-------------|
| mentzer_index | MCV divided by RBC | Less than 13 suggests thalassemia trait | Distinguishes thalassemia from iron deficiency |
| green_king_index | (MCV squared times RDW) divided by (hemoglobin times 100) | Elevated in iron deficiency | Alternative iron deficiency indicator |
| england_fraser_index | MCV minus RBC minus (5 times hemoglobin) minus 8.4 | Greater than 0 suggests thalassemia trait | Alternative thalassemia indicator |
| srivastava_index | MCH divided by RBC | Less than 3.7 suggests thalassemia trait | Another thalassemia indicator |
| rdw_cv | RDW | Greater than 15 suggests mixed deficiency | Red cell distribution width |

### Derived Index Example Calculation

For a patient with MCV = 70 fL and RBC = 5.2 million/uL:

mentzer_index = 70 divided by 5.2

Result = 13.46 (borderline, indeterminate)

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

## Clinical Context Features

| Feature | Type | Values | Description |
|---------|------|--------|-------------|
| age_group | categorical | pediatric, adult, elderly | Age-based reference range selection |
| sex_numeric | binary | 0 equals Male, 1 equals Female | For sex-specific reference ranges |
| pregnancy_status | binary | 0 equals false, 1 equals true | Affects hemoglobin reference range |
| medication_effect | binary | 0 equals absent, 1 equals present | Flag for medications that affect CBC |

## Missing Data Indicators

Binary flags indicating whether a specific lab value was available at a given timepoint. These help the model distinguish between a normal value and a missing value.

| Feature | Format | Description |
|---------|--------|-------------|
| hgb_missing | 0 or 1 | 1 if hemoglobin was not measured |
| mcv_missing | 0 or 1 | 1 if MCV was not measured |
| rbc_missing | 0 or 1 | 1 if RBC count was not measured |
| rdw_missing | 0 or 1 | 1 if RDW was not measured |
| platelet_missing | 0 or 1 | 1 if platelet count was not measured |

## Target Labels (Diagnosis Codes)

These are the ICD-10 codes used as ground truth labels for model training.

| Condition | ICD-10 Code | Description |
|-----------|-------------|-------------|
| Beta-thalassemia trait | D56.3 | Carrier state for beta-thalassemia |
| Iron deficiency anemia | D50.8, D50.9 | Anemia due to insufficient iron stores |
| Sickle cell trait | D57.3 | Carrier state for sickle cell |
| Sickle cell disease | D57.0, D57.1, D57.2 | Active sickle cell disease requiring management |
| HbE trait | D56.5 | Carrier state for hemoglobin E |
| Healthy control | N/A | No hemoglobinopathy or significant anemia |

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

## Data Quality Rules

| Rule | Description | Action |
|------|-------------|--------|
| Missing values | XGBoost handles missing values natively | Leave as NA, do not impute |
| Outliers | Values beyond 3 standard deviations | Flag but do not remove automatically |
| Negative values | Biologically impossible (e.g., negative hemoglobin) | Treat as missing |
| Zero values | Zero for hemoglobin is incompatible with life | Treat as missing |
| Unit validation | Ensure units match expected UCUM codes | Reject request if mismatch |

## Normalization Approach

Features are normalized using age-adjusted and sex-adjusted reference ranges rather than global z-scores. This preserves clinical interpretability.

### Example Calculation

For a 49-year-old female with hemoglobin of 11.4 g/dL and normal range of 12.0 to 16.0 g/dL:

normalized_value = (value - ref_low) divided by (ref_high - ref_low)

normalized_value = (11.4 - 12.0) divided by (16.0 - 12.0) = -0.15

Negative values indicate below normal range. Positive values indicate above normal range.

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-06-01 | Initial version for hemoglobinopathy pilot |
