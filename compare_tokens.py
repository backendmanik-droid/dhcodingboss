import os
import sys
import django
import json

# Setup Django
sys.path.append(r'D:\manik_django\api-codingboss')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Quiz.settings')
django.setup()

from herbal.payglocal import create_jwe_token, create_jws_token

payload = {
    "merchantTxnId": "TEST_123",
    "merchantCallbackURL": "https://example.com/callback",
    "paymentData": {
        "totalAmount": "10.00",
        "txnCurrency": "INR"
    }
}
payload_str = json.dumps(payload)

jwe = create_jwe_token(payload_str)
jws = create_jws_token(jwe, is_encrypted=True)

print("JWE Token:")
print(jwe)
print("\nJWS Token:")
print(jws)
