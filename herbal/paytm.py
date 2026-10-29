import hashlib
import json
import uuid
import hmac
import requests

from django.conf import settings


class PaytmGateway:

    @staticmethod
    def generate_order_id():

        return "ORDER_" + uuid.uuid4().hex[:18]

    @staticmethod
    def generate_signature(body):

        payload = json.dumps(body)

        key = settings.PAYTM_MERCHANT_KEY

        return hashlib.sha256((payload + key).encode()).hexdigest()

    @staticmethod
    def initiate_transaction(body):

        signature = PaytmGateway.generate_signature(body)

        url = (
            settings.PAYTM_INITIATE_URL
            + f"?mid={settings.PAYTM_MID}"
            + f"&orderId={body['body']['orderId']}"
        )

        headers = {
            "Content-Type": "application/json"
        }

        payload = {
            "body": body["body"],
            "head": {
                "signature": signature
            }
        }

        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=30,
        )

        return response.json()
    
# Checksum Verification

def verify_checksum(body, checksum, merchant_key):

    generated = hmac.new(
        merchant_key.encode(),
        body.encode(),
        hashlib.sha256
    ).hexdigest()

    return generated == checksum


# Signature Generation

def generate_signature(body, merchant_key):

    return hmac.new(

        merchant_key.encode(),

        body.encode(),

        hashlib.sha256

    ).hexdigest()


# checksum = generate_signature(
#     json.dumps(body),
#     settings.PAYTM_MERCHANT_KEY
# )