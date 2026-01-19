import streamlit as st
from google import genai
from google.genai import types
import os
import json
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
import stripe
import textwrap

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
if 'is_subscribed' not in st.session_state: st.session_state.is_subscribed = False
if 'active_tab' not in st.session_state: st.session_state.active_tab = "omni" 
if 'omni_result' not in st.session_state: st.session_state.omni_result = None 
if 'referral_captured' not in st.session_state: st.session_state.referral_captured = None
if 'user_profile' not in st.session_state: st.session_state.user_profile = None

# --- CAPTURE REFERRAL CODE (STICKY) ---
if not st.session_state.referral_captured:
    try:
        query_params = st.query_params
        if "ref" in query_params:
            ref_val = query_params["ref"]
            if isinstance(ref_val, list):
                st.session_state.referral_captured = ref_val[0]
            else:
                st.session_state.referral_captured = ref_val
    except:
        pass

# ==========================================
# 2. CONNECTIONS (SUPABASE & STRIPE)
# ==========================================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8501")

@st.cache_resource
def init_supabase():
    if SUPABASE_URL and SUPABASE_KEY:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    return None

supabase = init_supabase()

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# ==========================================
# 3. CSS (Native App Feel + Horizontal Mobile Fix)
# ==========================================
st.markdown("""
    <style>
        /* --- 1. LOCK VIEWPORT (Native App Feel) --- */
        html, body, .stApp {
            height: 100vh;
            width: 100vw;
            overflow: hidden !important; /* Disable global scrolling */
            overscroll-behavior: none;   /* Disable bounce effect */
        }
        
        /* --- 2. INTERNAL SCROLLING --- */
        /* This targets the specific container where Streamlit puts content */
        .main .block-container {
            height: calc(100vh - 70px) !important; /* Leave room for bottom nav */
            overflow-y: auto !important;          /* Enable internal scrolling */
            padding-top: 1rem !important;
            padding-bottom: 2rem !important;
            max-width: 100% !important;
        }
        /* Hide Scrollbars for cleaner look */
        ::-webkit-scrollbar { display: none; }
        
        /* --- 3. FORCE HORIZONTAL COLUMNS ON MOBILE --- */
        /* This is the critical fix. It stops Streamlit from stacking columns vertically on mobile. */
        @media (max-width: 640px) {
            div[data-testid="stHorizontalBlock"] {
                flex-direction: row !important; /* Force side-by-side */
                flex-wrap: nowrap !important;   /* Prevent wrapping */
                gap: 5px !important;
            }
            div[data-testid="column"] {
                flex: 1 !important;             /* Make them equal width */
                min-width: 0 !important;        /* Allow shrinking below content size */
                width: auto !important;
            }
        }

        /* --- 4. HIDE STREAMLIT UI --- */
        [data-testid="stHeader"] { display: none; }
        footer {visibility: hidden;}
        
        /* --- 5. FIXED BOTTOM NAV BAR --- */
        .nav-fixed-container {
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            height: 70px;
            background: #ffffff;
            border-top: 1px solid #f2f2f2;
            z-index: 999999;
            padding: 10px 0;
            display: flex;
            align-items: center;
        }

        /* --- STYLES --- */
        button[kind="primary"] {
            background-color: #FF385C !important;
            color: white !important;
            border-radius: 12px !important;
            border: none !important;
            height: 50px !important;
            width: 100% !important;
        }
        
        /* Nav Button Styles */
        .nav-btn button {
            background-color: transparent !important;
            color: #b0b0b0 !important;
            border: none !important;
            font-size: 11px !important;
            font-weight: 600 !important;
            text-transform: uppercase !important;
            box-shadow: none !important;
            height: 100% !important;
            padding: 0 !important;
        }
        .nav-active button {
            color: #FF385C !important;
            background-color: transparent !important; /* Removed pink bg for cleaner look */
        }
        
        /* Executive Card & Typography */
        h1, h2, h3 { color: #222 !important; font-weight: 800 !important; }
        .exec-card { background: white; border: 1px solid #e0e0e0; border-radius: 16px; margin-bottom: 24px; overflow: hidden; }
        .exec-header { background: #222; color: white; padding: 20px; }
        .exec-title { font-size: 22px; font-weight: 700; color: white !important; margin: 0; }
        .exec-badge { background: #FF385C; color: white; font-size: 10px; font-weight: 800; padding: 4px 8px; border-radius: 4px; text-transform: uppercase; margin-bottom: 8px; display:inline-block; }
        .exec-body { padding: 20px; }
        .briefing-box { background-color: #F7F7F7; border-left: 4px solid #FF385C; padding: 15px; border-radius: 0 8px 8px 0; margin-bottom: 20px; }
        .stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px; }
        .stat-label { font-size: 10px; font-weight: 700; text-transform: uppercase; color: #888; }
        .stat-value { font-size: 14px; font-weight: 600; color: #222 !important; margin-top: 2px; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 4. DATA & LOGIC HELPERS
# ==========================================
def fetch_user_profile(user_id):
    try:
        response = supabase.table("profiles").select("*").eq("id", user_id).execute()
        if response.data: return response.data[0]
    except: return None

def check_subscription_status(email):
    if not STRIPE_SECRET_KEY: return True 
    try:
        customers = stripe.Customer.list(email=email).data
        if not customers: return False
        subscriptions = stripe.Subscription.list(customer=customers[0].id, status='active').data
        return True
    except: return False

def create_checkout_session(email, user_id):
    try:
        customers = stripe.Customer.list(email=email).data
        customer_id = customers[0].id if customers else stripe.Customer.create(email=email).id
        
        profile = fetch_user_profile(user_id)
        metadata = {'referred_by': profile.get('referred_by')} if profile and profile.get('referred_by') else {}

        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            line_items=[{'price': STRIPE_PRICE_ID, 'quantity': 1}],
            mode='subscription',
            success_url=f"{APP_BASE_URL}?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{APP_BASE_URL}",
            metadata=metadata
        )
        return session.url
    except: return None

# ==========================================
# 5. OMNI-TOOL BACKEND
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

def load_leads_summary():
    if not st.session_state.user or not supabase: return []
    try:
        response = supabase.table("leads").select("id, name, background, contact_info").eq("user_id", st.session_state.user.id).execute()
        return response.data
    except: return []

def process_omni_voice(audio_bytes, existing_leads_context):
    leads_json = json.dumps(existing_leads_context)
    prompt = f"""
    You are 'The Closer', an expert Executive Assistant. 
    Here is the user's Rolodex (Existing Leads): {leads_json}

    User Audio Provided. Listen carefully.
    
    YOUR TASK:
    1. MATCHING: Is the user talking about a person in the Rolodex?
    2. INTENT: 
       - describing a NEW person -> "CREATE"
       - adding info about EXISTING person -> "UPDATE"
       - asking a question -> "QUERY"

    RETURN ONLY RAW JSON:
    {{
        "action": "CREATE" | "UPDATE" | "QUERY",
        "match_id": (Integer ID if matches a lead, else null),
        "lead_data": {{
            "name": "Full Name",
            "contact_info": "Phone/Email",
            "background": "The full context/history",
            "sales_angle": "Current Strategy",
            "product_pitch": "Recommended Product",
            "follow_up": "Next Step Timeframe"
        }},
        "executive_brief": "A 2-sentence briefing for the user.",
        "confidence": "High/Low"
    }}
    """
    try:
        response = client.models.generate_content(
            model=TEXT_MODEL_ID,
            contents=[types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"), prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(clean_json_string(response.text))
    except Exception as e: 
        return {"error": str(e)}

def save_new_lead(lead_data):
    if not st.session_state.user: return "Not logged in"
    lead_data['user_id'] = st.session_state.user.id
    lead_data['created_at'] = datetime.now().isoformat()
    try: 
        supabase.table("leads").insert(lead_data).execute()
        return None
    except Exception as e: return str(e)

def update_existing_lead(lead_id, new_data, old_background=""):
    if not st.session_state.user: return "Not logged in"
    timestamp = datetime.now().strftime("%Y-%m-%d")
    final_data = {
        "sales_angle": new_data.get('sales_angle'),
        "product_pitch": new_data.get('product_pitch'),
        "follow_up": new_data.get('follow_up'),
        "contact_info": new_data.get('contact_info'),
        "background": new_data.get('background') 
    }
    try:
        supabase.table("leads").update(final_data).eq("id", lead_id).execute()
        return None
    except Exception as e: return str(e)

def create_vcard(data):
    vcard = [
        "BEGIN:VCARD", "VERSION:3.0", 
        f"FN:{data.get('name', 'Lead')}", 
        f"TEL;TYPE=CELL:{data.get('contact_info', '')}", 
        f"NOTE:{data.get('executive_brief','')}", 
        "END:VCARD"
    ]
    return "\n".join(vcard)

# ==========================================
# 6. APP VIEWS
# ==========================================

def render_executive_card(data):
    lead = data.get('lead_data', {})
    action = data.get('action', 'QUERY')
    brief = data.get('executive_brief', 'No briefing available.')
    
    badge_text = "INTELLIGENCE REPORT"
    if action == "CREATE": badge_text = "NEW ASSET"
    elif action == "UPDATE": badge_text = "FILE UPDATED"
    
    # We strip newlines to prevent markdown code block issues
    html_content = f"""
        <div class="exec-card">
            <div class="exec-header">
                <div class="exec-badge">{badge_text}</div>
                <div class="exec-title">{lead.get('name') or 'Rolodex Query'}</div>
            </div>
            <div class="exec-body">
                <div class="briefing-box">
                    <div style="font-size:10px; font-weight:700; color:#FF385C; margin-bottom:4px;">MORNING BRIEFING</div>
                    <div style="font-size:15px; font-weight:500; color:#222; line-height:1.4;">{brief}</div>
                </div>
                
                <div class="stat-grid">
                    <div>
                        <div class="stat-label">Strategy</div>
                        <div class="stat-value">{lead.get('sales_angle') or '-'}</div>
                    </div>
                    <div>
                        <div class="stat-label">Next Step</div>
                        <div class="stat-value">{lead.get('follow_up') or '-'}</div>
                    </div>
                    <div>
                        <div class="stat-label">Product Fit</div>
                        <div class="stat-value">{lead.get('product_pitch') or '-'}</div>
                    </div>
                    <div>
                        <div class="stat-label">Contact</div>
                        <div class="stat-value">{lead.get('contact_info') or '-'}</div>
                    </div>
                </div>
                
                <div style="margin-top:15px; border-top:1px solid #eee; padding-top:15px;">
                    <div class="stat-label">Background / Notes</div>
                    <p style="font-size:13px; margin-top:5px; line-height:1.5; color:#555;">{lead.get('background') or '-'}</p>
                </div>
            </div>
        </div>
    """.replace("\n", " ")
    
    st.markdown(html_content, unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)
    with c1:
        if lead.get('name'):
            vcf = create_vcard(data)
            safe_name = lead.get('name').strip().replace(" ", "_")
            st.download_button("Export Contact", data=vcf, file_name=f"{safe_name}.vcf", mime="text/vcard", use_container_width=True, type="primary")
    with c2:
        if st.button("Close File", type="secondary", use_container_width=True):
            st.session_state.omni_result = None
            st.rerun()

def view_omni():
    # Header
    c1, c2 = st.columns([8, 1]) 
    with c1: st.markdown("<h2 style='margin-top:0;'>Omni-Assistant</h2>", unsafe_allow_html=True)
    with c2:
        with st.popover("👤"):
            if st.button("Sign Out"):
                supabase.auth.sign_out()
                st.session_state.user = None
                st.rerun()

    if not st.session_state.omni_result:
        st.markdown("""
            <div style="text-align: center; padding: 60px 20px;">
                <div style="font-size: 60px; margin-bottom: 10px;">🎙️</div>
                <p style="font-size: 18px; color: #222; font-weight:600;">Tap to Speak</p>
                <p style="font-size: 14px; color: #888;">"Create a lead for John..."<br>"Update Sarah..."</p>
            </div>
        """, unsafe_allow_html=True)
        
        audio_val = st.audio_input("OmniInput", label_visibility="collapsed")
        
        if audio_val:
            with st.spinner("Processing..."):
                existing_leads = load_leads_summary()
                result = process_omni_voice(audio_val.read(), existing_leads)
                
                if "error" in result:
                    st.error(result['error'])
                else:
                    action = result.get('action')
                    lead_data = result.get('lead_data', {})
                    if action == "CREATE": save_new_lead(lead_data)
                    elif action == "UPDATE" and result.get('match_id'): update_existing_lead(result['match_id'], lead_data)
                    st.session_state.omni_result = result
                    st.rerun()
    else:
        render_executive_card(st.session_state.omni_result)

def view_pipeline():
    st.markdown("<h2>Rolodex</h2>", unsafe_allow_html=True)
    if not st.session_state.user: return
    leads = supabase.table("leads").select("*").eq("user_id", st.session_state.user.id).order("created_at", desc=True).execute().data
    if not leads: st.info("Rolodex is empty.")
    for lead in leads:
        with st.expander(f"{lead.get('name', 'Unknown')}"):
            st.caption(f"Strategy: {lead.get('sales_angle', '-')}")
            st.write(lead.get('background'))

def view_analytics():
    st.markdown("<h2>Analytics</h2>", unsafe_allow_html=True)
    if not st.session_state.user: return
    leads = supabase.table("leads").select("*").eq("user_id", st.session_state.user.id).execute().data
    if not leads: st.warning("No data."); return
    df = pd.DataFrame(leads)
    st.metric("Total Network", len(leads))
    st.bar_chart(df['product_pitch'].value_counts())

# ==========================================
# 7. MAIN ROUTER
# ==========================================
if not st.session_state.user:
    st.markdown("<h1 style='text-align: center; margin-top: 50px;'>The Closer</h1>", unsafe_allow_html=True)
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    c1, c2 = st.columns(2)
    if c1.button("Log In", type="primary", use_container_width=True):
        try:
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            st.session_state.user = res.user
            st.session_state.is_subscribed = check_subscription_status(res.user.email)
            st.rerun()
        except Exception as e: st.error(str(e))
    if c2.button("Sign Up", type="secondary", use_container_width=True):
        try:
            meta = {"referred_by": st.session_state.referral_captured} if st.session_state.referral_captured else {}
            res = supabase.auth.sign_up({"email": email, "password": password, "options": {"data": meta}})
            if res.user: st.success("Account created! Log in."); 
        except Exception as e: st.error(str(e))
    st.stop()

if not st.session_state.is_subscribed:
    if "session_id" in st.query_params:
        st.session_state.is_subscribed = check_subscription_status(st.session_state.user.email)
        if st.session_state.is_subscribed: st.rerun()
    st.markdown("<br><h2 style='text-align:center'>Subscribe</h2>", unsafe_allow_html=True)
    if st.button("Subscribe ($15/mo)", type="primary"):
        url = create_checkout_session(st.session_state.user.email, st.session_state.user.id)
        if url: st.link_button("Go to Checkout", url, type="primary")
    st.stop()

# --- CONTENT ---
if st.session_state.active_tab == "omni": view_omni()
elif st.session_state.active_tab == "pipeline": view_pipeline()
elif st.session_state.active_tab == "analytics": view_analytics()

st.markdown("<div style='height: 80px;'></div>", unsafe_allow_html=True)

# --- NAVIGATION ---
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
    nav_btn(c1, "Assistant", "omni")
    nav_btn(c2, "Rolodex", "pipeline")
    nav_btn(c3, "Analytics", "analytics")
    st.markdown('</div>', unsafe_allow_html=True)
