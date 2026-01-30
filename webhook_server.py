import os
import stripe
from flask import Flask, request, jsonify
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# ==========================================
# 1. SETUP & VALIDATION
# ==========================================
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
endpoint_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
url = os.getenv('SUPABASE_URL')

# RECOMMENDATION: Use the SERVICE_ROLE_KEY for webhooks to bypass RLS policies
# If you don't have it in your .env, fall back to the standard key, 
# but you must ensure RLS policies allow inserts.
key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')

if not url or not key:
    raise ValueError("CRITICAL: Supabase URL or KEY is missing.")

supabase: Client = create_client(url, key)

@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    event = None

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError:
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError:
        return jsonify({'error': 'Invalid signature'}), 400

    print(f"Received event: {event['type']}")

    # --- ROUTER ---
    if event['type'] == 'checkout.session.completed':
        # MONTH 1: Pay Commission + Stamp Subscription
        handle_new_subscription(event['data']['object'])
        
    elif event['type'] == 'invoice.payment_succeeded':
        # MONTH 2+: Check Subscription Stamp + Pay Commission
        handle_renewal_payment(event['data']['object'])

    return jsonify({'status': 'success'}), 200

def handle_new_subscription(session):
    """
    Runs only on the FIRST payment (Signup).
    """
    # A. Find Referrer
    referrer_id = session.get('client_reference_id') or session.get('metadata', {}).get('referred_by')

    if not referrer_id:
        print("Month 1: No referrer found. Skipping.")
        return

    # B. Stamp the Subscription for Future Months
    subscription_id = session.get('subscription')
    if subscription_id:
        try:
            stripe.Subscription.modify(
                subscription_id,
                metadata={'referred_by': referrer_id}
            )
            print(f"STAMPED Subscription {subscription_id} with referrer {referrer_id}")
        except Exception as e:
            print(f"ERROR Stamping Subscription: {e}")

    # C. Pay Month 1 Commission
    record_commission(referrer_id, session.get('customer_details', {}).get('email'), "Direct Referral (Month 1)")

def handle_renewal_payment(invoice):
    """
    Runs on MONTH 2, 3, 4...
    """
    # A. Only pay on Renewals
    if invoice.get('billing_reason') != 'subscription_cycle':
        print(f"Skipping Invoice {invoice.get('id')}: Reason is {invoice.get('billing_reason')}")
        return

    # B. Get the Subscription
    subscription_id = invoice.get('subscription')
    if not subscription_id:
        return

    try:
        sub = stripe.Subscription.retrieve(subscription_id)
        referrer_id = sub.get('metadata', {}).get('referred_by')

        if referrer_id:
            record_commission(referrer_id, invoice.get('customer_email'), "Monthly Renewal Commission")
        else:
            print(f"Renewal: No referrer stamp found on Subscription {subscription_id}")

    except Exception as e:
        print(f"Error processing renewal: {e}")
        raise e

def record_commission(referrer_id, customer_email, desc):
    """
    1. Inserts into commissions table (ledger).
    2. MANUALLY updates the profiles table (balance).
    """
    amount = 10.00
    print(f"PROCESSING COMMISSION: {referrer_id} | ${amount} | {desc}")

    # 1. INSERT LEDGER RECORD
    try:
        data = {
            'recipient_id': referrer_id,      
            'source_user_email': customer_email, 
            'amount': amount,
            'status': 'paid', # Mark as paid since we are updating balance immediately             
            'type': 'recurring_renewal' if 'Renewal' in desc else 'direct_referral',        
            'description': desc
        }
        supabase.table('commissions').insert(data).execute()
    except Exception as e:
        # Don't crash if ledger fails, we still want to pay the user
        print(f"WARNING: Failed to insert into commissions table: {e}")

    # 2. UPDATE USER BALANCE (The Logic Missing from your previous code)
    try:
        # A. Get current balance
        res = supabase.table("profiles").select("commission_balance").eq("id", referrer_id).execute()
        
        if res.data:
            current_balance = res.data[0].get('commission_balance') or 0.0
            new_balance = float(current_balance) + amount
            
            # B. Write new balance
            supabase.table("profiles").update({
                "commission_balance": new_balance
            }).eq("id", referrer_id).execute()
            
            print(f"SUCCESS: Updated balance for {referrer_id} from ${current_balance} to ${new_balance}")
        else:
            print(f"ERROR: Profile not found for {referrer_id}")

    except Exception as e:
        print(f"CRITICAL ERROR updating profile balance: {e}")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 4242))
    app.run(host='0.0.0.0', port=port)
