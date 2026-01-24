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

# ==========================================
# 1. CONFIG & STATE
# ==========================================
st.set_page_config(
    page_title="The Closer", 
    page_icon="🎙️", 
    layout="centered", # Changed to centered for better Login UI, switches to wide internally if needed
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
            overflow-x: hidden !important;
            overscroll-behavior: none;
            -webkit-user-select: none;
            user-select: none;
            -webkit-tap-highlight-color: transparent;
        }
        
        h1, h2, h3 { font-weight: 800 !important; color: #4F4F4F !important; letter-spacing: -0.5px; text-align: center; }
        p, label, span, div { color: #717171; }
        
        /* HIDE HEADER & FOOTER COMPLETELY */
        [data-testid="stHeader"], footer, [data-testid="stFooter"] { 
            display: none !important; 
            visibility: hidden !important; 
            height: 0px !important; 
        }
        
        /* AGGRESSIVE WHITE BAR REMOVAL */
        .main .block-container {
            padding-top: 40px !important;
            padding-bottom: 20px !important; 
            padding-left: 20px !important;
            padding-right: 20px !important;
            max-width: 100% !important;
            gap: 0px !important;
        }
        
        /* =========================================================
           LOGIN & INPUT STYLING (The "The Closer" Look)
           ========================================================= */
           
        /* Round Inputs */
        .stTextInput > div > div > input {
            border-radius: 25px !important;
            padding-top: 12px !important;
            padding-bottom: 12px !important;
            padding-left: 20px !important;
            border: 1px solid #E0E0E0 !important;
            background-color: #F8F9FA !important;
            color: #222222 !important;
        }
        
        /* Password Alignment Fix */
        .stTextInput input[type="password"] {
             line-height: 1.5 !important;
        }

        /* Input Focus */
        .stTextInput > div > div > input:focus {
            border-color: #FF4B6A !important;
            box-shadow: 0 0 0 1px #FF4B6A !important;
        }

        /* Button Styling - Base */
        .stButton > button {
            border-radius: 25px !important;
            width: 100% !important;
            padding-top: 12px !important;
            padding-bottom: 12px !important;
            font-weight: bold !important;
            border: none !important;
            transition: all 0.2s ease !important;
        }

        /* "Log In" Button (Primary - Pink) */
        button[kind="primary"] {
            background-color: #FF4B6A !important;
            color: white !important;
            border: none !important;
        }
        button[kind="primary"]:hover {
             box-shadow: 0 4px 12px rgba(255, 75, 106, 0.4) !important;
        }

        /* "Sign Up" Button (Secondary) */
        button[kind="secondary"] {
            background-color: white !important;
            color: #FF4B6A !important;
            border: 2px solid #FF4B6A !important;
        }

       /*TAB STYLES */
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
            border-bottom-color: #FF4B6A !important;
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
            background-color: #FF4B6A; color: white; font-size: 10px; font-weight: 800;
            padding: 6px 10px; border-radius: 8px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px; display: inline-block;
        }
        .meta-bubble {
            font-size: 12px; font-weight: 700; padding: 4px 10px; border-radius: 12px;
            border: 1px solid #EBEBEB; white-space: nowrap; vertical-align: middle; display: inline-flex; align-items: center;
        }
        
        /* BUBBLE COLORS */
        .bubble-client { background-color: #E6FFFA; color: #008a73; border-color: #008a73; }
        .bubble-lead { background-color: #FFF5F7; color: #FF4B6A; border-color: #FF4B6A; } 
        .bubble-outreach { background-color: #FFFFF0; color: #D69E2E; border-color: #D69E2E; }
        
        .report-bubble { background-color: #F7F7F7; border-radius: 16px; padding: 20px; margin-top: 16px; border: 1px solid #EBEBEB; }
        .transaction-bubble { background-color: #F0FFF4; border-radius: 16px; padding: 20px; margin-top: 16px; border: 1px solid #C6F6D5; }
        
        /* ROLODEX SPECIFIC OVERRIDES */
        div.element-container:has(.rolodex-marker) + div.element-container button {
            text-align: left !important;
            justify-content: flex-start !important;
            font-weight: 800 !important;
            border-left: 6px solid #FF4B6A !important;
            border-radius: 12px !important;
            background-color: white !important;
            color: #222 !important;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05) !important;
        }
        
        div.element-container:has(.rolodex-marker) + div.element-container button:hover {
             border-color: #FF4B6A !important;
             transform: translateY(-2px) !important;
             color: #FF4B6A !important;
        }

        /* ANALYTICS */
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
        .analytics-card-red { border-left: 6px solid #FF4B6A; }
        .analytics-card-green { border-left: 6px solid #008a73; }
        
        .stat-title { font-size: 11px; font-weight: 800; color: #717171; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 6px; }
        .stat-metric { font-size: 26px; font-weight: 900; color: #222222; margin: 0; line-height: 1.1; }
        .stat-sub { font-size: 14px; font-weight: 500; color: #717171; margin-top: 4px; }

        /* REFERRAL BOX */
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
            color: #FF4B6A;
            font-weight: 600;
            word-break: break-all;
        }
        .stCodeBlock {
            background-color: #F7F7F7 !important;
            border-radius: 12px !important;
            border: 1px dashed #dddddd !important;
        }
        
        .subtitle {
            text-align: center;
            color: #8F8F8F;
            margin-bottom: 30px;
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

# --- INFINITY COMMISSION LOGIC START ---

def ensure_referral_link(user_id, user_meta):
    try:
        profile = fetch_user_profile(user_id)
        if not profile: return
        if profile.get('referred_by'): return
        referrer_id = user_meta.get('referred_by')
        if referrer_id:
              supabase.table("profiles").update({'referred_by': referrer_id}).eq("id", user_id).execute()
    except Exception as e:
        print(f"Hierarchy Error: {e}")

def count_referrals(user_id):
    try:
        res = supabase.table("profiles").select("id", count="exact").eq("referred_by", user_id).execute()
        return res.count
    except:
        return 0

def process_subscription_commission(payer_user_id, payment_amount=15.00):
    try:
        profile = fetch_user_profile(payer_user_id)
        if not profile: return
        referrer_id = profile.get('referred_by')
        if not referrer_id: return 

        tier1_amt = payment_amount * 0.15
        r_prof = fetch_user_profile(referrer_id)
        if r_prof:
            new_bal = (r_prof.get('commission_balance') or 0.0) + tier1_amt
            supabase.table("profiles").update({'commission_balance': new_bal}).eq("id", referrer_id).execute()

        current_user_id = r_prof.get('referred_by')
        override_amt = payment_amount * 0.05
        max_depth = 20 
        
        for _ in range(max_depth):
            if not current_user_id: break 
            u_prof = fetch_user_profile(current_user_id)
            if not u_prof: break
            
            ref_count = count_referrals(current_user_id)
            if ref_count >= 10:
                new_bal = (u_prof.get('commission_balance') or 0.0) + override_amt
                supabase.table("profiles").update({'commission_balance': new_bal}).eq("id", current_user_id).execute()
                break
            
            current_user_id = u_prof.get('referred_by')

    except Exception as e:
        print(f"Commission Error: {e}")

def check_and_process_commissions_on_login(user_id, email):
    try:
        profile = fetch_user_profile(user_id)
        if not profile: return
        last_run = profile.get('last_commission_date')
        should_run = True
        
        if last_run:
            try:
                last_date = datetime.fromisoformat(str(last_run).replace('Z', '+00:00'))
                if (datetime.now(timezone.utc) - last_date).days < 28:
                    should_run = False
            except:
                should_run = True
        
        if should_run:
            is_active = check_subscription_status(email)
            if is_active:
                process_subscription_commission(user_id)
                now_iso = datetime.now().isoformat()
                supabase.table("profiles").update({"last_commission_date": now_iso}).eq("id", user_id).execute()
                
    except Exception as e:
        print(f"Auto-Commission Error: {e}")

# --- INFINITY COMMISSION LOGIC END ---

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
    You are 'The Closer', an expert Executive Assistant. 
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
PRODID:-//The Closer//EN
BEGIN:VEVENT
UID:{dt_str}-{clean_name}@thecloser.app
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
# 6. APP VIEWS
# ==========================================

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
    <div class="stat-item"><div class="stat-label">Contact</div><div class="stat-value">{lead.get('contact_info') or '-'}</div></div>
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
        if st.button("← Back to List", key="back_to_list", type="secondary"):
            st.session_state.selected_lead = None
            st.session_state.is_editing = False
            st.rerun()
        render_executive_card({'lead_data': st.session_state.selected_lead, 'action': 'QUERY'})
        return

    st.markdown("<h2 style='padding:0px 0 0px 0;'>Rolodex</h2>", unsafe_allow_html=True)
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

# ==========================================
# 7. MAIN ROUTER
# ==========================================
if not st.session_state.user:
    # --- UPDATED LOGIN UI (Removed White Box & Fixed Alignment) ---
    st.title("The Closer")
    st.markdown('<p class="subtitle">Your AI Sales Companion</p>', unsafe_allow_html=True)
    
    with st.form("login_form", clear_on_submit=False):
        # NOTE: Standard spacing is handled by the new CSS for .stTextInput
        email = st.text_input("Email", placeholder="name@example.com")
        password = st.text_input("Password", type="password", placeholder="••••••••")
        
        st.write("")
        st.write("")
        
        c1, c2 = st.columns(2)
        with c1:
            # kind="primary" triggers the Pink CSS override
            login_submitted = st.form_submit_button("Log In", type="primary", use_container_width=True)
        with c2:
            signup_submitted = st.form_submit_button("Sign Up", type="secondary", use_container_width=True)

        if login_submitted:
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.user = res.user
                st.session_state.is_subscribed = check_subscription_status(res.user.email)
                ensure_referral_link(res.user.id, res.user.user_metadata)
                check_and_process_commissions_on_login(res.user.id, res.user.email)
                st.rerun()
            except Exception as e: st.error(str(e))
            
        if signup_submitted:
            try:
                meta = {"referred_by": st.session_state.referral_captured} if st.session_state.referral_captured else {}
                res = supabase.auth.sign_up({"email": email, "password": password, "options": {"data": meta}})
                if res.user: st.success("Account created! Log in.") 
            except Exception as e: st.error(str(e))
    st.stop()

# [TRIGGER] Check commissions on Page Refresh (if already logged in)
if st.session_state.user:
    check_and_process_commissions_on_login(st.session_state.user.id, st.session_state.user.email)

if not st.session_state.is_subscribed:
    if "session_id" in st.query_params:
        st.session_state.is_subscribed = check_subscription_status(st.session_state.user.email)
        if st.session_state.is_subscribed: st.rerun()
    st.markdown("""<div style="text-align:center; padding: 40px 20px;"><h1>Upgrade Plan</h1><p>Unlock unlimited leads and pipeline storage.</p><div class="airbnb-card" style="margin-top:20px;"><h2 style="margin:0;">$15<small style="font-size:16px; color:#717171;">/mo</small></h2></div></div>""", unsafe_allow_html=True)
    if st.button("Subscribe Now", type="primary", use_container_width=True):
        url = create_checkout_session(st.session_state.user.email, st.session_state.user.id)
        if url: st.link_button("Go to Checkout", url, type="primary")
    st.stop()

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

# --- REPLACED: REFERRAL HUB UI (CREATOR WALLET EDITION) ---
with st.popover("👤", use_container_width=True):
    st.subheader("Profile")
    if st.button("Sign Out", key="logout_btn", type="secondary", use_container_width=True):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.rerun()

    st.markdown("---")
    
    st.subheader("Referral Hub")
    
    my_profile = fetch_user_profile(st.session_state.user.id)
    if my_profile:
        balance = my_profile.get('commission_balance') or 0.00
        
        # Fetch existing settings
        saved_method = my_profile.get('payout_method') or "Venmo"
        saved_handle = my_profile.get('payout_handle') or ""
        payout_req_time = my_profile.get('payout_requested_at')
        
        referral_link = f"{APP_BASE_URL}?ref={st.session_state.user.id}"

        # 1. BALANCE CARD
        st.markdown(f"""
            <div class="analytics-card analytics-card-green" style="margin-bottom: 16px;">
                <div class="stat-title">WALLET BALANCE</div>
                <div class="stat-metric">${balance:,.2f}</div>
                <div class="stat-sub">Available for payout</div>
            </div>
        """, unsafe_allow_html=True)

        # 2. REFERRAL LINK
        st.caption("Your Referral Link")
        st.code(referral_link, language="text")
        
        # 3. PAYOUT SETTINGS (FLEXIBLE WALLET)
        st.markdown("### Payout Settings")
        
        with st.form("payout_form"):
            # Select Method
            method_opts = ["Venmo", "CashApp", "PayPal", "Zelle"]
            # specific index logic to handle defaults if saved_method is not in list
            try:
                idx = method_opts.index(saved_method)
            except:
                idx = 0
                
            new_method = st.selectbox("Preferred Method", method_opts, index=idx)
            
            # Dynamic Placeholder based on selection
            placeholders = {
                "Venmo": "@username", 
                "CashApp": "$cashtag", 
                "PayPal": "name@example.com", 
                "Zelle": "Phone or Email"
            }
            new_handle = st.text_input(f"Your {new_method} Handle", value=saved_handle, placeholder=placeholders.get(new_method, ""))
            
            # LOGIC: Can withdraw if POSITIVE balance and NO pending request
            can_withdraw = (balance > 0.00) and (payout_req_time is None)
            
            # Dynamic Button Label
            if payout_req_time:
                btn_label = "Payout Pending..."
            elif balance <= 0.00:
                btn_label = "No Balance to Withdraw"
            else:
                btn_label = f"Cash Out ${balance:,.2f} to {new_method}"
            
            # Save Details Logic
            if st.form_submit_button("Update Details"):
                supabase.table("profiles").update({
                    "payout_method": new_method, 
                    "payout_handle": new_handle
                }).eq("id", st.session_state.user.id).execute()
                st.success("Details saved.")
                st.rerun()

        # 4. WITHDRAW ACTION (Outside form to prevent double-submit)
        if st.button(btn_label, disabled=not can_withdraw, type="primary", use_container_width=True):
            if not saved_handle:
                st.error("Please save your payout details above first.")
            else:
                # Mark as requested
                now_iso = datetime.now().isoformat()
                supabase.table("profiles").update({"payout_requested_at": now_iso}).eq("id", st.session_state.user.id).execute()
                st.balloons()
                st.success(f"Request sent! We will {saved_method} you shortly.")
                st.rerun()
