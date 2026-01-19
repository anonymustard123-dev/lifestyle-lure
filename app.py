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
if 'active_tab' not in st.session_state: st.session_state.active_tab = "generate"
if 'generated_lead' not in st.session_state: st.session_state.generated_lead = None
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
# 3. AIRBNB-STYLE CSS
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
        [data-testid="stPopover"] > button:hover {
            box-shadow: 0 2px 8px rgba(0,0,0,0.1) !important;
            color: #222 !important;
            border-color: #222 !important;
        }

        /* --- PAYWALL CARD --- */
        .paywall-container {
            text-align: center;
            padding: 40px 20px;
            max-width: 500px;
            margin: 0 auto;
        }
        .price-tag {
            font-size: 32px;
            font-weight: 800;
            color: #222;
            margin: 20px 0;
        }
        .price-sub {
            font-size: 16px;
            color: #717171;
            font-weight: 400;
        }

        /* --- EARNINGS BALANCE CARD --- */
        .balance-card {
            background-color: #f7f7f7;
            padding: 15px;
            border-radius: 12px;
            text-align: center;
            margin-bottom: 15px;
            border: 1px solid #e0e0e0;
        }
        .balance-amount {
            font-size: 24px;
            font-weight: 800;
            color: #222;
            margin-top: 5px;
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
        button[kind="primary"]:hover { background-color: #d90b3e !important; }

        button[kind="secondary"] {
            background-color: transparent !important;
            color: #222 !important;
            border: 1px solid #e0e0e0 !important;
            box-shadow: none !important;
            border-radius: 12px !important;
            height: 50px !important;
        }

        /* Nav Buttons */
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
# 4. SUBSCRIPTION & REFERRAL LOGIC
# ==========================================
def fetch_user_profile(user_id):
    """Fetches the profile (ref code, payout info) from Supabase"""
    try:
        response = supabase.table("profiles").select("*").eq("id", user_id).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]
    except Exception as e:
        print(f"Profile Fetch Error: {e}")
    return None

def calculate_commissions(profile):
    """
    Calculates 20% commission by finding all users referred by this profile
    and summing their successful Stripe payments.
    """
    if not STRIPE_SECRET_KEY or not profile or not profile.get('referral_code'):
        return 0.0
    
    try:
        my_code = profile.get('referral_code')
        
        # 1. Find all users I referred
        referred_users = supabase.table("profiles").select("email").eq("referred_by", my_code).execute()
        if not referred_users.data:
            return 0.0
            
        total_revenue = 0.0
        
        # 2. For each referred user, find their Stripe ID then their Money (The Robust Way)
        for user in referred_users.data:
            email = user['email']
            
            # A. Find the Stripe Customer object for this email
            customers = stripe.Customer.list(email=email, limit=1).data
            if customers:
                customer_id = customers[0].id
                
                # B. Sum up all PAID invoices for this Customer ID
                # (Invoices are the source of truth for Subscriptions)
                invoices = stripe.Invoice.list(customer=customer_id, status='paid', limit=100)
                for inv in invoices.data:
                    # amount_paid is in cents, convert to dollars
                    total_revenue += (inv.amount_paid / 100)
                    
        return round(total_revenue * 0.20, 2) # 20% Commission
    except Exception as e:
        print(f"Commission Calc Error: {e}")
        return 0.0

def check_subscription_status(email):
    if not STRIPE_SECRET_KEY: return True 
    try:
        customers = stripe.Customer.list(email=email).data
        if not customers: return False
        subscriptions = stripe.Subscription.list(customer=customers[0].id, status='active').data
        return True if subscriptions else False
    except:
        return False

def create_checkout_session(email, user_id):
    """Creates a session AND attaches the referral code if one exists"""
    try:
        # Get Customer
        customers = stripe.Customer.list(email=email).data
        if customers:
            customer_id = customers[0].id
        else:
            customer = stripe.Customer.create(email=email)
            customer_id = customer.id
            
        # Check if this user was referred by someone (stored in their profile)
        profile = fetch_user_profile(user_id)
        metadata = {}
        if profile and profile.get('referred_by'):
            metadata['referred_by'] = profile.get('referred_by')

        # Create Session
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            line_items=[{'price': STRIPE_PRICE_ID, 'quantity': 1}],
            mode='subscription',
            success_url=f"{APP_BASE_URL}?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{APP_BASE_URL}",
            metadata=metadata # This is where the magic happens
        )
        return session.url
    except Exception as e:
        return None

# ==========================================
# 5. BACKEND LOGIC (AI & DATA)
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

def save_lead(lead_data):
    if not st.session_state.user: return "Not logged in"
    lead_data['user_id'] = st.session_state.user.id
    lead_data['created_at'] = datetime.now().isoformat()
    if supabase:
        try: supabase.table("leads").insert(lead_data).execute(); return None
        except Exception as e: return str(e)
    else: return "DB Error"

def load_leads():
    if not st.session_state.user: return []
    if supabase:
        try:
            response = supabase.table("leads").select("*").eq("user_id", st.session_state.user.id).order("created_at", desc=True).execute()
            return response.data
        except: return []
    return []

# ==========================================
# 6. LOGIN SCREEN (NO VERIFICATION)
# ==========================================
def login_screen():
    st.markdown("<h1 style='text-align: center; margin-bottom: 30px;'>The Closer</h1>", unsafe_allow_html=True)
    
    # If a referral code was captured, show a friendly message
    if st.session_state.referral_captured:
        st.info(f"🎉 Invite Applied: {st.session_state.referral_captured}")

    tab_login, tab_signup = st.tabs(["Log In", "Sign Up"])
    
    with tab_login:
        st.markdown("<br>", unsafe_allow_html=True)
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pass")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Log In", type="primary", use_container_width=True):
            if supabase:
                try:
                    res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    st.session_state.user = res.user
                    st.session_state.is_subscribed = check_subscription_status(res.user.email)
                    st.session_state.user_profile = fetch_user_profile(res.user.id)
                    st.rerun()
                except Exception as e: st.error(f"Login failed: {e}")

    with tab_signup:
        st.markdown("<br>", unsafe_allow_html=True)
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password", type="password", key="signup_pass")
        st.markdown("<br>", unsafe_allow_html=True)
        
        # DEBUG LABEL
        btn_label = "Create Account"
        if st.session_state.referral_captured:
            btn_label = f"Create Account (Ref: {st.session_state.referral_captured})"
            
        if st.button(btn_label, type="primary", use_container_width=True):
            if supabase:
                try:
                    meta = {}
                    if st.session_state.referral_captured:
                        meta["referred_by"] = st.session_state.referral_captured
                    
                    # 1. Create the user
                    res = supabase.auth.sign_up({
                        "email": email, 
                        "password": password,
                        "options": {"data": meta} 
                    })
                    
                    # 2. AUTO-LOGIN LOGIC
                    # If Supabase "Confirm Email" is OFF, 'res.user' and 'res.session' will be present.
                    if res.user:
                        st.session_state.user = res.user
                        st.session_state.is_subscribed = check_subscription_status(res.user.email)
                        st.session_state.user_profile = fetch_user_profile(res.user.id)
                        
                        # Double-check: Ensure referral is saved in profile
                        if st.session_state.referral_captured and st.session_state.user_profile:
                            if not st.session_state.user_profile.get('referred_by'):
                                try:
                                    supabase.table("profiles").update({
                                        "referred_by": st.session_state.referral_captured
                                    }).eq("id", res.user.id).execute()
                                except: pass
                        
                        st.success("Account created! Logging you in...")
                        st.rerun()
                    else:
                        st.warning("Account created, but auto-login failed. Please log in manually.")
                        
                except Exception as e: st.error(f"Signup failed: {e}")
            else: st.warning("Database not connected.")

# ==========================================
# 7. MAIN APP ROUTER
# ==========================================
if not st.session_state.user:
    login_screen()
    st.stop()

# --- HEADER (PROFILE & PAYOUTS) ---
def render_header():
    # If profile not loaded, try fetching it
    if not st.session_state.user_profile:
        st.session_state.user_profile = fetch_user_profile(st.session_state.user.id)
        
    c1, c2 = st.columns([8, 1]) 
    with c2:
        with st.popover("👤", help="Menu"):
            # Email Display
            st.markdown(f"<div style='font-size:12px; color:#888; text-align:center;'>{st.session_state.user.email}</div>", unsafe_allow_html=True)
            st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)
            
            # --- REFERRAL & EARNINGS SECTION ---
            if st.session_state.user_profile:
                # Calculate Earnings
                earnings = calculate_commissions(st.session_state.user_profile)
                payout_requested_at = st.session_state.user_profile.get('payout_requested_at')

                # Display Balance
                st.markdown(f"""
                    <div class="balance-card">
                        <div style="font-size:12px; text-transform:uppercase; font-weight:700; color:#888;">Lifetime Earnings</div>
                        <div class="balance-amount">${earnings:.2f}</div>
                    </div>
                """, unsafe_allow_html=True)

                # Payout Request Logic
                if earnings > 0:
                    if payout_requested_at:
                        st.info("Payout Pending review.")
                    else:
                        if st.button("Request Payout (PayPal)", use_container_width=True):
                            # Mark as requested in DB
                            try:
                                supabase.table("profiles").update({
                                    "payout_requested_at": datetime.now().isoformat()
                                }).eq("id", st.session_state.user.id).execute()
                                # Update local state immediately for UI feedback
                                st.session_state.user_profile['payout_requested_at'] = datetime.now().isoformat()
                                st.success("Request sent!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
                else:
                    st.caption("Share your link to start earning.")

                # Invite Link
                my_code = st.session_state.user_profile.get('referral_code', 'N/A')
                st.markdown(f"**My Invite Link:**")
                st.code(f"{APP_BASE_URL}?ref={my_code}", language="text")
                st.caption("Share this to earn 20% commission.")
                
                # PayPal Input
                st.markdown("**Payout Info:**")
                current_paypal = st.session_state.user_profile.get('payout_info', '')
                paypal_email = st.text_input("PayPal Email", value=current_paypal if current_paypal else "", placeholder="you@paypal.com")
                if st.button("Save PayPal"):
                    try:
                        supabase.table("profiles").update({"payout_info": paypal_email}).eq("id", st.session_state.user.id).execute()
                        st.session_state.user_profile['payout_info'] = paypal_email # Update local
                        st.toast("Payout info saved!", icon="✅")
                    except:
                        st.error("Error saving.")
            
            st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)
            
            if st.button("Sign Out", type="primary", use_container_width=True):
                if supabase: supabase.auth.sign_out()
                st.session_state.user = None
                st.session_state.is_subscribed = False
                st.session_state.user_profile = None
                st.rerun()

# --- CHECK SUBSCRIPTION GATE ---
if not st.session_state.is_subscribed:
    query_params = st.query_params
    if "session_id" in query_params:
        st.session_state.is_subscribed = check_subscription_status(st.session_state.user.email)
        if st.session_state.is_subscribed:
            st.toast("Welcome to Premium!", icon="🎉")
            st.rerun()
    
    render_header()
    st.markdown("""
        <div class="paywall-container">
            <h1 style="font-size: 42px; margin-bottom: 10px;">Unlock The Closer</h1>
            <p style="font-size: 18px; color: #717171;">Get unlimited AI lead generation and pipeline tracking.</p>
            <div class="price-tag">$15.00 <span class="price-sub">/ month</span></div>
        </div>
    """, unsafe_allow_html=True)
    
    if st.button("Subscribe via Stripe", type="primary", use_container_width=True):
        # We pass user_id so we can look up their referrer inside the helper function
        checkout_url = create_checkout_session(st.session_state.user.email, st.session_state.user.id)
        if checkout_url:
            st.link_button("Proceed to Checkout 👉", checkout_url, type="primary", use_container_width=True)
        else:
            st.error("Error creating checkout.")
    st.stop()

# --- APP VIEWS ---
def view_generate():
    render_header()
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
                    err = save_lead(data)
                    if err: st.error(f"Database Error: {err}")
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
