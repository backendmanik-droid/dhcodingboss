from django.http import JsonResponse
from herbal.models import Payment, Order
from herbal.payglocal import get_payglocal_status
from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt
def payglocal_checkin(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "POST required"}, status=405)
    
    try:
        body = json.loads(request.body)
    except Exception:
        body = request.POST.dict()

    payment_id = body.get("payment_id")
    gateway_order_id = body.get("gateway_order_id")
    gateway_transaction_id = body.get("gateway_transaction_id")

    payment = None
    if payment_id:
        payment = Payment.objects.filter(id=payment_id).first()
    elif gateway_transaction_id:
        payment = Payment.objects.filter(gateway_transaction_id=gateway_transaction_id).first()
    elif gateway_order_id:
        payment = Payment.objects.filter(gateway_order_id=gateway_order_id).first()
    
    if not payment:
        return JsonResponse({"success": False, "message": "Payment not found"}, status=404)

    gid = payment.gateway_transaction_id
    if not gid:
        return JsonResponse({"success": False, "message": "No gateway_transaction_id (GID) found for this payment"}, status=400)

    try:
        response = get_payglocal_status(gid)
        response_data = response.json()
        
        gateway_status = (
            response_data.get("status")
            or response_data.get("Status")
            or response_data.get("data", {}).get("status")
            or response_data.get("paymentData", {}).get("status")
        )
        
        if gateway_status:
            gateway_status = str(gateway_status).upper()

        if gateway_status in ["SUCCESS", "SENT_FOR_CAPTURE", "CAPTURED"]:
            payment.status = "success"
        elif gateway_status in ["FAILED", "FAILURE", "CANCELLED", "CUSTOMER_CANCELLED", "PAYMENT_FAILED"]:
            payment.status = "failed"
        else:
            payment.status = "pending"

        payment.gateway_response = response_data
        payment.save()

        # Update order if payment successful
        if payment.status == "success" and payment.order:
            order = payment.order
            if order.status != "confirmed":
                order.status = "confirmed"
                order.save()

        return JsonResponse({
            "success": True,
            "message": "Payment status checked and updated successfully",
            "payment_id": payment.id,
            "status": payment.status,
            "gateway_status": gateway_status,
            "data": response_data
        })

    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)
