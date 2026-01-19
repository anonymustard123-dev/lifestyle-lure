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
# 3. CSS (AIRBNB DESIGN SYSTEM + NATIVE FEEL)
# ==========================================
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700;900&display=swap');

        /* --- 1. GLOBAL RESET & TYPOGRAPHY --- */
        html, body, .stApp {
            font-family: 'Circular', -apple-system, BlinkMacSystemFont, Roboto, "Helvetica Neue", sans-serif;
            background-color: #FFFFFF !important;
            color: #222222;
            height: 100vh;
            width: 100vw;
            margin: 0;
            padding: 0;
            overflow: hidden !important;
            overscroll-behavior: none;
            position: fixed;
            top: 0;
            left: 0;
            -webkit-user-select: none;
            user-select: none;
            -webkit-tap-highlight-color: transparent;
        }

        h1, h2, h3 {
            font-weight: 800 !important;
            color: #222222 !important;
            letter-spacing: -0.5px;
        }

        p, label, span, div {
            color: #717171;
        }

        /* Hide Default Streamlit Chrome */
        [data-testid="stHeader"], footer { display: none !important; }

        /* --- 2. SCROLLABLE CONTENT AREA --- */
        .main .block-container {
            height: calc(100vh - 80px); /* Leave room for bottom nav */
            overflow-y: auto !important;
            overflow-x: hidden;
            padding-top: max(env(safe-area-inset-top), 20px) !important;
            padding-bottom: 100px !important;
            padding-left: 20px !important;
            padding-right: 20px !important;
            -webkit-overflow-scrolling: touch;
        }

        /* --- 3. AIRBNB CARDS --- */
        .airbnb-card {
            background-color: #FFFFFF;
            border-radius: 16px;
            box-shadow: 0 6px 16px rgba(0,0,0,0.08);
            border: 1px solid #dddddd;
            padding: 24px;
            margin-bottom: 24px;
        }
        
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 16px;
        }

        .status-badge {
            background-color: #FF385C;
            color: white;
            font-size: 10px;
            font-weight: 800;
            padding: 6px 10px;
            border-radius: 8px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .card-title {
            font-size: 22px;
            font-weight: 800;
            color: #222222;
            margin: 10px 0 5px 0;
        }

        /* --- 4. BUTTONS --- */
        /* Primary (Rausch Pink) */
        button[kind="primary"] {
            background-color: #FF385C !important;
            color: white !important;
            border: none !important;
            border-radius: 12px !important;
            padding: 14px 24px !important;
            font-weight: 600 !important;
            font-size: 16px !important;
            height: auto !important;
            box-shadow: none !important;
            transition: transform 0.1s ease;
        }
        button[kind="primary"]:active {
            transform: scale(0.98);
        }

        /* Secondary (Outline) */
        button[kind="secondary"] {
            background-color: transparent !important;
            color: #222222 !important;
            border: 1px solid #222222 !important;
            border-radius: 12px !important;
            font-weight: 600 !important;
            height: auto !important;
        }

        /* --- 5. INPUTS --- */
        /* Text Inputs */
        div[data-baseweb="input"] {
            background-color: #F7F7F7 !important;
            border: 1px solid transparent !important;
            border-radius: 12px !important;
        }
        div[data-baseweb="input"]:focus-within {
            border: 1px solid #222222 !important;
            background-color: #FFFFFF !important;
        }
        input {
            color: #222222 !important;
            font-weight: 500 !important;
            caret-color: #FF385C !important;
        }
        
        /* Audio Input - Pill Shape */
        [data-testid="stAudioInput"] {
            background-color: #F7F7F7 !important;
            border-radius: 50px !important;
            border: none !important;
            color: #222 !important;
            padding: 5px !important;
        }

        /* --- 6. NAVIGATION (Fixed Bottom) --- */
        .nav-fixed-container {
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            height: 80px;
            background-color: #FFFFFF;
            border-top: 1px solid #f2f2f2;
            z-index: 999999;
            padding-bottom: env(safe-area-inset-bottom);
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 -4px 10px rgba(0,0,0,0.03);
        }

        .nav-fixed-container [data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            width: 100% !important;
            gap: 0 !important;
        }
        
        .nav-fixed-container [data-testid="column"] {
            flex: 1 !important;
            padding: 0 !important;
        }
        
        .nav-btn button, .nav-active button {
            width: 100% !important;
            height: 100% !important;
            border: none !important;
            background: transparent !important;
            box-shadow: none !important;
            padding: 10px 0 !important;
        }
        
        .nav-btn button p { color: #b0b0b0 !important; font-weight: 500 !important; font-size: 11px !important; }
        .nav-active button p { color: #FF385C !important; font-weight: 700 !important; font-size: 11px !important; }

        /* --- UTILS --- */
        .stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 20px; }
        .stat-item { background: #F7F7F7; padding: 12px; border-radius: 12px; }
        .stat-label { font-size: 10px; font-weight: 700; text-transform: uppercase; color: #717171; letter-spacing: 0.5px; }
        .stat-value { font-size: 14px; font-weight: 600; color: #222222; margin-top: 4px; line-height: 1.3; }
        
        .briefing-section {
            background-color: #F7F7F7;
            border-radius: 12px;
            padding: 16px;
            margin-top: 16px;
        }
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
# 5. OMNI-TOOL BACKEND (AI CORE)
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
    1. MATCHING: Is the user talking about a person in the Rolodex? (Use fuzzy matching on name/context).
    2. INTENT: 
       - If they are describing a NEW person not in the list -> Action: "CREATE"
       - If they are adding info about an EXISTING person -> Action: "UPDATE"
       - If they are asking a question about a person or the list -> Action: "QUERY"
    RETURN ONLY RAW JSON:
    {{
        "action": "CREATE" | "UPDATE" | "QUERY",
        "match_id": (Integer ID if UPDATE/QUERY matches a specific lead, else null),
        "lead_data": {{
            "name": "Full Name",
            "contact_info": "Phone/Email",
            "background": "The full context/history (If UPDATE, append new info to old)",
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
    except Exception as e: return {"error": str(e)}

def save_new_lead(lead_data):
    if not st.session_state.user: return "Not logged in"
    lead_data['user_id'] = st.session_state.user.id
    lead_data['created_at'] = datetime.now().isoformat()
    try: 
        res = supabase.table("leads").insert(lead_data).execute()
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
    """Display the sleek Omni-Tool Output"""
    lead = data.get('lead_data', {})
    action = data.get('action', 'QUERY')
    brief = data.get('executive_brief', 'No briefing available.')
    badge_text = "INTELLIGENCE REPORT"
    if action == "CREATE": badge_text = "NEW ASSET"
    elif action == "UPDATE": badge_text = "UPDATED"
    
    # Updated HTML to match Airbnb Card Aesthetic
    html_content = f"""
        <div class="airbnb-card">
            <div class="card-header">
                <div>
                    <span class="status-badge">{badge_text}</span>
                    <div class="card-title">{lead.get('name') or 'Rolodex Query'}</div>
                </div>
            </div>
            
            <div class="briefing-section">
                <div class="stat-label" style="color:#FF385C;">Morning Briefing</div>
                <div style="font-size:16px; font-weight:500; color:#222; margin-top:4px; line-height:1.5;">{brief}</div>
            </div>

            <div class="stat-grid">
                <div class="stat-item">
                    <div class="stat-label">Strategy</div>
                    <div class="stat-value">{lead.get('sales_angle') or '-'}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Next Step</div>
                    <div class="stat-value">{lead.get('follow_up') or '-'}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Product Fit</div>
                    <div class="stat-value">{lead.get('product_pitch') or '-'}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Contact</div>
                    <div class="stat-value">{lead.get('contact_info') or '-'}</div>
                </div>
            </div>
            
            <div style="margin-top:24px;">
                <div class="stat-label">Background / Notes</div>
                <p style="font-size:14px; margin-top:8px; line-height:1.6; color:#717171;">{lead.get('background') or '-'}</p>
            </div>
        </div>
    """.replace("\n", " ")
    
    st.markdown(html_content, unsafe_allow_html=True)
    
    # Action Buttons
    c1, c2 = st.columns(2)
    with c1:
        if lead.get('name'):
            vcf = create_vcard(data)
            safe_name = lead.get('name').strip().replace(" ", "_")
            st.download_button("Save Contact", data=vcf, file_name=f"{safe_name}.vcf", mime="text/vcard", use_container_width=True, type="primary")
    with c2:
        if st.button("Close File", use_container_width=True, type="secondary"):
            st.session_state.omni_result = None
            st.rerun()

def view_omni():
    c1, c2 = st.columns([8, 1]) 
    with c1: st.markdown("<h2 style='margin-top:10px;'>Omni-Assistant</h2>", unsafe_allow_html=True)
    with c2:
        with st.popover("👤"):
            if st.button("Sign Out", type="secondary"):
                supabase.auth.sign_out(); st.session_state.user = None; st.rerun()

    if not st.session_state.omni_result:
        st.markdown("""
            <div style="text-align: center; padding: 60px 20px;">
                <div style="font-size: 64px; margin-bottom: 20px;">🎙️</div>
                <h3 style="margin-bottom: 10px;">Tap to Speak</h3>
                <p style="font-size: 16px;">"Create a lead for John..."<br>"Update Sarah's file..."</p>
            </div>
        """, unsafe_allow_html=True)
        
        # Audio input styled as pill
        audio_val = st.audio_input("OmniInput", label_visibility="collapsed")
        
        if audio_val:
            with st.spinner("Analyzing Rolodex..."):
                existing_leads = load_leads_summary()
                result = process_omni_voice(audio_val.read(), existing_leads)
                if "error" in result: st.error(result['error'])
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
    st.markdown("<h2 style='padding:20px 0 10px 0;'>Pipeline</h2>", unsafe_allow_html=True)
    if not st.session_state.user: return
    leads = supabase.table("leads").select("*").eq("user_id", st.session_state.user.id).order("created_at", desc=True).execute().data
    if not leads: st.info("Rolodex is empty.")
    for lead in leads:
        # Using markdown for card look instead of expander for better style control, 
        # but expander is safer for native streamlit. We'll stick to expander but it might look basic.
        with st.expander(f"{lead.get('name', 'Unknown')} - {lead.get('sales_angle', '')}"):
            st.write(lead.get('background'))
            st.caption(f"Last updated: {lead.get('created_at')[:10]}")

def view_analytics():
    st.markdown("<h2 style='padding:20px 0 10px 0;'>Analytics</h2>", unsafe_allow_html=True)
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
    st.markdown("<div style='text-align:center; padding-top:40px;'><h1>The Closer</h1><p>Your AI Sales Companion</p></div>", unsafe_allow_html=True)
    
    st.markdown("<div class='airbnb-card'>", unsafe_allow_html=True)
    email = st.text_input("Email", placeholder="name@example.com")
    password = st.text_input("Password", type="password", placeholder="••••••••")
    st.markdown("</div>", unsafe_allow_html=True)
    
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
    
    st.markdown("""
        <div style="text-align:center; padding: 40px 20px;">
            <h1>Upgrade Plan</h1>
            <p>Unlock unlimited leads and pipeline storage.</p>
            <div class="airbnb-card" style="margin-top:20px;">
                <h2 style="margin:0;">$15<small style="font-size:16px; color:#717171;">/mo</small></h2>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    if st.button("Subscribe Now", type="primary", use_container_width=True):
        url = create_checkout_session(st.session_state.user.email, st.session_state.user.id)
        if url: st.link_button("Go to Checkout", url, type="primary")
    st.stop()

if st.session_state.active_tab == "omni": view_omni()
elif st.session_state.active_tab == "pipeline": view_pipeline()
elif st.session_state.active_tab == "analytics": view_analytics()

# --- NAVIGATION BAR (FIXED) ---
with st.container():
    st.markdown('<div class="nav-fixed-container">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    def nav_btn(col, label, target, icon):
        with col:
            cls = "nav-active" if st.session_state.active_tab == target else "nav-btn"
            st.markdown(f'<div class="{cls}">', unsafe_allow_html=True)
            if st.button(label, key=f"nav_{target}", use_container_width=True):
                st.session_state.active_tab = target
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
    
    nav_btn(c1, "Assistant", "omni", "")
    nav_btn(c2, "Rolodex", "pipeline", "")
    nav_btn(c3, "Analytics", "analytics", "")
    st.markdown('</div>', unsafe_allow_html=True)
