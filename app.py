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
    page_icon=None,  # Removed emoji
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Initialize Session State
if 'user' not in st.session_state: st.session_state.user = None
if 'is_subscribed' not in st.session_state: st.session_state.is_subscribed = False
if 'active_tab' not in st.session_state: st.session_state.active_tab = "command_center"
if 'referral_captured' not in st.session_state: st.session_state.referral_captured = None
if 'user_profile' not in st.session_state: st.session_state.user_profile = None
if 'last_command_result' not in st.session_state: st.session_state.last_command_result = None 

# --- CAPTURE REFERRAL CODE (STICKY) ---
if not st.session_state.referral_captured:
    try:
        query_params = st.query_params
        if "ref" in query_params:
            ref_val = query_params["ref"]
            if isinstance(ref_val, list): st.session_state.referral_captured = ref_val[0]
            else: st.session_state.referral_captured = ref_val
    except: pass

# ==========================================
# 2. CONNECTIONS
# ==========================================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8501")

@st.cache_resource
def init_supabase():
    if SUPABASE_URL and SUPABASE_KEY: return create_client(SUPABASE_URL, SUPABASE_KEY)
    return None

supabase = init_supabase()
if STRIPE_SECRET_KEY: stripe.api_key = STRIPE_SECRET_KEY

# ==========================================
# 3. EXECUTIVE CSS (Fixed Login & Mic)
# ==========================================
st.markdown("""
    <style>
        /* BASE RESET */
        .stApp { background-color: #ffffff; color: #222; font-family: 'Helvetica Neue', sans-serif; }
        [data-testid="stHeader"] { display: none; }
        footer {visibility: hidden;}
        
        h1, h2, h3 { color: #222 !important; font-weight: 800 !important; letter-spacing: -0.5px; }
        p, label, span, div { color: #555; }
        
        /* INPUTS (Fixed Visibility) */
        /* Forces inputs to have white background and dark text for readability */
        div[data-baseweb="input"], div[data-baseweb="base-input"] { 
            background-color: #ffffff !important; 
            border: 1px solid #e0e0e0 !important; 
            border-radius: 12px !important; 
        }
        input.st-bd, input.st-bc, input { 
            background-color: #ffffff !important; 
            color: #000000 !important; 
            -webkit-text-fill-color: #000000 !important;
            caret-color: #FF385C !important;
        }
        
        /* MINIMALIST MICROPHONE */
        /* Strips the heavy styling to make it a clean pill */
        [data-testid="stAudioInput"] {
            border-radius: 50px !important;
            border: 1px solid #eee !important;
            background-color: #fff !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05) !important;
            padding: 5px 15px !important; /* Smaller padding */
            width: 100% !important;
            max-width: 60px !important; /* Forces it small */
            margin: 0 auto !important;
            min-height: 50px !important;
        }
        /* Hide the waveform visualization to keep it minimal */
        [data-testid="stAudioInputCanvas"] { display: none !important; }
        
        /* PAYWALL & PROFILE */
        .paywall-container { text-align: center; padding: 40px 20px; max-width: 500px; margin: 0 auto; }
        .price-tag { font-size: 32px; font-weight: 800; color: #222; margin: 20px 0; }
        .balance-card { background-color: #f7f7f7; padding: 15px; border-radius: 12px; text-align: center; margin-bottom: 15px; border: 1px solid #e0e0e0; }
        .balance-amount { font-size: 24px; font-weight: 800; color: #222; margin-top: 5px; }
        
        /* BUTTONS */
        button[kind="primary"] { background-color: #FF385C !important; color: white !important; border-radius: 12px !important; padding: 12px 24px !important; font-weight: 600 !important; border: none !important; height: 50px !important; width: 100% !important; box-shadow: 0 4px 12px rgba(255, 56, 92, 0.2) !important; }
        button[kind="primary"]:hover { background-color: #d90b3e !important; }
        button[kind="secondary"] { background-color: transparent !important; color: #222 !important; border: 1px solid #e0e0e0 !important; box-shadow: none !important; border-radius: 12px !important; height: 50px !important; }

        /* EXECUTIVE CARD UI */
        .airbnb-card { background: white; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); padding: 30px; margin-bottom: 10px; border: 1px solid #f0f0f0; }
        .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid #f0f0f0; padding-bottom: 15px; }
        .card-title { font-size: 28px; font-weight: 800; color: #222; margin: 0; }
        .card-badge { background-color: #222; padding: 6px 12px; border-radius: 8px; font-size: 12px; font-weight: 700; color: #fff; text-transform: uppercase; letter-spacing: 1px; }
        .strategy-box { background-color: #FFF0F3; border-left: 6px solid #FF385C; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
        .strategy-title { color: #FF385C; font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 6px; display: block; }
        .strategy-text { color: #222; font-weight: 700; font-size: 18px; line-height: 1.4; }
        .intel-box { color: #444; font-size: 15px; line-height: 1.8; }
        
        /* NAVIGATION */
        .nav-fixed-container { position: fixed; bottom: 0; left: 0; width: 100%; background: #ffffff; border-top: 1px solid #f2f2f2; z-index: 999999; padding: 10px 0 20px 0; box-shadow: 0 -2px 10px rgba(0,0,0,0.02); }
        .nav-btn button { background-color: transparent !important; color: #b0b0b0 !important; border: none !important; font-size: 10px !important; font-weight: 600 !important; text-transform: uppercase !important; }
        .nav-active button { color: #FF385C !important; background-color: #FFF0F3 !important; border-radius: 20px !important; }
        
        /* EXPANDER STYLING (For Rolodex) */
        .streamlit-expanderHeader { background-color: #fff !important; font-weight: 700 !important; color: #222 !important; border-radius: 12px !important; border: 1px solid #eee !important; }
        .streamlit-expanderContent { border: none !important; box-shadow: none !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 4. SUBSCRIPTION & REFERRAL LOGIC
# ==========================================
def fetch_user_profile(user_id):
    try:
        response = supabase.table("profiles").select("*").eq("id", user_id).execute()
        return response.data[0] if response.data else None
    except: return None

def calculate_commissions(profile):
    if not STRIPE_SECRET_KEY or not profile or not profile.get('referral_code'): return 0.0
    try:
        my_code = profile.get('referral_code')
        referred_users = supabase.table("profiles").select("email").eq("referred_by", my_code).execute()
        if not referred_users.data: return 0.0
        total_revenue = 0.0
        for user in referred_users.data:
            email = user['email']
            customers = stripe.Customer.list(email=email, limit=1).data
            if customers:
                invoices = stripe.Invoice.list(customer=customers[0].id, status='paid', limit=100)
                for inv in invoices.data: total_revenue += (inv.amount_paid / 100)
        return round(total_revenue * 0.20, 2)
    except: return 0.0

def check_subscription_status(email):
    if not STRIPE_SECRET_KEY: return True 
    try:
        customers = stripe.Customer.list(email=email).data
        if not customers: return False
        subscriptions = stripe.Subscription.list(customer=customers[0].id, status='active').data
        return True if subscriptions else False
    except: return False

def create_checkout_session(email, user_id):
    try:
        customers = stripe.Customer.list(email=email).data
        if customers: customer_id = customers[0].id
        else: customer = stripe.Customer.create(email=email).id
        profile = fetch_user_profile(user_id)
        metadata = {'referred_by': profile.get('referred_by')} if profile and profile.get('referred_by') else {}
        session = stripe.checkout.Session.create(
            customer=customer_id, payment_method_types=['card'], line_items=[{'price': STRIPE_PRICE_ID, 'quantity': 1}],
            mode='subscription', success_url=f"{APP_BASE_URL}?session_id={{CHECKOUT_SESSION_ID}}", cancel_url=f"{APP_BASE_URL}", metadata=metadata
        )
        return session.url
    except: return None

# ==========================================
# 5. BACKEND LOGIC (THE OMNI-TOOL ENGINE)
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

def process_voice_command(audio_bytes):
    prompt = """
    You are an Executive Assistant. Listen to the user's voice command.
    Classify the intent into one of two categories:
    
    1. 'UPDATE': The user is providing new information about a lead (e.g., "I just met Ryan", "Update Sarah's file").
    2. 'RETRIEVE': The user is asking to see a file (e.g., "Pull up Ryan", "Who is Sarah?", "Show me the plumber").

    Return JSON:
    {
        "intent": "UPDATE" or "RETRIEVE",
        "name_query": "The name or keyword to search for (e.g., 'Ryan Sherman'). IF NEW, extract the full name carefully.",
        "context_payload": "If UPDATE, extract the raw notes provided. If RETRIEVE, leave null."
    }
    """
    try:
        response = client.models.generate_content(
            model=TEXT_MODEL_ID, contents=[types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"), prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(clean_json_string(response.text))
    except Exception as e: return {"error": str(e)}

def synthesize_dossier(existing_lead, new_input):
    prompt = f"""
    You are a Chief of Staff. Rewrite this client dossier.
    - Merge new info into existing bullet points.
    - Remove outdated info.
    - Keep it high-level and executive.
    
    OLD: {existing_lead.get('background')} | Strategy: {existing_lead.get('sales_angle')}
    NEW INPUT: {new_input}
    
    RETURN JSON:
    {{ "sales_angle": "Updated Strategy", "background": "• Point 1\\n• Point 2...", "follow_up": "Next Step" }}
    """
    try:
        response = client.models.generate_content(
            model=TEXT_MODEL_ID, contents=prompt, config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(clean_json_string(response.text))
    except: return None

def execute_command(command_data):
    if not st.session_state.user: return "Not logged in"
    user_id = st.session_state.user.id
    intent = command_data.get('intent')
    query = command_data.get('name_query')
    
    if not query: return {"status": "error", "msg": "Could not identify who you are talking about."}

    # 1. Search DB for the person
    existing = None
    try:
        res = supabase.table("leads").select("*").eq("user_id", user_id).ilike("name", f"%{query}%").execute()
        if res.data: existing = res.data[0]
    except: pass

    # --- PATH A: RETRIEVE ---
    if intent == "RETRIEVE":
        if existing:
            return {"status": "success", "type": "card", "data": existing}
        else:
            return {"status": "error", "msg": f"No dossier found for '{query}'."}

    # --- PATH B: UPDATE (or CREATE) ---
    elif intent == "UPDATE":
        context = command_data.get('context_payload', '')
        
        if existing:
            # Update Existing
            new_dossier = synthesize_dossier(existing, context)
            if new_dossier:
                supabase.table("leads").update({
                    "background": new_dossier.get('background'),
                    "sales_angle": new_dossier.get('sales_angle'),
                    "follow_up": new_dossier.get('follow_up')
                }).eq("id", existing['id']).execute()
                updated_row = supabase.table("leads").select("*").eq("id", existing['id']).execute().data[0]
                return {"status": "success", "type": "card", "data": updated_row, "msg": "Dossier Updated."}
        else:
            # Create New - NAME FIX APPLIED HERE
            # We explicitly use the 'query' (which is the extracted name from the Router)
            # as the name for the new file.
            init_dossier = synthesize_dossier({"background": "", "sales_angle": ""}, context)
            if init_dossier:
                # Format name nicely (e.g. "ryan sherman" -> "Ryan Sherman")
                clean_name = query.title() 
                new_lead = {
                    "user_id": user_id,
                    "name": clean_name, # <--- Fix 1: Use extracted name
                    "created_at": datetime.now().isoformat(),
                    "background": init_dossier.get('background'),
                    "sales_angle": init_dossier.get('sales_angle'),
                    "follow_up": init_dossier.get('follow_up')
                }
                data = supabase.table("leads").insert(new_lead).execute()
                if data.data:
                    return {"status": "success", "type": "card", "data": data.data[0], "msg": f"New Dossier: {clean_name}"}
            
    return {"status": "error", "msg": "Could not process command."}

def load_leads():
    if not st.session_state.user: return []
    try: return supabase.table("leads").select("*").eq("user_id", st.session_state.user.id).order("created_at", desc=True).execute().data
    except: return []

# ==========================================
# 6. LOGIN SCREEN
# ==========================================
def login_screen():
    st.markdown("<h1 style='text-align: center; margin-bottom: 30px;'>The Closer</h1>", unsafe_allow_html=True)
    if st.session_state.referral_captured: st.info(f"🎉 Invite Applied: {st.session_state.referral_captured}")

    tab_login, tab_signup = st.tabs(["Log In", "Sign Up"])
    
    with tab_login:
        st.markdown("<br>", unsafe_allow_html=True)
        email = st.text_input("Email", key="l_email")
        password = st.text_input("Password", type="password", key="l_pass")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Log In", type="primary", use_container_width=True):
            if supabase:
                try:
                    res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    st.session_state.user = res.user
                    st.session_state.is_subscribed = check_subscription_status(res.user.email)
                    st.session_state.user_profile = fetch_user_profile(res.user.id)
                    if st.session_state.referral_captured and st.session_state.user_profile:
                        if not st.session_state.user_profile.get('referred_by'):
                            try: supabase.table("profiles").update({"referred_by": st.session_state.referral_captured}).eq("id", res.user.id).execute()
                            except: pass
                    st.rerun()
                except Exception as e: st.error(f"Login failed: {e}")

    with tab_signup:
        st.markdown("<br>", unsafe_allow_html=True)
        email = st.text_input("Email", key="s_email")
        password = st.text_input("Password", type="password", key="s_pass")
        st.markdown("<br>", unsafe_allow_html=True)
        
        btn_label = f"Create Account (Ref: {st.session_state.referral_captured})" if st.session_state.referral_captured else "Create Account"
        if st.button(btn_label, type="primary", use_container_width=True):
            if supabase:
                try:
                    meta = {}
                    if st.session_state.referral_captured: meta["referred_by"] = st.session_state.referral_captured
                    
                    res = supabase.auth.sign_up({"email": email, "password": password, "options": {"data": meta}})
                    
                    if res.user:
                        st.session_state.user = res.user
                        st.session_state.is_subscribed = check_subscription_status(res.user.email)
                        st.session_state.user_profile = fetch_user_profile(res.user.id)
                        st.success("Account created! Logging in...")
                        st.rerun()
                    else: st.warning("Please verify email manually.")
                except Exception as e: st.error(f"Signup failed: {e}")

# ==========================================
# 7. MAIN APP ROUTER (Auth Guard Moved Here)
# ==========================================
if not st.session_state.user:
    login_screen()
    st.stop()

def render_header():
    if not st.session_state.user_profile: st.session_state.user_profile = fetch_user_profile(st.session_state.user.id)
    c1, c2 = st.columns([8, 1])
    with c2:
        with st.popover("👤"):
            if st.session_state.user_profile:
                earnings = calculate_commissions(st.session_state.user_profile)
                st.markdown(f"**Lifetime Earnings:** ${earnings:.2f}")
                if st.button("Sign Out"):
                    supabase.auth.sign_out()
                    st.session_state.clear()
                    st.rerun()

# --- SUBSCRIPTION GATE ---
if not st.session_state.is_subscribed:
    if "session_id" in st.query_params:
        st.session_state.is_subscribed = check_subscription_status(st.session_state.user.email)
        if st.session_state.is_subscribed: st.rerun()
    render_header()
    st.markdown("""<div class="paywall-container"><h1>The Closer</h1><div class="price-tag">$15/mo</div></div>""", unsafe_allow_html=True)
    if st.button("Subscribe", type="primary", use_container_width=True):
        url = create_checkout_session(st.session_state.user.email, st.session_state.user.id)
        if url: st.link_button("Checkout", url, type="primary", use_container_width=True)
    st.stop()

# --- TAB 1: THE OMNI-TOOL (COMMAND CENTER) ---
def view_command_center():
    render_header()
    
    st.markdown("""
        <div class="omni-container">
            <div class="omni-title">How can I help?</div>
            <div class="omni-sub">Tap to Create, Update, or Retrieve Dossiers</div>
        </div>
    """, unsafe_allow_html=True)
    
    # 1. The Microphone (Fix 4: Minimalist)
    audio = st.audio_input("Command", label_visibility="collapsed")
    
    # 2. Processor
    if audio:
        with st.spinner("Processing..."):
            # A. Parse Intent
            command = process_voice_command(audio.read())
            
            if "error" not in command:
                # B. Execute Intent
                result = execute_command(command)
                st.session_state.last_command_result = result
                st.rerun()
            else:
                st.error("Could not understand audio.")

    # 3. Result Display
    res = st.session_state.last_command_result
    if res:
        if res['status'] == 'success' and res.get('type') == 'card':
            if res.get('msg'): st.toast(res['msg'], icon="✅")
            
            lead = res['data']
            st.markdown(f"""
            <div class="airbnb-card">
                <div class="card-header">
                    <h3 class="card-title">{lead['name']}</h3>
                    <span class="card-badge">{lead.get('follow_up', 'Active')}</span>
                </div>
                
                <div class="strategy-box">
                    <span class="strategy-title">The Strategy</span>
                    <span class="strategy-text">{lead['sales_angle']}</span>
                </div>
                
                <div class="intel-box">
                    <strong>Executive Briefing:</strong><br>
                    {lead['background']} 
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("Close Dossier", type="secondary", use_container_width=True):
                st.session_state.last_command_result = None
                st.rerun()
                
        elif res['status'] == 'error':
            st.error(res['msg'])

# --- TAB 2: THE ROLODEX (Fix 3: Sleek Expandable Cards) ---
def view_rolodex():
    render_header()
    st.markdown("## Full Rolodex")
    leads = load_leads()
    for lead in leads:
        # Expander acts as the "Closed" state (Just Name)
        with st.expander(f"📂 {lead['name']}", expanded=False):
            # Inside is the sleek executive card
            st.markdown(f"""
            <div class="airbnb-card">
                <div class="card-header">
                    <h3 class="card-title">{lead['name']}</h3>
                    <span class="card-badge">{lead.get('follow_up', 'No Action')}</span>
                </div>
                <div class="strategy-box">
                    <span class="strategy-title">The Strategy</span>
                    <span class="strategy-text">{lead['sales_angle']}</span>
                </div>
                <div class="intel-box">
                    <strong>Key Intel:</strong><br>
                    {lead['background']} 
                </div>
            </div>
            """, unsafe_allow_html=True)

def view_analytics():
    render_header()
    st.markdown("## Analytics")
    leads = load_leads()
    st.metric("Total Dossiers", len(leads))

# --- ROUTER ---
if st.session_state.active_tab == "command_center": view_command_center()
elif st.session_state.active_tab == "rolodex": view_rolodex()
elif st.session_state.active_tab == "analytics": view_analytics()

# --- BOTTOM NAV ---
st.markdown("<div style='height: 100px;'></div>", unsafe_allow_html=True)
with st.container():
    st.markdown('<div class="nav-fixed-container">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    def nav(col, label, key):
        with col:
            cls = "nav-active" if st.session_state.active_tab == key else "nav-btn"
            st.markdown(f'<div class="{cls}">', unsafe_allow_html=True)
            if st.button(label, key=f"nav_{key}", use_container_width=True): st.session_state.active_tab = key; st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
    nav(c1, "Assistant", "command_center")
    nav(c2, "Rolodex", "rolodex")
    nav(c3, "Stats", "analytics")
    st.markdown('</div>', unsafe_allow_html=True)
