import streamlit as st
from google import genai
from google.genai import types
import os
import json
import pandas as pd
from datetime import datetime

# ==========================================
# 1. CONFIG & STATE MANAGEMENT
# ==========================================
st.set_page_config(
    page_title="The Closer", 
    page_icon="🎙️", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Initialize Session State
if 'active_tab' not in st.session_state: st.session_state.active_tab = "generate"
if 'generated_lead' not in st.session_state: st.session_state.generated_lead = None
if 'last_audio_bytes' not in st.session_state: st.session_state.last_audio_bytes = None

# ==========================================
# 2. AIRBNB-STYLE CSS (The "Secret Sauce")
# ==========================================
st.markdown("""
    <style>
        /* --- RESET & BASICS --- */
        .stApp { background-color: #ffffff; color: #222222; font-family: 'Circular', -apple-system, BlinkMacSystemFont, Roboto, Helvetica Neue, sans-serif; }
        [data-testid="stHeader"] { display: none; }
        
        /* --- TYPOGRAPHY --- */
        h1, h2, h3 { color: #222222 !important; font-weight: 600 !important; }
        p, label, span, div { color: #717171; }
        
        /* --- HIDE DEFAULT STREAMLIT ELEMENTS --- */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        
        /* --- BOTTOM NAVIGATION BAR --- */
        .nav-container {
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            height: 80px;
            background-color: white;
            border-top: 1px solid #ebebeb;
            z-index: 9999;
            display: flex;
            justify-content: space-around;
            align-items: center;
            padding-bottom: 10px; /* Safe area for mobile */
        }
        
        /* Style the Streamlit buttons inside the columns to look like Nav Icons */
        div[data-testid="column"] button {
            background-color: transparent !important;
            border: none !important;
            color: #717171 !important;
            font-size: 12px !important;
            font-weight: 600 !important;
            padding: 0px !important;
            margin-top: 5px !important;
        }
        
        div[data-testid="column"] button:hover {
            color: #FF385C !important; /* Airbnb Red */
        }
        
        div[data-testid="column"] button:focus {
            color: #FF385C !important;
            outline: none !important;
            box-shadow: none !important;
        }

        /* --- CARDS (DOSSIER STYLE) --- */
        .airbnb-card {
            background: white;
            border-radius: 12px;
            box-shadow: 0 6px 16px rgba(0,0,0,0.12);
            padding: 24px;
            margin-bottom: 24px;
            border: 1px solid #dddddd;
        }
        
        .card-title {
            font-size: 22px;
            font-weight: 600;
            color: #222;
            margin-bottom: 4px;
        }
        
        .card-subtitle {
            font-size: 16px;
            color: #717171;
            margin-bottom: 16px;
        }
        
        .info-row {
            display: flex;
            justify-content: space-between;
            border-bottom: 1px solid #ebebeb;
            padding: 12px 0;
            font-size: 14px;
        }
        
        .highlight-box {
            background-color: #F7F7F7;
            border-radius: 8px;
            padding: 16px;
            margin-top: 16px;
            font-weight: 600;
            color: #222;
            text-align: center;
        }

        /* --- LIST VIEW --- */
        .list-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px 0;
            border-bottom: 1px solid #ebebeb;
            cursor: pointer;
        }
        .list-item:hover {
            background-color: #f7f7f7;
        }

        /* --- BUTTONS --- */
        div.stButton > button {
            background-color: #FF385C; /* Airbnb Red */
            color: white;
            border-radius: 8px;
            padding: 14px 24px;
            font-size: 16px;
            font-weight: 600;
            border: none;
            width: 100%;
        }
        div.stButton > button:hover {
            background-color: #D50027;
            color: white;
        }
        
        /* Secondary Button (Wireframe style) */
        button[kind="secondary"] {
            background-color: white !important;
            color: #222 !important;
            border: 1px solid #222 !important;
        }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. BACKEND LOGIC (AI & DATA)
# ==========================================
DB_FILE = "leads_db.json"
api_key = os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None
TEXT_MODEL_ID = "gemini-2.0-flash"

def load_leads():
    if not os.path.exists(DB_FILE): return []
    try:
        with open(DB_FILE, "r") as f: return json.load(f)
    except: return []

def save_lead(lead_data):
    leads = load_leads()
    lead_data['date'] = datetime.now().strftime("%Y-%m-%d %H:%M")
    leads.insert(0, lead_data)
    with open(DB_FILE, "w") as f: json.dump(leads, f)

def clean_json_string(json_str):
    json_str = json_str.strip()
    if json_str.startswith("```json"): json_str = json_str[7:]
    if json_str.startswith("```"): json_str = json_str[3:]
    if json_str.endswith("```"): json_str = json_str[:-3]
    return json_str

def process_voice_contact(audio_bytes):
    prompt = """
    Listen to this sales voice memo. Extract these fields.
    Return ONLY raw JSON (no markdown formatting):
    {
        "name": "Full Name",
        "contact_info": "Phone/Email",
        "background": "Context/Pain Points",
        "sales_angle": "Strategy Hook (1 short sentence)",
        "product_pitch": "Recommended Product",
        "follow_up": "Next Step Timeframe"
    }
    """
    try:
        response = client.models.generate_content(
            model=TEXT_MODEL_ID,
            contents=[types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"), prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        data = json.loads(clean_json_string(response.text))
        if isinstance(data, list): data = data[0] if len(data) > 0 else {"error": "Empty list"}
        return data
    except Exception as e: return {"error": str(e)}

def create_vcard(data):
    notes = f"STRATEGY: {data.get('sales_angle','')}\\n\\nPRODUCT: {data.get('product_pitch','')}\\n\\nBG: {data.get('background','')}"
    vcard = ["BEGIN:VCARD", "VERSION:3.0", f"FN:{data.get('name', 'Lead')}", f"TEL;TYPE=CELL:{data.get('contact_info', '')}", f"NOTE:{notes}", "END:VCARD"]
    return "\n".join(vcard)

# ==========================================
# 4. VIEW CONTROLLERS
# ==========================================

def render_bottom_nav():
    # Fixed container at bottom
    with st.container():
        st.markdown('<div class="nav-container">', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("🎙️ Generate", key="nav_gen"): st.session_state.active_tab = "generate"
        with c2:
            if st.button("📂 Leads", key="nav_pipe"): st.session_state.active_tab = "pipeline"
        with c3:
            if st.button("📊 Analytics", key="nav_an"): st.session_state.active_tab = "analytics"
        st.markdown('</div>', unsafe_allow_html=True)

def view_generate():
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 1. EMPTY STATE (Recording)
    if not st.session_state.generated_lead:
        st.markdown("""
            <div style="text-align: center; padding-top: 50px;">
                <h2 style="font-size: 28px; margin-bottom: 10px;">New Lead</h2>
                <p>Record your interaction details.</p>
            </div>
        """, unsafe_allow_html=True)
        
        # Centered Mic Interface
        st.markdown("<div style='margin: 40px auto; max-width: 400px;'>", unsafe_allow_html=True)
        audio_val = st.audio_input("Record", label_visibility="collapsed")
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("<p style='text-align:center; font-size:14px; color:#ccc; text-transform:uppercase; letter-spacing:1px;'>Tap to Record</p>", unsafe_allow_html=True)

        if audio_val:
            with st.spinner("Processing Intelligence..."):
                data = process_voice_contact(audio_val.read())
                if isinstance(data, dict) and "error" not in data:
                    save_lead(data)
                    st.session_state.generated_lead = data
                    st.rerun()
                else:
                    st.error(f"Error: {data.get('error')}")

    # 2. RESULT STATE (Dossier Card)
    else:
        lead = st.session_state.generated_lead
        
        st.markdown(f"""
            <div class="airbnb-card">
                <div style="display:flex; justify-content:space-between; align-items:start;">
                    <div>
                        <div class="card-title">{lead.get('name', 'Unknown Lead')}</div>
                        <div class="card-subtitle">{lead.get('sales_angle')}</div>
                    </div>
                </div>
                
                <div class="info-row">
                    <span>Contact</span>
                    <span style="color:#222; font-weight:500;">{lead.get('contact_info')}</span>
                </div>
                <div class="info-row">
                    <span>Follow Up</span>
                    <span style="color:#222; font-weight:500;">{lead.get('follow_up')}</span>
                </div>
                
                <div style="margin-top: 20px;">
                    <span style="font-size:12px; font-weight:700; text-transform:uppercase;">Background</span>
                    <p style="margin-top:5px; font-size:15px; color:#222; line-height:1.4;">{lead.get('background')}</p>
                </div>

                <div class="highlight-box">
                    Recommended: {lead.get('product_pitch')}
                </div>
            </div>
        """, unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            vcf = create_vcard(lead)
            safe_name = lead.get('name').strip().replace(" ", "_")
            st.download_button("Save Contact", data=vcf, file_name=f"{safe_name}.vcf", mime="text/vcard", use_container_width=True)
        with c2:
            if st.button("New Lead", type="secondary", use_container_width=True):
                st.session_state.generated_lead = None
                st.rerun()

def view_pipeline():
    st.markdown("<h2>Pipeline</h2>", unsafe_allow_html=True)
    all_leads = load_leads()
    
    if not all_leads:
        st.info("No leads recorded yet.")
        
    for lead in all_leads:
        with st.expander(f"{lead.get('name')} - {lead.get('product_pitch')}"):
            st.markdown(f"""
                <div style="padding: 10px;">
                    <p><strong>Strategy:</strong> {lead.get('sales_angle')}</p>
                    <p><strong>Next Step:</strong> {lead.get('follow_up')}</p>
                    <p style="font-size: 12px; color: #888;">{lead.get('contact_info')}</p>
                </div>
            """, unsafe_allow_html=True)

def view_analytics():
    st.markdown("<h2>Analytics</h2>", unsafe_allow_html=True)
    all_leads = load_leads()
    if not all_leads:
        st.warning("Not enough data.")
        return
        
    df = pd.DataFrame(all_leads)
    
    st.markdown('<div class="airbnb-card">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    c1.metric("Total Leads", len(all_leads))
    try:
        top = df['product_pitch'].mode()[0]
    except: top = "N/A"
    c2.metric("Top Product", top)
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.caption("Product Distribution")
    if 'product_pitch' in df.columns:
        st.bar_chart(df['product_pitch'].value_counts(), color="#FF385C")

# ==========================================
# 5. MAIN ROUTER
# ==========================================
if not api_key:
    st.error("⚠️ API Key Missing.")
    st.stop()

# Router
if st.session_state.active_tab == "generate":
    view_generate()
elif st.session_state.active_tab == "pipeline":
    view_pipeline()
elif st.session_state.active_tab == "analytics":
    view_analytics()

# Render Floating Nav (Always Last)
render_bottom_nav()
