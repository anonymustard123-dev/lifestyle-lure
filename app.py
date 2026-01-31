import streamlit as st
from google import genai
from google.genai import types
import os
import json
import pandas as pd
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client
import stripe
import textwrap
import re
from dotenv import load_dotenv  #

# FORCE LOAD ENV VARIABLES (Fixes missing keys locally)
load_dotenv()

# ==========================================
# 1. CONFIG & STATE
# ==========================================
st.set_page_config(
    page_title="NexusFlowAI", 
    page_icon="🎙️", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Initialize Session State
if 'user' not in st.session_state: st.session_state.user = None
if 'is_subscribed' not in st.session_state: st.session_state.is_subscribed = False
if 'active_tab' not in st.session_state: st.session_state.active_tab = "omni" 
if 'omni_result' not in st.session_state: st.session_state.omni_result = None
if 'selected_lead' not in st.session_state: st.session_state.selected_lead = None
if 'referral_captured' not in st.session_state: st.session_state.referral_captured = None
if 'is_editing' not in st.session_state: st.session_state.is_editing = False
if 'show_profile' not in st.session_state: st.session_state.show_profile = False
# NEW: State for toggling email login visibility
if 'show_email_login' not in st.session_state: st.session_state.show_email_login = False
# NEW: State for PWA Install Guide
if 'show_install_guide' not in st.session_state: st.session_state.show_install_guide = False

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
APP_BASE_URL = "https://app.nexusflowapp.pro" # Hardcoded to ensure custom domain is used

@st.cache_resource
def init_supabase():
    if SUPABASE_URL and SUPABASE_KEY:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    return None

supabase = init_supabase()

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# ==========================================
# 3. CSS (COMPLETE REFACTOR)
# ==========================================
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700;900&display=swap');
        
        /* 1. FORCE LIGHT MODE & REMOVE PADDING */
        :root {
            color-scheme: light;
        }
        
        html, body, .stApp {
            font-family: 'Circular', -apple-system, BlinkMacSystemFont, Roboto, "Helvetica Neue", sans-serif;
            background-color: #FFFFFF !important;
            color: #222222;
            min-height: 100dvh !important;
            width: 100vw;
            margin: 0;
            padding: 0;
            overflow-x: hidden !important;
            overscroll-behavior: none;
            -webkit-user-select: none;
            user-select: none;
            -webkit-tap-highlight-color: transparent;
        }
        
        h1, h2, h3 { font-weight: 800 !important; color: #222222 !important; letter-spacing: -0.5px; }
        p, label, span, div { color: #717171; }
        
        /* HIDE HEADER & FOOTER COMPLETELY */
        [data-testid="stHeader"], footer, [data-testid="stFooter"] { 
            display: none !important; 
            visibility: hidden !important; 
            height: 0px !important; 
            opacity: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
        }
        
        /* AGGRESSIVE WHITE BAR REMOVAL */
        .main .block-container {
            padding-top: 20px !important;
            margin-top: 0px !important;
            padding-bottom: 0px !important;
            padding-left: 20px !important;
            padding-right: 20px !important;
            max-width: 100% !important;
            gap: 0px !important;
        }
        
        [data-testid="stVerticalBlock"] {
            gap: 0rem !important;
            padding-bottom: 0rem !important;
        }
        
       /* TAB STYLES */
        [data-testid="stRadio"] {
            width: 100% !important;
            padding: 0 !important;
            background: transparent !important;
            border-bottom: 1px solid #F2F2F2 !important;
            margin-bottom: 24px !important;
            display: block !important;
        }

        [data-testid="stRadio"] div[role="radiogroup"] {
            width: 100% !important;
            display: flex !important;
            flex-direction: row !important;
            justify-content: center !important; 
            align-items: center !important;
            gap: 24px !important; 
            overflow-x: auto !important;
            white-space: nowrap !important;
            border: none !important;
            padding: 0 !important;
            margin: 0 !important;
        }

        [data-testid="stRadio"] label > div:first-child { display: none !important; }

        [data-testid="stRadio"] div[role="radiogroup"] label {
            cursor: pointer;
            padding: 12px 16px !important;
            margin: 0 !important;
            border-bottom: 3px solid transparent;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
        }
        
        [data-testid="stRadio"] div[role="radiogroup"] label p {
            font-size: 15px !important;
            font-weight: 600 !important;
            color: #717171 !important;
            margin: 0 !important;
        }

        [data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) {
            border-bottom-color: #FF385C !important;
        }
        [data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) p {
            color: #222222 !important;
        }        
        
        /* CARD STYLES */
        .airbnb-card {
            background-color: #FFFFFF; border-radius: 16px; box-shadow: 0 6px 16px rgba(0,0,0,0.08);
            border: 1px solid #dddddd; padding: 24px; margin-bottom: 24px;
        }
        
        .status-badge {
            background-color: #FF385C; color: white; font-size: 10px; font-weight: 800;
            padding: 6px 10px; border-radius: 8px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px; display: inline-block;
        }
        .meta-bubble {
            font-size: 12px; font-weight: 700; padding: 4px 10px; border-radius: 12px;
            border: 1px solid #EBEBEB; white-space: nowrap; vertical-align: middle; display: inline-flex; align-items: center;
        }
        
        .bubble-client { background-color: #E6FFFA; color: #008a73; border-color: #008a73; }
        .bubble-lead { background-color: #FFF5F7; color: #FF385C; border-color: #FF385C; } 
        .bubble-outreach { background-color: #FFFFF0; color: #D69E2E; border-color: #D69E2E; }
        
        .report-bubble { background-color: #F7F7F7; border-radius: 16px; padding: 20px; margin-top: 16px; border: 1px solid #EBEBEB; }
        .transaction-bubble { background-color: #F0FFF4; border-radius: 16px; padding: 20px; margin-top: 16px; border: 1px solid #C6F6D5; }
        
        /* BUTTONS & ACTIONS */
        div[data-testid="stButton"] > button, div[data-testid="stDownloadButton"] > button {
            background-color: #FFFFFF !important;
            border: 1px solid #EBEBEB !important; 
            border-left: 6px solid #FF385C !important;
            border-radius: 12px !important;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05) !important;
            padding: 12px 20px !important;
            font-weight: 600 !important;
            transition: all 0.2s ease !important;
            color: #222222 !important;
            text-align: center !important;
            justify-content: center !important;
            display: flex !important;
            width: 100% !important;
        }

        div[data-testid="stButton"] > button p, div[data-testid="stDownloadButton"] > button p {
            color: #222222 !important;
        }
        
        div[data-testid="stButton"] > button:hover, div[data-testid="stDownloadButton"] > button:hover {
            border-color: #FF385C !important;
            transform: translateY(-2px) !important;
            box-shadow: 0 8px 15px rgba(255, 56, 92, 0.15) !important;
            color: #FF385C !important;
        }
        div[data-testid="stButton"] > button:hover p, div[data-testid="stDownloadButton"] > button:hover p { 
            color: #FF385C !important; 
        }

        /* ROLODEX OVERRIDES */
        div.element-container:has(.rolodex-marker) + div.element-container button {
            text-align: left !important;
            justify-content: flex-start !important;
            font-weight: 800 !important;
        }
        div.element-container:has(.rolodex-marker) + div.element-container button p {
            font-weight: 800 !important;
            color: #222222 !important;
        }
        div.element-container:has(.rolodex-marker) + div.element-container button > div {
            justify-content: flex-start !important; 
        }

        div.element-container:has(.client-marker) + div.element-container button { border-left-color: #008a73 !important; }
        div.element-container:has(.client-marker) + div.element-container button:hover {
            border-color: #008a73 !important;
            color: #008a73 !important;
            box-shadow: 0 8px 15px rgba(0, 138, 115, 0.15) !important;
        }
        div.element-container:has(.client-marker) + div.element-container button:hover p { color: #008a73 !important; }

        /* BOLD LEFT BUTTON OVERRIDES */
        div.element-container:has(.bold-left-marker) + div.element-container button {
            text-align: left !important;
            justify-content: flex-start !important;
            font-weight: 800 !important; 
        }
        div.element-container:has(.bold-left-marker) + div.element-container button p {
            font-weight: 800 !important;
        }
        div.element-container:has(.bold-left-marker) + div.element-container button > div {
            justify-content: flex-start !important; 
        }

        /* ANALYTICS & STATS */
        .analytics-card {
            background-color: #FFFFFF;
            border: 1px solid #EBEBEB;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            padding: 16px 20px;
            margin-bottom: 12px;
            width: 100%;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: flex-start;
        }
        .analytics-card-red { border-left: 6px solid #FF385C; }
        .analytics-card-green { border-left: 6px solid #008a73; }
        
        .stat-title { font-size: 11px; font-weight: 800; color: #717171; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 6px; }
        .stat-metric { font-size: 26px; font-weight: 900; color: #222222; margin: 0; line-height: 1.1; }
        .stat-sub { font-size: 14px; font-weight: 500; color: #717171; margin-top: 4px; }

        /* INPUT FIELDS */
        div[data-baseweb="input"], div[data-baseweb="select"], div[data-baseweb="textarea"], div[data-testid="stMarkdownContainer"] textarea {
            background-color: #F7F7F7 !important;
            color: #222222 !important;
            border: 1px solid transparent !important;
            border-radius: 12px !important;
        }
        div[data-baseweb="base-input"] {
            background-color: transparent !important;
            border: none !important;
            width: 100% !important;
        }
        input, textarea, select {
            color: #222222 !important;
            background-color: transparent !important;
            font-weight: 500 !important; 
            caret-color: #FF385C !important; 
            width: 100% !important;
        }
        input::placeholder, textarea::placeholder {
            color: #717171 !important;
            opacity: 1 !important;
            -webkit-text-fill-color: #717171 !important;
        }
        div[data-baseweb="input"]:focus-within, div[data-baseweb="base-input"]:focus-within { 
            border: 1px solid #222222 !important; 
            background-color: #FFFFFF !important; 
        }
        div[data-baseweb="select"] > div {
            background-color: #F7F7F7 !important;
            color: #222222 !important;
        }
        div[data-baseweb="select"] svg {
            fill: #222222 !important; 
        }
        ul[data-baseweb="menu"] {
            background-color: #FFFFFF !important;
        }
        li[data-baseweb="menu-item"] {
            color: #222222 !important;
        }
        
        button[kind="primary"] { 
            background-color: #FF385C !important; color: white !important; border: none !important; 
            text-align: center !important; justify-content: center !important; padding: 12px 24px !important; border-left: none !important; 
        }
        button[kind="primary"] p { color: white !important; text-align: center !important; width: 100% !important; justify-content: center !important; }
        button[kind="primary"] > div { justify-content: center !important; }
        button[kind="primary"]:hover { box-shadow: 0 4px 12px rgba(255, 56, 92, 0.4) !important; transform: none !important; }
        
        [data-testid="stAudioInput"] { background-color: #F7F7F7 !important; border-radius: 50px !important; border: none !important; color: #222 !important; padding: 5px !important; }
        
        .card-title {
            font-size: 22px; font-weight: 800; color: #222222; margin: 0; line-height: 1.2;
            display: flex; flex-wrap: wrap; align-items: center; gap: 8px;
        }
        .stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 20px; }
        .stat-item { background: #F7F7F7; padding: 12px; border-radius: 12px; }
        .stat-label { font-size: 10px; font-weight: 700; text-transform: uppercase; color: #717171; letter-spacing: 0.5px; }
        .stat-value { font-size: 14px; font-weight: 600; color: #222222; margin-top: 4px; line-height: 1.3; }
        
        .referral-box {
            background-color: #F7F7F7;
            border: 1px dashed #dddddd;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 24px;
            text-align: center;
        }
        .referral-link {
            font-family: monospace;
            background: #ffffff;
            padding: 8px;
            border-radius: 6px;
            border: 1px solid #eee;
            color: #FF385C;
            font-weight: 600;
            word-break: break-all;
        }
        .stCodeBlock {
            background-color: #F7F7F7 !important;
            border-radius: 12px !important;
            border: 1px dashed #dddddd !important;
        }
        
        .profile-container {
            display: flex;
            justify-content: flex-end;
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

def count_user_referrals(user_id):
    """Counts how many users have this user_id as their referrer"""
    try:
        res = supabase.table("profiles").select("id", count="exact").eq("referred_by", user_id).execute()
        return res.count
    except: return 0

def check_subscription_status(email):
    # FIX: FAIL SAFE - If Stripe is missing, return FALSE (Not Subscribed)
    if not STRIPE_SECRET_KEY: 
        return False
        
    try:
        customers = stripe.Customer.list(email=email).data
        if not customers: return False
        subscriptions = stripe.Subscription.list(customer=customers[0].id, status='active').data
        return len(subscriptions) > 0
    except: return False

def create_checkout_session(email, user_id):
    if not STRIPE_SECRET_KEY: return None
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
    except Exception as e:
        st.error(f"Stripe Error: {e}")
        return None

def cancel_active_subscription(email):
    """
    Cancels the user's subscription at the end of the current billing period.
    Returns (Success: bool, Message: str).
    """
    if not STRIPE_SECRET_KEY: return False, "Stripe configuration missing."
    
    try:
        # 1. Find the Stripe Customer by Email
        customers = stripe.Customer.list(email=email).data
        if not customers: 
            return False, "No subscription account found."
            
        # 2. Find Active Subscriptions
        subscriptions = stripe.Subscription.list(customer=customers[0].id, status='active').data
        if not subscriptions: 
            return False, "No active subscription found."
            
        # 3. Modify Subscription to Cancel at Period End
        stripe.Subscription.modify(
            subscriptions[0].id,
            cancel_at_period_end=True
        )
        return True, "Subscription canceled. Access remains until the end of your billing cycle."
        
    except Exception as e:
        return False, f"Error: {str(e)}"

# --- HIERARCHY LOGIC (SIMPLIFIED) ---
def ensure_referral_link(user_id, user_meta, ref_override=None):
    """
    Called on login.
    Links the new user to their Direct Referrer (Tier 1).
    Now accepts an override for Google Login flow.
    """
    try:
        profile = fetch_user_profile(user_id)
        if not profile: return
        
        # Check if already linked
        if profile.get('referred_by'): return

        # Priority: 1. URL Override (Google) -> 2. Metadata (Email/Pass)
        referrer_id = ref_override if ref_override else user_meta.get('referred_by')
        
        if referrer_id:
             supabase.table("profiles").update({'referred_by': referrer_id}).eq("id", user_id).execute()
    except Exception as e:
        print(f"Hierarchy Error: {e}")

# --- CONTACT FORMATTING HELPER ---
def format_contact_details(contact_info):
    if not contact_info: return "-"
    s = str(contact_info).strip()
    pattern = r'(?<!\d)(1?)(\d{3})(\d{3})(\d{4})(?!\d)'
    def repl(m): return f"({m.group(2)})-{m.group(3)}-{m.group(4)}"
    return re.sub(pattern, repl, s)

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
        response = supabase.table("leads").select("id, name, background, contact_info, status, next_outreach, transactions, product_pitch").eq("user_id", st.session_state.user.id).execute()
        return response.data
    except: return []

def process_omni_voice(audio_bytes, existing_leads_context):
    leads_json = json.dumps(existing_leads_context)
    est_now = datetime.now() - timedelta(hours=5)
    current_date_str = est_now.strftime("%Y-%m-%d %H:%M")
    
    prompt = f"""
    You are 'NexusFlowAI', an expert Executive Assistant. 
    Current Date/Time (User's Timezone): {current_date_str}
    Here is the user's Rolodex (Existing Leads): {leads_json}
    User Audio Provided. Listen carefully.
    
    YOUR TASK:
    1. MATCHING: Is the user talking about a person in the Rolodex? (Use fuzzy matching on name/context).
    2. INTENT: 
       - "CREATE": New person.
       - "UPDATE": Adding info to existing.
       - "QUERY": Asking questions.
    
    CRITICAL RULES:
    - **Transaction Logic**: If a sale/deal occurred, set 'transaction_item' to the specific item sold. 
    - **Product Fit Preservation**: Do NOT change 'product_pitch' unless explicitly told to.
    - **Status**: If a sale occurred, set "status" to "Client".
    - **Meeting/Outreach**: If a specific meeting date/time is mentioned, set 'next_outreach' to strict ISO 8601 format (YYYY-MM-DDTHH:MM:SS). 
      - Calculate relative dates (e.g., "in 5 days", "next week") starting from TODAY ({current_date_str}), NOT from any existing meeting date.
      - The new date MUST REPLACE the old one. If vague, use text.
    - **SILENCE / NOISE / UNINTELLIGIBLE**: If the audio is silent, background noise, mumbling, or lacks a clear name/intent, you MUST return:
      {{ "error": "No clear speech detected. Please try again." }}

    RETURN ONLY RAW JSON (or the error JSON above):
    {{
        "action": "CREATE" | "UPDATE" | "QUERY",
        "match_id": (Integer/String ID from Rolodex if UPDATE matches),
        "lead_data": {{
            "name": "Full Name",
            "contact_info": "Phone/Email",
            "background": "Updated summary (OR NULL if no change)",
            "product_pitch": "Updated Product Fit (OR NULL if just a sale occurred)",
            "status": "Lead" | "Client",
            "next_outreach": "ISO 8601 Date or Text" (or null),
            "transaction_item": "New item sold (OR NULL)" 
        }},
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
    if not st.session_state.user: return None
    lead_data['user_id'] = st.session_state.user.id
    lead_data['created_at'] = datetime.now().isoformat()
    if not lead_data.get('status'): lead_data['status'] = 'Lead'
    
    # Clean temp field
    if 'transaction_item' in lead_data:
        if lead_data['transaction_item']:
            lead_data['transactions'] = f"{datetime.now().strftime('%Y-%m-%d')}: {lead_data['transaction_item']}"
        del lead_data['transaction_item']
        
    try: 
        res = supabase.table("leads").insert(lead_data).execute()
        if res.data:
            return res.data[0]
        return None
    except Exception as e: return str(e)

def update_existing_lead(lead_id, new_data, existing_leads_context):
    if not st.session_state.user: return "Not logged in"
    
    original = next((item for item in existing_leads_context if str(item["id"]) == str(lead_id)), None)
    
    if not original:
        return "Error: Could not find original record to update."
    
    current_tx = original.get('transactions') or ""
    new_item = new_data.get('transaction_item')
    final_tx = current_tx
    
    if new_item:
        timestamp = datetime.now().strftime('%Y-%m-%d')
        entry = f"• {timestamp}: {new_item}"
        if current_tx:
            final_tx = f"{current_tx}\n{entry}"
        else:
            final_tx = entry
            
    final_status = "Client" if new_item else (new_data.get('status') or original.get('status'))

    final_data = {
        "name": new_data.get('name') or original.get('name'),
        "contact_info": new_data.get('contact_info') or original.get('contact_info'),
        "product_pitch": new_data.get('product_pitch') if new_data.get('product_pitch') else original.get('product_pitch'),
        "background": new_data.get('background') if new_data.get('background') else original.get('background'),
        "status": final_status,
        "next_outreach": new_data.get('next_outreach') or original.get('next_outreach'), 
        "transactions": final_tx
    }

    try:
        supabase.table("leads").update(final_data).eq("id", lead_id).execute()
        final_data['id'] = lead_id
        return final_data 
    except Exception as e: return str(e)

def create_vcard(data):
    lead_info = data.get('lead_data', data)
    vcard = [
        "BEGIN:VCARD", "VERSION:3.0", 
        f"FN:{lead_info.get('name', 'Lead')}", 
        f"TEL;TYPE=CELL:{lead_info.get('contact_info', '')}", 
        f"NOTE:{lead_info.get('background', '')}", 
        "END:VCARD"
    ]
    return "\n".join(vcard)

def create_ics_string(event_name, dt, description):
    try:
        dt_str = dt.strftime("%Y%m%dT%H%M%S")
        now_str = datetime.now().strftime("%Y%m%dT%H%M%S")
        clean_name = event_name.replace(' ', '')
        
        ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//NexusFlowAI//EN
BEGIN:VEVENT
UID:{dt_str}-{clean_name}@nexusflow.ai
DTSTAMP:{now_str}
DTSTART:{dt_str}
SUMMARY:Meeting with {event_name}
DESCRIPTION:{description}
END:VEVENT
END:VCALENDAR"""
        return ics_content
    except:
        return None

# ==========================================
# 6. APP VIEWS (SHARED)
# ==========================================

@st.dialog("Cancel Subscription")
def confirm_cancellation_dialog(email):
    st.write("Are you sure you want to cancel? You will lose access to premium features at the end of your billing cycle.")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Confirm Cancellation", type="primary", use_container_width=True):
            success, msg = cancel_active_subscription(email)
            if success:
                st.success(msg)
            else:
                st.error(msg)
    with col2:
        if st.button("Close", type="secondary", use_container_width=True):
            st.rerun()

def render_profile_view_overlay():
    """
    Renders the Full Page Profile Overlay.
    """
    # Top Bar: Back Button
    c_back, c_void = st.columns([1, 5])
    with c_back:
        # This button acts as the "Close" trigger
        if st.button("← Back", key="back_from_profile_overlay", type="tertiary"):
            st.session_state.show_profile = False
            st.rerun()

    st.subheader("Profile")
    st.markdown('<div class="bold-left-marker"></div>', unsafe_allow_html=True)
    if st.button("Sign Out", key="logout_btn", type="secondary", use_container_width=True):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.session_state.show_profile = False
        st.rerun()

    # Cancel Subscription with Confirmation Dialog
    if st.session_state.get('is_subscribed', False):
        st.markdown('<div class="bold-left-marker"></div>', unsafe_allow_html=True)
        if st.button("Cancel Subscription", key="cancel_sub_btn", type="primary", use_container_width=True):
            confirm_cancellation_dialog(st.session_state.user.email)

    st.markdown("---")
    
    st.subheader("Referral Hub")
    
    my_profile = fetch_user_profile(st.session_state.user.id)
    if my_profile:
        balance = my_profile.get('commission_balance') or 0.00
        ref_count = count_user_referrals(st.session_state.user.id)
        
        saved_method = my_profile.get('payout_method') or "Venmo"
        saved_handle = my_profile.get('payout_handle') or ""
        
        # FIX 1: FORCE CUSTOM DOMAIN
        referral_link = f"{APP_BASE_URL}?ref={st.session_state.user.id}"

        # 1. BALANCE CARD & REFERRAL COUNT
        st.markdown(f"""
            <div class="analytics-card analytics-card-green" style="margin-bottom: 16px;">
                <div class="stat-title">WALLET BALANCE</div>
                <div class="stat-metric">${balance:,.2f}</div>
                <div class="stat-sub">You earn $10.00 per referral</div>
            </div>
            
            <div class="analytics-card analytics-card-green" style="margin-bottom: 16px;">
                <div class="stat-title">ACTIVE REFERRALS</div>
                <div class="stat-metric">{ref_count}</div>
                <div class="stat-sub">Users signed up with your code</div>
            </div>
        """, unsafe_allow_html=True)

        # 2. REFERRAL LINK
        st.caption("Your Referral Link")
        st.code(referral_link, language="text")
        # FIX 3: UPDATED TEXT
        st.info("You earn $10 per month for every subscribed user that uses your link. Payouts will be made the first week of each month.")

        # REMOVED: 3. COMMISSION HISTORY (Transaction History Log)
        
        # 4. PAYOUT SETTINGS
        st.markdown("### Payout Settings")
        
        with st.form("payout_form"):
            method_opts = ["Venmo", "CashApp", "PayPal", "Zelle"]
            try: idx = method_opts.index(saved_method)
            except: idx = 0
                
            new_method = st.selectbox("Preferred Method", method_opts, index=idx)
            
            placeholders = {
                "Venmo": "@username", 
                "CashApp": "$cashtag", 
                "PayPal": "name@example.com", 
                "Zelle": "Phone or Email"
            }
            new_handle = st.text_input(f"Your {new_method} Handle", value=saved_handle, placeholder=placeholders.get(new_method, ""))
            
            if st.form_submit_button("Update Details"):
                supabase.table("profiles").update({
                    "payout_method": new_method, 
                    "payout_handle": new_handle
                }).eq("id", st.session_state.user.id).execute()
                st.success("Details saved.")
                st.rerun()

# --- NEW: INSTALL GUIDE OVERLAY ---
def render_install_guide():
    """Renders the PWA Installation Instructions."""
    
    # Back Button
    c_back, c_void = st.columns([1, 5])
    with c_back:
        if st.button("← Back", key="back_from_install", type="tertiary"):
            st.session_state.show_install_guide = False
            st.rerun()

    # Header
    st.markdown("""
        <div style="text-align: center; margin-bottom: 30px;">
            <div style="display:inline-block; background-color: #FFF5F7; color: #FF385C; font-size: 11px; font-weight: 800; padding: 6px 12px; border-radius: 20px; text-transform: uppercase; margin-bottom: 12px;">Mobile App</div>
            <h1 style="margin: 0; font-size: 32px; letter-spacing: -1px;">Install as an App</h1>
            <p style="font-size: 16px; margin-top: 10px; max-width: 600px; margin-left: auto; margin-right: auto; color: #717171;">
                NexusFlowAI is a Progressive Web App (PWA) that lives right on your home screen—no app store required.
            </p>
        </div>
    """, unsafe_allow_html=True)

    # Two Cards
    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown("""
            <div class="airbnb-card" style="height: 100%; padding: 32px;">
                <div style="display:flex; align-items:center; gap:12px; margin-bottom: 24px;">
                    <div style="background: #222; color:white; padding: 10px; border-radius: 12px;"><svg xmlns="[http://www.w3.org/2000/svg](http://www.w3.org/2000/svg)" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="20" x="5" y="2" rx="2" ry="2"/><path d="M12 18h.01"/></svg></div>
                    <div>
                        <h3 style="margin:0; color:#222;">iOS</h3>
                        <span style="font-size:13px; color:#717171;">iPhone & iPad</span>
                    </div>
                </div>
                
                <div style="display:flex; gap:16px; margin-bottom: 20px;">
                    <div style="background:#FFF5F7; color:#FF385C; width:24px; height:24px; border-radius:50%; text-align:center; font-weight:800; font-size:12px; line-height:24px; flex-shrink:0;">1</div>
                    <div>
                        <strong style="color:#222; display:block; margin-bottom:4px;">Open in Safari</strong>
                        <span style="font-size:14px; color:#717171;">Visit the app URL in Safari browser</span>
                    </div>
                </div>
                
                 <div style="display:flex; gap:16px; margin-bottom: 20px;">
                    <div style="background:#FFF5F7; color:#FF385C; width:24px; height:24px; border-radius:50%; text-align:center; font-weight:800; font-size:12px; line-height:24px; flex-shrink:0;">2</div>
                    <div>
                        <strong style="color:#222; display:block; margin-bottom:4px;">Tap the Share icon ⍐</strong>
                        <span style="font-size:14px; color:#717171;">Located at the bottom of Safari</span>
                    </div>
                </div>
                
                 <div style="display:flex; gap:16px;">
                    <div style="background:#FFF5F7; color:#FF385C; width:24px; height:24px; border-radius:50%; text-align:center; font-weight:800; font-size:12px; line-height:24px; flex-shrink:0;">3</div>
                    <div>
                        <strong style="color:#222; display:block; margin-bottom:4px;">Add to Home Screen +</strong>
                        <span style="font-size:14px; color:#717171;">Scroll down and tap the option</span>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
    with c2:
        st.markdown("""
            <div class="airbnb-card" style="height: 100%; padding: 32px;">
                <div style="display:flex; align-items:center; gap:12px; margin-bottom: 24px;">
                    <div style="background: #008a73; color:white; padding: 10px; border-radius: 12px;"><svg xmlns="[http://www.w3.org/2000/svg](http://www.w3.org/2000/svg)" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="20" x="5" y="2" rx="2" ry="2"/><path d="M12 18h.01"/></svg></div>
                    <div>
                        <h3 style="margin:0; color:#222;">Android</h3>
                        <span style="font-size:13px; color:#717171;">All Android devices</span>
                    </div>
                </div>
                
                <div style="display:flex; gap:16px; margin-bottom: 20px;">
                    <div style="background:#E6FFFA; color:#008a73; width:24px; height:24px; border-radius:50%; text-align:center; font-weight:800; font-size:12px; line-height:24px; flex-shrink:0;">1</div>
                    <div>
                        <strong style="color:#222; display:block; margin-bottom:4px;">Open in Chrome</strong>
                        <span style="font-size:14px; color:#717171;">Visit the app URL in Chrome browser</span>
                    </div>
                </div>
                
                 <div style="display:flex; gap:16px; margin-bottom: 20px;">
                    <div style="background:#E6FFFA; color:#008a73; width:24px; height:24px; border-radius:50%; text-align:center; font-weight:800; font-size:12px; line-height:24px; flex-shrink:0;">2</div>
                    <div>
                        <strong style="color:#222; display:block; margin-bottom:4px;">Tap the menu icon ⋮</strong>
                        <span style="font-size:14px; color:#717171;">Three dots in the top right</span>
                    </div>
                </div>
                
                 <div style="display:flex; gap:16px;">
                    <div style="background:#E6FFFA; color:#008a73; width:24px; height:24px; border-radius:50%; text-align:center; font-weight:800; font-size:12px; line-height:24px; flex-shrink:0;">3</div>
                    <div>
                        <strong style="color:#222; display:block; margin-bottom:4px;">Install App ↓</strong>
                        <span style="font-size:14px; color:#717171;">Or "Add to Home Screen"</span>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)


# --- INTERCEPTOR: If Profile Mode is active, render it and stop ---
if st.session_state.show_profile and st.session_state.user:
    render_profile_view_overlay()
    st.stop()
    
# --- INTERCEPTOR: If Install Guide is active, render it and stop ---
if st.session_state.show_install_guide:
    render_install_guide()
    st.stop()

def render_header():
    """Renders the standard header with Logo (Left/Center) and Profile Button (Right)."""
    # Grid: Logo Area | Spacer | Profile Area
    c1, c2, c3 = st.columns([1, 2, 1], vertical_alignment="center")
    
    with c2:
        try:
            st.image("nexus_logo.jpg", use_container_width=True)
        except:
            st.markdown("<h1 style='text-align: center; color: #FF385C;'>NexusFlowAI</h1>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center;'>Gravity for leads. Flow for deals.</p>", unsafe_allow_html=True)

    with c3:
        # Only show profile button if user is logged in
        if st.session_state.user:
            # Use columns to place buttons side by side
            c_info, c_profile = st.columns([1, 1])
            with c_info:
                if st.button("ℹ️", key="header_info_btn"):
                    st.session_state.show_install_guide = True
                    st.rerun()
            with c_profile:
                if st.button("👤", key="header_profile_btn"):
                    st.session_state.show_profile = True
                    st.rerun()

# ==========================================
# 7. MAIN ROUTER
# ==========================================

# --- AUTH HELPER: EXCHANGE GOOGLE CODE ---
def handle_google_callback():
    """Checks for OAuth 'code' in URL and exchanges it for a session."""
    try:
        query_params = st.query_params
        if "code" in query_params:
            code = query_params["code"]
            
            # 1. Exchange code for session
            res = supabase.auth.exchange_code_for_session({"auth_code": code})
            if res.user:
                st.session_state.user = res.user
                st.session_state.is_subscribed = check_subscription_status(res.user.email)
                
                # 2. CHECK FOR REFERRAL IN URL (Crucial for Google Signups)
                # If we passed ?ref=... in the redirect_to, it will be here now.
                ref_from_url = query_params.get("ref")
                
                # 3. Ensure Link
                # We pass the URL ref explicitly because Google metadata might be empty
                ensure_referral_link(res.user.id, res.user.user_metadata, ref_override=ref_from_url)
                
                # Clear the code from URL so it doesn't try to re-use it on refresh
                st.query_params.clear()
                st.rerun()
    except Exception as e:
        st.error(f"Login Error: {e}")

# 1. First, check for Google Callback immediately
handle_google_callback()

if not st.session_state.user:
    # --- LOGIN SCREEN ---
    render_header() # Shows Logo Only
    
    st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)
    
    # --- GOOGLE LOGIN BUTTON ---
    # DYNAMIC REDIRECT: Pass the referral code through the redirect URL
    redirect_target = APP_BASE_URL
    if st.session_state.referral_captured:
        redirect_target = f"{APP_BASE_URL}?ref={st.session_state.referral_captured}"

    # FIX: Replace broken get_url_for_provider with sign_in_with_oauth
    try:
        data = supabase.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {
                "redirect_to": redirect_target
            }
        })
        google_auth_url = data.url
    except Exception as e:
        # Fallback if the URL generation fails (e.g., config error)
        st.error(f"Config Error: {e}")
        google_auth_url = "#"

    # Custom Google Button Styling - FIXED with INLINE SVG (No broken links)
    google_icon_svg = """<svg xmlns="[http://www.w3.org/2000/svg](http://www.w3.org/2000/svg)" viewBox="0 0 48 48" width="20px" height="20px"><path fill="#FFC107" d="M43.611,20.083H42V20H24v8h11.303c-1.649,4.657-6.08,8-11.303,8c-6.627,0-12-5.373-12-12c0-6.627,5.373-12,12-12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C12.955,4,4,12.955,4,24c0,11.045,8.955,20,20,20c11.045,0,20-8.955,20-20C44,22.659,43.862,21.35,43.611,20.083z"/><path fill="#FF3D00" d="M6.306,14.691l6.571,4.819C14.655,15.108,18.961,12,24,12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C16.318,4,9.656,8.337,6.306,14.691z"/><path fill="#4CAF50" d="M24,44c5.166,0,9.86-1.977,13.409-5.192l-6.19-5.238C29.211,35.091,26.715,36,24,36c-5.202,0-9.619-3.317-11.283-7.946l-6.522,5.025C9.505,39.556,16.227,44,24,44z"/><path fill="#1976D2" d="M43.611,20.083H42V20H24v8h11.303c-0.792,2.237-2.231,4.166-4.087,5.571c0.001-0.001,0.002-0.001,0.003-0.002l6.19,5.238C36.971,39.205,44,34,44,24C44,22.659,43.862,21.35,43.611,20.083z"/></svg>"""

    # --- NEW: "FASTEST" BADGE & HIGHLIGHTED BUTTON ---
    # MODIFIED: Increased margin-bottom to 60px to increase spacing from the next button (Fix #1)
    button_html = f"""
        <div style="text-align: center; margin-bottom: 8px;">
            <span style="background-color: #E6FFFA; color: #008a73; font-size: 10px; font-weight: 800; padding: 4px 8px; border-radius: 12px; letter-spacing: 0.5px;">
                FASTEST
            </span>
        </div>
        <a href="{google_auth_url}" target="_self" style="text-decoration: none;">
            <div style="
                display: flex; align-items: center; justify-content: center;
                background-color: white; border: 2px solid #008a73; border-radius: 12px;
                padding: 12px; margin-bottom: 60px; cursor: pointer;
                box-shadow: 0 4px 12px rgba(0,138,115,0.15); transition: all 0.2s;">
                <div style="margin-right: 12px; display: flex; align-items: center;">
                    {google_icon_svg}
                </div>
                <span style="font-weight: 700; color: #222; font-size: 16px;">Continue with Google</span>
            </div>
        </a>
    """
    st.markdown(button_html, unsafe_allow_html=True)
    
    # --- NEW: PROGRESSIVE DISCLOSURE FOR EMAIL LOGIN ---
    if not st.session_state.show_email_login:
        # Show only the subtle "Reveal" button
        st.markdown("<div style='text-align: center; color: #717171; margin-bottom: 12px; font-size: 14px;'></div>", unsafe_allow_html=True)
        if st.button("I don't have a Google account", type="tertiary", use_container_width=True):
            st.session_state.show_email_login = True
            st.rerun()
    else:
        # MODIFIED: Removed the "Back to Google" button block (Fix #2)
        
        # Show Form
        st.markdown("---")

        email = st.text_input("Email", placeholder="name@example.com")
        password = st.text_input("Password", type="password", placeholder="••••••••")
        
        # MODIFIED: Added specific spacer between password and buttons (Fix #4)
        st.markdown("<div style='margin-bottom: 24px;'></div>", unsafe_allow_html=True)
        
        c1, c2 = st.columns(2)
        # MODIFIED: Added display:none to markers to decrease vertical stacking gap on mobile (Fix #3)
        with c1:
            st.markdown('<div class="bold-left-marker" style="display:none;"></div>', unsafe_allow_html=True)
            if st.button("Log In", type="primary", use_container_width=True):
                try:
                    res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    st.session_state.user = res.user
                    st.session_state.is_subscribed = check_subscription_status(res.user.email)
                    ensure_referral_link(res.user.id, res.user.user_metadata)
                    st.rerun()
                except Exception as e: st.error(str(e))
        
        with c2:
            st.markdown('<div class="bold-left-marker" style="display:none;"></div>', unsafe_allow_html=True)
            if st.button("Sign Up", type="secondary", use_container_width=True):
                try:
                    meta = {"referred_by": st.session_state.referral_captured} if st.session_state.referral_captured else {}
                    res = supabase.auth.sign_up({"email": email, "password": password, "options": {"data": meta}})
                    if res.user: st.success("Account created! Log in."); 
                except Exception as e: st.error(str(e))
    st.stop()

if not st.session_state.is_subscribed:
    # --- UPGRADE / PAYWALL SCREEN ---
    if "session_id" in st.query_params:
        st.session_state.is_subscribed = check_subscription_status(st.session_state.user.email)
        if st.session_state.is_subscribed: st.rerun()

    # 1. RENDER LOGO
    c1, c2, c3 = st.columns([1, 2, 1], vertical_alignment="center")
    with c2:
        try:
            st.image("nexus_logo.jpg", use_container_width=True)
        except:
            st.markdown("<h1 style='text-align: center; color: #FF385C;'>NexusFlowAI</h1>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center;'>Gravity for leads. Flow for deals.</p>", unsafe_allow_html=True)
    
    # 2. RENDER UPGRADE CARD ($20 UPDATE)
    st.markdown("""<div style="text-align:center; padding: 20px 20px;"><h1>Upgrade Plan</h1><p>Unlock unlimited leads and pipeline storage.</p><div class="airbnb-card" style="margin-top:20px;"><h2 style="margin:0;">$20<small style="font-size:16px; color:#717171;">/mo</small></h2></div></div>""", unsafe_allow_html=True)
    
    # 3. SUBSCRIBE BUTTON
    if st.button("Subscribe Now", type="primary", use_container_width=True):
        with st.spinner("Redirecting to checkout..."):
            url = create_checkout_session(st.session_state.user.email, st.session_state.user.id)
            if url:
                 st.markdown(f'<meta http-equiv="refresh" content="0;url={url}">', unsafe_allow_html=True)
    
    # 4. PROFILE BUTTON
    st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)
    
    # Updated: Add Info button here too
    c_sub_1, c_sub_2 = st.columns([1, 1])
    with c_sub_1:
         if st.button("ℹ️", key="upgrade_info_btn"):
            st.session_state.show_install_guide = True
            st.rerun()
    with c_sub_2:
        if st.button("👤", key="upgrade_profile_btn"):
            st.session_state.show_profile = True
            st.rerun()
    
    st.stop()

# --- MAIN APP (SUBSCRIBED) ---
render_header() # Shows Logo + Profile Button

# MAIN APP LOGIC FOR TABS (Assistant, Rolodex, Analytics)
def render_executive_card(data):
    lead = data.get('lead_data', data)
    action = data.get('action', 'QUERY')
    lead_id = lead.get('id') or data.get('match_id')
    
    badge_text = "INTELLIGENCE REPORT"
    if action == "CREATE": badge_text = "NEW ASSET"
    elif action == "UPDATE": badge_text = "UPDATED"
    
    status = lead.get('status', 'Lead')
    outreach = lead.get('next_outreach')
    status_class = "bubble-client" if str(status).lower() == "client" else "bubble-lead"
    
    display_outreach = outreach
    ics_file = None
    if outreach:
        try:
            outreach_dt = datetime.fromisoformat(str(outreach))
            est_now = datetime.now() - timedelta(hours=5)
            delta_days = (outreach_dt.date() - est_now.date()).days
            
            if delta_days < 0: display_outreach = f"Overdue ({abs(delta_days)}d)"
            elif delta_days == 0: display_outreach = f"Today {outreach_dt.strftime('%I:%M %p')}"
            elif delta_days == 1: display_outreach = f"Tomorrow {outreach_dt.strftime('%I:%M %p')}"
            else: display_outreach = outreach_dt.strftime("%b %d %I:%M %p")
                
            ics_file = create_ics_string(lead.get('name', 'Client'), outreach_dt, lead.get('background', ''))
        except ValueError: pass

    bubbles_html = f'<span class="meta-bubble {status_class}">{status}</span>'
    if display_outreach:
        bubbles_html += f' <span class="meta-bubble bubble-outreach">⏰ {display_outreach}</span>'

    with st.container():
        st.markdown('<div class="airbnb-card">', unsafe_allow_html=True)
        c_head, c_edit_btn = st.columns([5, 1], vertical_alignment="top")
        
        with c_head:
            st.markdown(f"""
                <span class="status-badge">{badge_text}</span>
                <div class="card-title">
                    {lead.get('name') or 'Rolodex Query'}
                    {bubbles_html}
                </div>
            """, unsafe_allow_html=True)
            
        with c_edit_btn:
            if not st.session_state.is_editing:
                st.markdown('<div class="bold-left-marker"></div>', unsafe_allow_html=True)
                if st.button("Edit", key=f"edit_btn_{lead_id}", use_container_width=True):
                    st.session_state.is_editing = True
                    st.rerun()

        if st.session_state.is_editing:
            st.markdown("<br>", unsafe_allow_html=True)
            new_name = st.text_input("Name", value=lead.get('name', ''))
            new_status = st.selectbox("Status", ["Lead", "Client"], index=0 if status == "Lead" else 1)
            
            c_e1, c_e2 = st.columns(2)
            new_pitch = c_e1.text_input("Product Fit", value=lead.get('product_pitch', ''))
            new_contact = c_e2.text_input("Contact", value=lead.get('contact_info', ''))
            
            new_bg = st.text_area("Background / Notes", value=lead.get('background', ''))
            new_tx = st.text_area("Purchase History", value=lead.get('transactions', ''))
            new_outreach = st.text_input("Next Outreach", value=lead.get('next_outreach', ''))
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            cf1, cf2 = st.columns(2)
            with cf1:
                if st.button("Cancel", key="cancel_edit", use_container_width=True):
                    st.session_state.is_editing = False
                    st.rerun()
            with cf2:
                if st.button("Save Changes", key="save_edit", type="primary", use_container_width=True):
                    if lead_id:
                        updates = {
                            "name": new_name, "status": new_status, "product_pitch": new_pitch,
                            "contact_info": new_contact, "background": new_bg,
                            "transactions": new_tx, "next_outreach": new_outreach
                        }
                        try:
                            supabase.table("leads").update(updates).eq("id", lead_id).execute()
                            lead.update(updates)
                            st.session_state.is_editing = False
                            st.success("Saved.")
                            st.rerun()
                        except Exception as e: st.error(f"Error: {e}")
                    else: st.error("Missing ID")
                        
        else:
            html_body = f"""
<div class="stat-grid">
    <div class="stat-item"><div class="stat-label">Product Fit</div><div class="stat-value">{lead.get('product_pitch') or 'None specified'}</div></div>
    <div class="stat-item"><div class="stat-label">Contact</div><div class="stat-value">{format_contact_details(lead.get('contact_info'))}</div></div>
</div>
<div class="report-bubble"><div class="stat-label" style="color:#222; margin-bottom:8px;">Background / Notes</div><p style="font-size:14px; margin:0; line-height:1.6; color:#717171;">{lead.get('background') or '-'}</p></div>
<div class="transaction-bubble"><div class="stat-label" style="color:#222; margin-bottom:8px;">Purchase History</div><p style="font-size:14px; margin:0; line-height:1.6; color:#717171; white-space: pre-line;">{lead.get('transactions') or 'No recorded transactions.'}</p></div>
<div style="margin-bottom: 24px;"></div>
"""
            st.markdown(html_body, unsafe_allow_html=True)
            
            if lead.get('name'):
                c_dl1, c_dl2 = st.columns(2)
                vcf = create_vcard(data)
                safe_name = lead.get('name').strip().replace(" ", "_")
                
                with c_dl1:
                    st.markdown('<div class="bold-left-marker"></div>', unsafe_allow_html=True)
                    st.download_button("Save Contact", data=vcf, file_name=f"{safe_name}.vcf", mime="text/vcard", use_container_width=True)
                with c_dl2:
                    if ics_file:
                        st.markdown('<div class="bold-left-marker"></div>', unsafe_allow_html=True)
                        st.download_button("Add to Calendar", data=ics_file, file_name=f"Meeting_{safe_name}.ics", mime="text/calendar", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

def view_omni():
    if st.session_state.omni_result:
        if st.button("← New Search", type="secondary"):
            st.session_state.omni_result = None
            st.session_state.is_editing = False
            st.rerun()
        render_executive_card(st.session_state.omni_result)
        return

    st.markdown("<div style='height: 15vh;'></div>", unsafe_allow_html=True)
    c_mic_1, c_mic_2, c_mic_3 = st.columns([1, 1, 1])
    with c_mic_2:
        audio_val = st.audio_input("OmniInput", label_visibility="collapsed")
    
    if audio_val:
        with st.spinner("Analyzing Rolodex..."):
            existing_leads = load_leads_summary()
            result = process_omni_voice(audio_val.read(), existing_leads)
            
            if isinstance(result, list):
                result = result[0] if len(result) > 0 else {"error": "AI returned empty list."}

            if "error" in result: 
                st.error(result['error'])
            else:
                action = result.get('action')
                lead_data = result.get('lead_data', {})
                if action == "QUERY" and not lead_data.get('name'):
                    st.error("Audio unclear. Please try again.")
                    return

                if action == "CREATE": 
                    saved_record = save_new_lead(lead_data)
                    if saved_record and isinstance(saved_record, dict): result['lead_data']['id'] = saved_record.get('id')
                         
                elif action == "UPDATE" and result.get('match_id'): 
                    saved_data = update_existing_lead(result['match_id'], lead_data, existing_leads)
                    if isinstance(saved_data, dict): result['lead_data'] = saved_data
                    else: st.error(saved_data); return

                st.session_state.omni_result = result
                st.rerun()

def view_pipeline():
    if st.session_state.selected_lead:
        st.markdown('<div class="bold-left-marker"></div>', unsafe_allow_html=True)
        if st.button("← Back to List", key="back_to_list", type="secondary"):
            st.session_state.selected_lead = None
            st.session_state.is_editing = False
            st.rerun()
        render_executive_card({'lead_data': st.session_state.selected_lead, 'action': 'QUERY'})
        return

    st.markdown("<h2 style='padding: 24px 0 12px 0;'>Rolodex</h2>", unsafe_allow_html=True)
    if not st.session_state.user: return

    c_search, c_filter = st.columns([2, 1])
    with c_search: search_query = st.text_input("Search", placeholder="Find a name...", label_visibility="collapsed")
    with c_filter: filter_status = st.pills("Status", ["All", "Lead", "Client"], default="All", selection_mode="single", label_visibility="collapsed")

    st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)
    leads = supabase.table("leads").select("*").eq("user_id", st.session_state.user.id).order("created_at", desc=True).execute().data
    
    if not leads: st.info("Rolodex is empty."); return

    filtered_leads = []
    for l in leads:
        if search_query and search_query.lower() not in (l.get('name') or '').lower(): continue
        if filter_status and filter_status != "All" and (l.get('status') or 'Lead').lower() != filter_status.lower(): continue
        filtered_leads.append(l)

    if not filtered_leads: st.caption("No matching contacts found."); return

    for lead in filtered_leads:
        status = lead.get('status', 'Lead')
        name = lead.get('name', 'Unknown')
        is_client = str(status).strip().lower() == "client"
        markers = '<div class="rolodex-marker"></div>'
        if is_client: markers += '<div class="client-marker"></div>'
        st.markdown(markers, unsafe_allow_html=True)
        
        if st.button(name, key=f"card_{lead['id']}", use_container_width=True):
            st.session_state.selected_lead = lead
            st.rerun()

def view_analytics():
    st.markdown("<h2 style='padding:10px 0 20px 0;'>Performance</h2>", unsafe_allow_html=True)
    if not st.session_state.user: return
    
    leads = supabase.table("leads").select("*").eq("user_id", st.session_state.user.id).execute().data
    if not leads: st.info("Start adding leads to see your stats!"); return
        
    df = pd.DataFrame(leads)
    total_leads = len(df)
    clients = len(df[df['status'].astype(str).str.strip().str.lower() == 'client'])
    conversion_rate = int((clients / total_leads) * 100) if total_leads > 0 else 0
    
    if 'created_at' in df.columns:
        df['created_at'] = pd.to_datetime(df['created_at'])
        thirty_days_ago = pd.Timestamp.now(tz=df['created_at'].dt.tz) - pd.Timedelta(days=30)
        recent_leads = len(df[df['created_at'] >= thirty_days_ago])
    else: recent_leads = 0

    st.markdown(f"""
    <div class="analytics-card analytics-card-green"><div class="stat-title">CONVERSION RATE</div><div class="stat-metric">{conversion_rate}%</div><div class="stat-sub">{clients} Clients / {total_leads} Total Network</div></div>
    <div class="analytics-card analytics-card-red"><div class="stat-title">30-DAY HUSTLE</div><div class="stat-metric">+{recent_leads}</div><div class="stat-sub">New leads added recently</div></div>
    """, unsafe_allow_html=True)

tabs = { "🎙️ Assistant": "omni", "📇 Rolodex": "pipeline", "📊 Analytics": "analytics" }
rev_tabs = {v: k for k, v in tabs.items()}
current_label = rev_tabs.get(st.session_state.active_tab, "🎙️ Assistant")
selected_label = st.radio("Navigation", options=list(tabs.keys()), index=list(tabs.keys()).index(current_label), label_visibility="collapsed", horizontal=True, key="nav_radio")
if tabs[selected_label] != st.session_state.active_tab:
    st.session_state.active_tab = tabs[selected_label]
    st.session_state.is_editing = False
    st.rerun()

if st.session_state.active_tab == "omni": view_omni()
elif st.session_state.active_tab == "pipeline": view_pipeline()
elif st.session_state.active_tab == "analytics": view_analytics()
