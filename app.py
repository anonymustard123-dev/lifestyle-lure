import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
import os
import io
import base64
import json

# ==========================================
# 1. SETUP & CONFIG
# ==========================================
st.set_page_config(
    page_title="Lifestyle Lure", 
    page_icon="💎", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom Styling: "Empire" Aesthetic
st.markdown("""
    <style>
        /* BASE THEME */
        .stApp { background-color: #050505; color: #ffffff; }
        [data-testid="stHeader"] { display: none; }
        
        /* TYPOGRAPHY */
        h1, h2, h3 { color: #d4af37 !important; font-family: 'Helvetica Neue', sans-serif; letter-spacing: 1px; }
        p, label { color: #a0a0a0; }
        
        /* -----------------------
           VIEW 1: RECORDER CARD 
           ----------------------- */
        .recorder-card {
            border: 1px solid #333;
            border-radius: 20px;
            padding: 30px;
            background: linear-gradient(145deg, #111, #0a0a0a);
            text-align: center;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            margin-bottom: 20px;
        }
        .status-badge {
            display: inline-block;
            background: rgba(0, 255, 0, 0.1);
            color: #00ff00;
            padding: 5px 15px;
            border-radius: 15px;
            font-size: 0.8rem;
            border: 1px solid rgba(0, 255, 0, 0.3);
            margin-bottom: 20px;
        }
        .intel-card {
            background: #1a1a1a;
            border-left: 3px solid #d4af37;
            padding: 10px 15px;
            margin: 10px 0;
            text-align: left;
            border-radius: 0 10px 10px 0;
        }

        /* -----------------------
           VIEW 2: DOSSIER CARD 
           ----------------------- */
        .dossier-card {
            background: linear-gradient(180deg, #1a1a1a 0%, #0d0d0d 100%);
            border: 1px solid #333;
            border-radius: 24px;
            padding: 25px;
            box-shadow: 0 20px 50px rgba(0,0,0,0.8);
        }
        .dossier-header {
            border-bottom: 1px solid #333;
            padding-bottom: 15px;
            margin-bottom: 15px;
        }
        .strategy-hook {
            color: #d4af37;
            font-weight: bold;
            font-size: 1.1rem;
            text-transform: uppercase;
            margin-top: 5px;
        }
        .tag-container {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin: 15px 0;
        }
        .tag {
            background: #222;
            color: #ddd;
            padding: 5px 12px;
            border-radius: 8px;
            font-size: 0.85rem;
            border: 1px solid #444;
        }
        .product-box {
            background: rgba(212, 175, 55, 0.1);
            border: 1px solid #d4af37;
            color: #d4af37;
            padding: 15px;
            border-radius: 12px;
            text-align: center;
            margin-top: 20px;
            font-weight: bold;
        }

        /* INPUT OVERRIDES (To blend into cards) */
        .stTextInput > div > div > input { 
            background-color: transparent !important; 
            border: none !important; 
            border-bottom: 1px solid #444 !important; 
            color: white !important; 
        }
        .stTextArea > div > div > textarea { 
            background-color: #111 !important; 
            border: 1px solid #333 !important; 
            color: #ccc !important; 
        }

        /* ACTION BUTTONS */
        div.stButton > button {
            background: linear-gradient(90deg, #d4af37, #b8860b);
            color: black;
            border: none;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 1px;
            width: 100%;
            border-radius: 12px;
            padding: 12px 0;
        }
    </style>
""", unsafe_allow_html=True)

# API Setup
api_key = os.getenv("GOOGLE_API_KEY")

client = None
if api_key:
    client = genai.Client(api_key=api_key)

IMAGE_MODEL_ID = "gemini-2.0-flash" 
TEXT_MODEL_ID = "gemini-2.0-flash"

# ==========================================
# 2. STATE MANAGEMENT
# ==========================================
if 'last_audio_bytes' not in st.session_state: st.session_state.last_audio_bytes = None
if 'has_lead' not in st.session_state: st.session_state.has_lead = False
# Initialize contact fields
if 'c_name' not in st.session_state: st.session_state.c_name = ""
if 'c_info' not in st.session_state: st.session_state.c_info = ""
if 'c_follow' not in st.session_state: st.session_state.c_follow = ""
if 'c_pitch' not in st.session_state: st.session_state.c_pitch = ""
if 'c_bg' not in st.session_state: st.session_state.c_bg = ""
if 'c_angle' not in st.session_state: st.session_state.c_angle = ""

# ==========================================
# 3. UTILITY FUNCTIONS
# ==========================================
def compress_image(image, max_size=(800, 800)):
    img = image.copy()
    if img.mode != 'RGB': img = img.convert('RGB')
    img.thumbnail(max_size, Image.Resampling.LANCZOS)
    return img

def generate_lifestyle_image(input_image, setting_prompt):
    full_prompt = f"""
    Act as a high-end social media photo editor.
    Task: Edit this selfie/photo.
    1. CRITICAL: Keep the person in the foreground EXACTLY as they are.
    2. REPLACE the background with: {setting_prompt}.
    3. BLENDING: Adjust lighting to match.
    4. STYLE: High-resolution, "Influencer" aesthetic.
    """
    try:
        response = client.models.generate_content(
            model=IMAGE_MODEL_ID,
            contents=[input_image, full_prompt],
            config=types.GenerateContentConfig(response_modalities=["IMAGE"], temperature=0.7)
        )
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    raw_data = part.inline_data.data
                    img_data = raw_data if isinstance(raw_data, bytes) else base64.b64decode(raw_data)
                    return Image.open(io.BytesIO(img_data)), None
        return None, "No image generated."
    except Exception as e: return None, str(e)

def generate_caption(context_text, tone):
    prompt = f"""
    Act as a Network Marketing Mentor. 
    Task: Rewrite this boring status update into a high-engagement caption.
    Input Context: "{context_text}"
    Tone: {tone}
    Requirements: Line breaks, 3-5 emojis, subtle "biz" mention, end with question.
    """
    try:
        response = client.models.generate_content(model=TEXT_MODEL_ID, contents=prompt)
        return response.text.strip()
    except Exception as e: return str(e)

def analyze_prospect(screenshot_img):
    prompt = """
    Analyze this social media profile screenshot.
    1. Identify "Pain Points" or "Interests".
    2. Draft 3 Cold Outreach DMs (Soft Connection, Compliment, Curiosity Gap).
    Strict Rule: Do NOT sound like a bot. Sound human.
    """
    try:
        response = client.models.generate_content(model=TEXT_MODEL_ID, contents=[screenshot_img, prompt])
        return response.text.strip()
    except Exception as e: return str(e)

def process_voice_contact(audio_bytes):
    prompt = """
    Listen to this voice memo of a sales interaction.
    Extract the following fields.
    Return ONLY a raw JSON object with these keys:
    {
        "name": "Full Name",
        "contact_info": "Phone or Email found (or 'Not mentioned')",
        "background": "Key details about them (job, kids, pain points)",
        "sales_angle": "A short, punchy 'Strategy Hook' (e.g. 'Focus on Time Freedom')",
        "product_pitch": "Recommended Product (e.g. Starter Kit B)",
        "follow_up": "When to contact them next"
    }
    """
    try:
        response = client.models.generate_content(
            model=TEXT_MODEL_ID,
            contents=[
                types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"),
                prompt
            ],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        data = json.loads(response.text)
        if isinstance(data, list):
            if len(data) > 0: data = data[0]
            else: return {"error": "No valid data found."}
        return data
    except Exception as e:
        return {"error": str(e)}

def analyze_call_recording(audio_bytes, mime_type):
    prompt = """
    Analyze this sales call. Provide a markdown summary:
    1. **Executive Summary**
    2. **Key Points**
    3. **Client Objections**
    4. **Sentiment Analysis**
    5. **Action Items**
    """
    try:
        response = client.models.generate_content(
            model=TEXT_MODEL_ID,
            contents=[types.Part.from_bytes(data=audio_bytes, mime_type=mime_type), prompt]
        )
        return response.text
    except Exception as e:
        return f"Error: {str(e)}"

def create_vcard(data):
    # Using double newlines for iOS compatibility
    notes = f"--- LEAD BACKGROUND ---\\n{data.get('background','')}\\n\\n"
    notes += f"--- STRATEGY HOOK ---\\n{data.get('sales_angle','')}\\n\\n"
    notes += f"--- RECOMMENDED PRODUCT ---\\n{data.get('product_pitch','')}\\n\\n"
    notes += f"--- FOLLOW UP ---\\n{data.get('follow_up','')}"
    
    vcard = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"FN:{data.get('name', 'New Lead')}",
        f"TEL;TYPE=CELL:{data.get('contact_info', '')}",
        f"NOTE:{notes}",
        "END:VCARD"
    ]
    return "\n".join(vcard)

# ==========================================
# 4. UI LAYOUT
# ==========================================
if not api_key:
    st.warning("⚠️ API Key Missing. Set GOOGLE_API_KEY in Railway.")
    st.stop()

# TABS
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📸 Editor", "📝 Captions", "🕵️ Prospecting", "🎤 Capture", "📞 Audit"])

# --- FEATURE 1-3 (Kept compact for brevity, logic unchanged) ---
with tab1:
    st.header("Lifestyle Editor")
    img_file = st.file_uploader("Upload Selfie", type=["jpg", "png"], key="lure_upload")
    if img_file:
        input_img = compress_image(Image.open(img_file))
        st.image(input_img, width=200)
        setting = st.selectbox("Location", ["Dubai Balcony", "Private Jet", "Resort Pool", "TED Stage"])
        if st.button("Transform"):
            res, err = generate_lifestyle_image(input_img, setting)
            if res: st.image(res, use_container_width=True)

with tab2:
    st.header("Caption Writer")
    ctx = st.text_area("Context", placeholder="I bought coffee...")
    if st.button("Generate"): st.write(generate_caption(ctx, "Boss Babe"))

with tab3:
    st.header("Prospect Analyzer")
    p_file = st.file_uploader("Screenshot", type=["jpg", "png"])
    if p_file:
        if st.button("Analyze"): st.write(analyze_prospect(Image.open(p_file)))

# --- FEATURE 4: THE NEW UI (VIEW 1 & VIEW 2) ---
with tab4:
    # Logic to switch views based on data presence
    
    # VIEW 1: RECORDING STATE (If no lead data yet)
    if not st.session_state.has_lead:
        st.markdown("""
            <div class="recorder-card">
                <div class="status-badge">EMPIRE STATUS: ACTIVE 🟢</div>
                <h3>RECENT INTELLIGENCE</h3>
                <div class="intel-card">MARK T. - HATES COMMUTE</div>
                <div class="intel-card">LISA R. - PASSIVE INCOME GOAL</div>
                <br>
                <p style="opacity: 0.7">RECORD NEW LEAD INTERACTION</p>
            </div>
        """, unsafe_allow_html=True)
        
        # The Audio Input sits "inside" the card visually due to layout
        audio_value = st.audio_input("Record Voice Note", label_visibility="collapsed")
        
        if audio_value:
            current_audio_bytes = audio_value.read()
            if current_audio_bytes != st.session_state.last_audio_bytes:
                st.session_state.last_audio_bytes = current_audio_bytes
                with st.spinner("Analyzing Intelligence..."):
                    contact_data = process_voice_contact(current_audio_bytes)
                    if isinstance(contact_data, dict) and "error" not in contact_data:
                        # Save to State
                        st.session_state.c_name = contact_data.get("name", "")
                        st.session_state.c_info = contact_data.get("contact_info", "")
                        st.session_state.c_follow = contact_data.get("follow_up", "")
                        st.session_state.c_pitch = contact_data.get("product_pitch", "")
                        st.session_state.c_bg = contact_data.get("background", "")
                        st.session_state.c_angle = contact_data.get("sales_angle", "")
                        st.session_state.has_lead = True
                        st.rerun() # Force reload to show View 2

    # VIEW 2: DOSSIER STATE (If lead data exists)
    else:
        # 1. The Container "Card"
        with st.container():
            st.markdown('<div class="dossier-card">', unsafe_allow_html=True)
            
            # HEADER
            st.markdown(f"""
                <div class="dossier-header">
                    <p style="font-size: 0.9rem; margin-bottom: 0;">DOSSIER</p>
                    <h2 style="margin-top: 0; font-size: 2.5rem;">{st.session_state.c_name.upper()}</h2>
                    <p class="strategy-hook">STRATEGY HOOK: {st.session_state.c_angle}</p>
                </div>
            """, unsafe_allow_html=True)

            # EDITABLE FIELDS (Styled to blend in)
            c1, c2 = st.columns(2)
            with c1:
                st.caption("CONTACT")
                st.text_input("Contact", value=st.session_state.c_info, key="c_info", label_visibility="collapsed")
            with c2:
                st.caption("FOLLOW UP")
                st.text_input("Follow Up", value=st.session_state.c_follow, key="c_follow", label_visibility="collapsed")
            
            # TAGS VISUALIZATION (For Background)
            st.markdown('<div class="tag-container">', unsafe_allow_html=True)
            # Split background by commas to make fake tags, or just show text
            bg_points = st.session_state.c_bg.split(',') if ',' in st.session_state.c_bg else [st.session_state.c_bg]
            for point in bg_points:
                st.markdown(f'<span class="tag">⚡ {point.strip().upper()}</span>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            # RECOMMENDED PRODUCT BOX
            st.markdown(f"""
                <div class="product-box">
                    📦 RECOMMENDED: {st.session_state.c_pitch.upper()}
                </div>
                <br>
            """, unsafe_allow_html=True)

            # SAVE BUTTON
            current_data = {
                "name": st.session_state.c_name, "contact_info": st.session_state.c_info,
                "follow_up": st.session_state.c_follow, "product_pitch": st.session_state.c_pitch,
                "background": st.session_state.c_bg, "sales_angle": st.session_state.c_angle
            }
            vcf_string = create_vcard(current_data)
            safe_name = st.session_state.c_name.strip().replace(" ", "_")
            
            st.download_button(
                label="SAVE TO PIPELINE (CONTACTS)",
                data=vcf_string,
                file_name=f"{safe_name}.vcf",
                mime="text/vcard",
                type="primary"
            )

            # RESET BUTTON (To go back to recorder)
            if st.button("LOG NEW INTERACTION"):
                st.session_state.has_lead = False
                st.session_state.last_audio_bytes = None
                st.rerun()

            st.markdown('</div>', unsafe_allow_html=True) # End Card

with tab5:
    st.header("Call Auditor")
    call_file = st.file_uploader("Upload Audio", type=["mp3", "wav"])
    if call_file and st.button("Audit"):
        st.write(analyze_call_recording(call_file.read(), "audio/mp3"))

st.markdown("---")
st.caption("🔒 Private Tool for Diamond Team Members Only.")
