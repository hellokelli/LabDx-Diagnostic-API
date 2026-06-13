# ADR 002: Use FHIR R4 for Interoperability

## Context
The API needs to accept laboratory data from external systems. Potential users include:
- EHR vendors (Epic, Cerner, Meditech)
- RCM and billing clients
- Prior authorization facilities
- Health information exchanges

Each of these systems may use different data formats. Supporting proprietary formats for each customer would require custom integrations, increasing implementation time and cost.

## Decision
Use FHIR R4 (Fast Healthcare Interoperability Resources) as the primary input format for laboratory data. Specifically, implement the US Core 6.1.0 profiles for DiagnosticReport and Observation resources.

## Rationale

### Regulatory Alignment
CMS and the Office of the National Coordinator for Health IT (ONC) have mandated FHIR as the standard for healthcare data exchange. USCDI v3 requires FHIR for certified EHRs. Building on FHIR now ensures compliance with future regulations.

### Industry Direction
Major EHR vendors including Epic, Cerner, and Meditech have adopted FHIR APIs. Third-party systems already know how to send FHIR bundles. By accepting FHIR, the API fits into existing workflows without requiring customers to transform their data.

### Faster Implementation
Customers can send what they already have. No custom data mapping per customer. No ETL pipelines. Implementation time drops from weeks to days.

### Lower Cost
Less custom development means lower integration costs for both the API provider and the customer. This makes the product more attractive to price-sensitive RCM and billing clients.

### Extensibility
FHIR uses a resource-based model with extensions. Adding new features (e.g., medication data, vital signs, genomics) requires only adding new resource types or elements. No breaking changes to the API contract.

### Future-Proofing
As CMS pushes more programs toward FHIR (e.g., prior authorization, quality measurement, risk adjustment), the API will already speak the required language.

## Consequences

### Positive
- Interoperable with any FHIR-compliant system
- No custom integration per customer
- Regulatory compliance (USCDI v3, ONC certification)
- Extensible for future features
- Documented via OpenAPI (since FastAPI generates docs from Pydantic models)

### Negative
- FHIR bundles are verbose compared to simple JSON
- Some customers may need to learn FHIR structure
- Validation logic is more complex

### Mitigations
- Also provide a simplified native JSON endpoint (/diagnose) for customers who prefer it
- Both endpoints use the same internal feature extraction logic
- FHIR endpoint is optional; customers can use whichever format they prefer


## References
- HL7 FHIR Release 4: https://hl7.org/fhir/R4/
- US Core Implementation Guide 6.1.0: http://hl7.org/fhir/us/core/
- CMS Interoperability and Patient Access Final Rule
- ONC Cures Act Final Rule (USCDI v3)