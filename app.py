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

# Custom Styling: Dark Mode + Luxury Gold + Hide Header
st.markdown("""
    <style>
        /* General App Styling */
        .stApp { background-color: #0e1117; color: #ffffff; }
        
        /* HIDE STREAMLIT HEADER */
        [data-testid="stHeader"] { display: none; }
        
        /* Headers */
        h1, h2, h3 { color: #d4af37 !important; font-family: 'Helvetica Neue', sans-serif; } 
        
        /* Buttons */
        div.stButton > button {
            background: linear-gradient(45deg, #d4af37, #f6e27a, #d4af37);
            color: black;
            border: none;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 1px;
            transition: all 0.3s ease;
        }
        div.stButton > button:hover {
            transform: scale(1.02);
            box-shadow: 0 4px 15px rgba(212, 175, 55, 0.4);
        }
        
        /* Inputs */
        .stTextInput > div > div > input { background-color: #1f2937; color: white; border: 1px solid #374151; }
        .stTextArea > div > div > textarea { background-color: #1f2937; color: white; border: 1px solid #374151; }
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
# 2. STATE MANAGEMENT (Fixes the "Stale Data" Bug)
# ==========================================
if 'last_audio_bytes' not in st.session_state: st.session_state.last_audio_bytes = None
if 'has_lead' not in st.session_state: st.session_state.has_lead = False
# Initialize contact fields in state so edits persist
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
    """Optimizes images for mobile upload stability."""
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
    """
    Takes audio bytes, sends to Gemini, and extracts contact fields.
    """
    prompt = """
    Listen to this voice memo of a sales interaction.
    Extract the following 6 fields accurately.
    Return ONLY a raw JSON object with these keys:
    {
        "name": "Full Name (if not mentioned, use description e.g. 'Yoga Mom from Gym')",
        "contact_info": "Phone or Email found",
        "background": "Key details about them (job, kids, pain points)",
        "sales_angle": "How to approach the sale psychologically",
        "product_pitch": "Which specific product (e.g. Energy Drink, Collagen, Skincare) fits their need?",
        "follow_up": "When to contact them next (Time/Day)"
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
        
        # Unwrap list if Gemini returns [{...}] instead of {...}
        if isinstance(data, list):
            if len(data) > 0:
                data = data[0]
            else:
                return {"error": "No valid data found."}
        return data
    except Exception as e:
        return {"error": str(e)}

def create_vcard(data):
    """
    Generates a .vcf file string compatible with iOS/Android Contacts.
    We stuff the context notes into the 'NOTE' field.
    """
    # Create the notes block with clear section headers and spacing
    # FIX: Using double newlines (\\n\\n) to ensure iOS displays line breaks
    notes = f"--- LEAD BACKGROUND ---\\n{data.get('background','')}\\n\\n"
    notes += f"--- SALES STRATEGY ---\\n{data.get('sales_angle','')}\\n\\n"
    notes += f"--- RECOMMENDED PRODUCT ---\\n{data.get('product_pitch','')}\\n\\n"
    notes += f"--- FOLLOW UP ---\\n{data.get('follow_up','')}"
    
    # Simple VCard 3.0 Format
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
    st.warning("⚠️ API Key Missing. Please set GOOGLE_API_KEY in Railway variables.")
    st.stop()

st.title("💎 Lifestyle Lure")
st.markdown("*Fake it 'til you make it. Build your downline faster.*")

# TABS
tab1, tab2, tab3, tab4 = st.tabs(["📸 Lifestyle Editor", "📝 Caption Writer", "🕵️ Prospect Analyzer", "🎤 Voice Contact"])

# --- FEATURE 1: IMAGE EDITOR ---
with tab1:
    st.header("Upgrade Your Reality")
    st.info("Upload a selfie -> We put you in Dubai.")
    img_file = st.file_uploader("Upload Selfie", type=["jpg", "png", "jpeg"], key="lure_upload")
    if img_file:
        input_img = Image.open(img_file)
        input_img = compress_image(input_img)
        st.image(input_img, caption="Original", width=250)
        setting = st.selectbox("Choose Your New Location:", [
            "Luxury Hotel Balcony in Dubai (Sunset)", 
            "Private Jet Interior (Cream Leather Seats)", 
            "Poolside at a 5-Star Resort (Tropical)", 
            "Modern Minimalist Home Office (Macbook & Coffee)",
            "TED Talk Style Stage (Holding Microphone)"
        ])
        if st.button("✨ Transform Photo", key="btn_transform"):
            with st.spinner("Booking your flight..."):
                res_img, err = generate_lifestyle_image(input_img, setting)
                if res_img:
                    st.image(res_img, caption="✨ Your New Reality", use_container_width=True)
                elif err:
                    st.error(f"Error: {err}")

# --- FEATURE 2: CAPTION WRITER ---
with tab2:
    st.header("Humble Brag Generator")
    context = st.text_area("What actually happened?", placeholder="e.g. I bought a coffee today.")
    tone = st.select_slider("Select Tone", options=["😭 Emotional/Grateful", "🔥 Boss Babe/Hustle", "🤫 Mysterious/Vague"])
    if st.button("✍️ Write Caption", key="btn_caption"):
        if context:
            with st.spinner("Spinning the story..."):
                caption = generate_caption(context, tone)
                st.text_area("Copy this:", value=caption, height=250)

# --- FEATURE 3: PROSPECT ANALYZER ---
with tab3:
    st.header("The Warm Outreach Tool")
    prospect_file = st.file_uploader("Upload Profile Screenshot", type=["jpg", "png", "jpeg"], key="prospect_upload")
    if prospect_file:
        p_img = Image.open(prospect_file)
        st.image(p_img, caption="Prospect Profile", width=250)
        if st.button("🕵️ Analyze & Write DMs", key="btn_prospect"):
            with st.spinner("Analyzing profile..."):
                analysis = analyze_prospect(p_img)
                st.markdown(analysis)

# --- FEATURE 4: VOICE CONTACT (FIXED) ---
with tab4:
    st.header("🗣️ Instant Lead Capture")
    st.info("Record a voice memo. We'll split the details into a strategy card.")
    
    audio_value = st.audio_input("Record Voice Note")

    if audio_value:
        # Check if this is a NEW recording or just a screen refresh
        current_audio_bytes = audio_value.read()
        
        if current_audio_bytes != st.session_state.last_audio_bytes:
            # NEW AUDIO DETECTED - Process it
            st.session_state.last_audio_bytes = current_audio_bytes
            st.success("Recording received! Processing...")
            
            with st.spinner("Extracting lead details..."):
                contact_data = process_voice_contact(current_audio_bytes)
                
                if isinstance(contact_data, dict) and "error" not in contact_data:
                    # Update Session State with new data
                    st.session_state.c_name = contact_data.get("name", "")
                    st.session_state.c_info = contact_data.get("contact_info", "")
                    st.session_state.c_follow = contact_data.get("follow_up", "")
                    st.session_state.c_pitch = contact_data.get("product_pitch", "")
                    st.session_state.c_bg = contact_data.get("background", "")
                    st.session_state.c_angle = contact_data.get("sales_angle", "")
                    st.session_state.has_lead = True
                elif isinstance(contact_data, dict) and "error" in contact_data:
                    st.error(f"Error: {contact_data['error']}")
                else:
                    st.error("Unexpected data format received.")

    # ALWAYS DISPLAY FORM IF WE HAVE LEAD DATA (Allows editing)
    if st.session_state.has_lead:
        st.subheader("✅ Lead Detected")
        
        # NOTE: Keys match session state variables, so edits automatically update state
        c1, c2 = st.columns(2)
        with c1:
            st.text_input("Name", key="c_name")
            st.text_input("Contact", key="c_info")
        with c2:
            st.text_input("Next Step", key="c_follow")
            st.text_input("💡 Product Pitch", key="c_pitch")
        
        st.text_area("Background Info", height=100, key="c_bg")
        st.text_area("Sales Angle / Strategy", height=100, key="c_angle")
        
        # GENERATE VCARD FROM CURRENT STATE (Fixes "Stale Data" bug)
        current_data = {
            "name": st.session_state.c_name,
            "contact_info": st.session_state.c_info,
            "follow_up": st.session_state.c_follow,
            "product_pitch": st.session_state.c_pitch,
            "background": st.session_state.c_bg,
            "sales_angle": st.session_state.c_angle
        }
        
        vcf_string = create_vcard(current_data)
        
        # Dynamic filename forces iOS to treat it as a new contact
        safe_name = st.session_state.c_name.strip().replace(" ", "_")
        if not safe_name: safe_name = "New_Lead"
        
        st.download_button(
            label="💾 Save to Phone Contacts",
            data=vcf_string,
            file_name=f"{safe_name}.vcf",
            mime="text/vcard",
            use_container_width=True,
            type="primary",
            help="Tap this, then select 'Create New Contact' on the next screen."
        )

st.markdown("---")
st.caption("🔒 Private Tool for Diamond Team Members Only.")
