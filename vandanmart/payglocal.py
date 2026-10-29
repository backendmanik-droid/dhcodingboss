import json
import time
import base64
import hashlib
import requests
from django.conf import settings
from jwcrypto import jwk, jwe, jws

PAYGLOCAL_PAYCOLLECT_ENDPOINT = "/gl/v1/payments/initiate/paycollect"

def get_private_key():
    with open(settings.PAYGLOCAL_PRIVATE_KEY_PATH, "rb") as f:
        return jwk.JWK.from_pem(f.read())

def get_public_key():
    with open(settings.PAYGLOCAL_PUBLIC_KEY_PATH, "rb") as f:
        return jwk.JWK.from_pem(f.read())

def create_jwe_token(payload_json_str):
    public_key = get_public_key()
    jwe_headers = {
        'alg': 'RSA-OAEP-256',
        'enc': 'A128CBC-HS256',
        'kid': getattr(settings, "PAYGLOCAL_PUBLIC_KEY_ID", ""),
        'iat': str(int(time.time() * 1000)),
        'exp': 300000,
        'issued-by': getattr(settings, "PAYGLOCAL_MERCHANT_ID", ""),
        'is-digested': 'true'
    }
    jwetoken = jwe.JWE(payload_json_str.encode('utf-8'), json.dumps(jwe_headers, separators=(',', ':')))
    jwetoken.add_recipient(public_key)
    return jwetoken.serialize(compact=True)

def create_jws_token(payload_str, is_encrypted=True):
    private_key = get_private_key()
    digest = hashlib.sha256(payload_str.encode('utf-8')).digest()
    digest_decoded = base64.b64encode(digest).decode("utf-8")
    
    merchant_id = getattr(settings, "PAYGLOCAL_MERCHANT_ID", "")
    jws_headers = {
        'alg': 'RS256',
        'kid': getattr(settings, "PAYGLOCAL_PRIVATE_KEY_ID", ""),
        'x-gl-merchantId': merchant_id,
        'x-gl-enc': 'true' if is_encrypted else 'false',
        'issued-by': merchant_id,
        'is-digested': 'true'
    }
    
    jws_claimset = {
        'digest': digest_decoded,
        'digestAlgorithm': 'SHA-256',
        'iat': str(int(time.time() * 1000)),
        'exp': 300000,
    }
    jwstoken = jws.JWS(payload=json.dumps(jws_claimset, separators=(',', ':')))
    jwstoken.add_signature(key=private_key, protected=jws_headers)
    return jwstoken.serialize(compact=True)

def create_payglocal_payment(payload):
    base_url = getattr(settings, "PAYGLOCAL_BASE_URL", None)
    if not base_url:
        raise Exception("PAYGLOCAL_BASE_URL is not configured in settings.py")
    
    url = base_url.rstrip("/") + PAYGLOCAL_PAYCOLLECT_ENDPOINT
    
    payload_str = json.dumps(payload)
    jwe_token = create_jwe_token(payload_str)
    jws_token = create_jws_token(jwe_token, is_encrypted=True)
    print(jws_token,"jwt")
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "text/plain",
        "User-Agent": "PostmanRuntime/7.28.4",
        "x-gl-token-external": jws_token,
    }
    
    try:
        response = requests.post(url, headers=headers, data=jwe_token, timeout=30)
        return response
    except requests.exceptions.RequestException as e:
        raise Exception(f"PayGlocal API request failed: {str(e)}")

def get_payglocal_response(response):
    try:
        return response.json()
    except ValueError:
        return {"raw_response": response.text}

def is_payglocal_success(response):
    if response.status_code != 200:
        return False
    data = get_payglocal_response(response)
    return data.get("status") == "CREATED"

def get_payglocal_status(gid):
    if not gid:
        raise ValueError("PayGlocal GID is required")
    base_url = settings.PAYGLOCAL_BASE_URL.rstrip("/")
    status_payload = f"/gl/v1/payments/{gid}/status"
    url = base_url + status_payload
    
    jws_token = create_jws_token(status_payload, is_encrypted=False)
    headers = {
        "Accept": "application/json",
        "x-gl-token-external": jws_token,
    }
    print(jws_token,"jwt")
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        return response
    except requests.exceptions.RequestException as e:
        raise Exception(f"PayGlocal status request failed: {str(e)}")

def refund_payglocal_payment(gid, merchant_txn_id, amount):
    if not gid or not merchant_txn_id:
        raise ValueError("PayGlocal GID and merchant_txn_id are required")
    base_url = settings.PAYGLOCAL_BASE_URL.rstrip("/")
    url = base_url + f"/gl/v1/payments/{gid}/refund"
    
    payload = {
        "merchantTxnId": merchant_txn_id,
        "paymentData": {"totalAmount": str(amount)},
    }
    payload_str = json.dumps(payload)
    jwe_token = create_jwe_token(payload_str)
    jws_token = create_jws_token(jwe_token, is_encrypted=True)
    print(jwe_token,"jwe")
    headers = {
        "Accept": "application/json",
        "Content-Type": "text/plain",
        "User-Agent": "PostmanRuntime/7.28.4",
        "x-gl-token-external": jws_token,
    }
    
    try:
        response = requests.post(url, headers=headers, data=jwe_token, timeout=30)
        return response
    except requests.exceptions.RequestException as e:
        raise Exception(f"PayGlocal refund request failed: {str(e)}")
