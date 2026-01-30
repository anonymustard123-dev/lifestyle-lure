import os
import stripe
from flask import Flask, request, jsonify
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# 1. Setup & Validation
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
endpoint_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_KEY')

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
    1. Pays the first $10.
    2. STAMPS the 'referred_by' ID onto the Stripe Subscription so we remember it forever.
    """
    # A. Find Referrer
    referrer_id = session.get('client_reference_id') or session.get('metadata', {}).get('referred_by')

    if not referrer_id:
        print("Month 1: No referrer found. Skipping.")
        return

    # B. Stamp the Subscription for Future Months
    # We do this immediately so next month's invoice knows who gets paid.
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
    1. Checks if this is a renewal (billing_reason='subscription_cycle').
    2. Looks up the Subscription to see if it was stamped with a referrer.
    3. Pays the $10.
    """
    # A. Only pay on Renewals (Ignore 'subscription_create' because handle_new_subscription handles that)
    if invoice.get('billing_reason') != 'subscription_cycle':
        print(f"Skipping Invoice {invoice['id']}: Reason is {invoice.get('billing_reason')}")
        return

    # B. Get the Subscription to look for the "Stamp"
    subscription_id = invoice.get('subscription')
    if not subscription_id:
        return

    try:
        # Fetch fresh subscription data from Stripe to get metadata
        sub = stripe.Subscription.retrieve(subscription_id)
        referrer_id = sub.get('metadata', {}).get('referred_by')

        if referrer_id:
            # C. Pay Renewal Commission
            record_commission(referrer_id, invoice.get('customer_email'), "Monthly Renewal Commission")
        else:
            print(f"Renewal: No referrer stamp found on Subscription {subscription_id}")

    except Exception as e:
        print(f"Error processing renewal: {e}")
        # We raise error here so Stripe retries if it's a temp network issue
        raise e

def record_commission(referrer_id, customer_email, desc):
    """
    Reusable function to insert into Supabase.
    The SQL Trigger automatically updates the balance.
    """
    print(f"PAYING COMMISSION: {referrer_id} for {customer_email} ({desc})")
    
    data = {
        'recipient_id': referrer_id,      
        'source_user_email': customer_email, 
        'amount': 10.00,
        'status': 'pending',              
        'type': 'recurring_renewal' if 'Renewal' in desc else 'direct_referral',        
        'description': desc
    }
    
    response = supabase.table('commissions').insert(data).execute()
    
    if hasattr(response, 'error') and response.error:
        raise Exception(f"Supabase DB Error: {response.error}")
        
    print(f"SUCCESS: Commission Recorded.")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 4242))
    app.run(host='0.0.0.0', port=port)
