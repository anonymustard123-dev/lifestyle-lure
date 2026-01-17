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
        h1, h2, h3 { color: #d4af37 !important; font-family: 'Helvetica Neue', sans-serif; } /* Gold Color */
        
        /* Buttons - Gold Gradient */
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

# --- MODEL CONFIGURATION ---
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
    """Swaps background while keeping the user intact."""
    full_prompt = f"""
    Act as a high-end social media photo editor.
    Task: Edit this selfie/photo.
    1. CRITICAL: Keep the person in the foreground EXACTLY as they are (face, hair, clothes, product in hand). Do not alter their identity.
    2. REPLACE the background with: {setting_prompt}.
    3. BLENDING: Adjust the lighting on the subject slightly to match the new background's ambiance so it looks realistic, not like a sticker.
    4. STYLE: High-resolution, "Influencer" aesthetic.
    """
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash", # Using Flash for speed/cost, switch to Pro if quality needed
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
    """Turns boring life updates into MLM success stories."""
    prompt = f"""
    Act as a top-tier Network Marketing Mentor. 
    Task: Rewrite this boring status update into a high-engagement "Lifestyle" caption.
    Input Context: "{context_text}"
    Tone: {tone}
    
    Requirements:
    - Use line breaks for readability.
    - Include 3-5 relevant emojis.
    - subtly mention "freedom", "opportunity", or "biz" without sounding desperate.
    - End with a question to drive engagement.
    """
    try:
        response = client.models.generate_content(model=TEXT_MODEL_ID, contents=prompt)
        return response.text.strip()
    except Exception as e: return str(e)

def analyze_prospect(screenshot_img):
    """Reads a prospect's profile screenshot and writes DMs."""
    prompt = """
    Analyze this screenshot of a social media profile.
    1. Identify the user's potential "Pain Points" (e.g., tired mom, hates job, wants travel) or "Interests" based on their bio and recent posts.
    2. Draft 3 Cold Outreach Messages (DMs) to recruit them:
       - Option 1: The "Soft Connection" (Focus on common ground).
       - Option 2: The "Compliment" (Focus on their vibe/content).
       - Option 3: The "Curiosity Gap" (Vague hook about business).
    
    Strict Rule: Do NOT sound like a bot. Sound like a real human girl/guy reaching out.
    """
    try:
        response = client.models.generate_content(model=TEXT_MODEL_ID, contents=[screenshot_img, prompt])
        return response.text.strip()
    except Exception as e: return str(e)

# ==========================================
# 3. UI LAYOUT
# ==========================================
if not api_key:
    st.warning("⚠️ API Key Missing. Please set GOOGLE_API_KEY in Railway variables.")
    st.stop()

st.title("💎 Lifestyle Lure")
st.markdown("*Fake it 'til you make it. Build your downline faster.*")

# TABS for the 3 Main Features
tab1, tab2, tab3 = st.tabs(["📸 Lifestyle Editor", "📝 Caption Writer", "🕵️ Prospect Analyzer"])

# --- FEATURE 1: IMAGE EDITOR ---
with tab1:
    st.header("Upgrade Your Reality")
    st.info("Upload a selfie from your messy kitchen -> We put you in Dubai.")
    
    img_file = st.file_uploader("Upload Selfie", type=["jpg", "png", "jpeg"], key="lure_upload")
    
    if img_file:
        input_img = Image.open(img_file)
        # Resize immediately for speed/memory safety
        input_img = compress_image(input_img)
        st.image(input_img, caption="Original", width=250)
        
        # Preset Luxury Settings
        setting = st.selectbox("Choose Your New Location:", [
            "Luxury Hotel Balcony in Dubai (Sunset)", 
            "Private Jet Interior (Cream Leather Seats)", 
            "Poolside at a 5-Star Resort (Tropical)", 
            "Modern Minimalist Home Office (Macbook & Coffee)",
            "TED Talk Style Stage (Holding Microphone)"
        ])
        
        if st.button("✨ Transform Photo", key="btn_transform"):
            with st.spinner("Booking your flight... (Generating)"):
                res_img, err = generate_lifestyle_image(input_img, setting)
                if res_img:
                    st.image(res_img, caption="✨ Your New Reality", use_container_width=True)
                    # Download Button logic would go here
                elif err:
                    st.error(f"Error: {err}")

# --- FEATURE 2: CAPTION WRITER ---
with tab2:
    st.header("Humble Brag Generator")
    st.info("Turn small wins into 'Biz Opportunity' posts.")
    
    context = st.text_area("What actually happened?", placeholder="e.g. I bought a coffee today.", height=100)
    tone = st.select_slider("Select Tone", options=["😭 Emotional/Grateful", "🔥 Boss Babe/Hustle", "🤫 Mysterious/Vague"])
    
    if st.button("✍️ Write Caption", key="btn_caption"):
        if context:
            with st.spinner("Spinning the story..."):
                caption = generate_caption(context, tone)
                st.text_area("Copy this:", value=caption, height=250)
        else:
            st.warning("Tell me what happened first!")

# --- FEATURE 3: PROSPECT ANALYZER ---
with tab3:
    st.header("The Warm Outreach Tool")
    st.info("Upload a screenshot of a potential recruit's Instagram/Facebook profile.")
    
    prospect_file = st.file_uploader("Upload Profile Screenshot", type=["jpg", "png", "jpeg"], key="prospect_upload")
    
    if prospect_file:
        p_img = Image.open(prospect_file)
        st.image(p_img, caption="Prospect Profile", width=250)
        
        if st.button("🕵️ Analyze & Write DMs", key="btn_prospect"):
            with st.spinner("Analyzing their psychological profile..."):
                analysis = analyze_prospect(p_img)
                st.markdown(analysis)

st.markdown("---")
st.caption("🔒 Private Tool for Diamond Team Members Only.")