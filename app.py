import streamlit as st
from google import genai
from google.genai import types
import os
import json
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
import stripe

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
if 'active_tab' not in st.session_state: st.session_state.active_tab = "omni" # Renamed from 'generate'
if 'omni_result' not in st.session_state: st.session_state.omni_result = None # Stores the current Executive Card data
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
# 3. CSS (Airbnb + Executive Style)
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
        
        /* --- INPUTS --- */
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
            float: right;
        }

        /* --- EXECUTIVE CARD STYLES --- */
        .exec-card {
            background: white;
            border: 1px solid #e0e0e0;
            border-radius: 16px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.08);
            overflow: hidden;
            margin-bottom: 24px;
        }
        .exec-header {
            background: #222;
            color: white;
            padding: 20px 24px;
        }
        .exec-title { font-size: 24px; font-weight: 700; color: white !important; margin: 0; }
        .exec-badge { 
            background: #FF385C; 
            color: white; 
            font-size: 10px; 
            font-weight: 800; 
            padding: 4px 8px; 
            border-radius: 4px; 
            text-transform: uppercase; 
            letter-spacing: 1px;
            display: inline-block;
            margin-bottom: 8px;
        }
        .exec-body { padding: 24px; }
        
        .briefing-box {
            background-color: #F7F7F7;
            border-left: 4px solid #FF385C;
            padding: 16px;
            border-radius: 0 8px 8px 0;
            margin-bottom: 24px;
        }
        .briefing-label { font-size: 11px; font-weight: 700; text-transform: uppercase; color: #FF385C; margin-bottom: 4px; }
        .briefing-text { font-size: 16px; font-weight: 500; color: #222; line-height: 1.5; }

        .stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }
        .stat-label { font-size: 11px; font-weight: 700; text-transform: uppercase; color: #888; }
        .stat-value { font-size: 15px; font-weight: 600; color: #222; margin-top: 4px; }

        /* --- BUTTONS --- */
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
        button[kind="secondary"] {
            background-color: transparent !important;
            color: #222 !important;
            border: 1px solid #e0e0e0 !important;
            box-shadow: none !important;
            border-radius: 12px !important;
            height: 50px !important;
        }

        /* Nav Buttons */
        .nav-fixed-container {
            position: fixed; bottom: 0; left: 0; width: 100%; background: #ffffff;
            border-top: 1px solid #f2f2f2; z-index: 999999; padding: 10px 0 20px 0;
        }
        .nav-btn button { background-color: transparent !important; color: #b0b0b0 !important; border: none !important; }
        .nav-active button { color: #FF385C !important; background-color: #FFF0F3 !important; border-radius: 20px !important; }
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
    """Fetches a lightweight list of leads to give context to the AI."""
    if not st.session_state.user or not supabase: return []
    try:
        # Fetch ID, Name, and Background to help AI identify matching contexts
        response = supabase.table("leads").select("id, name, background, contact_info").eq("user_id", st.session_state.user.id).execute()
        return response.data
    except: return []

def process_omni_voice(audio_bytes, existing_leads_context):
    """
    The Brain: Decides if we are Creating, Updating, or Querying.
    """
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
        "executive_brief": "A 2-sentence briefing for the user. e.g. 'I've updated Sarah's file. She is ready to buy but needs the contract today.' or 'According to your notes, John hates early morning calls.'",
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
        res = supabase.table("leads").insert(lead_data).execute()
        return None
    except Exception as e: return str(e)

def update_existing_lead(lead_id, new_data, old_background=""):
    """
    Updates specific fields. We append the new background/notes to the old one with a timestamp.
    """
    if not st.session_state.user: return "Not logged in"
    
    # Create a history-style log for the background field
    timestamp = datetime.now().strftime("%Y-%m-%d")
    new_note = f"\n[{timestamp}] UPDATE: {new_data.get('background', '')}"
    
    # We don't want to overwrite the whole background if we can help it, just append
    # But if the AI returns a full merged background, use that. 
    # For safety, let's trust the AI's "background" field if it seems complete, 
    # otherwise we append.
    
    final_data = {
        "sales_angle": new_data.get('sales_angle'),
        "product_pitch": new_data.get('product_pitch'),
        "follow_up": new_data.get('follow_up'),
        "contact_info": new_data.get('contact_info'),
        # Assuming the AI merges it, if not we could do logic here. 
        # We'll overwrite with the AI's version which should include the new context.
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
    if action == "CREATE": badge_text = "NEW ASSET ACQUIRED"
    elif action == "UPDATE": badge_text = "FILE UPDATED"
    
    st.markdown(f"""
        <div class="exec-card">
            <div class="exec-header">
                <div class="exec-badge">{badge_text}</div>
                <div class="exec-title">{lead.get('name', 'Rolodex Query')}</div>
            </div>
            <div class="exec-body">
                <div class="briefing-box">
                    <div class="briefing-label">Morning Briefing</div>
                    <div class="briefing-text">{brief}</div>
                </div>
                
                <div class="stat-grid">
                    <div>
                        <div class="stat-label">Strategy</div>
                        <div class="stat-value">{lead.get('sales_angle', '-')}</div>
                    </div>
                    <div>
                        <div class="stat-label">Next Step</div>
                        <div class="stat-value">{lead.get('follow_up', '-')}</div>
                    </div>
                    <div>
                        <div class="stat-label">Product Fit</div>
                        <div class="stat-value">{lead.get('product_pitch', '-')}</div>
                    </div>
                    <div>
                        <div class="stat-label">Contact</div>
                        <div class="stat-value">{lead.get('contact_info', '-')}</div>
                    </div>
                </div>
                
                <div style="margin-top:20px;">
                    <div class="stat-label">Background / Notes</div>
                    <p style="font-size:14px; margin-top:5px; line-height:1.6;">{lead.get('background', '-')}</p>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Action Buttons
    c1, c2 = st.columns(2)
    with c1:
        if lead.get('name'):
            vcf = create_vcard(data)
            safe_name = lead.get('name').strip().replace(" ", "_")
            st.download_button("Export to Contacts", data=vcf, file_name=f"{safe_name}.vcf", mime="text/vcard", use_container_width=True, type="primary")
    with c2:
        if st.button("Close File", type="secondary", use_container_width=True):
            st.session_state.omni_result = None
            st.rerun()

def view_omni():
    """The New Omni-Assistant Interface"""
    # Header
    c1, c2 = st.columns([8, 1]) 
    with c1:
        st.markdown("<h2 style='margin-top:10px;'>Omni-Assistant</h2>", unsafe_allow_html=True)
    with c2:
        with st.popover("👤"):
            if st.button("Sign Out"):
                supabase.auth.sign_out()
                st.session_state.user = None
                st.rerun()

    # Main Interaction Area
    if not st.session_state.omni_result:
        st.markdown("""
            <div style="text-align: center; padding: 40px 20px;">
                <div style="font-size: 60px; margin-bottom: 10px;">🎙️</div>
                <p style="font-size: 18px; color: #222; font-weight:600;">Tap to Speak</p>
                <p style="font-size: 14px; color: #888;">"Create a lead for John..."<br>"Update Sarah's file..."<br>"What did I promise Mike?"</p>
            </div>
        """, unsafe_allow_html=True)
        
        audio_val = st.audio_input("OmniInput", label_visibility="collapsed")
        
        if audio_val:
            with st.spinner("Analyzing Rolodex..."):
                # 1. Get Context
                existing_leads = load_leads_summary()
                
                # 2. Process with AI
                result = process_omni_voice(audio_val.read(), existing_leads)
                
                if "error" in result:
                    st.error(result['error'])
                else:
                    # 3. Execute Database Actions
                    action = result.get('action')
                    lead_data = result.get('lead_data', {})
                    
                    if action == "CREATE":
                        save_new_lead(lead_data)
                    elif action == "UPDATE" and result.get('match_id'):
                        update_existing_lead(result['match_id'], lead_data)
                    
                    # 4. Show Result
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
        with st.expander(f"{lead.get('name', 'Unknown')} - {lead.get('sales_angle', '')}"):
            st.write(lead.get('background'))
            st.caption(f"Last updated: {lead.get('created_at')[:10]}")

def view_analytics():
    st.markdown("<h2 style='padding:20px 0 10px 0;'>Analytics</h2>", unsafe_allow_html=True)
    if not st.session_state.user: return
    leads = supabase.table("leads").select("*").eq("user_id", st.session_state.user.id).execute().data
    if not leads: 
        st.warning("No data.") 
        return
        
    df = pd.DataFrame(leads)
    st.metric("Total Network", len(leads))
    st.bar_chart(df['product_pitch'].value_counts())

# ==========================================
# 7. MAIN ROUTER
# ==========================================
if not st.session_state.user:
    # --- LOGIN SCREEN (Reuse existing logic simplified for brevity) ---
    st.markdown("<h1 style='text-align: center;'>The Closer</h1>", unsafe_allow_html=True)
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

# --- SUBSCRIPTION GATE (Preserved) ---
if not st.session_state.is_subscribed:
    if "session_id" in st.query_params:
        st.session_state.is_subscribed = check_subscription_status(st.session_state.user.email)
        if st.session_state.is_subscribed: st.rerun()
    
    st.markdown("<br><br><h1 style='text-align:center'>Premium Access Required</h1>", unsafe_allow_html=True)
    if st.button("Subscribe ($15/mo)", type="primary"):
        url = create_checkout_session(st.session_state.user.email, st.session_state.user.id)
        if url: st.link_button("Go to Checkout", url, type="primary")
    st.stop()

# --- VIEW ROUTING ---
if st.session_state.active_tab == "omni": view_omni()
elif st.session_state.active_tab == "pipeline": view_pipeline()
elif st.session_state.active_tab == "analytics": view_analytics()

st.markdown("<div style='height: 100px;'></div>", unsafe_allow_html=True)

# --- NAVIGATION BAR ---
with st.container():
    st.markdown('<div class="nav-fixed-container">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    def nav_btn(col, label, target, icon):
        with col:
            cls = "nav-active" if st.session_state.active_tab == target else "nav-btn"
            st.markdown(f'<div class="{cls}">', unsafe_allow_html=True)
            if st.button(f"{icon} {label}", key=f"nav_{target}", use_container_width=True):
                st.session_state.active_tab = target
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
    
    nav_btn(c1, "Assistant", "omni", "🎙️")
    nav_btn(c2, "Rolodex", "pipeline", "📇")
    nav_btn(c3, "Analytics", "analytics", "📈")
    st.markdown('</div>', unsafe_allow_html=True)
