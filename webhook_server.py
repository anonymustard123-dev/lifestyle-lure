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

if not url or not key:
    print("CRITICAL ERROR: Supabase URL or KEY is missing.")

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
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError as e:
        return jsonify({'error': 'Invalid signature'}), 400

    # 2. Handle the Checkout Session Completed Event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        # --- ERROR TRAPPING START ---
        # We wrap the logic here to catch the DB error and send it to Stripe
        try:
            handle_checkout_session(session)
        except Exception as e:
            # This is the key fix: Send the error message back to Stripe!
            error_message = f"Webhook Logic Failed: {str(e)}"
            print(error_message)
            return jsonify({'error': error_message}), 500
        # --- ERROR TRAPPING END ---

    return jsonify({'status': 'success'}), 200

def handle_checkout_session(session):
    """
    Handles the logic when a user successfully pays.
    SIMPLIFIED LOGIC: Flat $10 commission to the direct referrer.
    """
    
    # Use 'referred_by' to match the key sent from app.py
    referrer_id = session.get('client_reference_id') or session.get('metadata', {}).get('referred_by')

    if not referrer_id:
        # If this happens, we want to know why!
        raise Exception(f"No referrer_id found in metadata. Metadata received: {session.get('metadata')}")

    # Get the details of the sale
    customer_email = session.get('customer_details', {}).get('email')
    
    # 1. Define the flat commission amount
    commission_amount = 10.00
    
    # 2. Record the transaction in the 'commissions' table (Receipt)
    # If this fails (due to RLS, permissions, connection), it will now throw an error
    # that is caught by the webhook route above.
    data = {
        'recipient_id': referrer_id,      
        'source_user_email': customer_email, 
        'amount': commission_amount,
        'status': 'pending',              
        'type': 'direct_referral',        
        'description': 'Flat $10 Direct Referral Commission'
    }
    
    response = supabase.table('commissions').insert(data).execute()
    
    # Check if Supabase returned an explicit error (sometimes it doesn't raise Exception)
    # The python client usually raises exception on error, but we double check.
    if hasattr(response, 'error') and response.error:
        raise Exception(f"Supabase DB Error: {response.error}")
        
    print(f"Success: Recorded $10 commission receipt for {referrer_id}")
