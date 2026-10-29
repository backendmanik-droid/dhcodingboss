import sys, os
import django
import json

sys.path.append(r'D:\manik_django\api-codingboss')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Quiz.settings')
django.setup()

from herbal.payglocal import create_payglocal_payment

payload = {
    "merchantTxnId": "TEST_TXN_123",
    "merchantCallbackURL": "https://example.com/callback",
    "paymentData": {
        "totalAmount": "1.00",
        "txnCurrency": "INR"
    }
}

try:
    resp = create_payglocal_payment(payload)
    print("STATUS CODE:", resp.status_code)
    print("RESPONSE:", resp.text)
except Exception as e:
    print("ERROR:", e)
