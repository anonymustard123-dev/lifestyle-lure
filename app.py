import streamlit as st
from google import genai
from google.genai import types
import os
import json
import pandas as pd
from datetime import datetime
import re

# ==========================================
# 1. CONFIG & CSS
# ==========================================
st.set_page_config(
    page_title="The Closer", 
    page_icon="🎙️", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom Styling: Minimalist Luxury
st.markdown("""
    <style>
        /* --- GLOBAL THEME --- */
        .stApp { background-color: #000000; color: #e0e0e0; font-family: 'Helvetica Neue', sans-serif; }
        [data-testid="stHeader"] { display: none; }
        
        /* --- NAVIGATION TABS --- */
        .stTabs [data-baseweb="tab-list"] {
            gap: 20px;
            justify-content: center;
            border-bottom: 1px solid #333;
            padding-bottom: 10px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: pre-wrap;
            background-color: transparent;
            border-radius: 4px;
            color: #666;
            font-size: 14px;
            font-weight: 600;
            border: none;
        }
        .stTabs [data-baseweb="tab"][aria-selected="true"] {
            color: #d4af37;
            border-bottom: 2px solid #d4af37;
        }

        /* --- TYPOGRAPHY --- */
        h1, h2, h3 { color: #ffffff !important; font-weight: 300; letter-spacing: 1px; }
        p, label, span { color: #cccccc; }
        div[data-testid="stMarkdownContainer"] p { font-size: 1rem; line-height: 1.5; }

        /* --- CARD COMPONENTS --- */
        .dossier-container {
            background: linear-gradient(180deg, #111 0%, #0a0a0a 100%);
            border: 1px solid #333;
            border-radius: 16px;
            padding: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.8);
            margin-top: 20px;
        }
        
        .section-header {
            color: #d4af37;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-bottom: 5px;
            margin-top: 20px;
            border-bottom: 1px solid #333;
            padding-bottom: 5px;
        }

        .hero-text {
            font-size: 2.5rem;
            font-weight: 700;
            color: white;
            margin: 0;
            padding: 0;
            line-height: 1.1;
        }

        .strategy-text {
            font-style: italic;
            color: #aaa;
            margin-bottom: 20px;
        }

        /* --- MIC SECTION --- */
        .mic-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 100px 0;
            text-align: center;
        }
        .mic-label {
            margin-top: 20px;
            font-size: 1.2rem;
            color: #666;
            letter-spacing: 3px;
            text-transform: uppercase;
        }

        /* --- LEAD LIST ITEM --- */
        .lead-item {
            background-color: #111;
            border: 1px solid #222;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 10px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .lead-item:hover {
            border-color: #d4af37;
        }

        /* --- ANALYTICS METRICS --- */
        div[data-testid="stMetricValue"] {
            color: #d4af37 !important;
        }
        div[data-testid="stMetricLabel"] {
            color: #888 !important;
        }

        /* --- BUTTONS --- */
        /* Primary Button (Save Contact) */
        div.stButton > button {
            background: #d4af37;
            color: black;
            border: none;
            font-weight: bold;
            border-radius: 8px;
            padding: 10px 20px;
            width: 100%;
        }
        
        /* Secondary Button Hack */
        button[kind="secondary"] {
            background-color: #111 !important;
            color: #d4af37 !important;
            border: 1px solid #d4af37 !important;
        }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. DATA MANAGER (LOCAL JSON DB)
# ==========================================
DB_FILE = "leads_db.json"

def load_leads():
    if not os.path.exists(DB_FILE):
        return []
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_lead(lead_data):
    leads = load_leads()
    lead_data['date'] = datetime.now().strftime("%Y-%m-%d %H:%M")
    leads.insert(0, lead_data)
    with open(DB_FILE, "w") as f:
        json.dump(leads, f)

# ==========================================
# 3. AI LOGIC
# ==========================================
api_key = os.getenv("GOOGLE_API_KEY")
client = None
if api_key:
    client = genai.Client(api_key=api_key)

TEXT_MODEL_ID = "gemini-2.0-flash"

def clean_json_string(json_str):
    json_str = json_str.strip()
    if json_str.startswith("```json"):
        json_str = json_str[7:]
    if json_str.startswith("```"):
        json_str = json_str[3:]
    if json_str.endswith("```"):
        json_str = json_str[:-3]
    return json_str

def process_voice_contact(audio_bytes):
    prompt = """
    Listen to this sales voice memo. Extract these fields.
    Return ONLY raw JSON (no markdown formatting):
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
        clean_text = clean_json_string(response.text)
        data = json.loads(clean_text)
        if isinstance(data, list):
            if len(data) > 0: data = data[0]
            else: return {"error": "AI returned an empty list."}
        return data
    except Exception as e:
        return {"error": str(e)}

def create_vcard(data):
    notes = f"STRATEGY: {data.get('sales_angle','')}\\n\\nPRODUCT: {data.get('product_pitch','')}\\n\\nBG: {data.get('background','')}"
    vcard = [
        "BEGIN:VCARD", "VERSION:3.0",
        f"FN:{data.get('name', 'Lead')}",
        f"TEL;TYPE=CELL:{data.get('contact_info', '')}",
        f"NOTE:{notes}", "END:VCARD"
    ]
    return "\n".join(vcard)

# ==========================================
# 4. APP INTERFACE
# ==========================================
if not api_key:
    st.error("⚠️ API Key Missing. Check Railway Variables.")
    st.stop()

tab_create, tab_leads, tab_analytics = st.tabs(["🎙️ GENERATE LEAD", "📂 PIPELINE", "📊 ANALYTICS"])

# --- TAB 1: GENERATE LEAD ---
with tab_create:
    if 'generated_lead' not in st.session_state: st.session_state.generated_lead = None
    
    if not st.session_state.generated_lead:
        st.markdown('<div class="mic-container">', unsafe_allow_html=True)
        audio_val = st.audio_input("Record", label_visibility="collapsed")
        st.markdown('<div class="mic-label">Generate Lead</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        if audio_val:
            with st.spinner("Decrypting signal..."):
                data = process_voice_contact(audio_val.read())
                if isinstance(data, dict) and "error" not in data:
                    save_lead(data)
                    st.session_state.generated_lead = data
                    st.rerun()
                else:
                    error_msg = data.get('error', 'Unknown Error') if isinstance(data, dict) else "Invalid Data Format"
                    st.error(f"Analysis Failed: {error_msg}")

    else:
        lead = st.session_state.generated_lead
        
        # NOTE: I have removed extra indentation in the HTML string below to prevent Markdown code blocks
        st.markdown(f"""
<div class="dossier-container">
<div class="section-header">TARGET IDENTITY</div>
<h1 class="hero-text">{lead.get('name', 'Unknown').upper()}</h1>
<p class="strategy-text">{lead.get('sales_angle')}</p>
<div style="display:grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top:30px;">
<div>
<div class="section-header">CONTACT</div>
<p>{lead.get('contact_info')}</p>
</div>
<div>
<div class="section-header">TIMING</div>
<p>{lead.get('follow_up')}</p>
</div>
</div>
<div class="section-header">INTELLIGENCE</div>
<p>{lead.get('background')}</p>
<div style="background: rgba(212, 175, 55, 0.1); padding: 15px; border-radius: 8px; margin-top: 20px; text-align: center; border: 1px solid #d4af37;">
<span style="color: #d4af37; font-weight: bold; font-size: 0.9rem;">RECOMMENDED: {lead.get('product_pitch').upper()}</span>
</div>
</div>
""", unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            vcf = create_vcard(lead)
            safe_name = lead.get('name').strip().replace(" ", "_")
            st.download_button(
                "SAVE CONTACT", 
                data=vcf, 
                file_name=f"{safe_name}.vcf", 
                mime="text/vcard", 
                use_container_width=True,
                type="primary"
            )
        with col2:
            if st.button("NEW LEAD", use_container_width=True, type="secondary"):
                st.session_state.generated_lead = None
                st.rerun()

# --- TAB 2: PIPELINE ---
with tab_leads:
    st.markdown("<br>", unsafe_allow_html=True)
    all_leads = load_leads()
    
    if not all_leads:
        st.info("Pipeline empty. Record a lead to begin.")
    
    for i, lead in enumerate(all_leads):
        with st.expander(f"{lead.get('name', 'Unknown')}  |  {lead.get('date')}"):
            # Removed indentation in HTML string here too
            st.markdown(f"""
<div style="padding: 10px; border-left: 3px solid #d4af37; background: #111;">
<p><strong>Strategy:</strong> {lead.get('sales_angle')}</p>
<p><strong>Product:</strong> {lead.get('product_pitch')}</p>
<p><strong>Next Step:</strong> {lead.get('follow_up')}</p>
<p style="font-size: 0.8rem; color: #666;">{lead.get('contact_info')}</p>
</div>
""", unsafe_allow_html=True)

# --- TAB 3: ANALYTICS ---
with tab_analytics:
    st.markdown("<br>", unsafe_allow_html=True)
    all_leads = load_leads()
    
    if not all_leads:
        st.info("Record data to generate analytics.")
    else:
        df = pd.DataFrame(all_leads)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Leads", len(all_leads))
        
        try:
            top_prod = df['product_pitch'].mode()[0]
        except:
            top_prod = "N/A"
        c2.metric("Top Product", top_prod)
        
        st.markdown("### Product Demand")
        if 'product_pitch' in df.columns:
            chart_data = df['product_pitch'].value_counts()
            st.bar_chart(chart_data, color="#d4af37")
        
        st.markdown("### Pipeline Health")
        st.progress(min(len(all_leads) * 10, 100), text="Weekly Goal Progress")
