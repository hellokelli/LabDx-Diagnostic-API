# ADR 001: Use XGBoost Instead of LLM for Diagnosis

## Context
The API needed to generate differential diagnoses from lab results. LLMs are popular but hallucinate.

## Decision
Use XGBoost (gradient boosted trees) for the diagnostic engine. Use LLM only for test name resolution.

## Consequences
- No hallucination risk for diagnoses
- Faster inference (<100ms)
- Transparent SHAP explanations possible
- LLM cost isolated to non-critical path