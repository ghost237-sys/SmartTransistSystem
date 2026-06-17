import base64
import requests
from datetime import datetime
from decouple import config

SANDBOX_BASE_URL = 'https://sandbox.safaricom.co.ke'
PRODUCTION_BASE_URL = 'https://api.safaricom.co.ke'


def normalize_phone_number(phone):
    """
    Converts common Kenyan phone formats to the 2547XXXXXXXX format
    Daraja requires. Raises ValueError if the input doesn't look like
    a valid Kenyan number.
    """
    phone = phone.strip().replace(' ', '').replace('-', '')

    if phone.startswith('+254'):
        phone = phone[1:]
    elif phone.startswith('0'):
        phone = '254' + phone[1:]
    elif phone.startswith('254'):
        pass
    else:
        raise ValueError(f'Unrecognized phone number format: {phone}')

    if len(phone) != 12 or not phone.isdigit():
        raise ValueError(f'Phone number does not match expected length: {phone}')

    return phone


def get_base_url():
    return SANDBOX_BASE_URL if config('MPESA_ENV', default='sandbox') == 'sandbox' else PRODUCTION_BASE_URL


def get_access_token():
    """
    Daraja access tokens are short-lived (~1 hour). We fetch a fresh one
    per request rather than caching for now — simple and correct first,
    optimize with Redis caching later if request volume justifies it.
    """
    consumer_key = config('MPESA_CONSUMER_KEY')
    consumer_secret = config('MPESA_CONSUMER_SECRET')

    response = requests.get(
        f'{get_base_url()}/oauth/v1/generate?grant_type=client_credentials',
        auth=(consumer_key, consumer_secret),
        timeout=10,
    )
    response.raise_for_status()
    return response.json()['access_token']


def generate_password_and_timestamp():
    """
    Daraja's STK push password is base64(Shortcode + Passkey + Timestamp).
    The timestamp must match the format Daraja expects exactly.
    """
    shortcode = config('MPESA_SHORTCODE')
    passkey = config('MPESA_PASSKEY')
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    raw = f'{shortcode}{passkey}{timestamp}'
    password = base64.b64encode(raw.encode()).decode()
    return password, timestamp


def initiate_stk_push(phone_number, amount, account_reference, transaction_desc):
    """
    Initiates an STK push (the M-Pesa PIN prompt) to the customer's phone.
    Returns Daraja's response, which includes CheckoutRequestID — the key
    we use to match the eventual async webhook callback back to this request.
    """
    access_token = get_access_token()
    password, timestamp = generate_password_and_timestamp()
    shortcode = config('MPESA_SHORTCODE')
    callback_url = config('MPESA_CALLBACK_URL')

    payload = {
        'BusinessShortCode': shortcode,
        'Password': password,
        'Timestamp': timestamp,
        'TransactionType': 'CustomerPayBillOnline',
        'Amount': int(amount),  # Daraja sandbox rejects decimal amounts
        'PartyA': phone_number,
        'PartyB': shortcode,
        'PhoneNumber': phone_number,
        'CallBackURL': callback_url,
        'AccountReference': account_reference,
        'TransactionDesc': transaction_desc,
    }

    response = requests.post(
        f'{get_base_url()}/mpesa/stkpush/v1/processrequest',
        json=payload,
        headers={'Authorization': f'Bearer {access_token}'},
        timeout=10,
    )
    if response.status_code != 200:
        raise Exception(f'Daraja error {response.status_code}: {response.text}')
    return response.json()