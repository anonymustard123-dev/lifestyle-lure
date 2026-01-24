import os
import json
import stripe
from flask import Flask, jsonify, request
from supabase import create_client

# ==========================================
# 1. CONFIG
# ==========================================
# Load keys from environment variables
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET") # REQUIRED: Get this from Stripe Dashboard
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Commission Configuration
COMMISSION_AMOUNT = 5.00  # Amount to credit per referral (Change as needed)

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
        # Invalid payload
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return 'Invalid signature', 400

    # Handle the event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        handle_checkout_session(session)

    return jsonify(success=True)

def handle_checkout_session(session):
    """
    Credits the referrer's wallet when a subscription is purchased.
    """
    # 1. Get Referrer ID from Metadata (Set in app.py)
    metadata = session.get('metadata', {})
    referrer_id = metadata.get('referred_by')
    
    if not referrer_id:
        print("No referrer found in metadata. Skipping commission.")
        return

    print(f"Processing commission for Referrer: {referrer_id}")

    # 2. Update Referrer's Balance in Supabase
    try:
        # Fetch current profile
        res = supabase.table("profiles").select("commission_balance").eq("id", referrer_id).execute()
        
        if not res.data:
            print(f"Referrer profile {referrer_id} not found.")
            return
            
        current_balance = res.data[0].get('commission_balance') or 0.0
        new_balance = current_balance + COMMISSION_AMOUNT
        
        # Update the balance
        supabase.table("profiles").update({
            "commission_balance": new_balance
        }).eq("id", referrer_id).execute()
        
        print(f"SUCCESS: Credited ${COMMISSION_AMOUNT} to {referrer_id}. New Balance: ${new_balance}")
        
    except Exception as e:
        print(f"ERROR: Failed to update balance: {str(e)}")

# ==========================================
# 3. RUN SERVER
# ==========================================
if __name__ == '__main__':
    # Railway provides the PORT environment variable
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
