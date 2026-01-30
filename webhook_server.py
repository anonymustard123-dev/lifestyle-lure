import os
import stripe
from flask import Flask, request, jsonify
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup Flask
app = Flask(__name__)

# Setup Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
endpoint_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

# Setup Supabase
url: str = os.getenv('SUPABASE_URL')
key: str = os.getenv('SUPABASE_KEY')
supabase: Client = create_client(url, key)

@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    event = None

    # 1. Verify the Webhook Signature
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        # Invalid payload
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return jsonify({'error': 'Invalid signature'}), 400

    # 2. Handle the Checkout Session Completed Event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        handle_checkout_session(session)

    return jsonify({'status': 'success'}), 200

def handle_checkout_session(session):
    """
    Handles the logic when a user successfully pays.
    SIMPLIFIED LOGIC: Flat $10 commission to the direct referrer.
    """
    
    # Get the user who bought the subscription (The "New User")
    # In Stripe Checkout, client_reference_id is usually set to the Referrer's ID
    # But often we store the *Buyer's* ID in metadata or lookup by email.
    # Assuming standard setup: we need to find who *Referred* this sale.
    
    # Check if there is a referrer attached to this session
    # (Adjust this based on how you pass the referrer ID in app.py)
    referrer_id = session.get('client_reference_id') or session.get('metadata', {}).get('referrer_id')

    if not referrer_id:
        print("No referrer found for this sale. No commission payout.")
        return

    # Get the details of the sale
    customer_email = session.get('customer_details', {}).get('email')
    amount_paid = session.get('amount_total', 0) / 100  # Convert cents to dollars

    print(f"Processing sale for {customer_email}. Referrer: {referrer_id}")

    # --- NEW SIMPLIFIED LOGIC START ---
    
    # 1. Define the flat commission amount
    commission_amount = 10.00
    
    try:
        # 2. Insert the Commission Record into Supabase
        data, count = supabase.table('commissions').insert({
            'recipient_id': referrer_id,      # The person getting paid
            'source_user_email': customer_email, # The person who bought
            'amount': commission_amount,
            'status': 'pending',              # Or 'paid' depending on your flow
            'type': 'direct_referral',        # Tag it clearly
            'description': 'Flat $10 Direct Referral Commission'
        }).execute()
        
        print(f"Success: Recorded $10 commission for {referrer_id}")

    except Exception as e:
        print(f"Error recording commission: {str(e)}")

    # --- NEW SIMPLIFIED LOGIC END ---

if __name__ == '__main__':
    # Run on port 4242 (or whatever port you use in Railway)
    port = int(os.environ.get("PORT", 4242))
    app.run(host='0.0.0.0', port=port)
