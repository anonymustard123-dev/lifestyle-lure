import streamlit as st
from google import genai
from google.genai import types
import os
import json
import pandas as pd
from datetime import datetime
from supabase import create_client, Client

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
if 'user' not in st.session_state: st.session_state.user = None
if 'active_tab' not in st.session_state: st.session_state.active_tab = "generate"
if 'generated_lead' not in st.session_state: st.session_state.generated_lead = None

# ==========================================
# 2. SUPABASE CONNECTION
# ==========================================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        st.error(f"Supabase Connection Error: {e}")

# ==========================================
# 3. AIRBNB-STYLE CSS (Refined)
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
        
        /* --- INPUT FIELD FIXES --- */
        div[data-baseweb="input"], div[data-baseweb="base-input"] {
            background-color: #ffffff !important;
            border: 1px solid #e0e0e0 !important;
            border-radius: 12px !important;
        }
        input.st-bd, input.st-bc, input {
            background-color: #ffffff !important;
            color: #222222 !important;
            -webkit-text-fill-color: #222222 !important;
            caret-color: #FF385C !important;
        }
        
        /* --- HEADER PROFILE BUTTON --- */
        /* Style the popover button to look like a profile circle */
        [data-testid="stPopover"] > button {
            border-radius: 50% !important;
            width: 40px !important;
            height: 40px !important;
            border: 1px solid #dddddd !important;
            background: white !important;
            color: #717171 !important;
            box-shadow: none !important;
            padding: 0 !important;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        [data-testid="stPopover"] > button:hover {
            box-shadow: 0 2px 8px rgba(0,0,0,0.1) !important;
            color: #222 !important;
        }

        /* --- MICROPHONE FIX --- */
        [data-testid="stAudioInput"] {
            border-radius: 16px !important;
            border: 1px solid #e0e0e0 !important;
            background-color: #f7f7f7 !important;
            padding: 10px !important;
            box-shadow: none !important;
            color: #222 !important;
        }
        [data-testid="stAudioInput"] * {
            background-color: transparent !important;
            color: #222 !important;
        }
        [data-testid="stAudioInput"] svg {
            fill: #FF385C !important;
        }

        /* --- FIXED BOTTOM NAV BAR --- */
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
            .nav-fixed-container [data-testid="stHorizontalBlock"] {
                flex-direction: row !important;
                flex-wrap: nowrap !important;
                gap: 5px !important;
            }
            .nav-fixed-container [data-testid="column"] {
                width: 33.33% !important;
                flex: 1 1 auto !important;
                min-width: 0 !important;
            }
        }

        /* --- NAV BUTTONS --- */
        .nav-btn button {
            background-color: transparent !important;
            color: #b0b0b0 !important;
            border: none !important;
            font-size: 10px !important;
            font-weight: 600 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.5px !important;
            padding: 10px 0 !important;
            box-shadow: none !important;
            height: auto !important;
        }
        .nav-active button {
            color: #FF385C !important;
            background-color: #FFF0F3 !important;
            border-radius: 20px !important;
        }

        /* --- PRIMARY BUTTONS --- */
        button[kind="primary"] {
            background-color: #FF385C !important;
            color: white !important;
            border-radius: 12px !important;
            padding: 12px 24px !important;
            font-weight: 600 !important;
            border: none !important;
            height: 50px !important;
            width: 100% !important;
            box-shadow: 0 4px 12px rgba(255, 56, 92, 0.2) !important;
        }
        button[kind="primary"]:hover {
            background-color: #d90b3e !important;
        }

        /* --- SECONDARY BUTTONS --- */
        button[kind="secondary"] {
            background-color: transparent !important;
            color: #222 !important;
            border: 1px solid #e0e0e0 !important;
            box-shadow: none !important;
            border-radius: 12px !important;
            height: 50px !important;
        }

        /* --- CARDS --- */
        .airbnb-card {
            background: white;
            border-radius: 20px;
            box-shadow: 0 6px 20px rgba(0,0,0,0.06);
            padding: 24px;
            margin-bottom: 24px;
            border: 1px solid #f2f2f2;
        }
        .card-title { font-size: 24px; font-weight: 800; color: #222; margin-bottom: 5px; }
        .card-subtitle { font-size: 13px; color: #FF385C; font-weight: 700; text-transform:uppercase; letter-spacing:1px; margin-bottom: 20px; }
        
        /* --- TABS --- */
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
            background-color: #f7f7f7;
            padding: 5px;
            border-radius: 12px;
            border: none;
        }
        .stTabs [data-baseweb="tab"] {
            background-color: transparent;
            border-radius: 8px;
            color: #717171;
            font-weight: 600;
            border: none;
            flex: 1;
            text-align: center;
        }
        .stTabs [data-baseweb="tab"][aria-selected="true"] {
            background-color: white;
            color: #222;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 4. BACKEND LOGIC (AI & DATA)
# ==========================================
api_key = os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None
TEXT_MODEL_ID = "gemini-2.0-flash"

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
# 5. DATA MANAGER
# ==========================================
def save_lead(lead_data):
    if not st.session_state.user: return "Not logged in"
    lead_data['user_id'] = st.session_state.user.id
    lead_data['created_at'] = datetime.now().isoformat()
    if supabase:
        try: supabase.table("leads").insert(lead_data).execute(); return None
        except Exception as e: return str(e)
    else:
        DB_FILE = "leads_db.json"
        leads = []
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r") as f: leads = json.load(f)
        leads.insert(0, lead_data)
        with open(DB_FILE, "w") as f: json.dump(leads, f)
        return None

def load_leads():
    if not st.session_state.user: return []
    if supabase:
        try:
            response = supabase.table("leads").select("*").eq("user_id", st.session_state.user.id).order("created_at", desc=True).execute()
            return response.data
        except: return []
    else:
        DB_FILE = "leads_db.json"
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r") as f: return json.load(f)
        return []

# ==========================================
# 6. LOGIN SCREEN
# ==========================================
def login_screen():
    st.markdown("<h1 style='text-align: center; margin-bottom: 30px;'>The Closer</h1>", unsafe_allow_html=True)
    tab_login, tab_signup = st.tabs(["Log In", "Sign Up"])
    
    with tab_login:
        st.markdown("<br>", unsafe_allow_html=True)
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pass")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Log In", type="primary", use_container_width=True):
            if not supabase:
                st.session_state.user = type('obj', (object,), {'id': 'demo_user', 'email': email})
                st.rerun()
            else:
                try:
                    res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    st.session_state.user = res.user
                    st.rerun()
                except Exception as e: st.error(f"Login failed: {e}")

    with tab_signup:
        st.markdown("<br>", unsafe_allow_html=True)
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password", type="password", key="signup_pass")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Create Account", type="primary", use_container_width=True):
            if supabase:
                try:
                    res = supabase.auth.sign_up({"email": email, "password": password})
                    st.success("Account created! Check your email.")
                except Exception as e: st.error(f"Signup failed: {e}")
            else: st.warning("Database not connected.")

# ==========================================
# 7. MAIN APP ROUTER
# ==========================================
if not st.session_state.user:
    login_screen()
    st.stop()

# --- HEADER (PROFILE & LOGOUT) ---
def render_header():
    # Use 3 columns to push profile to far right
    c1, c2, c3 = st.columns([1, 4, 1])
    with c3:
        # Profile Popover (Icon Button)
        with st.popover("👤", help="Profile"):
            st.markdown(f"<div style='text-align:center; margin-bottom:10px; font-weight:600;'>{st.session_state.user.email}</div>", unsafe_allow_html=True)
            if st.button("Payments", use_container_width=True):
                st.info("Stripe integration coming soon.")
            
            st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)
            
            if st.button("Sign Out", type="primary", use_container_width=True):
                if supabase: supabase.auth.sign_out()
                st.session_state.user = None
                st.rerun()

# --- APP VIEWS ---
def view_generate():
    render_header()
    
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
                    err = save_lead(data)
                    if err:
                        st.error(f"Database Error: {err}")
                        st.info("Ensure you have run the RLS Policy SQL in Supabase.")
                    else:
                        st.session_state.generated_lead = data
                        st.rerun()
                else: st.error(f"Error: {data.get('error')}")
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
            vcf = create_vcard(lead)
            safe_name = lead.get('name').strip().replace(" ", "_")
            st.download_button("Save Contact", data=vcf, file_name=f"{safe_name}.vcf", mime="text/vcard", use_container_width=True, type="primary")
        with c2:
            if st.button("New Lead", type="secondary", use_container_width=True):
                st.session_state.generated_lead = None
                st.rerun()

def view_pipeline():
    render_header()
    st.markdown("<h2 style='padding:0 0 10px 0;'>Pipeline</h2>", unsafe_allow_html=True)
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
    render_header()
    st.markdown("<h2 style='padding:0 0 10px 0;'>Analytics</h2>", unsafe_allow_html=True)
    all_leads = load_leads()
    if not all_leads: st.warning("No data."); return
    df = pd.DataFrame(all_leads)
    st.markdown('<div class="airbnb-card">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    c1.metric("Total Leads", len(all_leads))
    try: top = df['product_pitch'].mode()[0]
    except: top = "-"
    c2.metric("Top Product", top)
    st.markdown('</div>', unsafe_allow_html=True)

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
            cls = "nav-active" if st.session_state.active_tab == target else "nav-btn"
            st.markdown(f'<div class="{cls}">', unsafe_allow_html=True)
            if st.button(label, key=f"nav_{target}", use_container_width=True):
                st.session_state.active_tab = target
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
    nav_btn(c1, "Generate", "generate")
    nav_btn(c2, "Leads", "pipeline")
    nav_btn(c3, "Analytics", "analytics")
    st.markdown('</div>', unsafe_allow_html=True)
