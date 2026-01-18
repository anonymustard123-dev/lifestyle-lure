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
# 2. AIRBNB-STYLE CSS (Mobile Forced Horizontal)
# ==========================================
st.markdown("""
    <style>
        /* --- RESET & BASICS --- */
        .stApp { background-color: #ffffff; color: #222222; font-family: 'Circular', -apple-system, BlinkMacSystemFont, Roboto, "Helvetica Neue", sans-serif; }
        [data-testid="stHeader"] { display: none; }
        footer {visibility: hidden;}
        
        /* --- TYPOGRAPHY --- */
        h1, h2, h3 { color: #222222 !important; font-weight: 800 !important; letter-spacing: -0.5px; }
        p, label, span, div { color: #717171; }
        
        /* --- AUDIO RECORDER (ROUNDED BOX STYLE) --- */
        [data-testid="stAudioInput"] {
            border-radius: 12px !important; /* Rounded Box, not Pill */
            border: 1px solid #e0e0e0 !important;
            background-color: #f7f7f7 !important; /* Light Grey Background */
            padding: 10px !important;
            box-shadow: none !important;
        }
        
        /* Fix the ugly black audio player inside */
        [data-testid="stAudioInput"] > div > div {
            background-color: #f7f7f7 !important; /* Match container */
            color: #222 !important;
        }
        audio {
            background-color: #f7f7f7 !important;
        }

        /* --- FIXED BOTTOM NAV BAR (FORCED HORIZONTAL) --- */
        .nav-container {
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            background: #ffffff;
            border-top: 1px solid #ebebeb;
            z-index: 999999;
            padding: 10px 0 25px 0; /* Extra padding at bottom for iPhone home bar */
            display: flex;
            justify-content: space-around; /* Distribute evenly */
            align-items: center;
        }

        /* The buttons themselves */
        .nav-btn {
            background: transparent !important;
            border: none !important;
            color: #b0b0b0 !important;
            font-size: 11px !important;
            font-weight: 600 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.5px !important;
            padding: 8px 0 !important;
            cursor: pointer;
            text-align: center;
            flex: 1; /* Grow to fill space */
        }
        
        .nav-btn:hover { color: #FF385C !important; }
        
        /* Active State */
        .nav-active { color: #FF385C !important; }

        /* --- CARDS & UI --- */
        .airbnb-card {
            background: white;
            border-radius: 16px;
            box-shadow: 0 6px 20px rgba(0,0,0,0.06);
            padding: 24px;
            margin-bottom: 24px;
            border: 1px solid #f2f2f2;
        }
        
        .card-title { font-size: 24px; font-weight: 800; color: #222; margin-bottom: 5px; }
        .card-subtitle { font-size: 14px; color: #FF385C; font-weight: 700; text-transform:uppercase; letter-spacing:1px; margin-bottom: 20px; }
        
        /* --- PRIMARY BUTTONS (Salmon) --- */
        div.stButton > button {
            background-color: #FF385C;
            color: white;
            border-radius: 8px;
            padding: 12px 24px;
            font-weight: 600;
            border: none;
            width: 100%;
            box-shadow: 0 4px 12px rgba(255, 56, 92, 0.2);
        }
        div.stButton > button:hover { background-color: #d90b3e; color: white; }
        
        /* --- SECONDARY BUTTONS (Outline) --- */
        button[kind="secondary"] {
            background-color: transparent !important;
            color: #222 !important;
            border: 1px solid #222 !important;
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
# 4. VIEW CONTROLLERS
# ==========================================

def view_generate():
    st.markdown("<br>", unsafe_allow_html=True)
    
    if not st.session_state.generated_lead:
        # Empty State
        st.markdown("""
            <div style="text-align: center; padding: 40px 20px;">
                <h2 style="font-size: 32px; margin-bottom: 8px;">New Lead</h2>
                <p style="font-size: 16px;">Capture intelligence instantly.</p>
            </div>
        """, unsafe_allow_html=True)
        
        # Audio Input (Standard Box Style)
        audio_val = st.audio_input("Record", label_visibility="collapsed")
        
        st.markdown("<p style='text-align:center; font-size:12px; color:#aaa; margin-top:10px;'>TAP MICROPHONE TO RECORD</p>", unsafe_allow_html=True)

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
        # Result Card
        lead = st.session_state.generated_lead
        
        st.markdown(f"""
            <div class="airbnb-card">
                <div class="card-subtitle">Intel Captured</div>
                <div class="card-title">{lead.get('name', 'Unknown Lead')}</div>
                <p style="color:#222; font-size:18px; margin-bottom:20px;">{lead.get('sales_angle')}</p>
                
                <div style="border-top:1px solid #f0f0f0; margin:20px 0;"></div>
                
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:15px; margin-bottom:20px;">
                    <div>
                        <span style="font-size:11px; font-weight:700; text-transform:uppercase;">Contact</span>
                        <div style="color:#222; font-size:15px; font-weight:500;">{lead.get('contact_info')}</div>
                    </div>
                    <div>
                        <span style="font-size:11px; font-weight:700; text-transform:uppercase;">Follow Up</span>
                        <div style="color:#222; font-size:15px; font-weight:500;">{lead.get('follow_up')}</div>
                    </div>
                </div>
                
                <div style="background:#f7f7f7; padding:20px; border-radius:12px; margin-top:10px;">
                    <span style="font-size:11px; font-weight:700; text-transform:uppercase;">Recommendation</span>
                    <div style="color:#222; font-weight:600; font-size:16px; margin-top:4px;">{lead.get('product_pitch')}</div>
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
    st.markdown("<h2 style='padding:20px 0 10px 0;'>Pipeline</h2>", unsafe_allow_html=True)
    all_leads = load_leads()
    
    if not all_leads:
        st.info("No leads recorded yet.")
        
    for lead in all_leads:
        with st.expander(f"{lead.get('name')}"):
            st.markdown(f"""
                <div style="padding:10px;">
                    <p style="color:#222; margin-bottom:5px;"><strong>Strategy:</strong> {lead.get('sales_angle')}</p>
                    <p style="color:#222; margin-bottom:5px;"><strong>Product:</strong> {lead.get('product_pitch')}</p>
                    <p style="font-size:13px; margin-top:10px;">{lead.get('contact_info')}</p>
                </div>
            """, unsafe_allow_html=True)

def view_analytics():
    st.markdown("<h2 style='padding:20px 0 10px 0;'>Analytics</h2>", unsafe_allow_html=True)
    all_leads = load_leads()
    if not all_leads:
        st.warning("No data.")
        return
    
    df = pd.DataFrame(all_leads)
    
    st.markdown('<div class="airbnb-card">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    c1.metric("Total Leads", len(all_leads))
    try: top = df['product_pitch'].mode()[0]
    except: top = "-"
    c2.metric("Top Product", top)
    st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 5. MAIN ROUTER & CUSTOM NAV
# ==========================================
if not api_key:
    st.error("⚠️ API Key Missing.")
    st.stop()

# Content Area
if st.session_state.active_tab == "generate": view_generate()
elif st.session_state.active_tab == "pipeline": view_pipeline()
elif st.session_state.active_tab == "analytics": view_analytics()

# Spacer for nav
st.markdown("<div style='height: 100px;'></div>", unsafe_allow_html=True)

# --- CUSTOM HTML NAVIGATION ---
# This uses Streamlit columns but relies on the CSS 'nav-container' class to force fixed positioning
# We use Python buttons to trigger state changes, but CSS positions them horizontally.
with st.container():
    st.markdown('<div class="nav-container">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    
    # Generate Button
    with c1:
        if st.button("Generate", key="nav_gen", use_container_width=True): 
            st.session_state.active_tab = "generate"
            st.rerun()
            
    # Leads Button
    with c2:
        if st.button("Leads", key="nav_leads", use_container_width=True): 
            st.session_state.active_tab = "pipeline"
            st.rerun()

    # Analytics Button
    with c3:
        if st.button("Analytics", key="nav_an", use_container_width=True): 
            st.session_state.active_tab = "analytics"
            st.rerun()
            
    st.markdown('</div>', unsafe_allow_html=True)
