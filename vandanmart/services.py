from .paytm import PaytmGateway


class PaytmService:

    @staticmethod
    def create_payment(
            amount,
            customer_id,
            mobile,
            email
    ):

        order_id = PaytmGateway.generate_order_id()

        body = {

            "body": {

                "requestType": "Payment",

                "mid": "YOUR_STAGING_MID",

                "websiteName": "WEBSTAGING",

                "orderId": order_id,

                "callbackUrl": "https://yourdomain.com/herbal/paytm/callback/",

                "txnAmount": {

                    "value": str(amount),

                    "currency": "INR"

                },

                "userInfo": {

                    "custId": str(customer_id),

                    "mobile": mobile,

                    "email": email

                }

            }

        }

        response = PaytmGateway.initiate_transaction(body)

        return response