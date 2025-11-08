import streamlit as st
import pandas as pd
import joblib
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- CONFIGURATION ---
SHEET_NAME = "Oral Health Logs"  # EXACT name of your Google Sheet

# --- 1. LOAD RESOURCES (Model & Sheets) ---
@st.cache_resource
def load_model_resources():
    model = joblib.load("oral_health_model.pkl")
    encoder = joblib.load("label_encoder.pkl")
    return model, encoder

@st.cache_resource
def get_google_sheet():
    # Define the scope needed to access Sheets and Drive
    scope = ['https://www.googleapis.com/auth/spreadsheets',
             'https://www.googleapis.com/auth/drive']
    # Authenticate using secrets
    creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
    client = gspread.authorize(creds)
    # Open the sheet
    return client.open(SHEET_NAME).sheet1

# Load Resources immediately
try:
    model, label_encoder = load_model_resources()
except Exception as e:
    st.error(f"Error loading models: {e}")
    st.stop()

st.set_page_config(page_title="Oral Health Bot", layout="centered")
st.title("🦷 Oral Health Self-Evaluation")
st.write("Answer the questions below to assess your current oral health status.")

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

# --- FORM ---
with st.form("oral_health_form"):
    user_input = {}
    for group, questions in question_groups.items():
        st.markdown(f"### 🔹 {group}")
        for key, question in questions.items():
            user_input[key] = st.checkbox(question)
    submitted = st.form_submit_button("🧾 Evaluate My Oral Health")

# --- PROCESS SUBMISSION ---
if submitted:
    # 1. Predict
    input_values = [1 if val else 0 for val in user_input.values()]
    input_df = pd.DataFrame([input_values], columns=user_input.keys())
    
    prediction = model.predict(input_df)[0]
    predicted_label = label_encoder.inverse_transform([prediction])[0]

    # 2. Display Results
    st.markdown("---")
    st.subheader("🦷 Your Oral Health Condition:")
    if predicted_label == "Good":
        st.success("✅ Good – You’re in good oral health. Recommended check-up every 12 months.")
    elif predicted_label == "Satisfactory":
        st.warning("⚠️ Satisfactory – Check-up recommended every 6 months. Improve oral hygiene.")
    elif predicted_label == "Bad":
        st.error("🚨 Bad – Immediate dental consultation recommended.")

    # 3. Log to Google Sheets (Background Task)
   # 3. Log to Google Sheets (Debug Version)
    with st.spinner("Logging results..."):
        try:
            # Test connection first
            client = get_google_sheet().client
            st.write(f"Debug: Connected as {client.auth.service_account_email}")

            # Test opening sheet
            sheet = client.open(SHEET_NAME).sheet1
            st.write(f"Debug: Found sheet '{SHEET_NAME}'")

            # Prepare data
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_row = [timestamp] + input_values + [predicted_label]
            
            # Attempt append
            response = sheet.append_row(log_row)
            st.success(f"Logged successfully! Response: {response}")

        except gspread.exceptions.SpreadsheetNotFound:
            st.error(f"❌ Error: Could not find Google Sheet named '{SHEET_NAME}'. Check the name exactly.")
        except gspread.exceptions.APIError as api_err:
            st.error(f"❌ Google API Error: {api_err}")
        except Exception as e:
            st.error(f"❌ Unexpected Error Type: {type(e).__name__}")
            st.error(f"Error Details: {e}")
