import streamlit as st
from google import genai
from google.genai import types
from supabase import create_client, Client
import os
import json
import pandas as pd
from datetime import datetime

# ==========================================
# 1. CONFIG & CSS
# ==========================================
st.set_page_config(
    page_title="The Closer", 
    page_icon="🎙️", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Initialize Session State
if 'user' not in st.session_state: st.session_state.user = None
if 'active_tab' not in st.session_state: st.session_state.active_tab = "generate"
if 'generated_lead' not in st.session_state: st.session_state.generated_lead = None
if 'auth_mode' not in st.session_state: st.session_state.auth_mode = "login" # login vs signup

# --- AIRBNB STYLE CSS ---
st.markdown("""
    <style>
        /* BASE & TYPOGRAPHY */
        .stApp { background-color: #ffffff; color: #222222; font-family: 'Circular', -apple-system, BlinkMacSystemFont, Roboto, sans-serif; }
        [data-testid="stHeader"] { display: none; }
        footer {visibility: hidden;}
        h1, h2, h3 { color: #222222 !important; font-weight: 800 !important; letter-spacing: -0.5px; }
        
        /* MICROPHONE */
        [data-testid="stAudioInput"] {
            border-radius: 16px !important;
            border: 1px solid #e0e0e0 !important;
            background-color: #f7f7f7 !important;
            padding: 10px !important;
            box-shadow: none !important;
        }
        [data-testid="stAudioInput"] * { background-color: transparent !important; }
        [data-testid="stAudioInput"] svg { fill: #FF385C !important; }

        /* FIXED NAV BAR */
        .nav-fixed-container {
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            background: #ffffff;
            border-top: 1px solid #f2f2f2;
            z-index: 999999;
            padding: 10px 0 20px 0;
            box-shadow: 0 -2px 10px rgba(0,0,0,0.02);
        }
        
        @media (max-width: 640px) {
            .nav-fixed-container [data-testid="stHorizontalBlock"] { flex-direction: row !important; gap: 5px !important; }
            .nav-fixed-container [data-testid="column"] { width: 33.33% !important; min-width: 0 !important; }
        }

        /* BUTTONS */
        .nav-btn button {
            background-color: transparent !important;
            color: #b0b0b0 !important;
            border: none !important;
            font-size: 10px !important;
            font-weight: 600 !important;
            text-transform: uppercase !important;
            height: auto !important;
            padding: 10px 0 !important;
        }
        .nav-active button {
            color: #FF385C !important;
            background-color: #FFF0F3 !important;
            border-radius: 20px !important;
        }
        .primary-btn button {
            background-color: #FF385C !important;
            color: white !important;
            border-radius: 12px !important;
            font-weight: 600 !important;
            border: none !important;
            height: 50px !important;
        }
        
        /* AUTH CARDS */
        .auth-card {
            max-width: 400px;
            margin: 50px auto;
            padding: 40px;
            border: 1px solid #e0e0e0;
            border-radius: 24px;
            box-shadow: 0 6px 20px rgba(0,0,0,0.08);
            text-align: center;
        }
        
        /* INPUT FIELDS */
        .stTextInput input {
            border-radius: 12px !important;
            padding: 12px !important;
            border: 1px solid #b0b0b0 !important;
        }
        
        /* DOSSIER CARD */
        .airbnb-card {
            background: white;
            border-radius: 20px;
            box-shadow: 0 6px 20px rgba(0,0,0,0.06);
            padding: 24px;
            border: 1px solid #f2f2f2;
            margin-bottom: 20px;
        }
        .card-title { font-size: 24px; font-weight: 800; color: #222; margin-bottom: 5px; }
        .card-subtitle { font-size: 13px; color: #FF385C; font-weight: 700; text-transform:uppercase; letter-spacing:1px; margin-bottom: 20px; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. SUPABASE CONNECTION
# ==========================================
# Get these from Railway Variables or .env file
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("⚠️ Supabase Credentials Missing. Check Environment Variables.")
    st.stop()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
client = genai.Client(api_key=GOOGLE_API_KEY) if GOOGLE_API_KEY else None
TEXT_MODEL_ID = "gemini-2.0-flash"

# ==========================================
# 3. AUTHENTICATION LOGIC
# ==========================================
def render_auth():
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    # Toggle Login/Signup
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Log In", type="primary" if st.session_state.auth_mode == "login" else "secondary", use_container_width=True):
            st.session_state.auth_mode = "login"
            st.rerun()
    with col2:
        if st.button("Sign Up", type="primary" if st.session_state.auth_mode == "signup" else "secondary", use_container_width=True):
            st.session_state.auth_mode = "signup"
            st.rerun()

    st.markdown('<div class="auth-card">', unsafe_allow_html=True)
    st.markdown(f"<h2>{'Welcome Back' if st.session_state.auth_mode == 'login' else 'Join the Empire'}</h2>", unsafe_allow_html=True)
    
    email = st.text_input("Email", key="auth_email")
    password = st.text_input("Password", type="password", key="auth_pass")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.session_state.auth_mode == "login":
        if st.button("Log In", use_container_width=True):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.user = res.user
                st.rerun()
            except Exception as e:
                st.error(f"Login Failed: {str(e)}")
    else:
        if st.button("Create Account", use_container_width=True):
            try:
                res = supabase.auth.sign_up({"email": email, "password": password})
                st.success("Account created! Please check your email to confirm, then log in.")
                st.session_state.auth_mode = "login"
            except Exception as e:
                st.error(f"Signup Failed: {str(e)}")
                
    st.markdown('</div>', unsafe_allow_html=True)

# IF NOT LOGGED IN, STOP HERE
if not st.session_state.user:
    render_auth()
    st.stop()

# ==========================================
# 4. DATA FUNCTIONS (Now Cloud-Native)
# ==========================================
def load_leads():
    """Fetches leads belonging to the logged-in user."""
    try:
        user_id = st.session_state.user.id
        response = supabase.table("leads").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        return response.data
    except Exception as e:
        st.error(f"Sync Error: {e}")
        return []

def save_lead(lead_data):
    """Saves lead to Supabase with User ID."""
    try:
        user_id = st.session_state.user.id
        payload = {
            "user_id": user_id,
            "name": lead_data.get('name'),
            "contact_info": lead_data.get('contact_info'),
            "background": lead_data.get('background'),
            "sales_angle": lead_data.get('sales_angle'),
            "product_pitch": lead_data.get('product_pitch'),
            "follow_up": lead_data.get('follow_up')
        }
        supabase.table("leads").insert(payload).execute()
        return True
    except Exception as e:
        st.error(f"Save Failed: {e}")
        return False

# ==========================================
# 5. AI FUNCTIONS
# ==========================================
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
# 6. APP VIEWS
# ==========================================
def view_generate():
    st.markdown(f"<div style='text-align:right; font-size:12px; color:#ccc;'>Logged in as {st.session_state.user.email}</div>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    if not st.session_state.generated_lead:
        st.markdown("""
            <div style="text-align: center; padding: 40px 20px;">
                <h2 style="font-size: 32px; margin-bottom: 8px;">New Lead</h2>
                <p style="font-size: 16px;">Capture intelligence instantly.</p>
            </div>
        """, unsafe_allow_html=True)
        
        audio_val = st.audio_input("Record", label_visibility="collapsed")
        st.markdown("<p style='text-align:center; font-size:11px; color:#bbb; margin-top:10px; letter-spacing:1px;'>TAP MICROPHONE TO RECORD</p>", unsafe_allow_html=True)

        if audio_val:
            with st.spinner("Processing..."):
                data = process_voice_contact(audio_val.read())
                if isinstance(data, dict) and "error" not in data:
                    save_lead(data) # Saves to cloud now
                    st.session_state.generated_lead = data
                    st.rerun()
                else:
                    st.error(f"Error: {data.get('error')}")
    else:
        lead = st.session_state.generated_lead
        st.markdown(f"""
            <div class="airbnb-card">
                <div class="card-subtitle">Intel Captured</div>
                <div class="card-title">{lead.get('name', 'Unknown Lead')}</div>
                <p style="color:#222; font-size:18px; margin-bottom:20px;">{lead.get('sales_angle')}</p>
                <div style="border-top:1px solid #f0f0f0; margin:20px 0;"></div>
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:15px; margin-bottom:20px;">
                    <div><span style="font-size:11px; font-weight:700; text-transform:uppercase;">Contact</span><div style="color:#222; font-size:15px; font-weight:500;">{lead.get('contact_info')}</div></div>
                    <div><span style="font-size:11px; font-weight:700; text-transform:uppercase;">Follow Up</span><div style="color:#222; font-size:15px; font-weight:500;">{lead.get('follow_up')}</div></div>
                </div>
                <div style="background:#f7f7f7; padding:20px; border-radius:12px; margin-top:10px;">
                    <span style="font-size:11px; font-weight:700; text-transform:uppercase;">Recommendation</span>
                    <div style="color:#222; font-weight:600; font-size:16px; margin-top:4px;">{lead.get('product_pitch')}</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown('<div class="primary-btn">', unsafe_allow_html=True)
            vcf = create_vcard(lead)
            safe_name = lead.get('name').strip().replace(" ", "_")
            st.download_button("Save Contact", data=vcf, file_name=f"{safe_name}.vcf", mime="text/vcard", use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
        with c2:
            if st.button("New Lead", use_container_width=True):
                st.session_state.generated_lead = None
                st.rerun()

def view_pipeline():
    st.markdown("<h2 style='padding:20px 0 10px 0;'>Pipeline</h2>", unsafe_allow_html=True)
    all_leads = load_leads()
    if not all_leads: st.info("No leads recorded yet.")
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
    
    # Logout Button (Top Right of Analytics)
    if st.button("Log Out", key="logout_btn"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.rerun()
        
    if not all_leads: st.warning("No data."); return
    df = pd.DataFrame(all_leads)
    st.markdown('<div class="airbnb-card">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    c1.metric("Total Leads", len(all_leads))
    try: top = df['product_pitch'].mode()[0]
    except: top = "-"
    c2.metric("Top Product", top)
    st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 7. MAIN ROUTER
# ==========================================
if st.session_state.active_tab == "generate": view_generate()
elif st.session_state.active_tab == "pipeline": view_pipeline()
elif st.session_state.active_tab == "analytics": view_analytics()

st.markdown("<div style='height: 100px;'></div>", unsafe_allow_html=True)

# --- NAVIGATION BAR ---
with st.container():
    st.markdown('<div class="nav-fixed-container">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    def nav_btn(col, label, target):
        with col:
            is_active = st.session_state.active_tab == target
            cls = "nav-active" if is_active else "nav-btn"
            st.markdown(f'<div class="{cls}">', unsafe_allow_html=True)
            if st.button(label, key=f"nav_{target}", use_container_width=True):
                st.session_state.active_tab = target
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
    nav_btn(c1, "Generate", "generate")
    nav_btn(c2, "Leads", "pipeline")
    nav_btn(c3, "Analytics", "analytics")
    st.markdown('</div>', unsafe_allow_html=True)
