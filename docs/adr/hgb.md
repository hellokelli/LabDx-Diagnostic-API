# ADR 004: Start with Hemoglobinopathies as First Condition Group


## Context
The API aims to support differential diagnosis for many conditions. Building for all conditions at once is not feasible due to data sparsity and validation requirements.

A focused first condition group is needed to prove the method works before expanding.

## Decision
Target hemoglobinopathies (beta-thalassemia trait, sickle cell disease/trait, HbE trait, and iron deficiency anemia) as the initial pilot condition group.

## Rationale

### Clear Laboratory Indicators
Hemoglobinopathies have well-established relationships with CBC parameters:
- Low MCV + normal/elevated RBC + normal ferritin → thalassemia trait
- Low MCV + low ferritin + high RDW → iron deficiency
- Low Hb + HbS on electrophoresis → sickle cell

This makes them ideal for initial model development.

### Commonly Overlooked
Hemoglobinopathies are often missed in non-endemic regions. Physicians may not consider HbE trait in a patient of non-Southeast Asian descent, even though it presents similarly to thalassemia trait. The API can serve as a safety net.

### Economic Screening Opportunity
The gold standard for hemoglobinopathy diagnosis is hemoglobin electrophoresis or HPLC, which costs $50-200 per test. A screening tool using routine CBC (cost $5-15) could reduce unnecessary confirmatory testing and guide appropriate use of expensive diagnostics.

### Clear Expansion Path
Success with hemoglobinopathies leads naturally to:
- Other anemias (hemolytic, megaloblastic, aplastic)
- Other hematologic conditions (polycythemia, thrombocytopenia, leukopenia)
- Non-hematologic lab-driven diagnoses (CKD, diabetes, liver disease)

### Manageable Scope for Pilot
The pilot requires:
- 4 target conditions
- 7 CBC parameters
- 4 derived indices
- Public data sources (NHANES for healthy controls, MIMIC-IV for cases)

This is achievable within 12 weeks by a solo developer.

## Consequences

### Positive
- Scientifically sound first step
- Demonstrable value (reduces unnecessary testing)
- Clear success metrics (AUC >0.90 for common conditions)
- Expandable architecture

### Negative
- Limited initial market (hematology focus)
- Rare variants (HbE trait) may have limited training data

### Mitigations
- Set lower AUC target (0.85) for rare variants
- Use synthetic data augmentation if needed
- Expand to other condition groups after pilot success

## Success Criteria

| Condition | Target AUC |
|-----------|------------|
| Beta-thalassemia trait | >0.90 |
| Iron deficiency anemia | >0.90 |
| Sickle cell trait/disease | >0.90 |
| HbE trait | >0.85 |

## References
- Taher et al. (2018). Thalassaemia. Lancet.
- Mentzer index (1973) for thalassemia screening
- NHANES CBC data
- MIMIC-IV hemoglobinopathy cases