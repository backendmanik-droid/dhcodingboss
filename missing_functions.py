# ============================================================
# PAYTM CONFIG HELPER
# ============================================================

def get_paytm_config():
    """
    Read Paytm settings safely.
    """

    required_settings = [
        "PAYTM_MID",
        "PAYTM_MERCHANT_KEY",
        "PAYTM_WEBSITE",
        "PAYTM_CHANNEL_ID",
        "PAYTM_INDUSTRY_TYPE",
        "PAYTM_INITIATE_URL",
        "PAYTM_STATUS_URL",
        "PAYTM_REFUND_URL",
        "PAYTM_CALLBACK_URL",
    ]

    missing = []

    for item in required_settings:
        if not hasattr(settings, item):
            missing.append(item)

    if missing:
        raise Exception(
            "Missing Paytm settings: " + ", ".join(missing)
        )

    return {
        "MID": str(settings.PAYTM_MID).strip(),
        "MERCHANT_KEY": str(settings.PAYTM_MERCHANT_KEY).strip(),
        "WEBSITE": str(settings.PAYTM_WEBSITE).strip(),
        "CHANNEL_ID": str(settings.PAYTM_CHANNEL_ID).strip(),
        "INDUSTRY_TYPE": str(settings.PAYTM_INDUSTRY_TYPE).strip(),
        "INITIATE_URL": str(settings.PAYTM_INITIATE_URL).strip(),
        "STATUS_URL": str(settings.PAYTM_STATUS_URL).strip(),
        "REFUND_URL": str(settings.PAYTM_REFUND_URL).strip(),
        "CALLBACK_URL": str(settings.PAYTM_CALLBACK_URL).strip(),
    }


# ============================================================
# 1. CREATE PAYTM ORDER / GENERATE TXN TOKEN
# ============================================================

@csrf_exempt
def create_paytm_order(request):

    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "message": "POST method required"
            },
            status=405
        )

    try:

        # ----------------------------------------------------
        # READ REQUEST
        # ----------------------------------------------------

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Invalid JSON"
                },
                status=400
            )

        print("\n========================================")
        print("PAYTM CREATE ORDER REQUEST")
        print("DATA:", data)
        print("========================================")

        # ----------------------------------------------------
        # REQUIRED DATA
        # ----------------------------------------------------

        ecommerce_order_id = data.get("order_id")
        amount_raw = data.get("amount")
        user_id = data.get("user_id")

        if not ecommerce_order_id:
            return JsonResponse(
                {
                    "success": False,
                    "message": "order_id is required"
                },
                status=400
            )

        if amount_raw is None:
            return JsonResponse(
                {
                    "success": False,
                    "message": "amount is required"
                },
                status=400
            )

        if not user_id:
            return JsonResponse(
                {
                    "success": False,
                    "message": "user_id is required"
                },
                status=400
            )

        # ----------------------------------------------------
        # VALIDATE AMOUNT
        # ----------------------------------------------------

        try:

            amount = Decimal(str(amount_raw))

            if amount <= 0:
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Amount must be greater than zero"
                    },
                    status=400
                )

            amount = amount.quantize(Decimal("0.01"))

        except (InvalidOperation, ValueError):

            return JsonResponse(
                {
                    "success": False,
                    "message": "Invalid amount"
                },
                status=400
            )

        amount_string = format(amount, ".2f")

        # ----------------------------------------------------
        # FIND DJANGO ORDER
        # ----------------------------------------------------

        try:

            ecommerce_order = Order.objects.get(
                id=int(ecommerce_order_id)
            )

        except (Order.DoesNotExist, ValueError, TypeError):

            return JsonResponse(
                {
                    "success": False,
                    "message": "E-commerce order not found"
                },
                status=404
            )

        # ----------------------------------------------------
        # FIND CUSTOMER
        # ----------------------------------------------------

        try:

            customer = User.objects.get(
                id=int(user_id)
            )

        except (User.DoesNotExist, ValueError, TypeError):

            return JsonResponse(
                {
                    "success": False,
                    "message": "User not found"
                },
                status=404
            )

        # ----------------------------------------------------
        # PAYTM CONFIG
        # ----------------------------------------------------

        config = get_paytm_config()

        # ----------------------------------------------------
        # GENERATE UNIQUE PAYTM ORDER ID
        # ----------------------------------------------------

        paytm_order_id = (
            "ORDER_" +
            uuid.uuid4().hex[:18]
        )

        # ----------------------------------------------------
        # PAYTM INITIATE URL
        # ----------------------------------------------------

        initiate_url = (
            f"{config['INITIATE_URL']}"
            f"?mid={config['MID']}"
            f"&orderId={paytm_order_id}"
        )

        # ----------------------------------------------------
        # PAYTM BODY
        # ----------------------------------------------------

        body = {

            "requestType": "Payment",

            "mid": config["MID"],

            "websiteName": config["WEBSITE"],

            "orderId": paytm_order_id,

            "txnAmount": {
                "value": amount_string,
                "currency": "INR"
            },

            "userInfo": {
                "custId": str(user_id)
            },

            "callbackUrl": config["CALLBACK_URL"]
        }

        # ==========================================
        # CHECKSUM
        # ==========================================

        merchant_key = config["MERCHANT_KEY"]

        if not merchant_key:
            return JsonResponse({
                "success": False,
                "message": "PAYTM_MERCHANT_KEY is missing"
            }, status=500)

        # IMPORTANT:
        # Generate checksum from the exact body being sent
        body_string = json.dumps(
            body,
            separators=(",", ":"),
            ensure_ascii=False
        )

        print("\n========================================")
        print("PAYTM BODY STRING")
        print(body_string)
        print("========================================")

        signature = PaytmChecksum.generateSignature(
            body_string,
            merchant_key
        )

        print("PAYTM SIGNATURE:")
        print(signature)


        # ==========================================
        # FINAL PAYTM PAYLOAD
        # ==========================================

        payload = {
            "body": body,
            "head": {
                "signature": signature
            }
        }


        # ==========================================
        # DEBUG
        # ==========================================

        print("\n========================================")
        print("PAYTM PRODUCTION CONFIG")
        print("MID:", config["MID"])
        print("WEBSITE:", config["WEBSITE"])
        print("INITIATE URL:", initiate_url)
        print("CALLBACK URL:", config["CALLBACK_URL"])
        print("MERCHANT KEY LENGTH:", len(merchant_key))

        print("\nPAYTM BODY:")
        print(json.dumps(body, indent=4))

        print("\nPAYTM SIGNATURE GENERATED")
        print("Signature length:", len(signature))

        print("\nPAYTM FINAL PAYLOAD:")
        print(json.dumps(payload, indent=4))

        print("========================================")


        # ==========================================
        # CALL PAYTM — ONLY ONCE
        # ==========================================

        response = requests.post(
            initiate_url,
            json=payload,
            headers={
                "Content-Type": "application/json"
            },
            timeout=60
        )

        print("\n========================================")
        print("PAYTM HTTP STATUS:", response.status_code)
        print("PAYTM RESPONSE:", response.text)
        print("========================================")

        # ----------------------------------------------------
        # PARSE RESPONSE
        # ----------------------------------------------------

        try:

            response_data = response.json()

        except ValueError:

            return JsonResponse(
                {
                    "success": False,
                    "message": "Invalid response from Paytm",
                    "http_status": response.status_code,
                    "response": response.text
                },
                status=502
            )

        # ----------------------------------------------------
        # PAYTM RESULT
        # ----------------------------------------------------

        result_info = (
            response_data
            .get("body", {})
            .get("resultInfo", {})
        )

        result_status = result_info.get(
            "resultStatus"
        )

        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        if result_status == "S":

            txn_token = (
                response_data
                .get("body", {})
                .get("txnToken")
            )

            if not txn_token:

                return JsonResponse(
                    {
                        "success": False,
                        "message": "Paytm returned success but txnToken is missing",
                        "details": response_data
                    },
                    status=502
                )

            # ------------------------------------------------
            # CREATE PAYMENT RECORD
            # ------------------------------------------------

            payment = Payment.objects.create(

                order=ecommerce_order,

                customer=customer,

                amount=amount,

                payment_gateway="paytm",

                gateway_order_id=paytm_order_id,

                status="pending",

                gateway_response=response_data
            )

            print("\nPAYTM PAYMENT CREATED")
            print("Payment ID:", payment.id)
            print("Django Order ID:", ecommerce_order.id)
            print("Paytm Order ID:", paytm_order_id)

            # ------------------------------------------------
            # RESPONSE TO FRONTEND
            # ------------------------------------------------

            return JsonResponse(
                {
                    "success": True,

                    "message": "Paytm transaction token generated",

                    # Your Django order
                    "order_id": ecommerce_order.id,

                    # Paytm order
                    "paytm_order_id": paytm_order_id,

                    "payment_id": payment.id,

                    "mid": config["MID"],

                    "amount": amount_string,

                    "txnToken": txn_token,

                    "paytm_response": response_data
                },
                status=200
            )

        # ----------------------------------------------------
        # PAYTM FAILURE
        # ----------------------------------------------------

        return JsonResponse(
            {
                "success": False,

                "message": "Failed to generate transaction token",

                "paytm_result_code": result_info.get(
                    "resultCode"
                ),

                "paytm_result_message": result_info.get(
                    "resultMsg"
                ),

                "details": response_data
            },
            status=400
        )

    except requests.RequestException as e:

        print("\nPAYTM REQUEST ERROR:")
        traceback.print_exc()

        return JsonResponse(
            {
                "success": False,
                "message": "Unable to connect to Paytm",
                "error": str(e)
            },
            status=502
        )

    except Exception as e:

        print("\nCREATE PAYTM ORDER ERROR:")
