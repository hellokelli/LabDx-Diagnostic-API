# Roadmap

## Pilot Phase

### Completed
- [x] FastAPI backend
- [x] FHIR R4 endpoint
- [x] Test name resolver
- [x] Derived indices (Mentzer, Green & King, England & Fraser, Srivastava)
- [x] SHAP explanations (placeholder)
- [x] Citation lookup
- [x] API key authentication
- [x] Rate limiting
- [x] Unit tests
- [x] GitHub Actions CI
- [x] Docker containers
- [x] Raspberry Pi deployment
- [x] MIMIC-IV approval 
- [x] Real XGBoost model training

### In Progress


### Planned

- [ ] Temporal slopes (3,6,12 months)
- [ ] Anomaly detection (Isolation Forest)
- [ ] OAuth 2.0 support
- [ ] Cloud deployment (Render/Fly.io)
- [ ] Redis caching

## Expansion Roadmap

Phase 1 (Current) succeeds only if all success metrics are met. Expansion proceeds conditionally, not by default.

### Phase 2: Complete Hemoglobinopathy Coverage

- Expand to alpha-thalassemia traits, HbC, HbD, and unstable hemoglobins.
- Additional data set with outpatient data.
- Multi-class model
-

| Condition | Target AUC | Data Source |
|-----------|------------|-------------|
| Alpha-thalassemia trait | >0.85 | MIMIC-IV + synthetic |
| HbC trait/disease | >0.85 | MIMIC-IV + literature |
| HbD trait | >0.85 | MIMIC-IV + literature |
| Unstable hemoglobins | >0.80 | Case reports + synthetic |

Go decision: Phase 1 metrics met AND data available for new conditions.

### Phase 3: Adjacent Hematologic Conditions

Expand to polycythemia vera, myelodysplastic syndromes, autoimmune hemolytic anemia, and G6PD deficiency.
- Temporal slopes (3,6,12 months)
- Anomaly detection (Isolation Forest)
- OAuth 2.0 support
- Cloud deployment (Render/Fly.io)
- Redis caching

| Condition | Primary Lab Markers |
|-----------|---------------------|
| Polycythemia vera | Elevated Hb, Hct, low EPO |
| Myelodysplastic syndromes | Cytopenias, macrocytosis |
| Autoimmune hemolytic anemia | Low Hb, high reticulocytes, positive DAT |
| G6PD deficiency | Acute hemolytic pattern |

Go decision: Phase 2 metrics met AND clinical partner engaged for validation.

### Phase 4: Non-Hematologic Lab-Driven Diagnoses That Go Undiagnosed

These conditions have clear lab markers but are frequently missed because symptoms are non-specific or overlap with common diseases. Each requires its own pilot with independent success metrics.

| Condition | Primary Lab Markers | Estimated Prevalence | Diagnostic Delay |
|-----------|---------------------|---------------------|------------------|
| Primary Biliary Cholangitis | Elevated ALP, positive AMA | ~1 in 3,000-4,000 | Average 3 years |
| Hereditary Hemochromatosis | Elevated ferritin, transferrin saturation >45% | ~1 in 300 (N. European descent) | Often diagnosed after iron overload |
| Celiac Disease | Positive tTG-IgA, EMA | ~1% of population | 6-10 years average |
| Autoimmune Hepatitis | Elevated ALT/AST, positive ANA/SMA, elevated IgG | ~1 in 5,000 | Often until cirrhosis develops |

Go decision: Each new condition group requires its own pilot with independent go/no-go metrics.

### Phase 5: Cross-Specialty Pattern Recognition (Vision)

Long-term goal: Recognize patterns across rheumatology, obstetrics, immunology, and gastroenterology using CMP, inflammatory markers, and hormone panels. This is speculative and depends on data availability and clinical partnerships.

## Expansion Principle

| Rule | Explanation |
|------|-------------|
| Evidence before expansion | No condition group expands without meeting its metrics |
| One group at a time | No parallel expansion across unrelated conditions |
| Data determines scope | Rare variants may require synthetic augmentation |
| Stop when metrics fail | Negative results are published, not ignored |

## Potential Future Conditions to Test

| Condition | Key Lab Tests | Prevalence / Impact | The Diagnostic Gap (Underdiagnosis/Delay) |
|-----------|---------------|---------------------|-------------------------------------------|
| Ehlers-Danlos Syndromes (EDS) | CMP (calcium, alk phos), Inflammatory markers (CRP, ESR, TNF-a), Hormone panel (DHEA-S, SHBG) | ~1 in 2,500 - 5,000 (likely underdiagnosed) | Patient experience confirms significant diagnostic odyssey; symptoms (IBS, dysautonomia, pain) are treated in silos without connecting the underlying cause |
| Rheumatoid Arthritis (RA) | Rheumatoid Factor (RF), Anti-CCP (very high specificity), CRP, ESR | ~0.5-1% of the population | Treatable disease that causes irreversible joint damage; delayed diagnosis is common due to lack of specialist access and reliance on nonspecific symptoms early on |
| Alzheimer's Disease (Early Stage) | pTau217, Amyloid beta 42/40 ratio; advanced imaging (PET) | ~1 in 9 people aged 65+ (>7M Americans) | Wildly underdiagnosed in early stages (MCI); <10% of eligible patients are diagnosed. New blood-based biomarkers (pTau217) are a major breakthrough for accessible, earlier screening |
| Hypophosphatasia (HPP) | ALP (chronically low for age/sex), Vitamin B6, Genetic testing | Severe forms are rare (~1/100,000), but milder adult-onset forms may be significantly underdiagnosed | Mild, nonspecific symptoms (pain, fractures, muscle weakness) are often dismissed; a very low ALP is a major clue often missed until more severe symptoms manifest |