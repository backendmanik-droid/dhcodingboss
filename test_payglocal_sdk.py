import sys, os
import django
import json
import requests

sys.path.append(r'D:\manik_django\api-codingboss')
sys.path.append(r'D:\manik_django\api-codingboss\scratch\payglocal-python-sdk')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Quiz.settings')
django.setup()

from jwt_helper import JwtHelper
from pem_file_helper import PemFileHelper

payload = {
    "merchantTxnId": "TEST_TXN_123",
    "merchantCallbackURL": "https://example.com/callback",
    "paymentData": {
        "totalAmount": "1.00",
        "txnCurrency": "INR"
    }
}
payload_str = json.dumps(payload)

helper = JwtHelper()
helper.merchant_private_key_kid = django.conf.settings.PAYGLOCAL_PRIVATE_KEY_ID
helper.glocal_public_key_kid = django.conf.settings.PAYGLOCAL_PUBLIC_KEY_ID
helper.merchant_mid = django.conf.settings.PAYGLOCAL_MERCHANT_ID
helper.parent_mid = ""
helper.is_payload_encrypted = True

pem_helper = PemFileHelper()
pem_helper.private_key_pem_file_location = django.conf.settings.PAYGLOCAL_PRIVATE_KEY_PATH
pem_helper.public_key_pem_file_location = django.conf.settings.PAYGLOCAL_PUBLIC_KEY_PATH

jwe_orig = helper.create_jwe_token(payload_str, pem_helper.get_public_key())
jws_orig = helper.create_jws_token_with_rsa(jwe_orig, pem_helper.get_private_key())

headers = {
    "Accept": "application/json",
    "Content-Type": "text/plain",
    "User-Agent": "PostmanRuntime/7.28.4",
    "x-gl-token-external": jws_orig,
}

url = django.conf.settings.PAYGLOCAL_BASE_URL.rstrip("/") + "/gl/v1/payments/initiate/paycollect"
print("Calling SDK-generated tokens...")
resp = requests.post(url, headers=headers, data=jwe_orig, timeout=30)
print("STATUS CODE:", resp.status_code)
print("RESPONSE:", resp.text)
