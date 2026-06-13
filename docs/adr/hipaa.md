# ADR 005: Data Privacy and HIPAA Compliance Strategy

## Context
The API processes patient laboratory data. This data may be considered Protected Health Information (PHI) under HIPAA. The API needs to balance:
- Clinical utility (age and sex are important for reference ranges)
- Privacy protection (minimize risk of re-identification)
- Regulatory compliance (HIPAA, GDPR, etc.)
- Practical implementation (ease of use for customers)

## Decision
Adopt a minimum necessary data approach. Accept only birth year (not full date of birth) and sex. Reject all other demographic identifiers (name, address, phone, email, MRN, etc.).

## Rationale

### Minimum Necessary Standard
HIPAA requires covered entities to limit PHI to the minimum necessary for the intended purpose. For lab result interpretation, the minimum necessary data is:
- Age (in years) for age-adjusted reference ranges
- Sex for sex-specific reference ranges
- Laboratory results with dates (de-identified by removing specific day)

### Birth Year vs Full Date of Birth
| Approach | PHI Status | Clinical Utility | Risk |
|----------|------------|------------------|------|
| Full DOB (YYYY-MM-DD) | PHI (identifier) | High (exact age) | Higher re-identification risk |
| Birth year only (YYYY) | Not PHI (under Safe Harbor) | Sufficient for adult reference ranges | Low |
| Age in years only | Not PHI | Sufficient | Very low |

Using birth year only removes the API from HIPAA coverage for that data element under the Safe Harbor method (dates must be stripped to year only).

### Sex Only (No Other Demographics)
Sex is necessary for reference ranges (hemoglobin, RBC, etc. differ by sex). Race, ethnicity, socioeconomic status, and other demographics are not needed for the diagnostic model and are therefore excluded.

### What Is Not Collected
- Patient name
- MRN or other identifiers
- Address (any level)
- Phone number
- Email address
- Full date of birth
- Race or ethnicity (unless voluntarily provided, which is optional)
- Provider names or identifiers

## Consequences

### Positive
- Minimal PHI exposure
- Simplified compliance (fewer HIPAA obligations)
- Lower risk profile for customers
- Data can be used more freely for model improvement
- Easier cross-border data transfer (GDPR considerations)

### Negative
- Pediatric patients: age in years is insufficient for younger patients
- Cannot track individual patients over time (no persistent identifier)
- Cannot link to external data sources

### Mitigations
- Document limitation: API is for adult patients only (age >= 18)
- If pediatric use is needed, alternative implementation with full DOB under BAA would be required
- Customers retain their own patient identifiers; API does not need them

## Future Enhancements

### Encryption in Transit
All API endpoints require TLS 1.3. No plaintext HTTP.

### Encryption at Rest
If the API logs requests for debugging, logs must be encrypted and retained only as long as necessary.

### Business Associate Agreements (BAAs)
For customers who need to send full PHI (e.g., integrating directly from EHR), the API provider would sign a BAA with the customer. This is a future enhancement, not implemented in the current version.

### Audit Logging
If PHI is ever processed, implement audit logging of:
- Who accessed what data
- When
- For what purpose

## Comparison to Industry Practice

| Approach | Used By | Risk Level |
|----------|---------|------------|
| Full PHI (name, DOB, MRN) | EHR vendors (Epic, Cerner) | High (requires full HIPAA compliance) |
| De-identified (year only, no identifiers) | Many research APIs, NHANES, MIMIC-IV | Low |
| Synthetic data (no real PHI) | SYNTHEMA project, SHARE initiative | None |

This API aligns with the de-identified approach, similar to public research datasets.


## References
- HIPAA Privacy Rule: Minimum Necessary Standard (45 CFR § 164.502(b))
- HIPAA Safe Harbor Method (45 CFR § 164.514(b)(2))
- NIST Guide to Protecting the Confidentiality of Personally Identifiable Information (SP 800-122)