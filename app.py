import streamlit as st
from google import genai
from google.genai import types
import os
import json
import pandas as pd
from datetime import datetime

# ==========================================
# 1. CONFIG & STATE
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
# 2. AIRBNB-STYLE CSS (Mobile Optimized)
# ==========================================
st.markdown("""
    <style>
        /* --- RESET & BASICS --- */
        .stApp { background-color: #ffffff; color: #222222; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
        [data-testid="stHeader"] { display: none; }
        
        /* --- TYPOGRAPHY --- */
        h1, h2, h3 { color: #222222 !important; font-weight: 800 !important; letter-spacing: -0.5px; }
        p, label, span, div { color: #717171; }
        
        /* --- SLEEK MICROPHONE (Pill Shape) --- */
        [data-testid="stAudioInput"] {
            max-width: 400px !important;
            margin: 0 auto !important; /* Center it */
            border-radius: 50px !important;
            border: 1px solid #e0e0e0 !important;
            background-color: #f7f7f7 !important;
            overflow: hidden !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05) !important;
        }
        [data-testid="stAudioInput"] > div {
            border: none !important;
            background: transparent !important;
        }
        
        /* --- FIXED BOTTOM NAV (The "App" Feel) --- */
        /* This targets the LAST container in the app to force it to the bottom */
        div[data-testid="stVerticalBlock"] > div:last-child {
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-top: 1px solid #ebebeb;
            z-index: 99999;
            padding-bottom: 20px; /* Safe area for iPhone home bar */
            padding-top: 10px;
        }

        /* FORCE HORIZONTAL ROW ON MOBILE */
        div[data-testid="stVerticalBlock"] > div:last-child [data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: row !important; /* Forces side-by-side */
            gap: 0px !important;
        }

        /* FORCE COLUMNS TO SHARE WIDTH EQUALLY */
        div[data-testid="stVerticalBlock"] > div:last-child [data-testid="column"] {
            width: 33.33% !important;
            flex: 1 !important;
            min-width: 0 !important;
        }
        
        /* STYLE THE NAV BUTTONS */
        div[data-testid="stVerticalBlock"] > div:last-child button {
            background-color: transparent !important;
            border: none !important;
            color: #b0b0b0 !important;
            font-size: 11px !important;
            font-weight: 600 !important;
            text-transform: uppercase;
            letter-spacing: 1px;
            padding: 10px 0 !important;
            margin: 0 !important;
            width: 100%;
            box-shadow: none !important;
        }
        
        div[data-testid="stVerticalBlock"] > div:last-child button:hover {
            color: #FF385C !important;
        }
        
        div[data-testid="stVerticalBlock"] > div:last-child button:focus {
            color: #FF385C !important;
        }

        /* --- CARDS & UI --- */
        .airbnb-card {
            background: white;
            border-radius: 16px;
            box-shadow: 0 6px 20px rgba(0,0,0,0.08);
            padding: 24px;
            margin-bottom: 24px;
            border: 1px solid #f0f0f0;
        }
        
        .card-title { font-size: 24px; font-weight: 800; color: #222; margin-bottom: 5px; }
        .card-subtitle { font-size: 16px; color: #FF385C; font-weight: 600; margin-bottom: 20px; }
        
        /* --- PRIMARY BUTTONS (Airbnb Red) --- */
        div.stButton > button {
            background-color: #FF385C;
            color: white;
            border-radius: 8px;
            padding: 12px 24px;
            font-weight: 600;
            border: none;
            width: 100%;
            box-shadow: 0 2px 10px rgba(255, 56, 92, 0.2);
        }
        div.stButton > button:hover {
            background-color: #d90b3e;
            color: white;
        }
        
        /* --- SECONDARY BUTTONS (Outline) --- */
        button[kind="secondary"] {
            background-color: transparent !important;
            color: #222 !important;
            border: 2px solid #222 !important;
            box-shadow: none !important;
        }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. BACKEND LOGIC
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
    Return ONLY raw JSON:
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
# 4. VIEWS
# ==========================================

def view_generate():
    st.markdown("<br>", unsafe_allow_html=True)
    
    if not st.session_state.generated_lead:
        # Initial State
        st.markdown("""
            <div style="text-align: center; padding: 40px 20px;">
                <h2 style="font-size: 32px; margin-bottom: 10px;">New Lead</h2>
                <p style="font-size: 16px;">Capture intelligence instantly.</p>
            </div>
        """, unsafe_allow_html=True)
        
        # Audio Input (Styled by CSS above to be sleek/pill)
        audio_val = st.audio_input("Record", label_visibility="collapsed")
        
        st.markdown("<p style='text-align:center; font-size:12px; color:#aaa; margin-top:10px;'>TAP TO RECORD</p>", unsafe_allow_html=True)

        if audio_val:
            with st.spinner("Processing..."):
                data = process_voice_contact(audio_val.read())
                if isinstance(data, dict) and "error" not in data:
                    save_lead(data)
                    st.session_state.generated_lead = data
                    st.rerun()
                else:
                    st.error(f"Error: {data.get('error')}")

    else:
        # Result State
        lead = st.session_state.generated_lead
        
        st.markdown(f"""
            <div class="airbnb-card">
                <div class="card-subtitle">SUCCESSFULLY CAPTURED</div>
                <div class="card-title">{lead.get('name', 'Unknown Lead')}</div>
                <p style="color:#222; font-size:18px; margin-bottom:20px;">{lead.get('sales_angle')}</p>
                
                <hr style="border:0; border-top:1px solid #eee; margin:20px 0;">
                
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:20px;">
                    <div>
                        <span style="font-size:12px; font-weight:700;">CONTACT</span>
                        <div style="color:#222;">{lead.get('contact_info')}</div>
                    </div>
                    <div>
                        <span style="font-size:12px; font-weight:700;">NEXT STEP</span>
                        <div style="color:#222;">{lead.get('follow_up')}</div>
                    </div>
                </div>
                
                <div style="background:#f7f7f7; padding:15px; border-radius:10px;">
                    <span style="font-size:12px; font-weight:700;">RECOMMENDATION</span>
                    <div style="color:#222; font-weight:600;">{lead.get('product_pitch')}</div>
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
    st.markdown("<h2 style='padding:20px;'>Pipeline</h2>", unsafe_allow_html=True)
    all_leads = load_leads()
    
    if not all_leads:
        st.info("No leads yet.")
        
    for lead in all_leads:
        with st.expander(f"{lead.get('name')}"):
            st.write(f"**Strategy:** {lead.get('sales_angle')}")
            st.write(f"**Product:** {lead.get('product_pitch')}")
            st.caption(f"Contact: {lead.get('contact_info')}")

def view_analytics():
    st.markdown("<h2 style='padding:20px;'>Analytics</h2>", unsafe_allow_html=True)
    all_leads = load_leads()
    if not all_leads:
        st.warning("No data.")
        return
    
    df = pd.DataFrame(all_leads)
    
    st.markdown('<div class="airbnb-card">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    c1.metric("Leads", len(all_leads))
    try: top = df['product_pitch'].mode()[0]
    except: top = "-"
    c2.metric("Top Product", top)
    st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 5. MAIN ROUTER & NAV
# ==========================================
if not api_key:
    st.error("⚠️ API Key Missing.")
    st.stop()

# Content Area
if st.session_state.active_tab == "generate":
    view_generate()
elif st.session_state.active_tab == "pipeline":
    view_pipeline()
elif st.session_state.active_tab == "analytics":
    view_analytics()

# Spacer to prevent content being hidden behind nav
st.markdown("<div style='height: 100px;'></div>", unsafe_allow_html=True)

# NAVIGATION BAR (MUST BE LAST)
# We use a container to group the buttons, and CSS forces them horizontal
with st.container():
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Generate", key="nav_gen"): st.session_state.active_tab = "generate"; st.rerun()
    with c2:
        if st.button("Leads", key="nav_pipe"): st.session_state.active_tab = "pipeline"; st.rerun()
    with c3:
        if st.button("Analytics", key="nav_an"): st.session_state.active_tab = "analytics"; st.rerun()
