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

# Custom Styling: "Luxury/High-Status" Dark Mode
st.markdown("""
    <style>
        /* General App Styling */
        .stApp { background-color: #0e1117; color: #ffffff; }
        
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
# 2. UTILITY FUNCTIONS
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
    Handles both List and Dictionary JSON responses to prevent crashes.
    """
    prompt = """
    Listen to this voice memo of a sales interaction.
    Extract the following 5 fields accurately.
    Return ONLY a raw JSON object with these keys:
    {
        "name": "Full Name (if not mentioned, use description e.g. 'Yoga Mom from Gym')",
        "contact_info": "Phone or Email found",
        "background": "Key details about them (job, kids, pain points)",
        "sales_angle": "How to sell to them based on the audio",
        "follow_up": "When to contact them next (Time/Day)"
    }
    """
    try:
        # Convert audio bytes to a format Gemini accepts part-wise
        response = client.models.generate_content(
            model=TEXT_MODEL_ID,
            contents=[
                types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"),
                prompt
            ],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        
        data = json.loads(response.text)
        
        # --- FIX: Unwrap list if Gemini returns [{...}] instead of {...} ---
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
    # Create the notes block
    notes = f"BACKGROUND: {data.get('background','')}\\n"
    notes += f"STRATEGY: {data.get('sales_angle','')}\\n"
    notes += f"FOLLOW UP: {data.get('follow_up','')}"
    
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
# 3. UI LAYOUT
# ==========================================
if not api_key:
    st.warning("⚠️ API Key Missing. Please set GOOGLE_API_KEY in Railway variables.")
    st.stop()

st.title("💎 Lifestyle Lure")
st.markdown("*Fake it 'til you make it. Build your downline faster.*")

# UPDATED TABS: Added "Voice Contact"
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

# --- FEATURE 4: VOICE CONTACT (NEW) ---
with tab4:
    st.header("🗣️ Instant Lead Capture")
    st.info("Record a voice memo after meeting someone. We'll extract the details and create a phone contact for you.")
    
    # New Native Audio Input (Streamlit 1.40+)
    audio_value = st.audio_input("Record Voice Note")

    if audio_value:
        st.success("Recording received! Processing...")
        
        with st.spinner("Extracting lead details..."):
            # Read audio bytes
            audio_bytes = audio_value.read()
            
            # Send to Gemini
            contact_data = process_voice_contact(audio_bytes)
            
            # Validate Response Type
            if isinstance(contact_data, dict) and "error" not in contact_data:
                # Display extracted info cleanly
                st.subheader("✅ Lead Detected")
                c1, c2 = st.columns(2)
                with c1:
                    st.text_input("Name", value=contact_data.get("name", ""), key="c_name")
                    st.text_input("Contact", value=contact_data.get("contact_info", ""), key="c_info")
                with c2:
                    st.text_input("Next Step", value=contact_data.get("follow_up", ""), key="c_follow")
                
                st.text_area("Background & Strategy", 
                             value=f"Background: {contact_data.get('background', '')}\n\nAngle: {contact_data.get('sales_angle', '')}", 
                             height=150)
                
                # Generate VCard
                vcf_string = create_vcard(contact_data)
                
                # Download Button
                st.download_button(
                    label="💾 Save to Phone Contacts",
                    data=vcf_string,
                    file_name=f"{contact_data.get('name', 'Lead')}.vcf",
                    mime="text/vcard",
                    use_container_width=True,
                    type="primary"
                )
            elif isinstance(contact_data, dict) and "error" in contact_data:
                st.error(f"Error: {contact_data['error']}")
            else:
                st.error("Unexpected data format received.")

st.markdown("---")
st.caption("🔒 Private Tool for Diamond Team Members Only.")
