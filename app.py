import streamlit as st
import requests
import json
from dotenv import load_dotenv
import os

load_dotenv()
API_KEY = os.getenv("LABDX_API_KEY")

# Page configuration
st.set_page_config(
    page_title="LabDx Diagnostic API Demo",
    page_icon="🔬",
    layout="wide"
)

# Title
st.title("🔬 LabDx Diagnostic API Demo")
st.markdown("""
This demo uses a machine learning API to analyze laboratory results and generate 
a differential diagnosis with SHAP explanations and peer-reviewed citations.
""")

# Sidebar for input
#st.sidebar.header("Patient Information")
#birth_year = st.sidebar.number_input("Birth Year", min_value=1900, max_value=2026, value=1975)
#sex = st.sidebar.selectbox("Sex", ["Female", "Male"])

#st.sidebar.header("Laboratory Results")
#hemoglobin = st.sidebar.number_input("Hemoglobin (g/dL)", value=11.4, step=0.1)
#mcv = st.sidebar.number_input("MCV (fL)", value=70.0, step=1.0)
#rbc = st.sidebar.number_input("RBC (million/uL)", value=5.2, step=0.1)
#rdw = st.sidebar.number_input("RDW (%)", value=13.5, step=0.1)

# API endpoint
api_url = st.text_input("API URL", value="http://localhost:8000/diagnose")

#Input
form = st.container(border=True)

pt_form_inner = form.container()
col1, col2 = pt_form_inner.columns(2)
col1.subheader("Patient Information")
birth_year = col1.slider("Birth Year", min_value=1900, max_value=2026, value=1975)
sex = col1.selectbox("Sex", ["Female", "Male"])
col1.space(size="large")

col2.subheader("Laboratory Results")
#lr_form_inner = form.container()
#col3, col4 = lr_form_inner.columns(2)
hemoglobin = col2.slider("Hemoglobin (g/dL)", value=11.4, min_value=0.0, max_value=20.0)
mcv = col2.slider("MCV (fL)", value=70.0, min_value=0.0, max_value=120.0)
rbc = col2.slider("RBC (million/uL)", value=5.2, min_value=0.0, max_value=10.0)
rdw = col2.slider("RDW (%)", value=13.5, min_value=0.0, max_value=20.0)

# Submit button
if col1.button("Run Diagnosis", type="primary"):
    with st.spinner("Calling API..."):
        # Prepare request
        request = {
            "patient": {
                "birth_year": birth_year,
                "sex": "F" if sex == "Female" else "M"
            },
            "lab_history": [
                {"date": "2024-06-20", "test_name": "hemoglobin", "value": hemoglobin, "unit": "g/dL"},
                {"date": "2024-06-20", "test_name": "MCV", "value": mcv, "unit": "fL"},
                {"date": "2024-06-20", "test_name": "RBC", "value": rbc, "unit": "million/uL"},
                {"date": "2024-06-20", "test_name": "RDW", "value": rdw, "unit": "%"}
            ]
        }

        headers = {"X-API-Key": API_KEY}
        
        try:
            response = requests.post(api_url, json=request, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                
                # Display results
                st.success(f"Request ID: {result['request_id']}")
                st.info(f"Processing Time: {result['processing_time_ms']} ms")
                
                st.header("📋 Potential Diagnoses")
                
                for idx, diag in enumerate(result['potential_diagnoses'], 1):
                    with st.expander(f"{idx}. {diag['diagnosis']} (Confidence: {diag['confidence']:.1%})"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown(f"**ICD-10 Code:** `{diag['icd10']}`")
                            st.markdown(f"**Confidence Interval:** {int(diag['confidence_interval_lower'] * 100)}% - {int(diag['confidence_interval_upper'] * 100)}%")
                            st.markdown("**Supporting Labs:**")
                            for lab in diag['supporting_labs']:
                                st.markdown(f"- {lab}")
                        
                        with col2:
                            st.markdown("**Feature Contributions (SHAP):**")
                            for feat in diag['feature_contributions']:
                                st.markdown(f"- {feat['feature']}: {feat['value']} → SHAP = {feat['shap']:.3f}")
                        
                        if diag.get('citations'):
                            st.markdown("**📚 Evidence & Citations:**")
                            for cite in diag['citations']:
                                st.markdown(f"- {cite['reference']}")
                                if cite.get('doi'):
                                    st.markdown(f"  DOI: http://doi.org/{cite['doi']}")
                                if cite.get('key_findings'):
                                    st.markdown(f"  *{cite['key_findings']}*")
            else:
                st.error(f"API Error: {response.status_code}")
                st.text(response.text)
                
        except Exception as e:
            st.error(f"Connection Error: {str(e)}")
            st.info("Make sure your FastAPI server is running: uvicorn labdx_api:app --reload --port 8000")

# Footer
st.markdown("---")
st.markdown("""
**Disclaimer:** This is a demonstration tool. Not validated for clinical use. 
Always consult a qualified healthcare provider for medical decisions.
""")
