import os
import json
import stripe
from flask import Flask, request, jsonify
from supabase import create_client

# ==========================================
# 1. CONFIGURATION
# ==========================================
app = Flask(__name__)

# Load secrets
STRIPE_API_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET") # NEW: Get this from Stripe Dashboard
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

stripe.api_key = STRIPE_API_KEY
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# 2. HELPER LOGIC (The Infinity Algorithm)
# ==========================================

def fetch_profile_by_email(email):
    try:
        # Note: We assume emails are unique in the profiles table
        res = supabase.table("profiles").select("*").eq("email", email).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]
        return None
    except Exception as e:
        print(f"DB Error: {e}")
        return None

def fetch_profile_by_id(user_id):
    try:
        res = supabase.table("profiles").select("*").eq("id", user_id).execute()
        return res.data[0] if res.data else None
    except: return None

def count_referrals(user_id):
    try:
        res = supabase.table("profiles").select("id", count="exact").eq("referred_by", user_id).execute()
        return res.count
    except: return 0

def process_commission_logic(payer_profile, amount_paid):
    """
    Executes the Infinity Commission split.
    payer_profile: The dict object of the user who paid.
    amount_paid: Float, the transaction amount (e.g. 15.00).
    """
    print(f"Processing commission for payer: {payer_profile.get('email')}")
    
    # 1. IDENTIFY DIRECT REFERRER
    referrer_id = payer_profile.get('referred_by')
    if not referrer_id:
        print("No referrer found. Company keeps 100%.")
        return

    referrer_profile = fetch_profile_by_id(referrer_id)
    if not referrer_profile:
        print("Referrer profile not found.")
        return

    # 2. PAY DIRECT REFERRER (Tier 1: 15%)
    tier1_commission = amount_paid * 0.15
    try:
        current_bal = float(referrer_profile.get('commission_balance') or 0.0)
        new_bal = current_bal + tier1_commission
        supabase.table("profiles").update({'commission_balance': new_bal}).eq("id", referrer_id).execute()
        print(f"Tier 1 Paid: ${tier1_commission} to {referrer_profile.get('email')}")
    except Exception as e:
        print(f"Error paying Tier 1: {e}")
        return

    # 3. ROLL-UP FOR LEADER (Tier 2: 5%)
    # Start looking at the Tier 1's referrer (The Grandparent)
    current_upline_id = referrer_profile.get('referred_by')
    override_amt = amount_paid * 0.05
    max_depth = 20
    
    leader_found = False
    
    for _ in range(max_depth):
        if not current_upline_id:
            break # End of chain
            
        upline_profile = fetch_profile_by_id(current_upline_id)
        if not upline_profile:
            break
            
        # QUALIFICATION CHECK: 10+ Referrals
        ref_count = count_referrals(current_upline_id)
        
        if ref_count >= 10:
            # Found a Leader
            try:
                c_bal = float(upline_profile.get('commission_balance') or 0.0)
                n_bal = c_bal + override_amt
                supabase.table("profiles").update({'commission_balance': n_bal}).eq("id", current_upline_id).execute()
                print(f"Leader Paid: ${override_amt} to {upline_profile.get('email')}")
                leader_found = True
            except Exception as e:
                print(f"Error paying Leader: {e}")
            break # Stop rolling up
            
        # Move up to next parent
        current_upline_id = upline_profile.get('referred_by')

    if not leader_found:
        print("No qualified leader found in upline. Breakage retained.")

# ==========================================
# 3. WEBHOOK ROUTE
# ==========================================
@app.route('/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError as e:
        return 'Invalid signature', 400

    # Handle the event
    if event['type'] == 'invoice.payment_succeeded':
        invoice = event['data']['object']
        
        # 1. Get Details
        customer_email = invoice.get('customer_email')
        amount_paid_cents = invoice.get('amount_paid') # e.g., 1500 for $15.00
        amount_dollars = float(amount_paid_cents) / 100.0
        
        # If email is missing in invoice, try to fetch customer
        if not customer_email and invoice.get('customer'):
             try:
                 cust = stripe.Customer.retrieve(invoice.get('customer'))
                 customer_email = cust.email
             except: pass

        if customer_email:
            # 2. Find User in DB
            profile = fetch_profile_by_email(customer_email)
            
            if profile:
                # 3. Run Commission Logic
                process_commission_logic(profile, amount_dollars)
                
                # 4. Update Last Commission Date (Optional, for auditing)
                # We use specific transaction logs ideally, but updating the profile works for simple tracking
                from datetime import datetime
                supabase.table("profiles").update(
                    {"last_commission_date": datetime.now().isoformat()}
                ).eq("id", profile['id']).execute()
            else:
                print(f"Profile not found for email: {customer_email}")
        else:
            print("No email found in invoice event.")

    return jsonify(success=True)

if __name__ == '__main__':
    # Run on port 4242 (standard for Stripe CLI testing)
    app.run(port=4242)