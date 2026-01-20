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
# TRACK SELECTED LEAD
if 'selected_lead' not in st.session_state: st.session_state.selected_lead = None
if 'referral_captured' not in st.session_state: st.session_state.referral_captured = None

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
# 3. CSS (CLAIMSCRIBE STYLE + NATIVE FEEL)
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
            height: 100vh;
            overflow-y: auto !important;
            overflow-x: hidden;
            padding-top: max(env(safe-area-inset-top), 20px) !important;
            padding-bottom: 100px !important;
            padding-left: 20px !important;
            padding-right: 20px !important;
            -webkit-overflow-scrolling: touch;
        }

        /* --- 3. CUSTOM NAV (STYLING RADIO BUTTONS) --- */
        [data-testid="stRadio"] div[role="radiogroup"] {
            display: flex;
            flex-direction: row;
            justify-content: center !important; 
            width: 100% !important;
            overflow-x: auto;
            white-space: nowrap;
            gap: 24px;
            border-bottom: 1px solid #F2F2F2;
            padding-bottom: 0px;
            margin-bottom: 24px;
            -webkit-overflow-scrolling: touch;
        }
        [data-testid="stRadio"] label > div:first-child { display: none !important; }
        [data-testid="stRadio"] label {
            padding: 12px 0px !important;
            margin-right: 0px !important;
            border-bottom: 3px solid transparent;
            transition: all 0.2s ease;
            cursor: pointer;
        }
        [data-testid="stRadio"] label p {
            font-size: 15px !important;
            font-weight: 600 !important;
            color: #717171 !important;
            margin: 0 !important;
        }
        [data-testid="stRadio"] label:has(input:checked) { border-bottom-color: #FF385C !important; }
        [data-testid="stRadio"] label:has(input:checked) p { color: #222222 !important; }

        /* --- 4. CARDS & BUBBLES --- */
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
            margin-bottom: 8px;
            display: inline-block;
        }
        .card-title {
            font-size: 22px;
            font-weight: 800;
            color: #222222;
            margin: 0;
            line-height: 1.2;
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 8px;
        }
        
        /* META BUBBLES */
        .meta-bubble {
            font-size: 12px;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 12px;
            border: 1px solid #EBEBEB;
            white-space: nowrap;
            vertical-align: middle;
            display: inline-flex;
            align-items: center;
        }
        .bubble-client { background-color: #E6FFFA; color: #008a73; border-color: #008a73; }
        .bubble-lead { background-color: #EBF8FF; color: #2C5282; border-color: #2C5282; }
        .bubble-outreach { background-color: #FFFFF0; color: #D69E2E; border-color: #D69E2E; }
        
        /* SECTIONS */
        .report-bubble {
            background-color: #F7F7F7;
            border-radius: 16px;
            padding: 20px;
            margin-top: 16px;
            border: 1px solid #EBEBEB;
        }
        .transaction-bubble {
            background-color: #F0FFF4;
            border-radius: 16px;
            padding: 20px;
            margin-top: 16px;
            border: 1px solid #C6F6D5;
        }

        /* --- 5. ROLODEX BUTTONS --- */
        .stButton > button {
            background-color: #FFE5E5 !important;
            border: 1px solid #000000 !important;
            border-radius: 12px !important;
            box-shadow: 0 2px 8px rgba(0,0,0,0.04) !important;
            color: #000000 !important;
            font-weight: 700 !important;
            padding: 16px 20px !important;
            text-align: left !important;
            display: flex !important;
            justify-content: flex-start !important;
            align-items: center !important;
            height: auto !important;
            min-height: 60px !important;
            width: 100% !important;
        }
        .stButton > button p { font-weight: 700 !important; text-align: left !important; }
        .stButton > button:active, .stButton > button:focus:not(:active) {
            transform: scale(0.98);
            background-color: #FFD1D1 !important;
        }
        button[kind="primary"] {
            background-color: #FF385C !important;
            color: white !important;
            border: none !important;
            text-align: center !important;
            justify-content: center !important;
        }
        button[kind="primary"] p { text-align: center !important; }

        /* --- 6. INPUTS & UTILS --- */
        div[data-baseweb="input"] { background-color: #F7F7F7 !important; border: 1px solid transparent !important; border-radius: 12px !important; }
        div[data-baseweb="input"]:focus-within { border: 1px solid #222222 !important; background-color: #FFFFFF !important; }
        input { color: #222222 !important; font-weight: 500 !important; caret-color: #FF385C !important; }
        [data-testid="stAudioInput"] { background-color: #F7F7F7 !important; border-radius: 50px !important; border: none !important; color: #222 !important; padding: 5px !important; }
        
        .stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 20px; }
        .stat-item { background: #F7F7F7; padding: 12px; border-radius: 12px; }
        .stat-label { font-size: 10px; font-weight: 700; text-transform: uppercase; color: #717171; letter-spacing: 0.5px; }
        .stat-value { font-size: 14px; font-weight: 600; color: #222222; margin-top: 4px; line-height: 1.3; }
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
        # Load all relevant fields including transactions
        response = supabase.table("leads").select("id, name, background, contact_info, status, next_outreach, transactions").eq("user_id", st.session_state.user.id).execute()
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
       - If they are describing a NEW person -> Action: "CREATE"
       - If they are adding info/updating -> Action: "UPDATE"
       - If just asking -> Action: "QUERY"
    
    CRITICAL RULES FOR UPDATING:
    - **SEPARATION OF CONCERNS**: 'Background' and 'Transactions' are separate. 
    - **BACKGROUND PRESERVATION**: If recording a transaction, do NOT change the 'background' field unless the user explicitly provides new narrative context. If no new background info is given, return the existing background string EXACTLY as is. Do not wipe it.
    - **TRANSACTION LOGGING**: If a sale/deal occurred, append the details to 'transactions'. Do NOT put transaction logs in the background.
    - **STATUS**: If a sale occurred, set "status" to "Client".
    - **OUTPUT**: You must return the FULLY updated lead record.
    
    RETURN ONLY RAW JSON:
    {{
        "action": "CREATE" | "UPDATE" | "QUERY",
        "match_id": (Integer ID if UPDATE matches),
        "lead_data": {{
            "name": "Full Name",
            "contact_info": "Phone/Email",
            "background": "The executive summary (Preserve existing if not changed)",
            "product_pitch": "Product interest",
            "status": "Lead" | "Client",
            "next_outreach": "Date/Timeframe" (or null),
            "transactions": "List of items sold (String)" (or null)
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
    if not st.session_state.user: return "Not logged in"
    lead_data['user_id'] = st.session_state.user.id
    lead_data['created_at'] = datetime.now().isoformat()
    if not lead_data.get('status'): lead_data['status'] = 'Lead'
    
    try: 
        res = supabase.table("leads").insert(lead_data).execute()
        return None
    except Exception as e: return str(e)

def update_existing_lead(lead_id, new_data, existing_leads_context):
    if not st.session_state.user: return "Not logged in"
    
    # 1. FIND ORIGINAL DATA TO MERGE
    # This prevents the AI from accidentally wiping a field by returning null
    original = next((item for item in existing_leads_context if item["id"] == lead_id), {})
    
    # 2. CONSTRUCT MERGED UPDATE
    # Priority: New Data > Original Data > Empty
    final_data = {
        "name": new_data.get('name') or original.get('name'),
        "contact_info": new_data.get('contact_info') or original.get('contact_info'),
        "product_pitch": new_data.get('product_pitch') or original.get('product_pitch'),
        
        # Explicit preservation logic for Background
        # If AI returns empty string but we had one, keep the old one unless intent was to clear it (unlikely)
        "background": new_data.get('background') if new_data.get('background') else original.get('background'),
        
        "status": new_data.get('status') or original.get('status'),
        "next_outreach": new_data.get('next_outreach'), # Can be null if cleared
        "transactions": new_data.get('transactions') or original.get('transactions')
    }

    try:
        supabase.table("leads").update(final_data).eq("id", lead_id).execute()
        return final_data # Return what we actually saved for display
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

# ==========================================
# 6. APP VIEWS
# ==========================================

def render_executive_card(data, show_close=True):
    """Display the sleek Omni-Tool Output"""
    lead = data.get('lead_data', {})
    action = data.get('action', 'QUERY')
    
    badge_text = "INTELLIGENCE REPORT"
    if action == "CREATE": badge_text = "NEW ASSET"
    elif action == "UPDATE": badge_text = "UPDATED"
    
    # --- PREPARE BUBBLES ---
    status = lead.get('status', 'Lead')
    outreach = lead.get('next_outreach')
    
    status_class = "bubble-client" if str(status).lower() == "client" else "bubble-lead"
    
    bubbles_html = f'<span class="meta-bubble {status_class}">{status}</span>'
    if outreach:
        bubbles_html += f' <span class="meta-bubble bubble-outreach">⏰ {outreach}</span>'

    html_content = f"""
        <div class="airbnb-card">
            <div class="card-header">
                <div>
                    <span class="status-badge">{badge_text}</span>
                    <div class="card-title">
                        {lead.get('name') or 'Rolodex Query'}
                        {bubbles_html}
                    </div>
                </div>
            </div>
            
            <div class="stat-grid">
                <div class="stat-item">
                    <div class="stat-label">Product Fit</div>
                    <div class="stat-value">{lead.get('product_pitch') or 'None specified'}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Contact</div>
                    <div class="stat-value">{lead.get('contact_info') or '-'}</div>
                </div>
            </div>
            
            <div class="report-bubble">
                <div class="stat-label" style="color:#222; margin-bottom:8px;">Background / Notes</div>
                <p style="font-size:14px; margin:0; line-height:1.6; color:#717171;">{lead.get('background') or '-'}</p>
            </div>

            <div class="transaction-bubble">
                <div class="stat-label" style="color:#222; margin-bottom:8px;">Purchase History</div>
                <p style="font-size:14px; margin:0; line-height:1.6; color:#717171;">{lead.get('transactions') or 'No recorded transactions.'}</p>
            </div>
        </div>
    """.replace("\n", " ")
    
    st.markdown(html_content, unsafe_allow_html=True)
    
    if show_close:
        c1, c2 = st.columns(2)
        with c1:
            if lead.get('name'):
                vcf = create_vcard(data)
                safe_name = lead.get('name').strip().replace(" ", "_")
                st.download_button("Save Contact", data=vcf, file_name=f"{safe_name}.vcf", mime="text/vcard", use_container_width=True, type="primary")
        with c2:
            if st.button("Close File", use_container_width=True, type="secondary"):
                st.session_state.omni_result = None
                st.session_state.selected_lead = None
                st.rerun()

def view_omni():
    # If a result exists, show the card.
    if st.session_state.omni_result:
        render_executive_card(st.session_state.omni_result, show_close=True)
        return

    # --- Minimal Omni Layout ---
    st.markdown("<div style='height: 15vh;'></div>", unsafe_allow_html=True)
    c_mic_1, c_mic_2, c_mic_3 = st.columns([1, 1, 1])
    with c_mic_2:
        audio_val = st.audio_input("OmniInput", label_visibility="collapsed")
    
    if audio_val:
        with st.spinner("Analyzing Rolodex..."):
            existing_leads = load_leads_summary()
            result = process_omni_voice(audio_val.read(), existing_leads)
            
            if "error" in result: 
                st.error(result['error'])
            else:
                action = result.get('action')
                lead_data = result.get('lead_data', {})
                
                if action == "CREATE": 
                    save_new_lead(lead_data)
                elif action == "UPDATE" and result.get('match_id'): 
                    # --- CRITICAL FIX: Merge & Save, then update display ---
                    saved_data = update_existing_lead(result['match_id'], lead_data, existing_leads)
                    
                    if isinstance(saved_data, dict):
                        # Ensure the display reflects exactly what was saved to DB
                        result['lead_data'] = saved_data
                    else:
                        st.error(f"Save Failed: {saved_data}")

                st.session_state.omni_result = result
                st.rerun()

def view_pipeline():
    if st.session_state.selected_lead:
        if st.button("← Back to List", key="back_to_list", type="secondary"):
            st.session_state.selected_lead = None
            st.rerun()
        
        wrapped_data = {'lead_data': st.session_state.selected_lead, 'action': 'QUERY'}
        render_executive_card(wrapped_data, show_close=False)
    else:
        st.markdown("<h2 style='padding:10px 0 10px 0;'>Rolodex</h2>", unsafe_allow_html=True)
        if not st.session_state.user: return
        leads = supabase.table("leads").select("*").eq("user_id", st.session_state.user.id).order("created_at", desc=True).execute().data
        
        if not leads:
            st.info("Rolodex is empty.")
            return
            
        for lead in leads:
            label = lead.get('name', 'Unknown')
            if st.button(label, key=f"lead_{lead['id']}", use_container_width=True):
                st.session_state.selected_lead = lead
                st.rerun()

def view_analytics():
    st.markdown("<h2 style='padding:10px 0 10px 0;'>Analytics</h2>", unsafe_allow_html=True)
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

tabs = { "🎙️ Assistant": "omni", "📇 Rolodex": "pipeline", "📊 Analytics": "analytics" }
rev_tabs = {v: k for k, v in tabs.items()}
current_label = rev_tabs.get(st.session_state.active_tab, "🎙️ Assistant")
selected_label = st.radio(
    "Navigation",
    options=list(tabs.keys()),
    index=list(tabs.keys()).index(current_label),
    label_visibility="collapsed",
    horizontal=True,
    key="nav_radio"
)
if tabs[selected_label] != st.session_state.active_tab:
    st.session_state.active_tab = tabs[selected_label]
    st.rerun()

if st.session_state.active_tab == "omni": view_omni()
elif st.session_state.active_tab == "pipeline": view_pipeline()
elif st.session_state.active_tab == "analytics": view_analytics()

st.markdown("---")
with st.popover("👤", use_container_width=True):
    if st.button("Sign Out", key="logout_btn", type="secondary", use_container_width=True):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.rerun()
    if st.button("Refer a Friend (Coming Soon)", key="refer_btn", disabled=True, use_container_width=True):
        pass
