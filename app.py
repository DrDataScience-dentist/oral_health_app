import streamlit as st
import pandas as pd
import joblib
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- CONFIGURATION ---
SHEET_NAME = "Oral Health Logs"
GOOGLE_FORM_URL = "https://forms.gle/2xNqVJq3Tzm8Cq859" # <-- PASTE YOUR GOOGLE FORM LINK HERE

# --- LOAD RESOURCES ---
@st.cache_resource
def load_model_resources():
    model = joblib.load("oral_health_model.pkl")
    encoder = joblib.load("label_encoder.pkl")
    return model, encoder

@st.cache_resource
def get_google_sheet():
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).sheet1

try:
    model, label_encoder = load_model_resources()
except Exception as e:
    st.error(f"Error loading models: {e}")
    st.stop()

st.set_page_config(page_title="Oral Health Bot", layout="centered")
st.title("🦷 Oral Health Self-Evaluation")
st.write("Please provide your basic details and answer the questions below.")

# --- QUESTIONS SETUP ---
question_groups = {
    "General Symptoms": {'Q1': "Presence of bad breath", 'Q2': "Presence of dry mouth", 'Q3': "Burning sensation in tongue/cheek/lips"},
    "Gum Health": {'Q4': "Bleeding in the gums while brushing", 'Q5': "Swollen gums", 'Q6': "Redness in gingiva"},
    "Tooth Sensitivity & Decay": {'Q7': "Sensitivity in a tooth", 'Q8': "Sensitivity in multiple teeth", 'Q9': "Pain in a fractured tooth", 'Q10': "Discolouration in a fractured tooth", 'Q11': "Pain in a filled tooth", 'Q12': "Extraction due to decay", 'Q13': "Tooth fell out on its own"},
    "Tooth Alignment": {'Q14': "Irregularly placed teeth", 'Q15': "Space between any teeth", 'Q16': "Forward upper teeth", 'Q17': "Forward lower teeth", 'Q18': "Space between upper and lower front teeth when biting"},
    "Swelling & Infection": {'Q19': "Swelling in the oral cavity", 'Q20': "Pain associated with swelling", 'Q21': "Pus discharge from swelling"},
    "Jaw Joint (TMJ)": {'Q22': "Clicking sound in jaw", 'Q23': "Pain when opening mouth", 'Q24': "Pain in front of ear while chewing"},
    "Soft Tissue Lesions": {'Q25': "White patch in the mouth", 'Q26': "Burning sensation with white patch", 'Q27': "Long-time ulcer in the mouth", 'Q28': "Pain with the ulcer", 'Q29': "Burning sensation with the ulcer"}
}

# --- MAIN FORM ---
with st.form("oral_health_form"):
    st.subheader("👤 Basic Details")
    c1, c2 = st.columns(2)
    with c1:
        age = st.number_input("Age", min_value=1, max_value=120, step=1, value=25)
    with c2:
        gender = st.selectbox("Gender", ["Male", "Female", "Other", "Prefer not to say"])

    st.markdown("---")
    
    user_input = {}
    for group, questions in question_groups.items():
        st.markdown(f"### 🔹 {group}")
        for key, question in questions.items():
            user_input[key] = st.checkbox(question)
            
    submitted = st.form_submit_button("🧾 Evaluate My Oral Health", type="primary")

# --- PROCESS SUBMISSION ---
if submitted:
    # 1. PREDICT (Only using symptom inputs, NOT age/gender)
    symptom_values = [1 if val else 0 for val in user_input.values()]
    # Ensure DataFrame has exact columns model expects
    input_df = pd.DataFrame([symptom_values], columns=user_input.keys())
    
    prediction = model.predict(input_df)[0]
    predicted_label = label_encoder.inverse_transform([prediction])[0]

    # 2. DISPLAY RESULTS
    st.divider()
    st.subheader("🦷 Your Oral Health Condition:")
    if predicted_label == "Good":
        st.success("✅ Good – You’re in good oral health. Recommended check-up every 12 months.")
    elif predicted_label == "Satisfactory":
        st.warning("⚠️ Satisfactory – Check-up recommended every 6 months. Improve oral hygiene.")
    elif predicted_label == "Bad":
        st.error("🚨 Bad – Immediate dental consultation recommended.")

    # 3. LOG TO SHEETS (Includes age/gender now)
    with st.spinner("Logging results..."):
        try:
            sheet = get_google_sheet()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # Log format: [Time, Age, Gender, Q1...Q29, Result]
            log_row = [timestamp, age, gender] + symptom_values + [predicted_label]
            sheet.append_row(log_row)
        except Exception as e:
            st.warning(f"Evaluation complete, but logging failed: {e}")

    # 4. POST-EVALUATION ACTION BUTTONS
    st.divider()
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        # Link button opens in new tab
        st.link_button("💬 Give Feedback (Google Form)", GOOGLE_FORM_URL, use_container_width=True)
    with col_f2:
        # Rerun button resets the app state
        if st.button("🔄 Start New Evaluation", use_container_width=True):
            st.rerun()

    st.caption("AI-based preliminary evaluation only. Consult a dentist for clinical diagnosis.")
