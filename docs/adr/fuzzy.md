# ADR 003: Use Fuzzy Matching Instead of LLM for Test Name Resolution

## Context
The API accepts free-text test names from users (e.g., "hgb", "HGB", "hemoglobin", "complete blood count"). These need to be mapped to standardized LOINC codes before feature extraction.

Options considered:
- LLM-based resolution (GPT, Claude, Llama)
- Fuzzy matching with synonym dictionary
- Exact match only (user must provide LOINC codes)

## Decision
Use fuzzy matching with a synonym dictionary and in-memory cache. Reject LLM-based resolution for the initial version.

## Rationale

### Lower Cost
LLM API calls incur per-token costs. Even at $0.10 per 1,000 tokens, high-volume usage adds up. Fuzzy matching has zero marginal cost.

### No Hallucination Risk
LLMs can map "CBC" to "Complete Blood Count" correctly 99% of the time, but the 1% failure rate could map it to "Cerebrospinal Fluid" or other incorrect LOINC codes. Fuzzy matching on a curated synonym list has no hallucinations.

### Faster
LLM resolution takes 500-2000ms per call. Fuzzy matching takes 5-20ms. Cache hits are near-instant.

### Sufficient Coverage
A well-maintained synonym dictionary can cover 99% of common test names. The initial dictionary covers 7 core CBC parameters with 5-10 synonyms each. Coverage expands over time.

### Observable Performance
The resolver can track unmatched test names to a log file. This provides data on how often users submit unrecognized names, informing future decisions about LLM adoption.

### Future LLM Option Remains Open
If fuzzy matching proves insufficient (e.g., users submit highly variable names, new test types are added), an LLM resolver can be added as a fallback without breaking existing functionality.

## Consequences

### Positive
- Zero ongoing cost
- No hallucination risk
- Fast response times
- Cache persists across requests
- Easy to add new synonyms

### Negative
- Requires manual curation of synonyms
- May fail on highly unusual test names
- No "understanding" of new test types without updates

### Mitigations
- Log unmatched names for periodic review
- Add synonyms based on real usage patterns
- Design with LLM fallback option for future versions

## Performance Metrics
- Exact match: <1ms
- Fuzzy match (cache miss): 5-20ms
- Cache hit: <1ms
- LLM (if added): 500-2000ms

## Related ADRs
- ADR 001: Use XGBoost Instead of LLM for Diagnosis (consistent philosophy)

## References
- fuzzywuzzy library documentation