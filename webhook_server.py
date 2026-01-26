import os
import json
import stripe
from flask import Flask, jsonify, request
from supabase import create_client

# ==========================================
# 1. CONFIG & CONSTANTS
# ==========================================
# Load keys from environment variables
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET") 
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# --- COMMISSION STRUCTURE ---
# Tier 1: Direct Referrer
DIRECT_COMMISSION = 2.25  # 15% of $15

# Overrides (Performance Bonuses)
SCOUT_BONUS = 0.30       # 2% of $15
ELITE_BONUS = 0.75       # 5% of $15

# Thresholds
SCOUT_THRESHOLD = 10     # Referrals needed for Scout status
ELITE_THRESHOLD = 100    # Referrals needed for Elite status

# Initialize App & DB
app = Flask(__name__)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# 2. WEBHOOK LOGIC
# ==========================================
@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    event = None

    try:
        # Verify the event came from Stripe
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError as e:
        return 'Invalid signature', 400

    # Handle the event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        handle_checkout_session(session)

    return jsonify(success=True)

def handle_checkout_session(session):
    """
    Orchestrates the commission payouts:
    1. Direct Commission to the immediate referrer.
    2. Scout & Elite bonuses up the hierarchy (with Shark Rule).
    """
    metadata = session.get('metadata', {})
    direct_referrer_id = metadata.get('referred_by')
    
    if not direct_referrer_id:
        print("No referrer found in metadata. Skipping commission.")
        return

    print(f"--- Processing Sale for Referrer: {direct_referrer_id} ---")

    # ---------------------------------------------------------
    # STEP 1: DIRECT COMMISSION (15%)
    # ---------------------------------------------------------
    credit_user(direct_referrer_id, DIRECT_COMMISSION, "Direct Commission")

    # ---------------------------------------------------------
    # STEP 2: OVERRIDES (Scout & Elite)
    # ---------------------------------------------------------
    # We traverse up the chain starting from the Direct Referrer.
    # If the Direct Referrer is an Elite, they get the bonuses immediately (Shark Rule).
    
    current_user_id = direct_referrer_id
    scout_bonus_remaining = True
    elite_bonus_remaining = True
    
    # Safety limit to prevent infinite loops in case of circular references
    loop_limit = 20 
    depth = 0

    while (scout_bonus_remaining or elite_bonus_remaining) and current_user_id and depth < loop_limit:
        
        # A. Get Profile Data (Upline & Balance)
        profile = get_profile(current_user_id)
        if not profile:
            break # User deleted or invalid
            
        # B. Check Status (Count Referrals)
        ref_count = count_referrals(current_user_id)
        is_scout = ref_count >= SCOUT_THRESHOLD
        is_elite = ref_count >= ELITE_THRESHOLD
        
        payout_amount = 0.0
        payout_notes = []

        # C. Calculate Payouts based on Status & Remaining Pools
        
        # ELITE LOGIC (Includes Shark Rule)
        if is_elite:
            # Captures Elite Bonus
            if elite_bonus_remaining:
                payout_amount += ELITE_BONUS
                elite_bonus_remaining = False
                payout_notes.append("Elite Bonus")
            
            # SHARK RULE: If Elite is found before Scout is paid, they eat the Scout bonus too.
            if scout_bonus_remaining:
                payout_amount += SCOUT_BONUS
                scout_bonus_remaining = False
                payout_notes.append("Shark Bonus (Scout Override)")

        # SCOUT LOGIC
        elif is_scout:
            if scout_bonus_remaining:
                payout_amount += SCOUT_BONUS
                scout_bonus_remaining = False
                payout_notes.append("Scout Bonus")

        # D. Credit User if applicable
        if payout_amount > 0:
            credit_user(current_user_id, payout_amount, ", ".join(payout_notes))

        # E. Move Up the Chain
        current_user_id = profile.get('referred_by')
        depth += 1

    print("--- Commission Processing Complete ---")

# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================
def get_profile(user_id):
    """Fetches profile to find the upline (referred_by)."""
    try:
        res = supabase.table("profiles").select("referred_by").eq("id", user_id).execute()
        if res.data:
            return res.data[0]
    except Exception as e:
        print(f"Error fetching profile {user_id}: {e}")
    return None

def count_referrals(user_id):
    """Counts how many people this user has directly referred."""
    try:
        # We count how many profiles have this user_id as their 'referred_by'
        res = supabase.table("profiles").select("id", count="exact").eq("referred_by", user_id).execute()
        return res.count
    except Exception as e:
        print(f"Error counting referrals for {user_id}: {e}")
        return 0

def credit_user(user_id, amount, note=""):
    """Updates the user's commission balance safely."""
    try:
        # 1. Fetch current balance
        res = supabase.table("profiles").select("commission_balance").eq("id", user_id).execute()
        if not res.data:
            print(f"User {user_id} not found for credit.")
            return

        current_balance = res.data[0].get('commission_balance') or 0.0
        new_balance = current_balance + amount
        
        # 2. Update balance
        supabase.table("profiles").update({
            "commission_balance": new_balance
        }).eq("id", user_id).execute()
        
        print(f"SUCCESS: Credited ${amount:.2f} to {user_id} [{note}]. New Balance: ${new_balance:.2f}")
        
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to credit {user_id}: {e}")

# ==========================================
# 4. RUN SERVER
# ==========================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
