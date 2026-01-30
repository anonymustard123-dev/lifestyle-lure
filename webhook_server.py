import os
import stripe
from flask import Flask, request, jsonify
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# --- Configuration ---
STRIPE_API_KEY = os.getenv("STRIPE_API_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # MUST be the SERVICE_ROLE key to bypass RLS

# Initialize Clients
stripe.api_key = STRIPE_API_KEY
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.route('/webhook', methods=['POST'])
def webhook():
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

    # --- Handle "invoice.payment_succeeded" ---
    # This fires when a subscription payment (first or recurring) succeeds
    if event['type'] == 'invoice.payment_succeeded':
        invoice = event['data']['object']
        
        # 1. Get the email of the person who just paid
        customer_email = invoice.get('customer_email')
        amount_paid = invoice.get('amount_paid')  # In cents (e.g., 2000 for $20.00)

        print(f"💰 Payment received from: {customer_email}")

        if customer_email:
            try:
                # 2. Find this user in your 'profiles' table to see who referred them
                # We use the service_role key, so we can see everyone.
                payer_response = supabase.table('profiles')\
                    .select('referred_by, id')\
                    .eq('email', customer_email)\
                    .execute()

                # Check if we found the user
                if payer_response.data and len(payer_response.data) > 0:
                    payer_profile = payer_response.data[0]
                    referrer_id = payer_profile.get('referred_by')

                    # 3. If they were referred by someone, give that person money
                    if referrer_id:
                        print(f"👉 User was referred by: {referrer_id}")
                        
                        # A. Fetch the referrer's current balance
                        referrer_data = supabase.table('profiles')\
                            .select('commission_balance')\
                            .eq('id', referrer_id)\
                            .execute()
                        
                        if referrer_data.data:
                            current_balance = float(referrer_data.data[0]['commission_balance'] or 0.0)
                            
                            # B. Calculate new balance (Add $10 flat fee)
                            # You can change 10.00 to whatever commission amount you want
                            new_balance = current_balance + 10.00 
                            
                            # C. Update the referrer's profile directly
                            update_response = supabase.table('profiles')\
                                .update({'commission_balance': new_balance})\
                                .eq('id', referrer_id)\
                                .execute()
                            
                            print(f"✅ Commission updated! New Balance: ${new_balance}")
                        else:
                            print("⚠️ Referrer ID found on user, but Referrer profile does not exist.")
                    else:
                        print("ℹ️ This user has no referrer. No commission paid.")
                else:
                    print(f"⚠️ User with email {customer_email} not found in public.profiles.")

            except Exception as e:
                print(f"❌ Error updating commission: {str(e)}")
                return jsonify(success=False), 500

    return jsonify(success=True)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
