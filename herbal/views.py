import json
import threading
import requests
from django.http import JsonResponse
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db.models import Sum, Count, Q
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, redirect, get_object_or_404
import razorpay
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import *
from django.views.decorators.csrf import csrf_exempt
import random
from django.core.mail import get_connection
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
import traceback
from django.http import QueryDict
from collections import defaultdict
from .serializers import *
from paytmpg.pg.Payment import Payment as PaytmSdkPayment
from .paytm import generate_signature
import uuid
from rest_framework import status
from paytmchecksum import PaytmChecksum

# ==========================
# Paytm SDK Imports
# ==========================
from paytmpg import (
    MerchantProperty,
    LibraryConstants,
    Payment as PaytmSdkPaymentType,
    Refund,
    PaymentDetailsBuilder,
    PaymentStatusDetailBuilder,
    RefundDetailBuilder,
    RefundStatusDetailBuilder,
    UserInfo,
    Money,
    EnumCurrency,
    EChannelId,
)


def send_email_with_fallback(
    subject,
    message,
    from_email=None,
    recipient=None,
    recipient_list=None,
    fail_silently=False,
):
    if recipient is None and recipient_list:
        recipient = recipient_list[0] if isinstance(recipient_list, list) else recipient_list

    if isinstance(recipient, list):
        recipient = recipient[0]

    if from_email is None:
        from_email = settings.EMAIL_HOST_USER

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[recipient],
            fail_silently=fail_silently,
        )
    except Exception:
        connection = get_connection(
            host=settings.EMAIL_HOST,
            port=settings.EMAIL_PORT,
            username=settings.EMAIL_HOST_USER_2,
            password=settings.EMAIL_HOST_PASSWORD_2,
            use_tls=True,
        )
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.EMAIL_HOST_USER_2,
            recipient_list=[recipient],
            connection=connection,
            fail_silently=fail_silently,
        )


import time

def send_sms_otp(mobile, otp, purpose="registration"):

    try:
        start = time.time()

        mobile = str(mobile).strip()

        if purpose == "user_login":
            template_id = "1777179128828939213"
            message = (
                f"<#> {otp} is your OTP to securely log in to your Dharani Herbals account. "
                f"This OTP is valid for 5 minutes. Do not share it with anyone.\n"
                f"@dharaniherbbals.in # {otp}"
            )
        else:
            template_id = getattr(settings, "SMS_TEMPLATE_ID", "")
            message = (
                f"OTP for Login/Transaction on Dharani Herbbals is {otp} "
                f"and valid for 30 minutes. "
                f"Do not share this OTP with anyone for security reasons."
            )

        # SMS gateway URL
        url = (
            f"{settings.SMS_API_URL}"
            f"username={settings.SMS_USERNAME}"
            f"&password={settings.SMS_PASSWORD}"
            f"&sender_id={settings.SMS_SENDER_ID}"
            f"&route=T"
            f"&phonenumber={mobile}"
            f"&message={requests.utils.quote(message)}"
        )
        if template_id:
            url += f"&template_id={template_id}"

        print("Calling SMS API...")

        response = requests.get(url, timeout=30)

        end = time.time()

        print("SMS RESPONSE:", response.text)
        print("TIME TAKEN:", round(end - start, 2), "seconds")

        return response

    except requests.exceptions.RequestException as e:

        print("SMS REQUEST ERROR:", e)
        return None

    except Exception as e:

        print("SMS ERROR:", e)
        return None

def send_sms_background(mobile, otp, purpose="registration"):
    send_sms_otp(mobile, otp, purpose)

# Utility to construct full URL for images if needed. For now, we'll just return the relative path.
def get_image_url(request, image_field):
    if image_field:
        try:
            val = str(image_field)
            if val.startswith('http://') or val.startswith('https://'):
                return val
        except Exception:
            pass
        if hasattr(image_field, 'url'):
            return f"https://api.codingboss.in{image_field.url}"
    return None

def get_role(request):
    role = (
        request.GET.get("role")
        or request.POST.get("role")
    )

    if role:
        return role.lower()

    user_id = (
        request.GET.get("user_id")
        or request.POST.get("user_id")
    )

    if user_id:
        try:
            user = User.objects.get(id=user_id)
            return user.role.lower()
        except User.DoesNotExist:
            pass

    return "customer"


def serialize_product(request, p, role='customer'):
    """
    Serialize a product with role-based price visibility.
    - admin         : sees ALL prices (can edit via dashboard)
    - staff         : sees customer + retailer + distributor (view only)
    - retailer      : sees customer + retailer price only
    - distributor   : sees customer + distributor price only
    - customer      : sees customer_price only
    """
    extra_images = ProductImage.objects.filter(
        product=p,
        is_active=True
    )
    if role == "staff":
        display_price = p.store_price

    elif role == "retailer":
        display_price = p.retailer_price or p.customer_price

    elif role == "distributor":
        display_price = p.distributor_price or p.customer_price

    else:
        display_price = p.customer_price
    base = {
        'id': p.id,
        'product_code': p.product_code,
        'barcode': p.barcode,
        'category': p.category.id if p.category else None,
        'category_name': p.category.name if p.category else '',
        'brand': p.brand.name if p.brand else None,
        'brand_id': p.brand.id if p.brand else None,
        'name': p.name,
        'erp_item_id': p.erp_item_id,
        'tamil_name': p.tamil_name,
        'description': p.description,
        'product_type': p.product_type,
        'unit': p.unit,
        'weight_volume': p.weight_volume,
        'stock': p.stock,
        'mrp': str(p.mrp) if p.mrp else '0',
        'price': str(display_price),
        'gst_percentage': str(p.gst_percentage),
        'image': get_image_url(request, p.image),
        'extra_images': [
            get_image_url(request, img.image)
            for img in extra_images
        ],
        'is_new': p.is_new,
        'is_public': p.is_public,
        'created_at': p.created_at.isoformat(),
    }

    if role == "admin":
        base.update({
            "purchase_price": str(p.purchase_price),
            "store_price": str(p.store_price),
            "reseller_price": str(p.reseller_price or 0),
            "retailer_price": str(p.retailer_price or 0),
            "distributor_price": str(p.distributor_price or 0),
            "sarvo_price": str(p.sarvo_price or 0),
            "drug_price": str(p.drug_price or 0),
            "reorder_level": p.reorder_level,
            "batch_number": p.batch_number,
            "manufacturer": p.manufacturer,
            "expiry_date": p.expiry_date.isoformat() if p.expiry_date else None,
            "is_active": p.is_active,
        })

    elif role == "staff":
        base.update({
            "store_price": str(p.store_price)
        })
    elif role == 'retailer':
        base.update({
            'retailer_price': str(p.retailer_price) if p.retailer_price else '0',
            'price_note': 'Retailer price is your applicable rate.',
        })
    elif role == 'distributor':
        base.update({
            'distributor_price': str(p.distributor_price) if p.distributor_price else '0',
            'price_note': 'Distributor price is your applicable rate.',
        })
    # customer: only base fields (customer_price already in base)

    return base

def serialize_review(review):

    return {
        "id": review.id,

        "product_id": review.product.id,

        "product_name": review.product.name,

        "product_code": review.product.product_code,

        "user_id": review.customer.id,

        "customer_name": review.customer.name,

        "rating": review.rating,

        "review_text": review.review_text,

        "status": review.status,

        "approved_by": review.approved_by.name if review.approved_by else None,

        "approved_at": review.approved_at.isoformat() if review.approved_at else None,

        "created_at": review.created_at.isoformat(),

        "updated_at": review.updated_at.isoformat()
    }

def get_rating_summary(product):

    approved_reviews = ProductReview.objects.filter(
        product=product,
        status="approved"
    )

    total_reviews = approved_reviews.count()

    if total_reviews == 0:

        return {
            "average_rating": 0,
            "total_reviews": 0,
            "rating_breakdown": {
                "5": 0,
                "4": 0,
                "3": 0,
                "2": 0,
                "1": 0
            }
        }

    total_rating = sum(r.rating for r in approved_reviews)

    average_rating = round(
        total_rating / total_reviews,
        1
    )

    return {
        "average_rating": average_rating,

        "total_reviews": total_reviews,

        "rating_breakdown": {
            "5": approved_reviews.filter(rating=5).count(),
            "4": approved_reviews.filter(rating=4).count(),
            "3": approved_reviews.filter(rating=3).count(),
            "2": approved_reviews.filter(rating=2).count(),
            "1": approved_reviews.filter(rating=1).count(),
        }
    }

@csrf_exempt
def address_management(request, user_id=None):

    # ==========================================
    # GET - LIST USER ADDRESSES
    # ==========================================
    if request.method == 'GET':
        try:
            user = get_object_or_404(User, id=user_id)

            role = request.GET.get("role")

            if role and user.role.lower() != role.lower():
                return JsonResponse(
                    {"message": "User not found"},
                    status=404
                )

            addresses = Address.objects.filter(
                user=user
            ).order_by('-id')

            data = []

            for address in addresses:
                data.append({
                    'id': address.id,
                    'full_name': address.full_name,
                    'phone': address.phone,
                    'address': address.address,
                    'city': address.city,
                    'state': address.state,
                    'pincode': address.pincode,
                    'latitude': str(address.latitude) if address.latitude else '',
                    'longitude': str(address.longitude) if address.longitude else '',
                    'is_default': address.is_default
                })

            return JsonResponse({
                'user_id': user.id,
                'user_name': user.name,
                'total_addresses': len(data),
                'addresses': data
            }, status=200)

        except Exception as e:
            return JsonResponse({
                'message': str(e)
            }, status=400)

    # ==========================================
    # POST - ADD ADDRESS
    # ==========================================
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)

            user = get_object_or_404(
                User,
                id=data.get('user_id')
            )

            if data.get('is_default'):

                Address.objects.filter(
                    user=user
                ).update(is_default=False)

            address = Address.objects.create(
                user=user,
                full_name=data.get('full_name'),
                phone=data.get('phone'),
                address=data.get('address'),
                city=data.get('city'),
                state=data.get('state'),
                pincode=data.get('pincode'),
                latitude=data.get('latitude') or None,
                longitude=data.get('longitude') or None,
                is_default=data.get('is_default', False)
            )

            return JsonResponse({
                'message': 'Address added successfully',
                'address_id': address.id
            }, status=201)

        except Exception as e:
            return JsonResponse({
                'message': str(e)
            }, status=400)

    # ==========================================
    # PUT - UPDATE ADDRESS
    # ==========================================
    elif request.method == 'PUT':
        try:
            data = json.loads(request.body)

            address = get_object_or_404(
                Address,
                id=data.get('address_id')
            )

            if data.get('is_default'):

                Address.objects.filter(
                    user=address.user
                ).exclude(
                    id=address.id
                ).update(is_default=False)

            address.full_name = data.get(
                'full_name',
                address.full_name
            )

            address.phone = data.get(
                'phone',
                address.phone
            )

            address.address = data.get(
                'address',
                address.address
            )

            address.city = data.get(
                'city',
                address.city
            )

            address.state = data.get(
                'state',
                address.state
            )

            address.pincode = data.get(
                'pincode',
                address.pincode
            )

            address.latitude = data.get(
                'latitude',
                address.latitude
            )

            address.longitude = data.get(
                'longitude',
                address.longitude
            )

            if 'is_default' in data:
                address.is_default = data.get(
                    'is_default'
                )

            address.save()

            return JsonResponse({
                'message': 'Address updated successfully'
            }, status=200)

        except Exception as e:
            return JsonResponse({
                'message': str(e)
            }, status=400)

    # ==========================================
    # DELETE - DELETE ADDRESS
    # ==========================================
    elif request.method == 'DELETE':
        try:
            data = json.loads(request.body)

            address = get_object_or_404(
                Address,
                id=data.get('address_id')
            )

            address.delete()

            return JsonResponse({
                'message': 'Address deleted successfully'
            }, status=200)

        except Exception as e:
            return JsonResponse({
                'message': str(e)
            }, status=400)

    return JsonResponse({
        'message': 'Method not allowed'
    }, status=405)

# =====================================================
# NOTIFICATION HELPERS
# =====================================================

def send_whatsapp_message(mobile, message):
    """
    WhatsApp API integration placeholder.
    Returns False until a real API (Meta Cloud / Twilio) is configured.
    Status will be saved as 'pending' — not 'sent' — until this is implemented.
    """
    # TODO: Replace with real API call, e.g.:
    # import requests
    # resp = requests.post('https://graph.facebook.com/v16.0/PHONE_ID/messages', json={...}, headers={'Authorization': 'Bearer TOKEN'})
    # return resp.status_code == 200
    print(f"[WhatsApp NOT SENT] To: {mobile} | Message: {message[:60]}...")
    return False   # ← Correctly returns False until WhatsApp API is wired up


def create_and_send_notification(customer, notif_type, subject, message):
    """
    Creates notification records and handles actual sending.
    notif_type: 'email' or 'whatsapp'
    Status values: 'sent', 'failed', 'pending', 'not_configured'
    """
    status = 'pending'
    error_detail = ''

    try:
        if notif_type == 'email':
            email_user = getattr(settings, 'EMAIL_HOST_USER', '')
            email_pass = getattr(settings, 'EMAIL_HOST_PASSWORD', '')
            placeholder_values = {'yourgmail@gmail.com', 'gmail_app_password', '', None}

            if email_user in placeholder_values or email_pass in placeholder_values:
                status = 'not_configured'
                error_detail = 'Email credentials not configured in settings.py'
                print(f"[Email NOT SENT] {error_detail}")
            elif not customer.email:
                status = 'failed'
                error_detail = 'Customer has no email address'
            else:
                send_email_with_fallback(subject, message, settings.DEFAULT_FROM_EMAIL, [customer.email])
                status = 'sent'

        elif notif_type == 'whatsapp':
            if not customer.mobile:
                status = 'failed'
                error_detail = 'Customer has no mobile number'
            elif send_whatsapp_message(customer.mobile, message):
                status = 'sent'
            else:
                status = 'pending'   # WhatsApp not yet integrated — awaiting API setup
                error_detail = 'WhatsApp API not yet configured'
        else:
            status = 'failed'
            error_detail = f'Unknown notification type: {notif_type}'

    except Exception as e:
        print(f"[Notification ERROR] {notif_type}: {str(e)}")
        status = 'failed'
        error_detail = str(e)

    # Save to Notification model
    Notification.objects.create(
        customer=customer,
        notification_type=notif_type,
        subject=subject,
        message=message,
        status=status,
        sent_at=timezone.now() if status == 'sent' else None
    )

    # Save to NotificationLog
    NotificationLog.objects.create(
        customer=customer,
        notification_type=notif_type,
        message=f"{message}" + (f" [ERROR: {error_detail}]" if error_detail else ''),
        status=status
    )

    return status == 'sent'


@csrf_exempt
def register(request):

    if request.method == "POST":

        try:

            data = (
                json.loads(request.body)
                if request.content_type == "application/json"
                else request.POST
            )

            name = data.get("name")
            mobile = data.get("mobile")
            password = data.get("password")
            email = data.get("email")
            role = "customer"

            if not name or not mobile or not password:
                return JsonResponse(
                    {"message": "Required fields missing"},
                    status=400
                )

            if User.objects.filter(mobile=mobile).exists():
                return JsonResponse(
                    {"message": "Mobile already exists"},
                    status=400
                )
            if email and User.objects.filter(email=email).exists():

                return JsonResponse(
                    {"message": "Email already exists"},
                    status=400
                )

            PendingRegistration.objects.filter(
                mobile=mobile
            ).delete()

            if email:
                PendingRegistration.objects.filter(
                    email=email
                ).delete()
            otp = str(random.randint(100000, 999999))

            pending_user = PendingRegistration.objects.create(
                name=name,
                mobile=mobile,
                email=email,
                password=password,
                role=role
            )
            
            expires_at = timezone.now() + timedelta(minutes=30)
            OTPVerification.objects.filter(mobile=mobile).delete()
            OTPVerification.objects.create(
                mobile=mobile,
                otp=otp,
                expires_at=expires_at
            )

            send_email_with_fallback(
                subject="Dharani Herbals - Account Verification OTP",
                message=f"""
            Welcome to Dharani Herbals!

            Dear {pending_user.name},

            Your One-Time Password (OTP) for account verification is:

            {otp}

            This OTP is valid for 30 minutes.

            Regards,
            Dharani Herbals Team
            """,
                recipient=email
            )

            threading.Thread(
                target=send_sms_background,
                args=(pending_user.mobile, otp),
                daemon=True
            ).start()

            return JsonResponse({
                "success": True,
                "message": "OTP sent successfully",
                "mobile": pending_user.mobile,
                "otp": otp
            })

        except Exception as e:

            return JsonResponse({
                "error": str(e)
            }, status=400)

    return JsonResponse({
        "message": "Method not allowed"
    }, status=405)
    
# email=email,

@csrf_exempt
def user_login(request):

    if request.method != "POST":
        return JsonResponse({
            "success": False,
            "message": "Only POST method is allowed"
        }, status=405)

    try:
        if request.content_type == "application/json":
            data = json.loads(request.body)
        else:
            data = request.POST

        mobile = data.get("mobile")

        if not mobile:
            return JsonResponse({
                "success": False,
                "message": "Mobile number is required"
            }, status=400)

        mobile = str(mobile).strip()

        # =====================================================
        # CHECK USER (Prioritize non-customer roles)
        # =====================================================

        user = User.objects.filter(mobile=mobile).exclude(role='customer').first()
        if not user:
            user = User.objects.filter(mobile=mobile).first()

        # =====================================================
        # IF USER EXISTS
        # =====================================================

        if user:
            otp = str(random.randint(100000, 999999))

            EmailOTP.objects.filter(
                user=user,
                purpose="user_login",
                is_verified=False
            ).delete()

            EmailOTP.objects.create(
                user=user,
                otp=otp,
                purpose="user_login"
            )

            if user.email:
                threading.Thread(
                    target=send_email_with_fallback,
                    kwargs={
                        "subject": "Dharani Herbals - Login OTP",
                        "message": f"""
Welcome to Dharani Herbals!

Dear {user.name},

Your One-Time Password (OTP) for login is:

{otp}

This OTP is valid for 30 minutes.

Regards,
Dharani Herbals Team
""",
                        "recipient": user.email
                    },
                    daemon=True
                ).start()

            threading.Thread(
                target=send_sms_background,
                args=(user.mobile, otp, "user_login"),
                daemon=True
            ).start()

            return JsonResponse({
                "success": True,
                "is_new_user": False,
                "message": "OTP sent successfully",
                "user_id": user.id,
                "mobile": user.mobile,
                "otp": otp
            })

        # =====================================================
        # ELSE USER DOES NOT EXIST
        # =====================================================

        else:
            name = data.get("name") or "Guest User"
            email = data.get("email")

            if email:
                email = str(email).strip()

            # IMPORTANT:
            # PendingRegistration.email cannot be NULL
            guest_email = email or f"{mobile}@guest.com"

            # Check real email only
            if email and User.objects.filter(email=email).exists():

                return JsonResponse({
                    "success": False,
                    "message": "Email already exists"
                }, status=400)

            # Remove previous pending registration
            PendingRegistration.objects.filter(
                mobile=mobile
            ).delete()

            # Remove previous OTP
            OTPVerification.objects.filter(
                mobile=mobile
            ).delete()

            # Generate OTP
            otp = str(random.randint(100000, 999999))

            # =================================================
            # CREATE PENDING USER
            # =================================================

            pending_user = PendingRegistration.objects.create(
                name=name,
                mobile=mobile,
                email=guest_email,
                password="",
                role="customer"
            )

            # =================================================
            # SAVE OTP
            # =================================================

            expires_at = timezone.now() + timedelta(minutes=30)

            OTPVerification.objects.create(
                mobile=mobile,
                otp=otp,
                expires_at=expires_at
            )

            # Send email in background only if actual email was provided
            if email:
                threading.Thread(
                    target=send_email_with_fallback,
                    kwargs={
                        "subject": "Dharani Herbals - Account Verification OTP",
                        "message": f"""
Welcome to Dharani Herbals!

Dear {name},

Your One-Time Password (OTP) for account verification is:

{otp}

This OTP is valid for 30 minutes.

Regards,
Dharani Herbals Team
""",
                        "recipient": email
                    },
                    daemon=True
                ).start()

            # Send SMS
            threading.Thread(
                target=send_sms_background,
                args=(mobile, otp, "user_login"),
                daemon=True
            ).start()

            return JsonResponse({
                "success": True,
                "is_new_user": True,
                "message": "OTP sent successfully",
                "mobile": mobile,
                "otp": otp
            })

    except Exception as e:

        print("LOGIN ERROR:", str(e))

        return JsonResponse({
            "success": False,
            "message": str(e)
        }, status=500)


# ==========================================
# WATI CONTACT MANAGEMENT
# ==========================================

import requests
from django.conf import settings


def save_customer_to_wati(customer):

    mobile = str(customer.mobile).strip()

    if mobile.startswith("+91"):
        whatsapp_number = mobile[1:]

    elif mobile.startswith("91") and len(mobile) == 12:
        whatsapp_number = mobile

    elif len(mobile) == 10:
        whatsapp_number = "91" + mobile

    else:
        raise ValueError(
            f"Invalid mobile number: {mobile}"
        )

    url = (
        f"{settings.WATI_BASE_URL}"
        f"/api/v1/addContact/{whatsapp_number}"
    )

    headers = {
        "Authorization": f"Bearer {settings.WATI_API_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "name": customer.name or "வாடிக்கையாளர்"
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=15
    )

    print("========== WATI CONTACT ==========")
    print("CUSTOMER:", customer.id)
    print("NAME:", customer.name)
    print("MOBILE:", mobile)
    print("WATI NUMBER:", whatsapp_number)
    print("STATUS:", response.status_code)
    print("RESPONSE:", response.text)

    return response
import requests
from django.conf import settings

import requests
from django.conf import settings


import requests
from django.conf import settings


# ==========================================
# WATI LOGIN WHATSAPP
# ==========================================

def send_login_whatsapp(customer):

    mobile = str(customer.mobile).strip()

    # ------------------------------------------
    # Convert Indian number
    # ------------------------------------------

    if mobile.startswith("+91"):
        whatsapp_number = mobile[1:]

    elif mobile.startswith("91") and len(mobile) == 12:
        whatsapp_number = mobile

    elif len(mobile) == 10:
        whatsapp_number = "91" + mobile

    else:
        raise ValueError(
            f"Invalid mobile number: {mobile}"
        )

    # ------------------------------------------
    # WATI URL
    # ------------------------------------------

    url = (
        f"{settings.WATI_BASE_URL}"
        f"/api/v1/sendTemplateMessage"
    )

    # ------------------------------------------
    # Headers
    # ------------------------------------------

    headers = {
        "Authorization": f"Bearer {settings.WATI_API_TOKEN}",
        "Content-Type": "application/json",
    }

    # ------------------------------------------
    # Recipient
    # ------------------------------------------

    params = {
        "whatsappNumber": whatsapp_number
    }

    # ------------------------------------------
    # APPROVED TEMPLATE
    # ------------------------------------------

    payload = {
        "template_name": "dharani_login_success77",
        "broadcast_name": "customer_login",
        "parameters": [
            {
                "name": "name",
                "value": customer.name or "Customer"
            }
        ]
    }

    # ------------------------------------------
    # DEBUG
    # ------------------------------------------

    print("")
    print("========================================")
    print("WATI LOGIN REQUEST")
    print("========================================")
    print("BASE URL:", settings.WATI_BASE_URL)
    print("FULL URL:", url)
    print("PARAMS:", params)
    print("WHATSAPP NUMBER:", whatsapp_number)
    print("TEMPLATE:", payload["template_name"])
    print("PAYLOAD:", payload)
    print("TOKEN EXISTS:", bool(settings.WATI_API_TOKEN))
    print("========================================")

    # ------------------------------------------
    # SEND REQUEST
    # ------------------------------------------

    try:

        response = requests.post(
            url,
            params=params,
            headers=headers,
            json=payload,
            timeout=15
        )

        # ------------------------------------------
        # RESPONSE
        # ------------------------------------------

        print("========== WATI LOGIN RESPONSE ==========")
        print("REQUEST URL:", response.request.url)
        print("STATUS:", response.status_code)
        print("RESPONSE:", response.text)
        print("==========================================")

        return response

    except requests.RequestException as e:

        print("========== WATI LOGIN ERROR ==========")
        print("ERROR:", str(e))
        print("======================================")

        return None

# =====================================================
# WATI INTEGRATION HELPERS
# =====================================================

@csrf_exempt
def verify_user_login_otp(request):

    if request.method != "POST":
        return JsonResponse({
            "success": False,
            "message": "Only POST method is allowed"
        }, status=405)

    try:

        # =====================================================
        # READ REQUEST DATA
        # =====================================================

        if request.content_type == "application/json":
            data = json.loads(request.body)
        else:
            data = request.POST

        user_id = data.get("user_id")
        mobile = data.get("mobile")
        otp = data.get("otp")

        otp = str(otp).strip() if otp else ""

        # =====================================================
        # EXISTING USER LOGIN
        # =====================================================

        if user_id:

            user = User.objects.filter(
                id=user_id
            ).first()

            if not user:
                return JsonResponse({
                    "success": False,
                    "message": "User not found"
                }, status=404)

            otp_obj = EmailOTP.objects.filter(
                user=user,
                otp=otp,
                purpose="user_login",
                is_verified=False
            ).order_by("-created_at").first()

            if not otp_obj:
                return JsonResponse({
                    "success": False,
                    "message": "Invalid OTP"
                }, status=400)

            # =================================================
            # CHECK OTP EXPIRY
            # =================================================

            if timezone.now() > otp_obj.created_at + timedelta(minutes=30):

                otp_obj.delete()

                return JsonResponse({
                    "success": False,
                    "message": "OTP expired"
                }, status=400)

            # =================================================
            # VERIFY OTP
            # =================================================

            otp_obj.is_verified = True
            otp_obj.save()

            # =================================================
            # WATI - EXISTING CUSTOMER
            # =================================================

            try:

                save_customer_to_wati(user)

                send_login_whatsapp(user)

            except Exception as wati_error:

                print(
                    "WATI EXISTING USER ERROR:",
                    str(wati_error)
                )

            # =================================================
            # LOGIN SUCCESS
            # =================================================

            return JsonResponse({

                "success": True,

                "is_new_user": False,

                "message": "Login successful",

                "user": {

                    "id": user.id,

                    "name": user.name,

                    "mobile": user.mobile,

                    "email": user.email,
                    
                    "role": user.role,
                    
                    "is_store_member": user.role == "staff",

                    "can_send_notifications":
                        user.can_send_notifications
                }

            }, status=200)

        # =====================================================
        # NEW USER VERIFICATION
        # =====================================================

        if not mobile:

            return JsonResponse({
                "success": False,
                "message": "Mobile number or user_id is required"
            }, status=400)

        mobile = str(mobile).strip()

        # =====================================================
        # FIND OTP
        # =====================================================

        otp_obj = OTPVerification.objects.filter(
            mobile=mobile,
            otp=otp
        ).first()

        if not otp_obj:

            return JsonResponse({
                "success": False,
                "message": "Invalid OTP"
            }, status=400)

        # =====================================================
        # CHECK OTP EXPIRY
        # =====================================================

        if timezone.now() > otp_obj.expires_at:

            otp_obj.delete()

            return JsonResponse({
                "success": False,
                "message": "OTP expired"
            }, status=400)

        # =====================================================
        # GET PENDING REGISTRATION
        # =====================================================

        pending_user = PendingRegistration.objects.filter(
            mobile=mobile
        ).first()

        if not pending_user:

            return JsonResponse({
                "success": False,
                "message": "Registration data not found"
            }, status=404)

        # =====================================================
        # CHECK IF USER ALREADY EXISTS
        # =====================================================

        existing_user = User.objects.filter(mobile=mobile).exclude(role='customer').first()
        if not existing_user:
            existing_user = User.objects.filter(mobile=mobile).first()

        if existing_user:

            otp_obj.delete()
            pending_user.delete()

            # =================================================
            # WATI - EXISTING CUSTOMER
            # =================================================

            try:

                save_customer_to_wati(existing_user)

                send_login_whatsapp(existing_user)

            except Exception as wati_error:

                print(
                    "WATI EXISTING USER ERROR:",
                    str(wati_error)
                )

            return JsonResponse({

                "success": True,

                "is_new_user": False,

                "message": "Login successful",

                "user": {

                    "id": existing_user.id,

                    "name": existing_user.name,

                    "mobile": existing_user.mobile,

                    "email": existing_user.email,

                    "role": existing_user.role,
                    
                    "is_store_member": existing_user.role == "staff"
                }

            }, status=200)

        # =====================================================
        # CREATE NEW USER
        # =====================================================

        user = User.objects.create(

            name=pending_user.name,

            mobile=pending_user.mobile,

            email=pending_user.email,

            password=pending_user.password,

            role="customer",

            is_verified=True
        )

        # =====================================================
        # WATI - NEW CUSTOMER
        # =====================================================

        try:

            save_customer_to_wati(user)

            send_login_whatsapp(user)

        except Exception as wati_error:

            print(
                "WATI NEW USER ERROR:",
                str(wati_error)
            )

        # =====================================================
        # DELETE OTP
        # =====================================================

        otp_obj.delete()

        # =====================================================
        # DELETE PENDING REGISTRATION
        # =====================================================

        pending_user.delete()

        # =====================================================
        # REGISTRATION SUCCESS EMAIL
        # =====================================================

        if user.email:

            try:

                context = {

                    "name": user.name,

                    "mobile": user.mobile,

                    "role": user.role
                }

                html_content = render_to_string(
                    "email/register_success.html",
                    context
                )

                email_msg = EmailMultiAlternatives(

                    subject="Registration Successful",

                    body="Registration Successful",

                    from_email=settings.DEFAULT_FROM_EMAIL,

                    to=[user.email]
                )

                email_msg.attach_alternative(
                    html_content,
                    "text/html"
                )

                email_msg.send()

            except Exception as email_err:

                print(
                    f"Failed to send registration email: {email_err}"
                )

        # =====================================================
        # RETURN NEW USER
        # =====================================================

        return JsonResponse({

            "success": True,

            "is_new_user": True,

            "message": "Account created and login successful",

            "user": {

                "id": user.id,

                "name": user.name,

                "mobile": user.mobile,

                "email": user.email,

                "role": user.role,
                
                "is_store_member": user.role == "staff",

                "can_send_notifications":
                    user.can_send_notifications,

                "created_at":
                    user.created_at.strftime("%Y-%m-%d")
            },

            "permissions": {

                "add_products":
                    user.role == "admin",

                "edit_products":
                    user.role == "admin",

                "delete_products":
                    user.role == "admin",

                "change_prices":
                    user.role == "admin",

                "manage_orders":
                    user.role in ["admin", "staff"],

                "manage_customers":
                    user.role in ["admin", "staff"],

                "manage_staff":
                    user.role == "admin",

                "send_whatsapp":
                    user.role == "admin",

                "send_emails":
                    user.role == "admin",

                "view_reports":
                    user.role in ["admin", "staff"],

                "print_bills":
                    user.role in ["admin", "staff"],

                "full_access":
                    user.role == "admin"
            }

        }, status=200)

    except Exception as e:

        print(
            "VERIFY LOGIN OTP ERROR:",
            str(e)
        )

        return JsonResponse({

            "success": False,

            "message": str(e)

        }, status=500)
    

# @csrf_exempt
# def verify_user_login_otp(request):

#     if request.method != "POST":
#         return JsonResponse({
#             "success": False,
#             "message": "Only POST method is allowed"
#         }, status=405)

#     try:

#         if request.content_type == "application/json":
#             data = json.loads(request.body)
#         else:
#             data = request.POST

#         user_id = data.get("user_id")
#         mobile = data.get("mobile")
#         otp = data.get("otp")

#         otp = str(otp).strip() if otp else ""

#         # =====================================================
#         # EXISTING USER LOGIN
#         # =====================================================

#         if user_id:

#             user = User.objects.filter(
#                 id=user_id
#             ).first()

#             if not user:
#                 return JsonResponse({
#                     "success": False,
#                     "message": "User not found"
#                 }, status=404)

#             otp_obj = EmailOTP.objects.filter(
#                 user=user,
#                 otp=otp,
#                 purpose="user_login",
#                 is_verified=False
#             ).order_by("-created_at").first()

#             if not otp_obj:

#                 return JsonResponse({
#                     "success": False,
#                     "message": "Invalid OTP"
#                 }, status=400)

#             # Check expiry
#             if timezone.now() > otp_obj.created_at + timedelta(minutes=30):

#                 otp_obj.delete()

#                 return JsonResponse({
#                     "success": False,
#                     "message": "OTP expired"
#                 }, status=400)

#             # Verify
#             otp_obj.is_verified = True
#             otp_obj.save()

# # =====================================================
# # WATI - SAVE CUSTOMER + SEND LOGIN MESSAGE
# # =====================================================

# try:
#     save_customer_to_wati(user)
#     send_login_whatsapp(user)
# except Exception as wati_error:
#     print("WATI LOGIN ERROR:", str(wati_error))

#             return JsonResponse({
#                 "success": True,
#                 "is_new_user": False,
#                 "message": "Login successful",
#                 "user": {
#                     "id": user.id,
#                     "name": user.name,
#                     "mobile": user.mobile,
#                     "email": user.email,
#                     "role": user.role,
#                     "can_send_notifications": user.can_send_notifications
#                 }
#             }, status=200)

#         # =====================================================
#         # NEW USER VERIFICATION
#         # =====================================================

#         if not mobile:

#             return JsonResponse({
#                 "success": False,
#                 "message": "Mobile number or user_id is required"
#             }, status=400)

#         mobile = str(mobile).strip()

#         otp_obj = OTPVerification.objects.filter(
#             mobile=mobile,
#             otp=otp
#         ).first()

#         if not otp_obj:

#             return JsonResponse({
#                 "success": False,
#                 "message": "Invalid OTP"
#             }, status=400)

#         # Check expiry
#         if timezone.now() > otp_obj.expires_at:

#             otp_obj.delete()

#             return JsonResponse({
#                 "success": False,
#                 "message": "OTP expired"
#             }, status=400)

#         # Get pending registration
#         pending_user = PendingRegistration.objects.filter(
#             mobile=mobile
#         ).first()

#         if not pending_user:

#             return JsonResponse({
#                 "success": False,
#                 "message": "Registration data not found"
#             }, status=404)

#         # Check if user was created meanwhile
#         existing_user = User.objects.filter(
#             mobile=mobile
#         ).first()

#         if existing_user:

#             otp_obj.delete()
#             pending_user.delete()

#             return JsonResponse({
#                 "success": True,
#                 "is_new_user": False,
#                 "message": "Login successful",
#                 "user": {
#                     "id": existing_user.id,
#                     "name": existing_user.name,
#                     "mobile": existing_user.mobile,
#                     "email": existing_user.email,
#                     "role": existing_user.role
#                 }
#             })

#         # =====================================================
#         # CREATE NEW USER
#         # =====================================================

#         user = User.objects.create(
#             name=pending_user.name,
#             mobile=pending_user.mobile,
#             email=pending_user.email,
#             password=pending_user.password,
#             role="customer",
#             is_verified=True
#         )

#         # Delete OTP
#         otp_obj.delete()

#         # Delete pending registration
#         pending_user.delete()

#         # Registration success email
#         if user.email:

#             try:

#                 context = {
#                     "name": user.name,
#                     "mobile": user.mobile,
#                     "role": user.role
#                 }

#                 html_content = render_to_string(
#                     "email/register_success.html",
#                     context
#                 )

#                 email_msg = EmailMultiAlternatives(
#                     subject="Registration Successful",
#                     body="Registration Successful",
#                     from_email=settings.DEFAULT_FROM_EMAIL,
#                     to=[user.email]
#                 )

#                 email_msg.attach_alternative(
#                     html_content,
#                     "text/html"
#                 )

#                 email_msg.send()

#             except Exception as email_err:

#                 print(
#                     f"Failed to send registration email: {email_err}"
#                 )

#         # =====================================================
#         # RETURN NEW USER
#         # =====================================================

#         return JsonResponse({
#             "success": True,
#             "is_new_user": True,
#             "message": "Account created and login successful",
#             "user": {
#                 "id": user.id,
#                 "name": user.name,
#                 "mobile": user.mobile,
#                 "email": user.email,
#                 "role": user.role,
#                 "can_send_notifications": user.can_send_notifications,
#                 "created_at": user.created_at.strftime("%Y-%m-%d")
#             },
#             "permissions": {
#                 "add_products": user.role == "admin",
#                 "edit_products": user.role == "admin",
#                 "delete_products": user.role == "admin",
#                 "change_prices": user.role == "admin",
#                 "manage_orders": user.role in ["admin", "staff"],
#                 "manage_customers": user.role in ["admin", "staff"],
#                 "manage_staff": user.role == "admin",
#                 "send_whatsapp": user.role == "admin",
#                 "send_emails": user.role == "admin",
#                 "view_reports": user.role in ["admin", "staff"],
#                 "print_bills": user.role in ["admin", "staff"],
#                 "full_access": user.role == "admin"
#             }
#         }, status=200)

#     except Exception as e:

#         print("VERIFY LOGIN OTP ERROR:", str(e))

#         return JsonResponse({
#             "success": False,
#             "message": str(e)
#         }, status=500)



# @csrf_exempt
# def user_login(request):

#     if request.method == "POST":

#         try:

#             data = json.loads(request.body)
#             print(f"DEBUG LOGIN DATA: {data}")

#             mobile = data.get("mobile")
#             if mobile:
#                 mobile = str(mobile).strip()
            
#             print(f"DEBUG LOGIN EXTRACTED MOBILE: '{mobile}'")

#             user = User.objects.filter(
#                 mobile=mobile
#             ).first()

#             if not user:

#                 return JsonResponse({
#                     "success": False,
#                     "message": "User not found"
#                 }, status=404)

#             otp = str(random.randint(100000, 999999))

#             EmailOTP.objects.create(
#                 user=user,
#                 otp=otp,
#                 purpose="user_login"
#             )

#             send_email_with_fallback(
#                 subject="Dharani Herbals - Login OTP",
#                 message=f"""
#             Welcome to Dharani Herbals!

#             Dear {user.name},

#             Your One-Time Password (OTP) for login is:

#             {otp}

#             This OTP is valid for 30 minutes.

#             Please do not share this OTP with anyone.

#             Regards,
#             Dharani Herbals Team
#             """,
#                 recipient=user.email
#             )

#             send_sms_otp(
#                 user.mobile,
#                 otp
#             )

#             return JsonResponse({
#                 "success": True,
#                 "message": "OTP sent successfully",
#                 "user_id": user.id
#             })

#         except Exception as e:

#             return JsonResponse({
#                 "success": False,
#                 "message": str(e)
#             }, status=500)

#     return JsonResponse({
#         "message": "Method not allowed"
#     }, status=405)

# @csrf_exempt
# def verify_user_login_otp(request):

#     if request.method == "POST":

#         try:

#             data = json.loads(request.body)

#             user_id = data.get("user_id")
#             otp = data.get("otp")

#             user = User.objects.filter(
#                 id=user_id
#             ).first()

#             if not user:

#                 return JsonResponse({
#                     "success": False,
#                     "message": "User not found"
#                 }, status=404)

#             otp_obj = EmailOTP.objects.filter(
#                 user=user,
#                 otp=otp,
#                 purpose="user_login",
#                 is_verified=False
#             ).order_by("-created_at").first()

#             if not otp_obj:

#                 return JsonResponse({
#                     "success": False,
#                     "message": "Invalid OTP"
#                 }, status=400)

#             if timezone.now() > otp_obj.created_at + timedelta(minutes=30):

#                 return JsonResponse({
#                     "success": False,
#                     "message": "OTP expired"
#                 }, status=400)

#             otp_obj.is_verified = True
#             otp_obj.save()

#             return JsonResponse({
#                 "success": True,
#                 "message": "OTP verified successfully",
#                 "user_id": user.id
#             })

#         except Exception as e:

#             return JsonResponse({
#                 "success": False,
#                 "message": str(e)
#             }, status=500)

#     return JsonResponse({
#         "message": "Method not allowed"
#     }, status=405)


@csrf_exempt
def reset_password(request):

    if request.method == "POST":

        try:

            data = json.loads(request.body)
            user_id = data.get("user_id")
            new_password = data.get("new_password")
            confirm_password = data.get("confirm_password")

            if new_password != confirm_password:

                return JsonResponse({
                    "success": False,
                    "message": "Passwords do not match"
                }, status=400)

            user = User.objects.filter(
                id=user_id
            ).first()

            if not user:

                return JsonResponse({
                    "success": False,
                    "message": "User not found"
                }, status=404)

            user.password = new_password
            user.save()

            return JsonResponse({
                "success": True,
                "message": "Password updated successfully"
            })

        except Exception as e:

            return JsonResponse({
                "success": False,
                "message": str(e)
            }, status=500)

    return JsonResponse({
        "message": "Method not allowed"
    }, status=405)

# # =====================================================
# # STORE REGISTER - Register a new staff/store account
# # =====================================================



# @csrf_exempt
# def store_register(request):

#     if request.method == 'POST':

#         try:

#             data = (
#                 json.loads(request.body)
#                 if request.content_type == 'application/json'
#                 else request.POST
#             )

#             name = (data.get('name') or '').strip()
#             mobile = (data.get('mobile') or '').strip()
#             password = data.get('password') or ''
#             email = (data.get('email') or '').strip()

#             store_name = (data.get('store_name') or '').strip()
#             store_address = (data.get('store_address') or '').strip()

#             if not name or not mobile or not password:
#                 return JsonResponse(
#                     {'message': 'Required fields missing'},
#                     status=400
#                 )

#             user = User.objects.create(
#                 name=name,
#                 mobile=mobile,
#                 password=password,
#                 role='staff'
#             )

#             # EMAIL TEMPLATE
#             if email:

#                 html = render_to_string(
#                     'email/register_success.html',
#                     {
#                         'name': name,
#                         'mobile': mobile,
#                         'role': 'Staff',
#                         'store_name': store_name,
#                         'store_address': store_address
#                     }
#                 )

#                 msg = EmailMultiAlternatives(
#                     subject='வரவேற்கிறோம் - Dharani Herbbals',
#                     body='Registration Successful',
#                     from_email=settings.DEFAULT_FROM_EMAIL,
#                     to=[email]
#                 )

#                 msg.attach_alternative(
#                     html,
#                     "text/html"
#                 )

#                 msg.send()

#             return JsonResponse({
#                 'message': 'Store Registered',
#                 'data': {
#                     'id': user.id
#                 }
#             })

#         except Exception as e:

#             return JsonResponse({
#                 'error': str(e)
#             }, status=400)

#     return JsonResponse({
#         'message': 'Method not allowed'
#     }, status=405)
# # =====================================================
# # STORE REGISTER - Register a new staff/store account
# # =====================================================
# @csrf_exempt
# def store_register(request):
#     if request.method == 'POST':
#         try:
#             if request.content_type == 'application/json':
#                 data = json.loads(request.body)
#             else:
#                 data = request.POST

#             name        = (data.get('name') or '').strip()
#             mobile      = (data.get('mobile') or '').strip()
#             password    = data.get('password') or ''
#             store_name  = (data.get('store_name') or '').strip()
#             store_address = (data.get('store_address') or '').strip()

#             # Validation
#             if not name or not mobile or not password:
#                 return JsonResponse({'message': 'Name, mobile, and password are required.'}, status=400)
#             if not store_name:
#                 return JsonResponse({'message': 'Store name is required.'}, status=400)

#             if User.objects.filter(mobile=mobile).exists():
#                 return JsonResponse({'message': 'A staff with this mobile number already exists.'}, status=400)

#             # Create staff user (role is always 'staff')
#             user = User.objects.create(
#                 name=name,
#                 mobile=mobile,
#                 password=password,
#                 role='staff'
#             )
#             return JsonResponse({
#                 'message': 'Store Staff Registered Successfully',
#                 'data': {
#                     'id': user.id,
#                     'name': user.name,
#                     'mobile': user.mobile,
#                     'store_name': store_name,
#                     'store_address': store_address,
#                     'role': user.role
#                 }
#             }, status=201)
#         except Exception as e:
#             return JsonResponse({'message': 'Registration failed', 'errors': str(e)}, status=400)

#     if request.method == 'OPTIONS':
#         response = JsonResponse({'message': 'OK'}, status=200)
#         response['Access-Control-Allow-Origin'] = '*'
#         response['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
#         response['Access-Control-Allow-Headers'] = '*'
#         return response
#     return JsonResponse({'message': 'Method not allowed'}, status=405)
# =====================================================
# STORE REGISTER - Register a new staff/store account
# =====================================================
@csrf_exempt
def store_register(request):

    if request.method == 'POST':

        try:

            # Accept JSON or Form Data
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST

            fullname = (data.get('fullname') or '').strip()
            email = (data.get('email') or '').strip().lower()
            mobile = (data.get('mobile') or '').strip()
            store_name = (data.get('store_name') or '').strip()
            credit_payment = data.get('credit_payment', False)
            credit_limit = data.get('credit_limit', 0)

            # -----------------------------
            # Validation
            # -----------------------------
            if not fullname:
                return JsonResponse(
                    {'message': 'Full name is required.'},
                    status=400
                )

            if not email:
                return JsonResponse(
                    {'message': 'Email is required.'},
                    status=400
                )

            if not mobile:
                return JsonResponse(
                    {'message': 'Mobile number is required.'},
                    status=400
                )

            if not store_name:
                return JsonResponse(
                    {'message': 'Store name is required.'},
                    status=400
                )

            # -----------------------------
            # Duplicate Checks
            # -----------------------------
            if User.objects.filter(email=email).exists():
                return JsonResponse(
                    {'message': 'Email already exists.'},
                    status=400
                )

            if User.objects.filter(mobile=mobile).exists():
                return JsonResponse(
                    {'message': 'Mobile number already exists.'},
                    status=400
                )

            # -----------------------------
            # Create Staff User
            # -----------------------------
            user = User.objects.create(
                name=fullname,
                email=email,
                mobile=mobile,
                store_name=store_name,
                role='staff',
                credit_payment_enabled=bool(credit_payment),
                credit_limit=Decimal(str(credit_limit or 0)),
                available_credit=Decimal(str(credit_limit or 0))
            )

            # -----------------------------
            # Send Registration Email
            # -----------------------------
            html = render_to_string(
                'email/register_success.html',
                {
                    'name': fullname,
                    'email': email,
                    'mobile': mobile,
                    'role': 'Staff',
                    'store_name': store_name,
                }
            )

            msg = EmailMultiAlternatives(
                subject='வரவேற்கிறோம் - Dharani Herbals',
                body='Registration Successful',
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[email]
            )

            msg.attach_alternative(html, "text/html")
            msg.send(fail_silently=True)

            # -----------------------------
            # Response
            # -----------------------------
            return JsonResponse(
                {
                    'message': 'Store Staff Registered Successfully.',
                    'data': {
                        'id': user.id,
                        'fullname': user.name,
                        'email': user.email,
                        'mobile': user.mobile,
                        'store_name': user.store_name,
                        'role': user.role,
                        'credit_payment': user.credit_payment_enabled,
                        'credit_limit': user.credit_limit,
                        'is_verified': user.is_verified,
                        'created_at': user.created_at,
                    }
                },
                status=201
            )

        except Exception as e:

            return JsonResponse(
                {
                    'message': 'Registration failed.',
                    'error': str(e)
                },
                status=400
            )

    elif request.method == 'OPTIONS':

        response = JsonResponse({'message': 'OK'}, status=200)
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = '*'
        return response

    return JsonResponse(
        {'message': 'Method not allowed'},
        status=405
    )
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404

@csrf_exempt
def delete_store_staff(request, staff_id):

    if request.method != "DELETE":
        return JsonResponse(
            {
                "success": False,
                "message": "Method not allowed"
            },
            status=405
        )

    try:

        staff = get_object_or_404(
            User,
            id=staff_id,
            role="staff"
        )

        staff.delete()

        return JsonResponse(
            {
                "success": True,
                "message": "Store staff deleted successfully"
            },
            status=200
        )

    except Exception as e:

        return JsonResponse(
            {
                "success": False,
                "message": str(e)
            },
            status=400
        )
# ========================================


# def store_login(request):
#     if request.method == 'POST':
#         try:
#             if request.content_type == 'application/json':
#                 data = json.loads(request.body)
#             else:
#                 data = request.POST

#             mobile   = data.get('mobile')
#             password = data.get('password')

#             if not mobile or not password:
#                 return JsonResponse({'message': 'Mobile and password are required.'}, status=400)

#             # Check if user exists at all
#             if not User.objects.filter(mobile=mobile).exists():
#                 return JsonResponse({'message': 'No account found with this mobile number. Please register first.'}, status=400)

#             # Check if password matches
#             if not User.objects.filter(mobile=mobile, password=password).exists():
#                 return JsonResponse({'message': 'Incorrect password.'}, status=400)

#             # Check if user is staff
#             user = User.objects.filter(mobile=mobile, password=password).first()
#             if user.role != 'staff':
#                 return JsonResponse({'message': f'This account is registered as "{user.role}", not staff. Use /api/store/register/ to create a staff account.'}, status=400)

#             return JsonResponse({
#                 'message': 'Store Login Successful',
#                 'user': {
#                     'id': user.id,
#                     'name': user.name,
#                     'mobile': user.mobile,
#                     'role': user.role
#                 }
#             }, status=200)
#         except Exception as e:
#             return JsonResponse({'message': 'Login failed', 'errors': str(e)}, status=400)

#     if request.method == 'OPTIONS':
#         response = JsonResponse({'message': 'OK'}, status=200)
#         response['Access-Control-Allow-Origin'] = '*'
#         response['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
#         response['Access-Control-Allow-Headers'] = '*'
#         return response
#     return JsonResponse({'message': 'Method not allowed'}, status=405)

@csrf_exempt
def store_login(request):

    if request.method == "POST":

        try:

            data = (
                json.loads(request.body)
                if request.content_type == "application/json"
                else request.POST
            )

            mobile = (data.get("mobile") or "").strip()

            if not mobile:
                return JsonResponse({
                    "success": False,
                    "message": "Mobile number is required."
                }, status=400)

            user = User.objects.filter(
                mobile=mobile,
                role="staff"
            ).first()

            if not user:
                return JsonResponse({
                    "success": False,
                    "message": "Staff account not found."
                }, status=404)

            otp = str(random.randint(100000, 999999))

            # Delete previous unused OTPs
            EmailOTP.objects.filter(
                user=user,
                purpose="forgot_password",
                is_verified=False
            ).delete()

            EmailOTP.objects.create(
                user=user,
                otp=otp,
                purpose="forgot_password"
            )

            send_sms_otp(user.mobile, otp)

            if user.email:

                send_email_with_fallback(
                    subject="Dharani Herbals - Login OTP",
                    message=f"""
Dear {user.name},

Your OTP is:

{otp}

This OTP is valid for 30 minutes.

Regards,
Dharani Herbals
""",
                    recipient=user.email
                )

            return JsonResponse({
                "success": True,
                "message": "OTP sent successfully.",
                "user_id": user.id
            })

        except Exception as e:

            return JsonResponse({
                "success": False,
                "message": str(e)
            }, status=500)

    return JsonResponse({
        "message": "Method not allowed"
    }, status=405)

# =====================================================
# STAFF LIST - Admin can see all staff accounts
# =====================================================
@csrf_exempt
def staff_list(request, staff_id=None):
    if request.method == 'GET':
        role_filter = request.GET.get('role', 'all')
        if role_filter.lower() == 'all':
            staff_users = User.objects.all().order_by('-id')
        else:
            staff_users = User.objects.filter(role=role_filter).order_by('-id')
            
        data = [{
            'id': u.id,
            'name': u.name,
            'fullname': u.name,
            'email': u.email,
            'mobile': u.mobile,
            'store_name': u.store_name,
            'role': u.role,
            'credit_payment': u.credit_payment_enabled,
            'credit_limit': float(u.credit_limit) if u.credit_limit else 0.0,
            'balance': float((u.credit_limit or 0) - (u.available_credit or 0)),
            'available_credit': float(u.available_credit) if u.available_credit else 0.0,
            'created_at': u.created_at.isoformat()
        } for u in staff_users]
        return JsonResponse(data, safe=False)

    if request.method == 'PUT' and staff_id:
        try:
            user = User.objects.get(id=staff_id)
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST

            if 'fullname' in data: user.name = data['fullname']
            if 'email' in data: user.email = data['email']
            if 'mobile' in data: user.mobile = data['mobile']
            if 'store_name' in data: user.store_name = data['store_name']
            if 'role' in data: user.role = data['role']
            
            if 'credit_payment' in data: 
                user.credit_payment_enabled = bool(data['credit_payment'])
                
            if 'credit_limit' in data: 
                user.credit_limit = Decimal(str(data['credit_limit'] or 0))

            if 'available_credit' in data:
                user.available_credit = Decimal(str(data['available_credit'] or 0))
            elif 'balance' in data:
                # If balance (debt) is passed, available_credit = credit_limit - balance
                new_balance = Decimal(str(data['balance'] or 0))
                user.available_credit = user.credit_limit - new_balance
                
            user.save()
            return JsonResponse({'message': 'User updated successfully'})
        except User.DoesNotExist:
            return JsonResponse({'message': 'User not found'}, status=404)
        except Exception as e:
            return JsonResponse({'message': 'Update failed', 'error': str(e)}, status=400)

    if request.method == 'DELETE' and staff_id:
        try:
            user = User.objects.get(id=staff_id)
            user.delete()
            return JsonResponse({'message': 'User deleted successfully'})
        except User.DoesNotExist:
            return JsonResponse({'message': 'User not found'}, status=404)
        except Exception as e:
            return JsonResponse({'message': 'Delete failed', 'error': str(e)}, status=400)

    if request.method == 'OPTIONS':
        response = JsonResponse({'message': 'OK'}, status=200)
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response['Access-Control-Allow-Headers'] = '*'
        return response
        
    return JsonResponse({'message': 'Method not allowed'}, status=405)


@csrf_exempt
def login(request):
    if request.method == 'GET':
        if request.GET.get('logged_out'):
            request.session.flush()
        return render(request, 'herbal/login.html', {
            'message': 'Logged out successfully.' if request.GET.get('logged_out') else ''
        })

    if request.method == 'POST':
        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                is_form_login = False
            else:
                data = request.POST
                is_form_login = True

            name = (data.get('name') or '').strip()
            mobile = (data.get('mobile') or '').strip()
            email = (data.get('email') or '').strip()
            password = data.get('password') or ''
            
            if not mobile or not password:
                if is_form_login:
                    return render(request, 'herbal/login.html', {
                        'error': 'Mobile number and password are required.',
                        'form': data
                    })
                return JsonResponse({'message': 'Mobile and password are required.'}, status=400)
            
            user = User.objects.filter(mobile=mobile).first()

            if user:
                if user.password != password:
                    if is_form_login:
                        return render(request, 'herbal/login.html', {
                            'error': 'Invalid mobile number or password.',
                            'form': data
                        })
                    return JsonResponse({'message': 'Invalid Mobile or Password'}, status=400)
            else:
                if not name:
                    if is_form_login:
                        return render(request, 'herbal/login.html', {
                            'error': 'Name is required for new login registration.',
                            'form': data
                        })
                    return JsonResponse({'message': 'Name is required for new registration.'}, status=400)

                if email and User.objects.filter(email=email).exists():
                    if is_form_login:
                        return render(request, 'herbal/login.html', {
                            'error': 'This email is already registered.',
                            'form': data
                        })
                    return JsonResponse({'message': 'This email is already registered.'}, status=400)

                user = User.objects.create(
                    name=name,
                    mobile=mobile,
                    email=email or None,
                    password=password,
                    role='customer'
                )
            
            tamil_message = f'''வணக்கம் {user.name},

தங்களின் கணக்கில் வெற்றிகரமாக உள்நுழைந்துள்ளீர்கள்.

நன்றி.
தாரணி ஹெர்பல்ஸ்'''
            create_and_send_notification(user, 'email', 'தாரணி ஹெர்பல்ஸ்', tamil_message)
            create_and_send_notification(user, 'whatsapp', 'தாரணி ஹெர்பல்ஸ்', tamil_message)

            if is_form_login:
                request.session['user_id'] = user.id
                request.session['user_name'] = user.name
                request.session['user_email'] = user.email or user.mobile
                return redirect('/api/dashboard/')

            return JsonResponse({
                'message': 'Login Success',
                'user': {
                    'id': user.id,
                    'name': user.name,
                    'mobile': user.mobile,
                    'email': user.email,
                    'role': user.role
                }
            }, status=200)
        except User.DoesNotExist:
            return JsonResponse({'message': 'Invalid Mobile or Password'}, status=400)
        except Exception as e:
            return JsonResponse({'message': 'Login failed', 'errors': str(e)}, status=400)
    if request.method == 'OPTIONS':
        response = JsonResponse({'message': 'OK'}, status=200)
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
        response['Access-Control-Allow-Headers'] = '*'
        return response
    return JsonResponse({'message': 'Method not allowed'}, status=405)

@csrf_exempt
def category_list_create(request):
    if request.method == 'GET':
        categories = Category.objects.all()
        data = [{
            'id': c.id, 
            'name': c.name, 
            'image': get_image_url(request, c.image),
            'created_at': c.created_at.isoformat()
        } for c in categories]
        return JsonResponse(data, safe=False)
        
    elif request.method == 'POST':
        # Handling file upload requires checking request.POST and request.FILES
        try:
            name = request.POST.get('name') or (json.loads(request.body).get('name') if request.body else None)
            image = request.FILES.get('image')
            
            if not name:
                return JsonResponse({'message': 'Name is required'}, status=400)
                
            category = Category.objects.create(name=name, image=image)
            return JsonResponse({
                'id': category.id,
                'name': category.name,
                'image': get_image_url(request, category.image),
                'created_at': category.created_at.isoformat()
            }, status=201)
        except Exception as e:
            return JsonResponse({'message': 'Failed to create category', 'errors': str(e)}, status=400)
    if request.method == 'OPTIONS':
        response = JsonResponse({'message': 'OK'}, status=200)
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
        response['Access-Control-Allow-Headers'] = '*'
        return response
    return JsonResponse({'message': 'Method not allowed'}, status=405)

@csrf_exempt
def category_detail(request, pk):
    try:
        category = Category.objects.get(id=pk)
    except Category.DoesNotExist:
        return JsonResponse({'message': 'Category Not Found'}, status=404)
        
    if request.method == 'GET':
        return JsonResponse({
            'id': category.id,
            'name': category.name,
            'image': get_image_url(request, category.image),
            'created_at': category.created_at.isoformat()
        })
        
    elif request.method in ['PUT', 'PATCH']:
        try:
            # PUT might be tricky with form-data in Django. Let's handle both JSON and form-data.
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                category.name = data.get('name', category.name)
            else:
                category.name = request.POST.get('name', category.name)
                if 'image' in request.FILES:
                    category.image = request.FILES.get('image')
                    
            category.save()
            return JsonResponse({
                'id': category.id,
                'name': category.name,
                'image': get_image_url(request, category.image),
                'created_at': category.created_at.isoformat()
            })
        except Exception as e:
            return JsonResponse({'message': 'Failed to update category', 'errors': str(e)}, status=400)
            
    elif request.method == 'DELETE':
        category.delete()
        return JsonResponse({'message': 'Category Deleted'}, status=200)
    if request.method == 'OPTIONS':
        response = JsonResponse({'message': 'OK'}, status=200)
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
        response['Access-Control-Allow-Headers'] = '*'
        return response
    return JsonResponse({'message': 'Method not allowed'}, status=405)

@csrf_exempt
def product_list_create(request):
    if request.method == 'GET':
        products = Product.objects.all().order_by('-id')
        data = [{
            'id': p.id,
            'category': p.category.id if p.category else None,
            'category_name': p.category.name if p.category else None,
            'brand': p.brand.name if p.brand else None,
            'brand_id': p.brand.id if p.brand else None,
            'name': p.name,
            'description': p.description,
            'product_code': p.product_code,
            'barcode': p.barcode,
            'tamil_name': p.tamil_name,
            'product_type': p.product_type,
            'unit': p.unit,
            'weight_volume': p.weight_volume,
            'purchase_price': str(p.purchase_price) if p.purchase_price else '0',
            'mrp': str(p.mrp) if p.mrp else '0',
            'customer_price': str(p.customer_price),
            'store_price': str(p.store_price),
            'reseller_price': str(p.reseller_price) if p.reseller_price else '0',
            'retailer_price': str(p.retailer_price) if p.retailer_price else '0',
            'distributor_price': str(p.distributor_price) if p.distributor_price else '0',
            'sarvo_price': str(p.sarvo_price) if p.sarvo_price else '0',
            'drug_price': str(p.drug_price) if p.drug_price else '0',
            'gst_percentage': str(p.gst_percentage) if p.gst_percentage else '0',
            'stock': p.stock,
            'reorder_level': p.reorder_level,
            'expiry_date': str(p.expiry_date) if p.expiry_date else None,
            'batch_number': p.batch_number,
            'manufacturer': p.manufacturer,
            'image': get_image_url(request, p.image),
            'is_new': p.is_new,
            'is_public': p.is_public,
            'is_active': p.is_active,
            'created_at': p.created_at.isoformat()
        } for p in products]
        return JsonResponse(data, safe=False)
        
    elif request.method == 'POST':
        try:
            # Handle both JSON and form data
            if request.content_type and 'application/json' in request.content_type:
                data = json.loads(request.body)
                image = None
            else:
                data = request.POST
                image = request.FILES.get('image')

            # DEBUG LOGGING to help frontend developer
            print("========== DEBUG PAYLOAD FROM FRONTEND ==========")
            print("DATA:", dict(data))
            if 'image' in request.FILES:
                print("IMAGE FILE UPLOADED:", request.FILES['image'].name)
            else:
                print("NO IMAGE FILE IN request.FILES")
            print("=================================================")

            category_id = data.get('category')
            if not category_id:
                return JsonResponse({'message': 'Category is required'}, status=400)
            category = Category.objects.get(id=category_id)

            name = data.get('name')
            if not name:
                return JsonResponse({'message': 'Product name is required'}, status=400)

            # Brand (optional)
            brand = None
            brand_id = data.get('brand') or data.get('brand_id')
            if brand_id:
                try:
                    brand = Brand.objects.get(id=brand_id)
                except Brand.DoesNotExist:
                    pass

            # Build the product with ALL fields
            product = Product.objects.create(
                category=category,
                brand=brand,
                name=name,
                description=data.get('description', ''),
                product_code=data.get('product_code') or None,
                barcode=data.get('barcode') or None,
                tamil_name=data.get('tamil_name') or None,
                product_type=data.get('product_type') or None,
                unit=data.get('unit', 'pcs'),
                weight_volume=data.get('weight_volume') or None,
                stock=int(data.get('stock', 0) or 0),
                reorder_level=int(data.get('reorder_level', 10) or 10),
                purchase_price=data.get('purchase_price') or 0,
                mrp=data.get('mrp') or 0,
                customer_price=data.get('customer_price') or 0,
                store_price=data.get('store_price') or 0,
                reseller_price=data.get('reseller_price') or 0,
                retailer_price=data.get('retailer_price') or 0,
                distributor_price=data.get('distributor_price') or 0,
                sarvo_price=data.get('sarvo_price') or 0,
                drug_price=data.get('drug_price') or 0,
                gst_percentage=data.get('gst_percentage') or data.get('gst') or 0,
                expiry_date=data.get('expiry_date') or None,
                batch_number=data.get('batch_number') or None,
                manufacturer=data.get('manufacturer') or 'Dharani Herbals',
                image=image,
                is_new=data.get('is_new', 'false') if isinstance(data.get('is_new'), bool) else str(data.get('is_new', 'false')).lower() in ['true', 'on'],
                is_public=data.get('is_public', 'true') if isinstance(data.get('is_public'), bool) else str(data.get('is_public', 'true')).lower() in ['true', 'on'],
                is_active=data.get('is_active', 'true') if isinstance(data.get('is_active'), bool) else str(data.get('is_active', 'true')).lower() in ['true', 'on']
            )
            return JsonResponse({
                'id': product.id,
                'category': product.category.id,
                'category_name': product.category.name,
                'brand': product.brand.name if product.brand else None,
                'brand_id': product.brand.id if product.brand else None,
                'name': product.name,
                'description': product.description,
                'product_code': product.product_code,
                'barcode': product.barcode,
                'tamil_name': product.tamil_name,
                'product_type': product.product_type,
                'unit': product.unit,
                'weight_volume': product.weight_volume,
                'purchase_price': str(product.purchase_price) if product.purchase_price else '0',
                'mrp': str(product.mrp) if product.mrp else '0',
                'customer_price': str(product.customer_price),
                'store_price': str(product.store_price),
                'gst_percentage': str(product.gst_percentage),
                'stock': product.stock,
                'reorder_level': product.reorder_level,
                'expiry_date': str(product.expiry_date) if product.expiry_date else None,
                'batch_number': product.batch_number,
                'manufacturer': product.manufacturer,
                'image': get_image_url(request, product.image),
                'is_new': product.is_new,
                'is_public': product.is_public,
                'is_active': product.is_active,
                'created_at': product.created_at.isoformat()
            }, status=201)
        except Category.DoesNotExist:
            return JsonResponse({'message': 'Category not found'}, status=400)
        except Exception as e:
            return JsonResponse({'message': 'Failed to create product', 'errors': str(e)}, status=400)
    if request.method == 'OPTIONS':
        response = JsonResponse({'message': 'OK'}, status=200)
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
        response['Access-Control-Allow-Headers'] = '*'
        return response
    return JsonResponse({'message': 'Method not allowed'}, status=405)

@csrf_exempt
def product_detail(request, pk):
    try:
        product = Product.objects.get(id=pk)
    except Product.DoesNotExist:
        return JsonResponse({'message': 'Product Not Found'}, status=404)
        
    if request.method == 'GET':
        extra_images = ProductImage.objects.filter(
            product=product,
            is_active=True
        )
        return JsonResponse({
            'id': product.id,
            'category': product.category.id if product.category else None,
            'category_name': product.category.name if product.category else None,
            'brand': product.brand.name if product.brand else None,
            'brand_id': product.brand.id if product.brand else None,
            'name': product.name,
            'description': product.description,
            'product_code': product.product_code,
            'barcode': product.barcode,
            'tamil_name': product.tamil_name,
            'product_type': product.product_type,
            'unit': product.unit,
            'weight_volume': product.weight_volume,
            'purchase_price': str(product.purchase_price) if product.purchase_price else '0',
            'mrp': str(product.mrp) if product.mrp else '0',
            'customer_price': str(product.customer_price),
            'store_price': str(product.store_price),
            'reseller_price': str(product.reseller_price) if product.reseller_price else '0',
            'retailer_price': str(product.retailer_price) if product.retailer_price else '0',
            'distributor_price': str(product.distributor_price) if product.distributor_price else '0',
            'sarvo_price': str(product.sarvo_price) if product.sarvo_price else '0',
            'drug_price': str(product.drug_price) if product.drug_price else '0',
            'gst_percentage': str(product.gst_percentage) if product.gst_percentage else '0',
            'stock': product.stock,
            'reorder_level': product.reorder_level,
            'expiry_date': str(product.expiry_date) if product.expiry_date else None,
            'batch_number': product.batch_number,
            'manufacturer': product.manufacturer,
            'image': get_image_url(request, product.image),
            'extra_images': [get_image_url(request, img.image)for img in extra_images],
            'is_new': product.is_new,
            'is_public': product.is_public,
            'is_active': product.is_active,
            'created_at': product.created_at.isoformat()
        })
        
    elif request.method in ['PUT', 'PATCH']:
        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                category_id = data.get('category')
                if not category_id:
                    category_id = product.category.id
                product.name = data.get('name') or product.name
                product.description = data.get('description') or product.description
                product.price = data.get('price') or product.price
                product.stock = data.get('stock') or product.stock
                product.is_new = data.get('is_new', product.is_new)
            else:
                category_id = request.POST.get('category')
                if not category_id:
                    category_id = product.category.id
                product.name = request.POST.get('name') or product.name
                product.description = request.POST.get('description') or product.description
                product.price = request.POST.get('price') or product.price
                product.stock = request.POST.get('stock') or product.stock
                if 'is_new' in request.POST:
                    product.is_new = request.POST.get('is_new').lower() == 'true'
                if 'image' in request.FILES:
                    product.image = request.FILES.get('image')
                    
            if int(category_id) != product.category.id:
                product.category = Category.objects.get(id=category_id)
                
            product.save()
            return JsonResponse({
                'id': product.id,
                'category': product.category.id,
                'category_name': product.category.name,
                'name': product.name,
                'description': product.description,
                'customer_price': str(product.customer_price),
                'stock': product.stock,
                'image': get_image_url(request, product.image),
                'is_new': product.is_new,
                'created_at': product.created_at.isoformat()
            })
        except Category.DoesNotExist:
            return JsonResponse({'message': 'Category not found'}, status=400)
        except Exception as e:
            return JsonResponse({'message': 'Failed to update product', 'errors': str(e)}, status=400)
            
    elif request.method == 'DELETE':
        product.delete()
        return JsonResponse({'message': 'Product Deleted'}, status=200)
    if request.method == 'OPTIONS':
        response = JsonResponse({'message': 'OK'}, status=200)
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
        response['Access-Control-Allow-Headers'] = '*'
        return response
    return JsonResponse({'message': 'Method not allowed'}, status=405)


@csrf_exempt
def product_edit(request, pk=None):
    if request.method in ['POST', 'PUT', 'PATCH']:
        try:
            # Always read multipart/form-data from request.POST/FILES
            if request.content_type and 'application/json' in request.content_type:
                data = json.loads(request.body)
            else:
                data = request.POST

            # DEBUG LOGGING to help frontend developer
            print("========== DEBUG EDIT PAYLOAD FROM FRONTEND ==========")
            print("DATA:", dict(data))
            if 'image' in request.FILES:
                print("IMAGE FILE UPLOADED:", request.FILES['image'].name)
            else:
                print("NO IMAGE FILE IN request.FILES")
            print("======================================================")

            product_id = pk or data.get('product_id') or data.get('id')
            if not product_id:
                return JsonResponse({'message': 'Product ID is required'}, status=400)

            try:
                product = Product.objects.get(id=int(product_id))
            except (Product.DoesNotExist, ValueError):
                return JsonResponse({'message': 'Product Not Found'}, status=404)

            # Only update category if a valid numeric value is provided
            raw_category = data.get('category')
            try:
                category_id = int(raw_category) if raw_category else product.category.id
            except (ValueError, TypeError):
                category_id = product.category.id

            if category_id != product.category.id:
                product.category = Category.objects.get(id=category_id)

            # Brand (optional)
            brand_id = data.get('brand') or data.get('brand_id')
            if brand_id:
                try:
                    product.brand = Brand.objects.get(id=int(brand_id))
                except (Brand.DoesNotExist, ValueError, TypeError):
                    pass

            # Text fields
            product.name = data.get('name') or product.name
            product.description = data.get('description') or product.description
            
            if data.get('product_code') is not None:
                product.product_code = data.get('product_code') or None
            if data.get('barcode') is not None:
                product.barcode = data.get('barcode') or None
            if data.get('tamil_name') is not None:
                product.tamil_name = data.get('tamil_name') or None
            if data.get('product_type') is not None:
                product.product_type = data.get('product_type') or None
            if data.get('unit') is not None:
                product.unit = data.get('unit') or product.unit
            if data.get('weight_volume') is not None:
                product.weight_volume = data.get('weight_volume') or None
            if data.get('expiry_date') is not None:
                product.expiry_date = data.get('expiry_date') or None
            if data.get('batch_number') is not None:
                product.batch_number = data.get('batch_number') or None
            if data.get('manufacturer') is not None:
                product.manufacturer = data.get('manufacturer') or product.manufacturer

            # Numeric fields - update only if provided
            for field_name in ['mrp', 'customer_price', 'store_price', 'reseller_price',
                               'retailer_price', 'distributor_price', 'sarvo_price',
                               'drug_price', 'gst_percentage', 'purchase_price']:
                raw_val = data.get(field_name)
                # Fallback for gst_percentage
                if field_name == 'gst_percentage' and raw_val is None:
                    raw_val = data.get('gst')
                if raw_val is not None and raw_val != '':
                    try:
                        setattr(product, field_name, float(raw_val))
                    except (ValueError, TypeError):
                        pass

            for int_field in ['stock', 'reorder_level']:
                raw_val = data.get(int_field)
                if raw_val is not None and raw_val != '':
                    try:
                        setattr(product, int_field, int(raw_val))
                    except (ValueError, TypeError):
                        pass

            # Handle boolean correctly
            for bool_field in ['is_new', 'is_public', 'is_active']:
                raw_val = data.get(bool_field)
                if raw_val is not None and raw_val != '':
                    if isinstance(raw_val, str):
                        setattr(product, bool_field, raw_val.lower() in ('true', 'on'))
                    else:
                        setattr(product, bool_field, bool(raw_val))

            if 'image' in request.FILES:
                product.image = request.FILES.get('image')

            product.save()

            return JsonResponse({
                'message': 'Product updated successfully',
                'product': {
                    'id': product.id,
                    'category': product.category.id,
                    'category_name': product.category.name,
                    'brand': product.brand.name if product.brand else None,
                    'brand_id': product.brand.id if product.brand else None,
                    'name': product.name,
                    'description': product.description,
                    'product_code': product.product_code,
                    'barcode': product.barcode,
                    'tamil_name': product.tamil_name,
                    'product_type': product.product_type,
                    'unit': product.unit,
                    'weight_volume': product.weight_volume,
                    'purchase_price': str(product.purchase_price) if product.purchase_price else '0',
                    'mrp': str(product.mrp) if product.mrp else '0',
                    'customer_price': str(product.customer_price),
                    'store_price': str(product.store_price),
                    'gst_percentage': str(product.gst_percentage),
                    'stock': product.stock,
                    'reorder_level': product.reorder_level,
                    'expiry_date': str(product.expiry_date) if product.expiry_date else None,
                    'batch_number': product.batch_number,
                    'manufacturer': product.manufacturer,
                    'image': get_image_url(request, product.image),
                    'is_new': product.is_new,
                    'is_public': product.is_public,
                    'is_active': product.is_active,
                    'created_at': product.created_at.isoformat()
                }
            })
        except Category.DoesNotExist:
            return JsonResponse({'message': 'Category not found'}, status=400)
        except Exception as e:
            return JsonResponse({'message': 'Failed to edit product', 'errors': str(e)}, status=400)

    if request.method == 'OPTIONS':
        response = JsonResponse({'message': 'OK'}, status=200)
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'POST, PUT, PATCH, OPTIONS'
        response['Access-Control-Allow-Headers'] = '*'
        return response

    return JsonResponse({'message': 'Method not allowed'}, status=405)

@csrf_exempt
def products_by_category(request, category_id):
    if request.method == 'GET':
        role = get_role(request)
        products = Product.objects.filter(category_id=category_id, is_public=True).order_by('-id')
        data = [serialize_product(request, p, role) for p in products]
        return JsonResponse(data, safe=False)
    if request.method == 'OPTIONS':
        response = JsonResponse({'message': 'OK'}, status=200)
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
        response['Access-Control-Allow-Headers'] = '*'
        return response
    return JsonResponse({'message': 'Method not allowed'}, status=405)


@csrf_exempt
def product_variations(request, product_id):

    if request.method == "GET":

        product = Product.objects.filter(id=product_id).first()

        if not product:
            return JsonResponse(
                {"success": False, "message": "Product not found"},
                status=404
            )

        variations = ProductVariation.objects.filter(
            product_id=product_id
        ).order_by("id")

        data = []

        for v in variations:
            data.append({
                "id": v.id,
                "product_id": product_id,
                "sku": v.sku,
                "erp_item_id": v.erp_item_id,
                "name": getattr(v, "name", ""),
                "weight": getattr(v, "weight", ""),
                "unit": getattr(v, "unit", ""),
                "customer_price": str(v.customer_price),
                "retailer_price": str(v.retailer_price),
                "reseller_price": str(v.reseller_price),
                "distributor_price": str(v.distributor_price),
                "store_price": str(v.store_price),
                "stock": v.stock,
                "is_active": v.is_active
            })

        return JsonResponse({
            "success": True,
            "count": len(data),
            "data": data
        })

    return JsonResponse(
        {"message": "Method not allowed"},
        status=405
    )

@csrf_exempt
def product_key_points(request, product_id):

    product = get_object_or_404(Product, id=product_id)

    # ================= GET =================
    if request.method == "GET":

        key_points = ProductKeyPoint.objects.filter(
            product=product,
            is_active=True
        ).order_by(
            "display_order",
            "id"
        )

        data = []

        for kp in key_points:

            data.append({
                "id": kp.id,
                "product_id": product.id,
                "title": kp.title,
                "display_order": kp.display_order,
                "is_active": kp.is_active,
            })

        return JsonResponse(
            data,
            safe=False,
            json_dumps_params={
                "ensure_ascii": False
            }
        )

    # ================= POST =================
    elif request.method == "POST":

        try:

            data = (
                request.POST
                if request.POST
                else json.loads(request.body)
            )

            key_point = ProductKeyPoint.objects.create(
                product=product,
                title=data.get("title"),
                display_order=data.get(
                    "display_order",
                    1
                ),
                is_active=data.get(
                    "is_active",
                    True
                ),
            )

            return JsonResponse(
                {
                    "message": "Key Point created successfully",
                    "id": key_point.id
                },
                status=201
            )

        except Exception as e:

            return JsonResponse(
                {
                    "error": str(e)
                },
                status=400
            )

    return JsonResponse(
        {
            "message": "Method not allowed"
        },
        status=405
    )

@csrf_exempt
def product_key_point_detail(request, id):

    key_point = get_object_or_404(
        ProductKeyPoint,
        id=id
    )

    # ================= PUT =================
    if request.method == "PUT":

        try:

            data = (
                request.POST
                if request.POST
                else json.loads(request.body)
            )

            key_point.title = data.get(
                "title",
                key_point.title
            )

            key_point.display_order = data.get(
                "display_order",
                key_point.display_order
            )

            key_point.is_active = data.get(
                "is_active",
                key_point.is_active
            )

            key_point.save()

            return JsonResponse({
                "message": "Key Point updated successfully"
            })

        except Exception as e:

            return JsonResponse(
                {
                    "error": str(e)
                },
                status=400
            )

    # ================= DELETE =================
    elif request.method == "DELETE":

        key_point.delete()

        return JsonResponse({
            "message": "Key Point deleted successfully"
        })

    return JsonResponse(
        {
            "message": "Method not allowed"
        },
        status=405
    )

@csrf_exempt
def shipping_charge_management(request):

    # ===================================
    # GET - List Shipping Charges
    # ===================================
    if request.method == "GET":

        charges = ShippingCharge.objects.all().order_by("state_name")

        data = []

        for charge in charges:
            data.append({
                "id": charge.id,
                "state_name": charge.state_name,
                "state_code": charge.state_code,
                "shipping_amount": str(charge.shipping_amount),
                "free_above": str(charge.free_above),
                "min_order": str(charge.min_order),
            })

        return JsonResponse({
            "total": len(data),
            "data": data
        }, status=200)

    # ===================================
    # POST - Create Shipping Charge
    # ===================================
    elif request.method == "POST":

        try:

            data = json.loads(request.body)

            if ShippingCharge.objects.filter(
                state_name=data.get("state_name")
            ).exists():

                return JsonResponse({
                    "message": "State already exists"
                }, status=400)

            shipping = ShippingCharge.objects.create(

                state_name=data.get("state_name"),
                state_code=data.get("state_code"),
                shipping_amount=data.get("shipping_amount"),
                free_above=data.get("free_above"),
                min_order=data.get("min_order")

            )

            return JsonResponse({
                "message": "Shipping charge created successfully",
                "id": shipping.id
            }, status=201)

        except Exception as e:

            return JsonResponse({
                "message": str(e)
            }, status=400)

    return JsonResponse({
        "message": "Method not allowed"
    }, status=405)


@csrf_exempt
def shipping_charge_detail(request, shipping_id):

    shipping = get_object_or_404(
        ShippingCharge,
        id=shipping_id
    )

    # ===================================
    # PUT - Update
    # ===================================
    if request.method == "PUT":

        try:

            data = json.loads(request.body)

            shipping.state_name = data.get(
                "state_name",
                shipping.state_name
            )

            shipping.state_code = data.get(
                "state_code",
                shipping.state_code
            )

            shipping.shipping_amount = data.get(
                "shipping_amount",
                shipping.shipping_amount
            )

            shipping.free_above = data.get(
                "free_above",
                shipping.free_above
            )

            shipping.min_order = data.get(
                "min_order",
                shipping.min_order
            )

            shipping.save()

            return JsonResponse({
                "message": "Shipping charge updated successfully"
            })

        except Exception as e:

            return JsonResponse({
                "message": str(e)
            }, status=400)

    # ===================================
    # DELETE
    # ===================================
    elif request.method == "DELETE":

        shipping.delete()

        return JsonResponse({
            "message": "Shipping charge deleted successfully"
        })

    return JsonResponse({
        "message": "Method not allowed"
    }, status=405)

import requests

# TENANT_ID = "10121744"

# Paste the Bearer token shown in WATI Swagger (without the word "Bearer")
# TOKEN = "wati_64e194d1-0f0f-4982-8a24-19705030a12e.oc6-SyMkf85EmyhDYdK6KLi308Ys4TqvycI0_4ZwyluE-2jctRdTsgMdUDemX_9zseo5Bxh8YSwBXQs6IEBi5Y0q1nO9HTKZAOoYXk7q2XTTYDIQjx8ssRZargAhTKqi"


# TENANT_ID = "10121744"
# TOKEN = "wati_64e194d1-0f0f-4982-8a24-19705030a12e.oc6-SyMkf85EmyhDYdK6KLi308Ys4TqvycI0_4ZwyluE-2jctRdTsgMdUDemX_9zseo5Bxh8YSwBXQs6IEBi5Y0q1nO9HTKZAOoYXk7q2XTTYDIQjx8ssRZargAhTKqi"

from django.conf import settings
import requests

def cart_message_template(product, quantity, price, total):

    return f"""
Added To Cart


Your product has been added successfully.

Product : {product.name}

Quantity : {quantity}

Price : ₹{price}

Total : ₹{round(total,2)}

Thank you.
"""


def send_wati_message(
    phone,
    product_name,
    quantity,
    price,
    total
):


    url = (
        f"{settings.WATI_BASE_URL}"
        f"/api/v1/sendTemplateMessage"
    )


    params = {
        "whatsappNumber": phone
    }


    headers = {
        "Authorization": f"Bearer {settings.WATI_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


    payload = {
        "template_name": "cart_added_notification",


        "broadcast_name": "cart_added_notification",


        "parameters": [
            {
                "name": "product_name",
                "value": str(product_name)
            },
            {
                "name": "quantity",
                "value": str(quantity)
            },
            {
                "name": "price",
                "value": str(price)
            },
            {
                "name": "total",
                "value": str(total)
            }
        ]
    }


    try:


        response = requests.post(
            url,
            params=params,
            headers=headers,
            json=payload,
            timeout=30
        )


        print("========== WATI TEMPLATE ==========")
        print("URL:", response.url)
        print("Phone:", phone)
        print("Template:", "cart_added_notification")
        print("Status:", response.status_code)
        print("Response:", response.text)
        print("===================================")


        try:
            return response.json()


        except Exception:


            return {
                "status_code": response.status_code,
                "response": response.text
            }


    except Exception as e:


        print("WATI TEMPLATE ERROR:", str(e))


        return {
            "status": False,
            "error": str(e)
        }

    
# import requests
# from django.conf import settings
# from django.http import JsonResponse
# from django.views.decorators.csrf import csrf_exempt


# @csrf_exempt
# def send_template(request):

#     if request.method != "POST":
#         return JsonResponse({"status": False, "message": "POST only"})

#     phone = request.POST.get("phone")

#     if not phone:
#         return JsonResponse({"status": False, "message": "Phone number required"})

#     url = f"{settings.WATI_BASE_URL}/{settings.WATI_TENANT_ID}/api/v2/sendTemplateMessage"

#     headers = {
#         "Authorization": f"Bearer {settings.WATI_TOKEN}",
#         "Content-Type": "application/json",
#         "Accept": "application/json"
#     }

#     payload = {
#         "template_name": "july_dispatch_letter",
#         "broadcast_name": "test_dispatch",
#         "parameters": [],
#         "channel_number": ""
#     }

#     response = requests.post(
#     url,
#     headers=headers,
#     params={
#         "whatsappNumber": phone
#     },
#     json=payload,
#     timeout=30
# )

#     print(response.status_code)
#     print(response.text)

#     return JsonResponse(response.json(), safe=False)



import requests
from django.conf import settings

def send_cart_template(phone):

    url = f"{settings.WATI_BASE_URL}/api/v2/sendTemplateMessage"

    headers = {
        "Authorization": f"Bearer {settings.WATI_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    payload ={
    "template_name": "cart_reminder_v1",
    "broadcast_name": "cart_reminder_campaign",
    "parameters": [],
    "channel_number": ""
    }

    response = requests.post(
        url,
        headers=headers,
        params={
            "whatsappNumber": phone
        },
        json=payload,
        timeout=30
    )
    print(response.status_code)
    print(response.text)

    return response.json()

def send_reorder_template(phone, customer_name, product_name, product_link):

    url = f"{settings.WATI_BASE_URL}/api/v2/sendTemplateMessage"

    headers = {
        "Authorization": f"Bearer {settings.WATI_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    payload = {
        "template_name": "reorder_reminder_v2",
        "broadcast_name": "reorder_reminder",
        "parameters": [
            {"name": "1", "value": customer_name},
            {"name": "2", "value": product_name},
            {"name": "3", "value": product_link}
        ],
        "channel_number": ""
    }

    response = requests.post(
        url,
        headers=headers,
        params={
            "whatsappNumber": phone
        },
        json=payload,
        timeout=30
    )

    return response.json()


def send_order_whatsapp(customer, order):

    mobile = str(customer.mobile).strip()

    if mobile.startswith("+91"):
        whatsapp_number = mobile[1:]
    elif mobile.startswith("91") and len(mobile) == 12:
        whatsapp_number = mobile
    elif len(mobile) == 10:
        whatsapp_number = "91" + mobile
    else:
        raise ValueError(f"Invalid mobile number: {mobile}")

    url = (
        f"{settings.WATI_BASE_URL.rstrip('/')}"
        f"/api/v1/sendTemplateMessage"
    )

    token = getattr(settings, "WATI_TOKEN", None) or getattr(settings, "WATI_API_TOKEN", None)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    template_name = getattr(settings, "WATI_ORDER_PLACED_TEMPLATE_NAME", "dharani_order_placed")

    payload = {
        "template_name": template_name,
        "broadcast_name": "order_placed",
        "parameters": [
            {
                "name": "name",
                "value": customer.name or "Customer"
            },
            {
                "name": "order_no",
                "value": str(order.id)
            },
            {
                "name": "total_amount",
                "value": str(order.total_amount)
            }
        ]
    }

    params = {
        "whatsappNumber": whatsapp_number
    }

    print("\n========== WATI ORDER REQUEST ==========")
    print("URL:", url)
    print("NUMBER:", whatsapp_number)
    print("TEMPLATE:", payload["template_name"])
    print("PARAMETERS:", payload["parameters"])
    print("TOKEN EXISTS:", bool(settings.WATI_TOKEN))

    response = requests.post(
        url,
        headers=headers,
        params=params,
        json=payload,
        timeout=15
    )

    print("WATI ORDER STATUS:", response.status_code)
    print("WATI ORDER RESPONSE:", response.text)

    return response.status_code == 200




@api_view(["GET", "POST"])
def cart_variation(request):

    # ===========================
    # GET
    # ===========================
    if request.method == "GET":

        user_id = request.GET.get("user_id")

        if not user_id:
            return Response({"message": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST)
            
        if not str(user_id).isdigit():
            return Response({"message": "Invalid user_id format. Must be an integer."}, status=status.HTTP_400_BAD_REQUEST)

        cart = Cart.objects.filter(user_id=user_id).select_related("product", "variation")

        serializer = CartVariationSerializer(
            cart,
            many=True,
            context={"request": request}
        )

        product_total = 0
        tax_total = 0
        cgst = 0
        sgst = 0
        igst = 0
        delivery_charge = 0

        address_id = request.GET.get("address_id")

        seller_state = "Tamil Nadu"
        customer_state = ""

        if address_id:
            try:
                address = Address.objects.get(id=address_id)
                customer_state = (address.state or "").strip()

            except Address.DoesNotExist:
                pass

        for item in cart:

            locked_price = float(item.price_at_add or item.product.customer_price)

            item_total = locked_price * item.quantity

            gst = float(item.product.gst_percentage or 0)

            item_tax = item_total * gst / 100

            tax_total += item_tax
            product_total += item_total

            if customer_state and customer_state.lower() == seller_state.lower():
                cgst += item_tax / 2
                sgst += item_tax / 2
            else:
                igst += item_tax

        # Staff users don't pay shipping
        user = User.objects.get(id=user_id)

        if user.role.lower() != "staff":
            if address_id:
                try:
                    address = Address.objects.get(id=address_id)

                    shipping = ShippingCharge.objects.filter(
                        state_name=address.state
                    ).first()

                    if shipping and product_total < float(shipping.free_above):
                        delivery_charge = float(shipping.shipping_amount)

                except Address.DoesNotExist:
                    pass

        grand_total = product_total + delivery_charge


        return Response({
            "count": cart.count(),
            "data": serializer.data,
            "product_total": round(product_total, 2),
            "cgst": round(cgst, 2),
            "sgst": round(sgst, 2),
            "igst": round(igst, 2),
            "tax_total": round(tax_total, 2),
            "delivery_charge": round(delivery_charge, 2),
            "grand_total": round(grand_total, 2)
        }, status=status.HTTP_200_OK)

    # ===========================
    # POST
    # ===========================
    elif request.method == "POST":

        try:

            user_id = request.data.get("user_id")
            product_id = request.data.get("product_id")
            variation_id = request.data.get("variation_id")
            quantity = int(request.data.get("quantity", 1))

            user = User.objects.get(id=user_id)
            product = Product.objects.get(id=product_id)

            variation = None

            if variation_id:
                variation = ProductVariation.objects.get(
                    id=variation_id,
                    product=product
                )

            role = user.role.lower()

            if variation:

                if role == "staff":
                    locked_price = variation.store_price

                elif role == "retailer":
                    locked_price = variation.retailer_price or variation.customer_price

                elif role == "distributor":
                    locked_price = variation.distributor_price or variation.customer_price

                else:
                    locked_price = variation.customer_price

            else:

                if role == "staff":
                    locked_price = product.store_price

                elif role == "retailer":
                    locked_price = product.retailer_price or product.customer_price

                elif role == "distributor":
                    locked_price = product.distributor_price or product.customer_price

                else:
                    locked_price = product.customer_price


            cart_item, created = Cart.objects.get_or_create(
                user=user,
                product=product,
                variation=variation,
                defaults={
                    "quantity": quantity,
                    "price_at_add": locked_price,
                    "role_at_add": role
                }
            )

            if not created:
                if request.data.get("action") == "sync":
                    cart_item.quantity = quantity
                else:
                    cart_item.quantity += quantity
                cart_item.save()

            

            serializer = CartVariationSerializer(
                cart_item,
                context={"request": request}
            )

            return Response(
                {
                    "message": "Added to Cart" if created else "Cart Updated",
                    "data": serializer.data
                },
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
            )

        except Exception as e:

            return Response(
                {
                    "message": str(e)
                },
                status=status.HTTP_400_BAD_REQUEST
            )


@csrf_exempt
def cart_list_add(request):
    """
    GET  /api/cart/?user_id=X
        - List cart items with role-aware prices

    POST /api/cart/
        - Add/update cart item
        - Price locked based on user's role
        - Send WhatsApp message after adding to cart
    """

    # =====================================================
    # GET - LIST CART
    # =====================================================

    if request.method == 'GET':

        user_id = request.GET.get('user_id')

        if not user_id:
            return JsonResponse(
                {'message': 'user_id is required'},
                status=400
            )

        try:
            user = User.objects.get(id=user_id)

        except User.DoesNotExist:
            return JsonResponse(
                {'message': 'User not found'},
                status=404
            )

        cart_items = Cart.objects.filter(
            user=user
        ).select_related(
            'product',
            'product__category'
        )

        data = []

        total = 0.00
        tax_total = 0.00
        cgst = 0.00
        sgst = 0.00
        igst = 0.00

        seller_state = "Tamil Nadu"
        customer_state = ""

        address_id = request.GET.get('address_id')

        delivery_charge = 0.00

        # -------------------------------------------------
        # Get customer state
        # -------------------------------------------------

        if address_id:

            try:
                address = Address.objects.get(id=address_id)
                customer_state = (
                    address.state or ""
                ).strip()

            except Address.DoesNotExist:
                pass

        # -------------------------------------------------
        # Calculate cart
        # -------------------------------------------------

        for item in cart_items:

            locked_price = (
                float(item.price_at_add)
                if item.price_at_add is not None
                else float(item.product.customer_price)
            )

            item_total = (
                locked_price * item.quantity
            )

            gst_percentage = float(
                item.product.gst_percentage or 0
            )

            item_gst = (
                item_total * gst_percentage
            ) / 100

            total += item_total
            tax_total += item_gst

            # -------------------------------------------------
            # GST
            # -------------------------------------------------

            if (
                customer_state
                and
                customer_state.lower()
                == seller_state.lower()
            ):

                cgst += item_gst / 2
                sgst += item_gst / 2

            else:

                igst += item_gst

            data.append({
                'id': item.id,

                'product_id':
                    item.product.id,

                'product_name':
                    item.product.name,

                'variation_id':
                    item.variation.id
                    if item.variation
                    else None,

                'variation_name':
                    item.variation.variation_name
                    if item.variation
                    else None,

                'product_image':
                    get_image_url(
                        request,
                        item.product.image
                    ),

                'category_name':
                    item.product.category.name,

                'price':
                    str(round(locked_price, 2)),

                'role':
                    item.role_at_add,

                'quantity':
                    item.quantity,

                'item_total':
                    str(round(item_total, 2)),

                'added_at':
                    item.added_at.isoformat()
            })

        # =================================================
        # SHIPPING
        # =================================================

        if user.role.lower() != "staff":

            if address_id:

                try:

                    address = Address.objects.get(
                        id=address_id
                    )

                    shipping_obj = (
                        ShippingCharge.objects.filter(
                            state_name=address.state
                        ).first()
                    )

                    if shipping_obj:

                        if total < float(
                            shipping_obj.free_above
                        ):

                            delivery_charge = float(
                                shipping_obj.shipping_amount
                            )

                except Address.DoesNotExist:
                    pass

        # =================================================
        # GRAND TOTAL
        # =================================================

        grand_total = (
            total
            + tax_total
            + delivery_charge
        )

        return JsonResponse({

            'cart': data,

            'total_items':
                len(data),

            'product_total':
                str(round(total, 2)),

            'cgst':
                str(round(cgst, 2)),

            'sgst':
                str(round(sgst, 2)),

            'igst':
                str(round(igst, 2)),

            'tax_total':
                str(round(tax_total, 2)),

            'delivery_charge':
                str(round(delivery_charge, 2)),

            'grand_total':
                str(round(grand_total, 2))
        })

    # =====================================================
    # POST - ADD TO CART
    # =====================================================

    elif request.method == 'POST':

        try:

            # -------------------------------------------------
            # Read request data
            # -------------------------------------------------

            if request.content_type == 'application/json':

                data = json.loads(
                    request.body
                )

            else:

                data = request.POST

            user_id = data.get(
                "user_id"
            )

            product_id = data.get(
                "product_id"
            )

            variation_id = data.get(
                "variation_id"
            )

            quantity = int(
                data.get(
                    "quantity",
                    1
                )
            )

            # -------------------------------------------------
            # Validate
            # -------------------------------------------------

            if not user_id or not product_id:

                return JsonResponse(
                    {
                        "message":
                            "user_id and product_id are required"
                    },
                    status=400
                )

            # -------------------------------------------------
            # Get user
            # -------------------------------------------------

            user = User.objects.get(
                id=user_id
            )

            # -------------------------------------------------
            # Get product
            # -------------------------------------------------

            product = Product.objects.get(
                id=product_id
            )

            # -------------------------------------------------
            # Get variation
            # -------------------------------------------------

            variation = None

            if variation_id:

                variation = ProductVariation.objects.get(
                    id=variation_id,
                    product=product
                )

            # -------------------------------------------------
            # User role
            # -------------------------------------------------

            role = (
                user.role or ""
            ).lower()

            # =================================================
            # DETERMINE PRICE
            # =================================================

            if variation:

                if role == "staff":

                    locked_price = (
                        variation.store_price
                    )

                elif role == "retailer":

                    locked_price = (
                        variation.retailer_price
                        or
                        variation.customer_price
                    )

                elif role == "distributor":

                    locked_price = (
                        variation.distributor_price
                        or
                        variation.customer_price
                    )

                else:

                    locked_price = (
                        variation.customer_price
                    )

            else:

                if role == "staff":

                    locked_price = (
                        product.store_price
                    )

                elif role == "retailer":

                    locked_price = (
                        product.retailer_price
                        or
                        product.customer_price
                    )

                elif role == "distributor":

                    locked_price = (
                        product.distributor_price
                        or
                        product.customer_price
                    )

                else:

                    locked_price = (
                        product.customer_price
                    )

            print(
                "Variation:",
                variation
            )

            print(
                "Locked Price:",
                locked_price
            )

            # =================================================
            # CREATE / UPDATE CART
            # =================================================

            cart_item, created = (
                Cart.objects.get_or_create(

                    user=user,

                    product=product,

                    variation=variation,

                    defaults={

                        "quantity":
                            quantity,

                        "price_at_add":
                            locked_price,

                        "role_at_add":
                            role
                    }
                )
            )

            # -------------------------------------------------
            # Existing cart item
            # -------------------------------------------------

            if not created:

                if data.get("action") == "sync":

                    cart_item.quantity = quantity

                else:

                    cart_item.quantity += quantity

                cart_item.save()

            # =================================================
            # ACTUAL PRICE
            # =================================================

            actual_price = (

                float(
                    cart_item.price_at_add
                )

                if cart_item.price_at_add is not None

                else

                float(
                    locked_price
                )
            )

            total = (
                actual_price
                *
                cart_item.quantity
            )

            print(
                "Cart Item:",
                cart_item.id
            )

            print(
                "Actual Price:",
                actual_price
            )

            print(
                "Quantity:",
                cart_item.quantity
            )

            print(
                "Total:",
                total
            )

            # =================================================
            # WHATSAPP - ADD TO CART
            # =================================================

            try:

                phone = str(
                    user.mobile or ""
                ).strip()

                print(
                    "RAW PHONE:",
                    phone
                )

                # Remove formatting

                phone = (
                    phone
                    .replace("+", "")
                    .replace(" ", "")
                    .replace("-", "")
                )

                # Add India country code

                if phone and not phone.startswith("91"):

                    phone = (
                        "91"
                        +
                        phone
                    )

                print(
                    "WATI PHONE:",
                    phone
                )

                # -------------------------------------------------
                # Send WhatsApp
                # -------------------------------------------------

                if phone:

                    whatsapp_result = send_wati_message(

                        phone=phone,

                        product_name=product.name,

                        quantity=cart_item.quantity,

                        price=actual_price,

                        total=total
                    )

                    print(
                        "WATI RESULT:",
                        whatsapp_result
                    )

                else:

                    print(
                        "WHATSAPP SKIPPED:"
                        " User mobile number is empty"
                    )

            except Exception as msg_error:

                # WhatsApp failure should NOT
                # stop cart operation

                print(
                    "WHATSAPP ERROR:",
                    str(msg_error)
                )

            # =================================================
            # RESPONSE
            # =================================================

            return JsonResponse(

                {

                    "message": (
                        "Added to cart"
                        if created
                        else
                        "Cart updated"
                    ),

                    "cart_item": {

                        "id":
                            cart_item.id,

                        "product_id":
                            product.id,

                        "product_name":
                            product.name,

                        "product_image":
                            get_image_url(
                                request,
                                product.image
                            ),

                        "variation_id":
                            variation.id
                            if variation
                            else None,

                        "variation_name":
                            variation.variation_name
                            if variation
                            else None,

                        "price":
                            str(
                                round(
                                    actual_price,
                                    2
                                )
                            ),

                        "role":
                            cart_item.role_at_add,

                        "quantity":
                            cart_item.quantity,

                        "item_total":
                            str(
                                round(
                                    total,
                                    2
                                )
                            )
                    }

                },

                status=(
                    201
                    if created
                    else
                    200
                )
            )

        # =================================================
        # USER NOT FOUND
        # =================================================

        except User.DoesNotExist:

            return JsonResponse(
                {
                    "message":
                        "User not found"
                },
                status=404
            )

        # =================================================
        # PRODUCT NOT FOUND
        # =================================================

        except Product.DoesNotExist:

            return JsonResponse(
                {
                    "message":
                        "Product not found"
                },
                status=404
            )

        # =================================================
        # VARIATION NOT FOUND
        # =================================================

        except ProductVariation.DoesNotExist:

            return JsonResponse(
                {
                    "message":
                        "Product variation not found"
                },
                status=404
            )

        # =================================================
        # OTHER ERROR
        # =================================================

        except Exception as e:

            print(
                "CART ERROR:",
                str(e)
            )

            return JsonResponse(
                {
                    "message":
                        str(e)
                },
                status=400
            )

    # =====================================================
    # OPTIONS
    # =====================================================

    elif request.method == 'OPTIONS':

        response = JsonResponse(
            {
                'message':
                    'OK'
            },
            status=200
        )

        response[
            'Access-Control-Allow-Origin'
        ] = '*'

        response[
            'Access-Control-Allow-Methods'
        ] = 'GET, POST, OPTIONS'

        response[
            'Access-Control-Allow-Headers'
        ] = '*'

        return response

    # =====================================================
    # METHOD NOT ALLOWED
    # =====================================================

    return JsonResponse(
        {
            'message':
                'Method not allowed'
        },
        status=405
    )




# =====================================================
# CART - UPDATE QUANTITY (PUT) / DELETE ITEM (DELETE)
# =====================================================

@csrf_exempt
def cart_detail(request, pk):

    try:
        cart_item = Cart.objects.get(id=pk)
    except Cart.DoesNotExist:
        return JsonResponse({'message': 'Cart item not found'}, status=404)

    # PUT/PATCH - Update quantity
    if request.method in ['PUT', 'PATCH']:
        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST

            action = data.get('action')
            
            if action == 'increase':
                cart_item.quantity += 1
            elif action == 'decrease':
                cart_item.quantity -= 1
            else:
                quantity = int(data.get('quantity', cart_item.quantity))
                cart_item.quantity = quantity

            # If quantity drops below 1, remove the item entirely
            if cart_item.quantity < 1:
                cart_item.delete()
                return JsonResponse({'message': 'Item removed from cart'}, status=200)

            cart_item.save()

            return JsonResponse({
                'message': 'Cart updated',
                'cart_item': {
                    'id': cart_item.id,
                    'product_id': cart_item.product.id,
                    'product_name': cart_item.product.name,
                    'price': str(cart_item.product.customer_price),
                    'quantity': cart_item.quantity,
                    'item_total': str(round(float(cart_item.product.customer_price) * cart_item.quantity, 2))
                }
            })
        except Exception as e:
            return JsonResponse({'message': 'Failed to update cart', 'errors': str(e)}, status=400)

    # DELETE - Remove item from cart
    elif request.method == 'DELETE':
        cart_item.delete()
        return JsonResponse({'message': 'Item removed from cart'}, status=200)

    if request.method == 'OPTIONS':
        response = JsonResponse({'message': 'OK'}, status=200)
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
        response['Access-Control-Allow-Headers'] = '*'
        return response
    return JsonResponse({'message': 'Method not allowed'}, status=405)


# =====================================================
# CART - CLEAR ENTIRE CART FOR A USER
# =====================================================

@csrf_exempt
def cart_clear(request, user_id):

    if request.method == 'DELETE':
        try:
            user = User.objects.get(id=user_id)
            deleted_count, _ = Cart.objects.filter(user=user).delete()
            return JsonResponse({
                'message': f'Cart cleared. {deleted_count} item(s) removed.'
            }, status=200)
        except User.DoesNotExist:
            return JsonResponse({'message': 'User not found'}, status=404)
        except Exception as e:
            return JsonResponse({'message': 'Failed to clear cart', 'errors': str(e)}, status=400)

    if request.method == 'OPTIONS':
        response = JsonResponse({'message': 'OK'}, status=200)
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
        response['Access-Control-Allow-Headers'] = '*'
        return response
    return JsonResponse({'message': 'Method not allowed'}, status=405)


# =====================================================
# SLIDER - LIST, CREATE
# =====================================================

@csrf_exempt
def slider_list_create(request):

    if request.method == 'OPTIONS':
        response = JsonResponse({'message': 'OK'}, status=200)
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = '*'
        return response

    if request.method == 'GET':
        sliders = Slider.objects.filter(is_active=True).order_by('order')
        data = [{
            'id': s.id,
            'title': s.title,
            'subtitle': s.subtitle,
            'image': get_image_url(request, s.image),
            'is_active': s.is_active,
            'order': s.order,
            'created_at': s.created_at.isoformat()
        } for s in sliders]
        return JsonResponse(data, safe=False)

    elif request.method == 'POST':
        try:
            title = request.POST.get('title', '')
            subtitle = request.POST.get('subtitle', '')
            order = request.POST.get('order', 0)
            is_active = request.POST.get('is_active', 'true').lower() == 'true'
            image = request.FILES.get('image')

            if not image:
                return JsonResponse({'message': 'Image is required'}, status=400)

            slider = Slider.objects.create(
                title=title,
                subtitle=subtitle,
                image=image,
                order=order,
                is_active=is_active
            )
            return JsonResponse({
                'id': slider.id,
                'title': slider.title,
                'subtitle': slider.subtitle,
                'image': get_image_url(request, slider.image),
                'is_active': slider.is_active,
                'order': slider.order,
                'created_at': slider.created_at.isoformat()
            }, status=201)
        except Exception as e:
            return JsonResponse({'message': 'Failed to create slider', 'errors': str(e)}, status=400)

    return JsonResponse({'message': 'Method not allowed'}, status=405)


# =====================================================
# SLIDER - DETAIL / UPDATE / DELETE
# =====================================================

@csrf_exempt
def slider_detail(request, pk):

    if request.method == 'OPTIONS':
        response = JsonResponse({'message': 'OK'}, status=200)
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, PUT, PATCH, DELETE, OPTIONS'
        response['Access-Control-Allow-Headers'] = '*'
        return response

    try:
        slider = Slider.objects.get(id=pk)
    except Slider.DoesNotExist:
        return JsonResponse({'message': 'Slider Not Found'}, status=404)

    if request.method == 'GET':
        return JsonResponse({
            'id': slider.id,
            'title': slider.title,
            'subtitle': slider.subtitle,
            'image': get_image_url(request, slider.image),
            'is_active': slider.is_active,
            'order': slider.order,
            'created_at': slider.created_at.isoformat()
        })

    elif request.method in ['PUT', 'PATCH']:
        try:
            slider.title = request.POST.get('title', slider.title)
            slider.subtitle = request.POST.get('subtitle', slider.subtitle)
            slider.order = request.POST.get('order', slider.order)
            if 'is_active' in request.POST:
                slider.is_active = request.POST.get('is_active').lower() == 'true'
            if 'image' in request.FILES:
                slider.image = request.FILES.get('image')
            slider.save()
            return JsonResponse({
                'id': slider.id,
                'title': slider.title,
                'subtitle': slider.subtitle,
                'image': get_image_url(request, slider.image),
                'is_active': slider.is_active,
                'order': slider.order,
                'created_at': slider.created_at.isoformat()
            })
        except Exception as e:
            return JsonResponse({'message': 'Failed to update slider', 'errors': str(e)}, status=400)

    elif request.method == 'DELETE':
        slider.delete()
        return JsonResponse({'message': 'Slider Deleted'}, status=200)

    return JsonResponse({'message': 'Method not allowed'}, status=405)


# =====================================================
# ADMIN PRODUCTS
# =====================================================

@csrf_exempt
def admin_products(request):
    if request.method == 'GET':
        products = Product.objects.all().order_by('-id')
        data = [serialize_product(request, p, role='admin') for p in products]
        return JsonResponse(data, safe=False)
        
    elif request.method == 'POST':
        try:
            import json
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST

            category_id = data.get('category')
            category = Category.objects.get(id=category_id)
            
            product = Product.objects.create(
                category=category,
                name=data.get('name'),
                product_code=data.get('product_code'),
                barcode=data.get('barcode'),
                description=data.get('description', ''),
                purchase_price=data.get('purchase_price', 0),
                customer_price=data.get('customer_price', 0),
                store_price=data.get('store_price', 0),
                gst_percentage=data.get('gst_percentage', 0),
                stock=data.get('stock', 0),
                reorder_level=data.get('reorder_level', 10),
                unit=data.get('unit', 'pcs'),
                weight_volume=data.get('weight_volume'),
                expiry_date=data.get('expiry_date') or None,
                batch_number=data.get('batch_number'),
                manufacturer=data.get('manufacturer', 'Dharani Herbals'),
                is_new=str(data.get('is_new', 'false')).lower() == 'true',
                is_public=str(data.get('is_public', 'true')).lower() == 'true',
                is_active=str(data.get('is_active', 'true')).lower() == 'true',
                image=request.FILES.get('image') if 'image' in request.FILES else None
            )
            return JsonResponse({'message': 'Product created', 'id': product.id}, status=201)
        except Exception as e:
            return JsonResponse({'message': 'Failed', 'error': str(e)}, status=400)
            
    if request.method == 'OPTIONS':
        response = JsonResponse({'message': 'OK'}, status=200)
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = '*'
        return response


@csrf_exempt
def admin_product_detail(request, pk):
    try:
        product = Product.objects.get(id=pk)
    except Product.DoesNotExist:
        return JsonResponse({'message': 'Product Not Found'}, status=404)
        
    if request.method == 'GET':
        return JsonResponse({
            'id': product.id,
            'name': product.name,
            'product_code': product.product_code,
            'barcode': product.barcode,
            'purchase_price': str(product.purchase_price),
            'customer_price': str(product.customer_price),
            'store_price': str(product.store_price),
            'gst_percentage': str(product.gst_percentage),
            'stock': product.stock,
            'reorder_level': product.reorder_level,
            'unit': product.unit,
            'weight_volume': product.weight_volume,
            'expiry_date': product.expiry_date.isoformat() if product.expiry_date else None,
            'batch_number': product.batch_number,
            'manufacturer': product.manufacturer,
            'is_active': product.is_active,
            'is_public': product.is_public
        })
        
    elif request.method in ['PUT', 'PATCH']:
        try:
            import json
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST
                
            if 'customer_price' in data:
                product.customer_price = data['customer_price']
            if 'purchase_price' in data:
                product.purchase_price = data['purchase_price']
            if 'store_price' in data:
                product.store_price = data['store_price']
            if 'gst_percentage' in data:
                product.gst_percentage = data['gst_percentage']
            if 'stock' in data:
                product.stock = data['stock']
            if 'reorder_level' in data:
                product.reorder_level = data['reorder_level']
            if 'name' in data:
                product.name = data['name']
            if 'product_code' in data:
                product.product_code = data['product_code']
            if 'barcode' in data:
                product.barcode = data['barcode']
            if 'unit' in data:
                product.unit = data['unit']
            if 'weight_volume' in data:
                product.weight_volume = data['weight_volume']
            if 'expiry_date' in data:
                product.expiry_date = data['expiry_date'] or None
            if 'batch_number' in data:
                product.batch_number = data['batch_number']
            if 'manufacturer' in data:
                product.manufacturer = data['manufacturer']
            if 'is_public' in data:
                product.is_public = str(data['is_public']).lower() == 'true'
            if 'is_active' in data:
                product.is_active = str(data['is_active']).lower() == 'true'
            if 'image' in request.FILES:
                product.image = request.FILES.get('image')
                
            product.save()
            return JsonResponse({'message': 'Product updated'})
        except Exception as e:
            return JsonResponse({'message': 'Failed', 'error': str(e)}, status=400)
            
    elif request.method == 'DELETE':
        product.delete()
        return JsonResponse({'message': 'Deleted'})
        
    if request.method == 'OPTIONS':
        response = JsonResponse({'message': 'OK'}, status=200)
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, PUT, PATCH, DELETE, OPTIONS'
        response['Access-Control-Allow-Headers'] = '*'
        return response

# =====================================================
# STORE PRODUCTS - returns store_price as 'price'
# =====================================================
@csrf_exempt
def store_products(request, product_id=None):
    """
    GET    /store/products/             -> List all products with staff pricing
    PUT    /store/products/<product_id>/ -> Update a product (CRM)
    DELETE /store/products/<product_id>/ -> Delete a product (CRM)
    """

    # =========================
    # GET - Staff Product List
    # =========================
    if request.method == "GET":

        products = Product.objects.all().order_by("-id")
        data = [serialize_product(request, product, role="staff") for product in products]

        return JsonResponse(
            data,
            safe=False,
            json_dumps_params={"ensure_ascii": False}
        )

    # =========================
    # PUT / DELETE
    # =========================
    elif request.method in ["PUT", "DELETE"]:

        if product_id is None:
            return JsonResponse(
                {"message": "Product ID is required."},
                status=400
            )

        from .crm_views import crm_product_detail

        return crm_product_detail(request, product_id)

    # =========================
    # OPTIONS
    # =========================
    elif request.method == "OPTIONS":

        response = JsonResponse({"message": "OK"})
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, PUT, DELETE, OPTIONS"
        response["Access-Control-Allow-Headers"] = "*"

        return response

    return JsonResponse(
        {"message": "Method not allowed"},
        status=405
    )




@csrf_exempt
def customer_products(request):

    if request.method == "GET":

        role = get_role(request)

        if role == "admin":
            from .crm_views import crm_products
            return crm_products(request)

        # =====================================================
        # PUBLIC PRODUCTS
        # batch_number = 1 FIRST
        # batch_number = 0 NEXT
        # =====================================================

        from django.db.models import Case, When, Value, IntegerField

        products = Product.objects.filter(
            is_public=True
        ).annotate(
            batch_order=Case(
                When(batch_number="1", then=Value(1)),
                When(batch_number="0", then=Value(2)),
                default=Value(3),
                output_field=IntegerField()
            )
        ).order_by(
            "batch_order",
            "-id"
        )

        data = [
            serialize_product(request, p, role)
            for p in products
        ]

        return JsonResponse(
            data,
            safe=False,
            json_dumps_params={
                "ensure_ascii": False
            }
        )

    # =====================================================
    # POST
    # =====================================================

    if request.method == "POST":

        from .crm_views import crm_products
        return crm_products(request)

    # =====================================================
    # OPTIONS
    # =====================================================

    if request.method == "OPTIONS":

        response = JsonResponse(
            {'message': 'OK'},
            status=200
        )

        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = '*'

        return response

    return JsonResponse(
        {'message': 'Method not allowed'},
        status=405
    )



# =====================================================
# CUSTOMER PRODUCTS - returns customer_price as 'price'
# Pass ?role=staff to get store_price instead
# =====================================================
# @csrf_exempt
# def customer_products(request):
#     if request.method == "GET":

#         role = get_role(request)

#         if role == "admin":
#             from .crm_views import crm_products
#             return crm_products(request)

#         products = Product.objects.filter(
#             is_public=True
#         ).order_by("-id")

#         data = [
#             serialize_product(request, p, role)
#             for p in products
#         ]

#         return JsonResponse(
#             data,
#             safe=False,
#             json_dumps_params={
#                 "ensure_ascii": False
#             }
#         )

#     if request.method == 'POST':
#         from .crm_views import crm_products
#         return crm_products(request)

#     if request.method == 'OPTIONS':
#         response = JsonResponse({'message': 'OK'}, status=200)
#         response['Access-Control-Allow-Origin'] = '*'
#         response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
#         response['Access-Control-Allow-Headers'] = '*'
#         return response

#     return JsonResponse({'message': 'Method not allowed'}, status=405)


@csrf_exempt
def public_product_detail(request, pk):

    # print("=" * 60)
    # print("HEADERS:", dict(request.headers))
    print("X-User-Id:", request.headers.get("X-User-Id"))
    print("X-Role:", request.headers.get("X-Role"))
    # print("GET:", request.GET)
    # print("POST:", request.POST)
    # print("ROLE =", get_role(request))
    # print("=" * 60)
    if request.method == "GET":

        role = get_role(request)
        print("ROLE =", role)
        print("GET =", request.GET)

        if role == "admin":
            from .crm_views import crm_product_detail
            return crm_product_detail(request, pk)

        try:
            p = Product.objects.get(
                id=pk,
                is_public=True
            )

            return JsonResponse(
                serialize_product(request, p, role),
                json_dumps_params={
                    "ensure_ascii": False
                }
            )

        except Product.DoesNotExist:
            return JsonResponse(
                {
                    "message":"Product Not Found"
                },
                status=404
            )

    if request.method in ['PUT', 'DELETE']:
        from .crm_views import crm_product_detail
        return crm_product_detail(request, pk)

    if request.method == 'OPTIONS':
        response = JsonResponse({'message': 'OK'}, status=200)
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, PUT, DELETE, OPTIONS'
        response['Access-Control-Allow-Headers'] = '*'
        return response

    return JsonResponse({'message': 'Method not allowed'}, status=405)

@csrf_exempt
def most_loved_products(request):

    if request.method != "GET":
        return JsonResponse({"message": "Method not allowed"}, status=405)

    role = get_role(request)

    loved_products = MostLovedProduct.objects.filter(
        is_active=True,
        product__is_public=True
    ).select_related(
        "product"
    ).order_by(
        "display_order",
        "-id"
    )

    data = []

    for obj in loved_products:
        data.append(
            serialize_product(
                request,
                obj.product,
                role
            )
        )

    return JsonResponse(
        data,
        safe=False,
        json_dumps_params={"ensure_ascii": False}
    )



# =====================================================
# ADMIN NOTIFICATIONS
# =====================================================

@csrf_exempt
def admin_send_email(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
            customer_id = data.get('customer_id')
            message = data.get('message')

            customer = User.objects.get(id=customer_id)
            success = create_and_send_notification(customer, 'email', 'தாரணி ஹெர்பல்ஸ்', message)

            return JsonResponse({'message': 'Email Sent Successfully' if success else 'Email Failed'}, status=200 if success else 400)
        except User.DoesNotExist:
            return JsonResponse({'message': 'Customer not found'}, status=404)
        except Exception as e:
            return JsonResponse({'message': 'Failed', 'error': str(e)}, status=400)
    
    if request.method == 'OPTIONS':
        resp = JsonResponse({'message': 'OK'}); resp['Access-Control-Allow-Origin'] = '*'
        resp['Access-Control-Allow-Methods'] = 'POST, OPTIONS'; resp['Access-Control-Allow-Headers'] = '*'
        return resp
    return JsonResponse({'message': 'Method not allowed'}, status=405)


@csrf_exempt
def resend_notification_email(request, log_id):
    if request.method == 'POST':
        log = get_object_or_404(NotificationLog, id=log_id)
        customer = log.customer
        clean_message = log.message.split(' [ERROR:')[0]

        recipient_email = (request.POST.get('recipient_email') or customer.email or '').strip()

        if not recipient_email:
            log.notification_type = 'email'
            log.status = 'failed'
            log.message = f"{clean_message} [ERROR: Customer has no email address]"
            log.save(update_fields=['notification_type', 'status', 'message'])
            return redirect('/api/dashboard/')

        if recipient_email != (customer.email or ''):
            if User.objects.exclude(id=customer.id).filter(email=recipient_email).exists():
                log.notification_type = 'email'
                log.status = 'failed'
                log.message = f"{clean_message} [ERROR: This email is already used by another user]"
                log.save(update_fields=['notification_type', 'status', 'message'])
                return redirect('/api/dashboard/')

            customer.email = recipient_email
            customer.save(update_fields=['email'])

        try:
            send_email_with_fallback(
                'தாரணி ஹெர்பல்ஸ்',
                clean_message,
                settings.DEFAULT_FROM_EMAIL,
                [recipient_email],
                fail_silently=False,
            )
            log.notification_type = 'email'
            log.status = 'sent'
            log.message = clean_message
            log.save(update_fields=['notification_type', 'status', 'message'])
        except Exception as e:
            log.notification_type = 'email'
            log.status = 'failed'
            log.message = f"{clean_message} [ERROR: {str(e)}]"
            log.save(update_fields=['notification_type', 'status', 'message'])

        return redirect('/api/dashboard/')

    return JsonResponse({'message': 'Method not allowed'}, status=405)


@csrf_exempt
def admin_send_whatsapp(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
            customer_id = data.get('customer_id')
            message = data.get('message')

            customer = User.objects.get(id=customer_id)
            success = create_and_send_notification(customer, 'whatsapp', '', message)

            return JsonResponse({'message': 'WhatsApp Sent Successfully' if success else 'WhatsApp Failed'}, status=200 if success else 400)
        except User.DoesNotExist:
            return JsonResponse({'message': 'Customer not found'}, status=404)
        except Exception as e:
            return JsonResponse({'message': 'Failed', 'error': str(e)}, status=400)
            
    if request.method == 'OPTIONS':
        resp = JsonResponse({'message': 'OK'}); resp['Access-Control-Allow-Origin'] = '*'
        resp['Access-Control-Allow-Methods'] = 'POST, OPTIONS'; resp['Access-Control-Allow-Headers'] = '*'
        return resp
    return JsonResponse({'message': 'Method not allowed'}, status=405)

@csrf_exempt
def admin_notification_history(request):
    if request.method == 'GET':
        logs = NotificationLog.objects.all().order_by('-created_at')
        data = []
        for log in logs:
            data.append({
                'id': log.id,
                'customer_name': log.customer.name,
                'type': log.notification_type,
                'message': log.message,
                'status': log.status,
                'created_at': log.created_at.isoformat()
            })
        return JsonResponse(data, safe=False)
        
    if request.method == 'OPTIONS':
        resp = JsonResponse({'message': 'OK'}); resp['Access-Control-Allow-Origin'] = '*'
        resp['Access-Control-Allow-Methods'] = 'GET, OPTIONS'; resp['Access-Control-Allow-Headers'] = '*'
        return resp
    return JsonResponse({'message': 'Method not allowed'}, status=405)

# =====================================================
# STAFF NOTIFICATIONS
# =====================================================

@csrf_exempt
def staff_notifications(request):
    # Same as admin history for now, but could be filtered if needed
    if request.method == 'GET':
        logs = NotificationLog.objects.all().order_by('-created_at')
        data = []
        for log in logs:
            data.append({
                'id': log.id,
                'customer_name': log.customer.name,
                'type': log.notification_type,
                'message': log.message,
                'status': log.status,
                'created_at': log.created_at.isoformat()
            })
        return JsonResponse(data, safe=False)
        
    if request.method == 'OPTIONS':
        resp = JsonResponse({'message': 'OK'}); resp['Access-Control-Allow-Origin'] = '*'
        resp['Access-Control-Allow-Methods'] = 'GET, OPTIONS'; resp['Access-Control-Allow-Headers'] = '*'
        return resp
    return JsonResponse({'message': 'Method not allowed'}, status=405)

@csrf_exempt
def staff_send_notification(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
            staff_id = data.get('staff_id')
            customer_id = data.get('customer_id')
            notif_type = data.get('type') # 'email' or 'whatsapp'
            message = data.get('message')

            staff = User.objects.get(id=staff_id)
            if not staff.can_send_notifications:
                return JsonResponse({'message': 'Permission denied. Staff member cannot send notifications.'}, status=403)

            customer = User.objects.get(id=customer_id)
            success = create_and_send_notification(customer, notif_type, 'தாரணி ஹெர்பல்ஸ்', message)

            return JsonResponse({'message': f'{notif_type.capitalize()} Sent Successfully' if success else f'{notif_type.capitalize()} Failed'}, status=200 if success else 400)
        except User.DoesNotExist:
            return JsonResponse({'message': 'Staff or Customer not found'}, status=404)
        except Exception as e:
            return JsonResponse({'message': 'Failed', 'error': str(e)}, status=400)
            
    if request.method == 'OPTIONS':
        resp = JsonResponse({'message': 'OK'}); resp['Access-Control-Allow-Origin'] = '*'
        resp['Access-Control-Allow-Methods'] = 'POST, OPTIONS'; resp['Access-Control-Allow-Headers'] = '*'
        return resp
    return JsonResponse({'message': 'Method not allowed'}, status=405)



# # @csrf_exempt
# @csrf_exempt
# def resend_otp(request):

#     print(">>> RESEND OTP VIEW CALLED <<<")

#     if request.method != "POST":
#         return JsonResponse({
#             "success": False,
#             "message": "Only POST method is allowed"
#         }, status=405)

#     try:
#         data = json.loads(request.body)

#         mobile = data.get("mobile")

#         if not mobile:
#             return JsonResponse({
#                 "success": False,
#                 "message": "Mobile number is required"
#             }, status=400)

#         mobile = str(mobile).strip()

#         # Check pending registration
#         pending_user = PendingRegistration.objects.filter(
#             mobile=mobile
#         ).first()

#         if not pending_user:
#             return JsonResponse({
#                 "success": False,
#                 "message": "User registration not found"
#             }, status=404)

#         # Generate new OTP
#         otp = str(random.randint(100000, 999999))

#         # Expiry
#         expires_at = timezone.now() + timedelta(minutes=30)

#         # Delete old OTP
#         OTPVerification.objects.filter(
#             mobile=mobile
#         ).delete()

#         # Save new OTP
#         OTPVerification.objects.create(
#             mobile=mobile,
#             otp=otp,
#             expires_at=expires_at
#         )

#         print("NEW OTP:", otp)

#         # ==========================================
#         # SEND SMS IN BACKGROUND
#         # ==========================================

#         threading.Thread(
#             target=send_sms_background,
#             args=(mobile, otp),
#             daemon=True
#         ).start()

#         return JsonResponse({
#             "success": True,
#             "message": "OTP resent successfully",
#             "mobile": mobile
#         })

#     except Exception as e:

#         print("RESEND OTP ERROR:", e)

#         return JsonResponse({
#             "success": False,
#             "message": str(e)
#         }, status=500)

# @csrf_exempt
# def verify_otp(request):

#     print(">>> VERIFY OTP VIEW CALLED <<<")

#     if request.method != "POST":
#         return JsonResponse({
#             "success": False,
#             "message": "Only POST method is allowed"
#         }, status=405)

#     try:

#         data = json.loads(request.body)

#         mobile = data.get("mobile")
#         otp = data.get("otp")

#         if not mobile or not otp:
#             return JsonResponse({
#                 "success": False,
#                 "message": "Mobile number and OTP are required"
#             }, status=400)

#         mobile = str(mobile).strip()
#         otp = str(otp).strip()

#         # Find OTPVerification
#         otp_record = OTPVerification.objects.filter(mobile=mobile).first()

#         if not otp_record:
#             return JsonResponse({
#                 "success": False,
#                 "message": "OTP not found or already verified"
#             }, status=404)

#         # Check 30-minute expiry
#         if timezone.now() > otp_record.expires_at:
#             otp_record.delete()
#             return JsonResponse({
#                 "success": False,
#                 "message": "OTP has expired"
#             }, status=400)

#         # Check OTP
#         if otp_record.otp != otp:
#             return JsonResponse({
#                 "success": False,
#                 "message": "Invalid OTP"
#             }, status=400)

#         # OTP is correct, find PendingRegistration
#         pending_user = PendingRegistration.objects.filter(mobile=mobile).first()

#         if not pending_user:
#             return JsonResponse({
#                 "success": False,
#                 "message": "Pending registration not found"
#             }, status=404)

#         if User.objects.filter(email=pending_user.email).exists():
#             pending_user.delete()
#             otp_record.delete()
#             return JsonResponse({
#                 "success": False,
#                 "message": "User already exists"
#             }, status=400)

#         # Create User
#         user = User.objects.create(
#             name=pending_user.name,
#             mobile=pending_user.mobile,
#             email=pending_user.email,
#             password=pending_user.password,
#             role=pending_user.role,
#             is_verified=True
#         )

#         if user.email:
#             try:
#                 context = {
#                     "name": user.name,
#                     "mobile": user.mobile,
#                     "role": user.role
#                 }
#                 html_content = render_to_string(
#                     "email/register_success.html",
#                     context
#                 )
#                 email_msg = EmailMultiAlternatives(
#                     subject="Registration Successful",
#                     body="Registration Successful",
#                     from_email=settings.DEFAULT_FROM_EMAIL,
#                     to=[user.email]
#                 )
#                 email_msg.attach_alternative(
#                     html_content,
#                     "text/html"
#                 )
#                 email_msg.send()
#             except Exception as email_err:
#                 print(f"Failed to send registration email: {email_err}")

#         # Delete PendingRegistration & OTPVerification
#         pending_user.delete()
#         otp_record.delete()

#         return JsonResponse({
#             "success": True,
#             "message": "Account verified successfully",
#             "user": {
#                 "id": user.id,
#                 "name": user.name,
#                 "mobile": user.mobile,
#                 "email": user.email,
#                 "role": user.role,
#                 "can_send_notifications": user.can_send_notifications,
#                 "created_at": user.created_at.strftime("%Y-%m-%d"),
#             },
#             "permissions": {
#                 "add_products": user.role == "admin",
#                 "edit_products": user.role == "admin",
#                 "delete_products": user.role == "admin",
#                 "change_prices": user.role == "admin",
#                 "manage_orders": user.role in ["admin", "staff"],
#                 "manage_customers": user.role in ["admin", "staff"],
#                 "manage_staff": user.role == "admin",
#                 "send_whatsapp": user.role == "admin",
#                 "send_emails": user.role == "admin",
#                 "view_reports": user.role in ["admin", "staff"],
#                 "print_bills": user.role in ["admin", "staff"],
#                 "full_access": user.role == "admin",
#             }
#         }, status=200)

#     except Exception as e:
#         return JsonResponse({
#             "success": False,
#             "message": str(e)
#         }, status=500)
     

# # =====================================================
# # CHECKOUT
# # =====================================================
# @csrf_exempt
# def checkout(request):
#         if request.method == 'POST':
#             try:
#                 data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
#                 user_id          = data.get('user_id')
#                 address_id = data.get('address_id')
#                 latitude         = data.get('latitude', '')
#                 longitude        = data.get('longitude', '')

#                 if not user_id:
#                     return JsonResponse({'message': 'user_id is required'}, status=400)

#                 user       = User.objects.get(id=user_id)
#                 if not address_id:
#                     return JsonResponse(
#                         {'message': 'address_id is required'},
#                         status=400
#                     )

#                 address = Address.objects.get(id=address_id)
#                 seller_state = "Tamil Nadu"
#                 customer_state = (address.state or "").strip()
#                 cart_items = Cart.objects.filter(user=user).select_related('product')

#                 if not cart_items.exists():
#                     return JsonResponse({'message': 'Cart is empty'}, status=400)

#                 # Use the price locked at add-time for each item (role-aware billing)
#                 # Product Total
#                 items_total = 0
            
#                 cgst = 0
#                 sgst = 0
#                 igst = 0
#                 tax_total = 0

#                 for item in cart_items:
#                     price = float(item.price_at_add) if item.price_at_add else float(item.product.customer_price)

#                     item_total = price * item.quantity
#                     items_total += item_total

#                     gst_percentage = float(item.product.gst_percentage or 0)

#                     gst_amount = (item_total * gst_percentage) / 100

#                     tax_total += gst_amount

#                     if customer_state.lower() == seller_state.lower():

#                         cgst = gst_amount / 2
#                         sgst = gst_amount / 2

#                         cgst += cgst
#                         sgst += sgst

#                     else:

#                         igst += gst_amount
                
#                 # Shipping Charge
#                 delivery_charge = 0.00

#                 # Staff users never pay shipping
#                 if user.role.lower() != "staff":
#                     shipping_obj = ShippingCharge.objects.filter(
#                         state_name=address.state
#                     ).first()

#                     if shipping_obj:
#                         if items_total < float(shipping_obj.free_above):
#                             delivery_charge = float(
#                                 shipping_obj.shipping_amount
#                             )
#                 total_amount = items_total + delivery_charge

#                 # Convert empty string to None for decimal fields
#                 lat_val = float(latitude) if latitude else None
#                 lng_val = float(longitude) if longitude else None

#                 # Create Order
#                 order = Order.objects.create(
#                     customer=user,
#                     product_amount=items_total,
#                     gst_amount=tax_total,
#                     cgst_amount=cgst,
#                     sgst_amount=sgst,
#                     igst_amount=igst,
#                     total_amount=total_amount,
#                     shipping_charges=delivery_charge,
#                     address=address,
#                     latitude=lat_val,
#                     longitude=lng_val,
#                     status='pending'
#                 )

#                 # Create OrderItems using locked price — not live product price
#                 for item in cart_items:
#                     billed_price = item.price_at_add if item.price_at_add else item.product.customer_price
#                     OrderItem.objects.create(
#                         order=order,
#                         product=item.product,
#                         variation=item.variation,
#                         quantity=item.quantity,
#                         price=billed_price
#                     )

#                 # Clear Cart
#                 cart_items.delete()

#                 # Optional: Send Order Notification
#                 message = f'''வணக்கம் {user.name},

#     உங்கள் ஆர்டர் வெற்றிகரமாக பதிவு செய்யப்பட்டுள்ளது.
#     ஆர்டர் எண்: #{order.id}
#     மொத்த தொகை: ₹{order.total_amount}

#     நன்றி,
#     தாரணி ஹெர்பல்ஸ்'''
#                 create_and_send_notification(user, 'email', 'ஆர்டர் உறுதி செய்யப்பட்டது', message)
#                 create_and_send_notification(user, 'whatsapp', 'ஆர்டர் உறுதி செய்யப்பட்டது', message)


#                 return JsonResponse({'message': 'Order placed successfully', 'order_id': order.id}, status=200)

#             except User.DoesNotExist:
#                 return JsonResponse({'message': 'User not found'}, status=404)
#             except Exception as e:
#                 return JsonResponse({'message': 'Checkout failed', 'error': str(e)}, status=400)

#         if request.method == 'OPTIONS':
#             resp = JsonResponse({'message': 'OK'}); resp['Access-Control-Allow-Origin'] = '*'
#             resp['Access-Control-Allow-Methods'] = 'POST, OPTIONS'; resp['Access-Control-Allow-Headers'] = '*'
#             return resp
#         return JsonResponse({'message': 'Method not allowed'}, status=405)


# =====================================================
# CHECKOUT
# =====================================================
@csrf_exempt
def checkout(request):

    # =========================================================
    # POST ONLY
    # =========================================================

    if request.method == 'POST':

        try:

            # -------------------------------------------------
            # Read request data
            # -------------------------------------------------

            data = (
                json.loads(request.body)
                if request.content_type == 'application/json'
                else request.POST
            )

            user_id = data.get('user_id')
            address_id = data.get('address_id')
            latitude = data.get('latitude', '')
            longitude = data.get('longitude', '')

            # -------------------------------------------------
            # Validate user
            # -------------------------------------------------

            if not user_id:
                return JsonResponse(
                    {
                        'success': False,
                        'message': 'user_id is required'
                    },
                    status=400
                )

            user = User.objects.get(id=user_id)

            # -------------------------------------------------
            # Validate address
            # -------------------------------------------------

            if not address_id:
                return JsonResponse(
                    {
                        'success': False,
                        'message': 'address_id is required'
                    },
                    status=400
                )

            address = Address.objects.get(id=address_id)

            # -------------------------------------------------
            # Get user's cart
            # -------------------------------------------------

            cart_items = Cart.objects.filter(
                user=user
            ).select_related('product')

            if not cart_items.exists():
                return JsonResponse(
                    {
                        'success': False,
                        'message': 'Cart is empty'
                    },
                    status=400
                )

            # -------------------------------------------------
            # Initialize product total
            # GST completely removed
            # -------------------------------------------------

            items_total = 0.00

            # -------------------------------------------------
            # Calculate product total
            # -------------------------------------------------

            for item in cart_items:

                # Use price locked when product was
                # added to cart
                if item.price_at_add is not None:
                    price = float(item.price_at_add)
                else:
                    price = float(
                        item.product.customer_price
                    )

                item_total = price * item.quantity

                items_total += item_total

            # -------------------------------------------------
            # Shipping charge
            # -------------------------------------------------

            delivery_charge = 0.00

            # Staff users don't pay shipping
            if user.role.lower() != "staff":

                shipping_obj = ShippingCharge.objects.filter(
                    state_name=address.state
                ).first()

                if shipping_obj:

                    if items_total < float(
                        shipping_obj.free_above
                    ):

                        delivery_charge = float(
                            shipping_obj.shipping_amount
                        )

            # -------------------------------------------------
            # FINAL TOTAL
            # Product + Shipping
            # GST REMOVED
            # -------------------------------------------------

            total_amount = (
                items_total
                + delivery_charge
            )

            # =================================================
            # CREDIT LIMIT LOGIC
            # =================================================
            amount_to_pay = total_amount
            credit_used = 0.00
            
            user_role = (user.role or '').lower()
            if user_role in ['retailer', 'reseller', 'staff', 'distributor'] or user.credit_payment_enabled or str(data.get('payment_method', '')).lower() == 'credit':
                avail_credit = float(user.available_credit or 0)
                if avail_credit > 0:
                    if avail_credit >= total_amount:
                        credit_used = total_amount
                        amount_to_pay = 0.00
                        user.available_credit = Decimal(str(avail_credit - total_amount))
                    else:
                        credit_used = avail_credit
                        amount_to_pay = total_amount - credit_used
                        user.available_credit = Decimal("0.00")
                    user.save()

            # -------------------------------------------------
            # Latitude / Longitude
            # -------------------------------------------------

            lat_val = (
                float(latitude)
                if latitude
                else None
            )

            lng_val = (
                float(longitude)
                if longitude
                else None
            )

            # -------------------------------------------------
            # Create Order
            # -------------------------------------------------

            order = Order.objects.create(
                customer=user,

                # Product amount
                product_amount=items_total,

                # GST fields removed from calculation
                # They will remain NULL/0 depending on
                # your model configuration.

                total_amount=total_amount,
                credit_used=credit_used,
                amount_to_pay=amount_to_pay,

                shipping_charges=delivery_charge,

                address=address,

                latitude=lat_val,
                longitude=lng_val,

                status='pending'
            )

            # -------------------------------------------------
            # Create Order Items
            # -------------------------------------------------

            for item in cart_items:

                if item.price_at_add is not None:
                    billed_price = item.price_at_add
                else:
                    billed_price = (
                        item.product.customer_price
                    )

                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    variation=item.variation,
                    quantity=item.quantity,
                    price=billed_price
                )

            # -------------------------------------------------
            # Clear cart
            # -------------------------------------------------

            cart_items.delete()

            # =================================================
            # ORDER WHATSAPP + EMAIL NOTIFICATION
            # =================================================

            message = f"""வணக்கம் {user.name},

உங்கள் ஆர்டர் வெற்றிகரமாக பதிவு செய்யப்பட்டுள்ளது.

ஆர்டர் எண்: #{order.id}

பொருள் தொகை: ₹{order.product_amount}
Shipping: ₹{order.shipping_charges}

மொத்த தொகை: ₹{order.total_amount}

நன்றி,
தாரணி ஹெர்பல்ஸ்"""

            # -------------------------------------------------
            # Email
            # -------------------------------------------------

            try:

                create_and_send_notification(
                    user,
                    'email',
                    'ஆர்டர் உறுதி செய்யப்பட்டது',
                    message
                )

            except Exception as email_error:

                print(
                    "ORDER EMAIL ERROR:",
                    str(email_error)
                )

            # -------------------------------------------------
            # WhatsApp
            # -------------------------------------------------

            try:

                whatsapp_result = send_order_whatsapp(
                    user,
                    order
                )

                print(
                    "ORDER WHATSAPP RESULT:",
                    whatsapp_result
                )

            except Exception as whatsapp_error:

                print(
                    "ORDER WHATSAPP ERROR:",
                    str(whatsapp_error)
                )

            # -------------------------------------------------
            # Response
            # -------------------------------------------------

            return JsonResponse(
                {
                    'success': True,
                    'message': 'Order placed successfully',

                    'order_id': order.id,

                    'product_amount': round(
                        items_total,
                        2
                    ),

                    'shipping_charges': round(
                        delivery_charge,
                        2
                    ),

                    'total_amount': round(
                        total_amount,
                        2
                    ),
                    
                    'amount_to_pay': round(
                        amount_to_pay,
                        2
                    ),
                    
                    'credit_used': round(
                        credit_used,
                        2
                    )
                },
                status=200
            )

        # -----------------------------------------------------
        # User not found
        # -----------------------------------------------------

        except User.DoesNotExist:

            return JsonResponse(
                {
                    'success': False,
                    'message': 'User not found'
                },
                status=404
            )

        # -----------------------------------------------------
        # Address not found
        # -----------------------------------------------------

        except Address.DoesNotExist:

            return JsonResponse(
                {
                    'success': False,
                    'message': 'Address not found'
                },
                status=404
            )

        # -----------------------------------------------------
        # Other errors
        # -----------------------------------------------------

        except Exception as e:

            print(
                "CHECKOUT ERROR:",
                str(e)
            )

            return JsonResponse(
                {
                    'success': False,
                    'message': 'Checkout failed',
                    'error': str(e)
                },
                status=400
            )

    # =========================================================
    # OPTIONS
    # =========================================================

    if request.method == 'OPTIONS':

        resp = JsonResponse(
            {
                'success': True,
                'message': 'OK'
            }
        )

        resp['Access-Control-Allow-Origin'] = '*'
        resp['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        resp['Access-Control-Allow-Headers'] = '*'

        return resp

    # =========================================================
    # METHOD NOT ALLOWED
    # =========================================================

    return JsonResponse(
        {
            'success': False,
            'message': 'Method not allowed'
        },
        status=405
    )

# =====================================================
# ADMIN DASHBOARD
# =====================================================
@csrf_exempt
def admin_dashboard(request):
    if request.method == 'GET':
        today = timezone.now().date()
        first_day_of_month = today.replace(day=1)

        # Basic Counts
        total_products = Product.objects.count()
        total_categories = Category.objects.count()
        total_brands = Brand.objects.count()

        # Today's Stats
        todays_orders = Order.objects.filter(created_at__date=today)
        todays_order_count = todays_orders.count()
        todays_income = todays_orders.aggregate(Sum('total_amount'))['total_amount__sum'] or 0.00

        # Monthly Stats
        monthly_orders = Order.objects.filter(created_at__date__gte=first_day_of_month)
        monthly_order_count = monthly_orders.count()
        monthly_income = monthly_orders.aggregate(Sum('total_amount'))['total_amount__sum'] or 0.00

        # Status Breakdown
        status_counts = Order.objects.values('status').annotate(count=Count('id'))
        status_breakdown = {item['status']: item['count'] for item in status_counts}

        # Pending Order Details (latest 5)
        pending_orders_qs = Order.objects.filter(status='pending').order_by('-created_at')[:5]
        pending_details = []
        for po in pending_orders_qs:
            pending_details.append({
                'order_id': po.id,
                'customer': po.customer.name,
                'amount': str(po.total_amount),
                'date': po.created_at.isoformat()
            })

        return JsonResponse({
            'message': 'Dashboard Data Retrieved',
            'dashboard_data': {
                'inventory': {
                    'products': total_products,
                    'categories': total_categories,
                    'brands': total_brands
                },
                'today': {
                    'orders': todays_order_count,
                    'income': str(todays_income)
                },
                'monthly': {
                    'orders': monthly_order_count,
                    'income': str(monthly_income)
                },
                'statuses': status_breakdown,
                'recent_pending_orders': pending_details
            }
        }, status=200)

    if request.method == 'OPTIONS':
        resp = JsonResponse({'message': 'OK'}); resp['Access-Control-Allow-Origin'] = '*'
        resp['Access-Control-Allow-Methods'] = 'GET, OPTIONS'; resp['Access-Control-Allow-Headers'] = '*'
        return resp
    return JsonResponse({'message': 'Method not allowed'}, status=405)



# =====================================================
# ORDER STATUS UPDATE (Admin / Staff)
# =====================================================
@csrf_exempt
def update_order_status(request, order_id):
    if request.method in ('POST', 'PATCH', 'PUT'):
        try:
            data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
            
            order = Order.objects.get(id=order_id)
            new_status    = data.get('status')
            note          = data.get('note', '')
            latitude      = data.get('latitude')
            longitude     = data.get('longitude')
            location_name = data.get('location_name', '')
            updated_by_id = data.get('updated_by')   # staff/admin user id
            cancel_reason = data.get('cancel_reason', '')
            damage_notes  = data.get('damage_notes', '')
            tracking_number = data.get('tracking_number', '')
            estimated_delivery = data.get('estimated_delivery')

            valid_statuses = [
                'pending', 'confirmed', 'processing', 'shipped',
                'out_for_delivery', 'delivered', 'received',
                'cancelled', 'damaged', 'returned'
            ]
            if new_status and new_status not in valid_statuses:
                return JsonResponse({'message': f'Invalid status. Choose from: {valid_statuses}'}, status=400)

            # Update order fields
            if new_status:
                order.status = new_status

                if (
                    new_status == "delivered"
                    and order.delivered_at is None
                ):
                    order.delivered_at = timezone.now()
            if cancel_reason:
                order.cancel_reason = cancel_reason
            if damage_notes:
                order.damage_notes = damage_notes
            if tracking_number:
                order.tracking_number = tracking_number
            if estimated_delivery:
                order.estimated_delivery = estimated_delivery
            if latitude:
                order.latitude = latitude
            if longitude:
                order.longitude = longitude
            order.save()

            # Log tracking entry
            updated_by = None
            if updated_by_id:
                try:
                    updated_by = User.objects.get(id=updated_by_id)
                except:
                    pass

            OrderTracking.objects.create(
                order=order,
                status=new_status or order.status,
                note=note,
                latitude=latitude,
                longitude=longitude,
                location_name=location_name,
                updated_by=updated_by
            )

            # Send Tamil notification to customer
            status_messages = {
                'confirmed':        'உங்கள் ஆர்டர் உறுதி செய்யப்பட்டது.',
                'processing':       'உங்கள் ஆர்டர் தயாரிக்கப்படுகிறது.',
                'shipped':          'உங்கள் ஆர்டர் அனுப்பப்பட்டது.',
                'out_for_delivery': 'உங்கள் ஆர்டர் டெலிவரிக்கு வருகிறது.',
                'delivered':        'உங்கள் ஆர்டர் டெலிவரி செய்யப்பட்டது.',
                'received':         'ஆர்டர் வெற்றிகரமாக பெறப்பட்டது.',
                'cancelled':        f'உங்கள் ஆர்டர் ரத்து செய்யப்பட்டது. காரணம்: {cancel_reason}',
                'damaged':          f'ஆர்டர் பாதிக்கப்பட்டுள்ளது. குறிப்பு: {damage_notes}',
                'returned':         'ஆர்டர் திரும்ப பெறப்பட்டது.',
            }
            status_note = status_messages.get(new_status, f'ஆர்டர் நிலை: {new_status}')
            loc_info = f'\nஇடம்: {location_name}' if location_name else ''
            message = f'''வணக்கம் {order.customer.name},

ஆர்டர் எண்: #{order.id}
{status_note}{loc_info}

நன்றி,
தாரணி ஹெர்பல்ஸ்'''
            create_and_send_notification(order.customer, 'email', f'ஆர்டர் #{order.id} நிலை புதுப்பிப்பு', message)
            create_and_send_notification(order.customer, 'whatsapp', f'ஆர்டர் #{order.id} நிலை புதுப்பிப்பு', message)

            return JsonResponse({
                'message': f'Order status updated to "{order.status}"',
                'order_id': order.id,
                'status': order.status,
                'tracking_number': order.tracking_number or ''
            }, status=200)

        except Order.DoesNotExist:
            return JsonResponse({'message': 'Order not found'}, status=404)
        except Exception as e:
            return JsonResponse({'message': 'Failed', 'error': str(e)}, status=400)

    if request.method == 'OPTIONS':
        resp = JsonResponse({'message': 'OK'}); resp['Access-Control-Allow-Origin'] = '*'
        resp['Access-Control-Allow-Methods'] = 'POST, PATCH, PUT, OPTIONS'; resp['Access-Control-Allow-Headers'] = '*'
        return resp
    return JsonResponse({'message': 'Method not allowed'}, status=405)


# =====================================================
# ORDER TRACKING - PUBLIC (Customer can view their order)
# =====================================================
@csrf_exempt
def track_order(request, order_id):
    if request.method == 'GET':
        try:
            # Support both database integer IDs and Razorpay order IDs (e.g. 'order_T2isJicOzmET4z')
            try:
                order = Order.objects.get(id=int(order_id))
            except (ValueError, Order.DoesNotExist):
                # Try looking up by Razorpay order ID via Payment
                payment = Payment.objects.filter(razorpay_order_id=order_id).first()
                if payment:
                    order = payment.order
                else:
                    return JsonResponse({'message': 'Order not found'}, status=404)
            history = order.tracking_history.all().order_by('created_at')

            tracking_steps = []
            for step in history:
                tracking_steps.append({
                    'status': step.status,
                    'note': step.note or '',
                    'location_name': step.location_name or '',
                    'latitude': str(step.latitude) if step.latitude else '',
                    'longitude': str(step.longitude) if step.longitude else '',
                    'updated_by': step.updated_by.name if step.updated_by else 'System',
                    'time': step.created_at.isoformat()
                })

            items = []
            for item in order.items.all():
                items.append({
                    'product': item.product.name if item.product else 'Deleted',
                    'quantity': item.quantity,
                    'price': str(item.price)
                })

            return JsonResponse({
                'order_id': order.id,
                'customer': order.customer.name,
                'status': order.status,
                'total_amount': str(order.total_amount),'product_amount': str(order.product_amount),
                'cgst': str(order.cgst_amount),
                'sgst': str(order.sgst_amount),
                'igst': str(order.igst_amount),
                'tax_total': str(order.gst_amount),
                'shipping_charges': str(order.shipping_charges),
                'total_amount': str(order.total_amount),
                'tracking_number': order.tracking_number or '',
                'estimated_delivery': str(order.estimated_delivery) if order.estimated_delivery else '',
                'shipping': {
                    'full_name': order.address.full_name if order.address else '',
                    'phone': order.address.phone if order.address else '',
                    'address': order.address.address if order.address else '',
                    'city': order.address.city if order.address else '',
                    'state': order.address.state if order.address else '',
                    'pincode': order.address.pincode if order.address else '',
                    'latitude': str(order.latitude) if order.latitude else '',
                    'longitude': str(order.longitude) if order.longitude else ''
                },
                'cancel_reason': order.cancel_reason or '',
                'damage_notes': order.damage_notes or '',
                'items': items,
                'tracking_history': tracking_steps,
                'created_at': order.created_at.isoformat()
            }, status=200)

        except Order.DoesNotExist:
            return JsonResponse({'message': 'Order not found'}, status=404)
        except Exception as e:
            return JsonResponse({'message': 'Error', 'error': str(e)}, status=400)

    if request.method == 'OPTIONS':
        resp = JsonResponse({'message': 'OK'}); resp['Access-Control-Allow-Origin'] = '*'
        resp['Access-Control-Allow-Methods'] = 'GET, OPTIONS'; resp['Access-Control-Allow-Headers'] = '*'
        return resp
    return JsonResponse({'message': 'Method not allowed'}, status=405)


# =====================================================
# LIST ALL ORDERS (Admin)
# =====================================================
# @csrf_exempt
# def admin_all_orders(request):
    
#     if request.method == 'GET':
#         orders = Order.objects.prefetch_related(
#             "items__product",
#             "items__variation",
#             "payments"
#         ).select_related("customer")

#         status_filter = request.GET.get('status')
#         user_filter   = request.GET.get('user_id')
        
#         if user_filter and not str(user_filter).isdigit():
#             return JsonResponse({"success": False, "message": "Invalid user_id format. Must be an integer."}, status=400)
        
#         if status_filter:
#             orders = orders.filter(status=status_filter)
#         if user_filter:
#             orders = orders.filter(customer_id=user_filter)

#         orders = orders.order_by('-created_at')

#         data = []

#         for o in orders:
#             items = []

#             for item in o.items.all():
#                 items.append({
#                     "id": item.id,
#                     "product_id": item.product.id if item.product else None,
#                     "product": item.product.name if item.product else 'Deleted',
#                     "product_name": item.product.name if item.product else 'Deleted',
#                     "variation_id": item.variation.id if item.variation else None,
#                     "variation_name": item.variation.variation_name if item.variation else "",
#                     "category": item.product.category.name if item.product and item.product.category else "",
#                     "brand": item.product.brand.name if item.product and getattr(item.product, 'brand', None) else "",
#                     "price": float(item.price),
#                     "quantity": item.quantity,
#                     "total": float(item.price * item.quantity),
#                     "product_image": get_image_url(request, item.product.image) if item.product and getattr(item.product, 'image', None) else "",
#                 })

#             success_payment = next((p for p in o.payments.all() if p.status == 'success'), None)

#             data.append({
#                 "id": o.id,
#                 "order_id": o.id,
#                 "order_no": o.invoice_number or f"ORD-{o.created_at.year}-{o.id}",
#                 "invoice_number": o.invoice_number,
#                 "created_at": o.created_at.isoformat(),

#                 "customer": o.customer.name,
#                 "customer_role": o.customer.role,
#                 "mobile": o.customer.mobile,

#                 "payment_method": o.payment_method or (success_payment.payment_gateway.title() if success_payment and success_payment.payment_gateway else ''),
#                 "payment_id": getattr(o, 'paytm_txn_id', '') or (success_payment.gateway_transaction_id if success_payment else ''),
#                 "price_category": getattr(o, 'price_category', ''),

#                 "subtotal": float(o.product_amount) if o.product_amount else 0,
#                 "product_amount": float(o.product_amount) if o.product_amount else 0,
                
#                 "gst_amount": float(o.gst_amount) if o.gst_amount else 0,
#                 "cgst": str(o.cgst_amount) if o.cgst_amount else '0',
#                 "sgst": str(o.sgst_amount) if o.sgst_amount else '0',
#                 "igst": str(o.igst_amount) if o.igst_amount else '0',
#                 "tax_total": str(o.gst_amount) if o.gst_amount else '0',
                
#                 "shipping_charges": float(o.shipping_charges) if o.shipping_charges else 0,
#                 "total_amount": float(o.total_amount) if o.total_amount else 0,
                
#                 "tracking_number": o.tracking_number or '',
#                 "address": {
#                     'full_name': o.address.full_name if getattr(o, 'address', None) else '',
#                     'phone': o.address.phone if getattr(o, 'address', None) else '',
#                     'address': o.address.address if getattr(o, 'address', None) else '',
#                     'city': o.address.city if getattr(o, 'address', None) else '',
#                     'state': o.address.state if getattr(o, 'address', None) else '',
#                     'pincode': o.address.pincode if getattr(o, 'address', None) else '',
#                 },
#                 "estimated_delivery": str(o.estimated_delivery) if o.estimated_delivery else '',

#                 "status": o.status,
#                 "items": items
#             })

#         response = JsonResponse({
#             "status": "success",
#             "data": data
#         }, safe=False)
        
#     elif request.method == 'POST':
#         try:
#             # Try parsing as JSON, fallback to standard form data
#             try:
#                 body = json.loads(request.body)
#             except json.JSONDecodeError:
#                 body = request.POST.dict()
                
#             # Accept 'customer_id' or 'customer' key
#             customer_id = body.get('customer_id') or body.get('customer')
            
#             if not customer_id:
#                 # Provide a more detailed error to see what we actually received
#                 received_keys = list(body.keys())
#                 response = JsonResponse({
#                     'message': 'Customer ID is required',
#                     'received_keys': received_keys
#                 }, status=400)
#             else:
#                 try:
#                     customer = User.objects.get(id=customer_id)
#                     # Create the order
#                     address_id = body.get('address_id')
#                     address = None

#                     if address_id:
#                         try:
#                             address = Address.objects.get(id=address_id)
#                         except Address.DoesNotExist:
#                             return JsonResponse({
#                                 'message': 'Address not found'
#                             }, status=404)
#                     order = Order.objects.create(
#                         customer=customer,
#                         address=address,
#                         invoice_number=body.get('invoice_number'),
#                         billing_address=body.get('billing_address'),
#                         mode_of_communication=body.get('mode_of_communication'),
#                         logistics=body.get('logistics'),
#                         remarks=body.get('remarks'),
#                         payment_method=body.get('payment_method'),
#                         shipping_charges=body.get('shipping_charges', 0.00),
#                         total_amount=body.get('total_amount', body.get('total_value', 0.00)),
#                         status='confirmed'
#                     )
                    
#                     # Add products (items)
#                     products = body.get('items', body.get('products', []))
#                     if isinstance(products, str):
#                         try:
#                             products = json.loads(products)
#                         except json.JSONDecodeError:
#                             products = []
                            
#                     for p in products:
#                         product_id = p.get('product') or p.get('product_id')
#                         quantity = p.get('quantity', 1)
#                         price = p.get('price', 0.00)
                        
#                         if product_id:
#                             try:
#                                 product_obj = Product.objects.get(id=product_id)
#                                 variation = None

#                                 variation_id = p.get("variation_id")

#                                 if variation_id:
#                                     try:
#                                         variation = ProductVariation.objects.get(id=variation_id)
#                                     except ProductVariation.DoesNotExist:
#                                         variation = None

#                                 OrderItem.objects.create(
#                                     order=order,
#                                     product=product_obj,
#                                     variation=variation,
#                                     quantity=quantity,
#                                     price=price
#                                 )
#                             except Product.DoesNotExist:
#                                 continue # Skip invalid products
                                
#                     response = JsonResponse({
#                         'message': 'Order created successfully',
#                         'order_id': order.id
#                     }, status=201)
#                 except User.DoesNotExist:
#                     response = JsonResponse({'message': 'Customer not found'}, status=404)
                    
#         except json.JSONDecodeError:
#             response = JsonResponse({'message': 'Invalid JSON body'}, status=400)
#         except Exception as e:
#             import traceback
#             response = JsonResponse({'message': str(e), 'detail': traceback.format_exc()}, status=500)

#     elif request.method == 'OPTIONS':
#         response = JsonResponse({'message': 'OK'})
#     else:
#         response = JsonResponse({'message': 'Method not allowed'}, status=405)

#     return response
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def admin_all_orders(request):

    # =========================================================
    # GET - LIST ALL ORDERS
    # =========================================================

    if request.method == 'GET':

        orders = Order.objects.prefetch_related(
            "items__product",
            "items__variation",
            "payments"
        ).select_related(
            "customer",
            "address"
        )

        # =====================================================
        # FILTERS
        # =====================================================

        status_filter = request.GET.get('status')
        user_filter = request.GET.get('user_id')

        # =====================================================
        # VALIDATE USER ID
        # =====================================================

        if user_filter and not str(user_filter).isdigit():

            return JsonResponse({
                "success": False,
                "message": "Invalid user_id format. Must be an integer."
            }, status=400)

        # =====================================================
        # FILTER BY ORDER STATUS
        # =====================================================

        if status_filter:

            orders = orders.filter(
                status=status_filter
            )

        # =====================================================
        # FILTER BY CUSTOMER
        # =====================================================

        if user_filter:

            orders = orders.filter(
                customer_id=user_filter
            )

        # =====================================================
        # ORDER BY LATEST
        # =====================================================

        orders = orders.order_by('-created_at')

        data = []

        # =====================================================
        # LOOP ORDERS
        # =====================================================

        for o in orders:

            items = []

            # =================================================
            # ORDER ITEMS
            # =================================================

            for item in o.items.all():

                product = item.product
                variation = item.variation

                items.append({

                    "id": item.id,

                    "product_id": (
                        product.id
                        if product
                        else None
                    ),

                    "product": (
                        product.name
                        if product
                        else "Deleted"
                    ),

                    "product_name": (
                        product.name
                        if product
                        else "Deleted"
                    ),

                    "variation_id": (
                        variation.id
                        if variation
                        else None
                    ),

                    "variation_name": (
                        variation.variation_name
                        if variation
                        else ""
                    ),

                    "category": (
                        product.category.name
                        if product
                        and getattr(product, 'category', None)
                        else ""
                    ),

                    "brand": (
                        product.brand.name
                        if product
                        and getattr(product, 'brand', None)
                        else ""
                    ),

                    "price": float(item.price),

                    "quantity": item.quantity,

                    "total": float(
                        item.price * item.quantity
                    ),

                    "product_image": (
                        get_image_url(
                            request,
                            product.image
                        )
                        if product
                        and getattr(product, 'image', None)
                        else ""
                    ),
                })

            # =================================================
            # PAYMENTS
            # =================================================

            payments = list(
                o.payments.all()
            )

            # =================================================
            # LATEST PAYMENT
            # =================================================

            latest_payment = (
                payments[-1]
                if payments
                else None
            )

            # =================================================
            # SUCCESS PAYMENT
            # =================================================

            success_payment = next(
                (
                    p for p in payments
                    if p.status == 'success'
                ),
                None
            )

            # =================================================
            # ADDRESS
            # =================================================

            address = o.address

            # =================================================
            # PAYMENT STATUS
            # =================================================

            payment_status = (
                latest_payment.status
                if latest_payment
                else "pending"
            )

            # =================================================
            # PAYMENT GATEWAY
            # =================================================

            payment_gateway = (
                latest_payment.payment_gateway
                if latest_payment
                else ""
            )

            # =================================================
            # PAYMENT TRANSACTION ID
            # =================================================

            payment_transaction_id = ""

            if latest_payment:

                payment_transaction_id = (
                    latest_payment.gateway_transaction_id
                    or latest_payment.paytm_txn_id
                    or latest_payment.razorpay_payment_id
                    or ""
                )

            # =================================================
            # ORDER RESPONSE
            # =================================================

            data.append({

                # -----------------------------------------
                # ORDER
                # -----------------------------------------

                "id": o.id,

                "order_id": o.id,

                "order_no": (
                    o.invoice_number
                    or f"ORD-{o.created_at.year}-{o.id}"
                ),


                "invoice_number": o.invoice_number,

                "mode_of_communication":o.mode_of_communication,

                "logistics": o.logistics,

                "created_at": (
                    o.created_at.isoformat()
                ),


                # -----------------------------------------
                # CUSTOMER
                # -----------------------------------------

                "customer": (
                    o.customer.name
                    if o.customer
                    else ""
                ),

                "customer_role": (
                    o.customer.role
                    if o.customer
                    else ""
                ),

                "mobile": (
                    o.customer.mobile
                    if o.customer
                    else ""
                ),

                # -----------------------------------------
                # PAYMENT
                # -----------------------------------------

                "payment_method": (
                    o.payment_method
                    or (
                        latest_payment.payment_gateway.title()
                        if latest_payment
                        and latest_payment.payment_gateway
                        else ""
                    )
                ),

                "payment_gateway": payment_gateway,

                "payment_id": (
                    payment_transaction_id
                ),

                # ⭐ IMPORTANT
                # PAYMENT STATUS

                "payment_status": payment_status,

                # -----------------------------------------
                # PRICE
                # -----------------------------------------

                "price_category": getattr(
                    o,
                    'price_category',
                    ''
                ),

                "subtotal": (
                    float(o.product_amount)
                    if o.product_amount
                    else 0
                ),

                "product_amount": (
                    float(o.product_amount)
                    if o.product_amount
                    else 0
                ),

                # -----------------------------------------
                # GST
                # -----------------------------------------

                "gst_amount": (
                    float(o.gst_amount)
                    if o.gst_amount
                    else 0
                ),

                "cgst": (
                    str(o.cgst_amount)
                    if o.cgst_amount
                    else '0'
                ),

                "sgst": (
                    str(o.sgst_amount)
                    if o.sgst_amount
                    else '0'
                ),

                "igst": (
                    str(o.igst_amount)
                    if o.igst_amount
                    else '0'
                ),

                "tax_total": (
                    str(o.gst_amount)
                    if o.gst_amount
                    else '0'
                ),

                # -----------------------------------------
                # TOTAL
                # -----------------------------------------

                "shipping_charges": (
                    float(o.shipping_charges)
                    if o.shipping_charges
                    else 0
                ),

                "total_amount": (
                    float(o.total_amount)
                    if o.total_amount
                    else 0
                ),
                
                "credit_used": (
                    float(o.credit_used)
                    if getattr(o, "credit_used", None)
                    else 0
                ),
                
                "amount_to_pay": (
                    float(o.amount_to_pay)
                    if getattr(o, "amount_to_pay", None)
                    else 0
                ),

                # -----------------------------------------
                # TRACKING
                # -----------------------------------------

                "tracking_number": (
                    o.tracking_number
                    or ''
                ),

                "estimated_delivery": (
                    str(o.estimated_delivery)
                    if o.estimated_delivery
                    else ''
                ),

                # -----------------------------------------
                # ADDRESS
                # -----------------------------------------

                "address": {

                    "id": (
                        address.id
                        if address
                        else None
                    ),

                    "full_name": (
                        address.full_name
                        if address
                        else ''
                    ),

                    "phone": (
                        address.phone
                        if address
                        else ''
                    ),

                    "address": (
                        address.address
                        if address
                        else ''
                    ),

                    "city": (
                        address.city
                        if address
                        else ''
                    ),

                    "state": (
                        address.state
                        if address
                        else ''
                    ),

                    "pincode": (
                        address.pincode
                        if address
                        else ''
                    ),

                    "address_type": (
                        address.address_type
                        if address
                        else ''
                    ),

                    "latitude": (
                        str(address.latitude)
                        if address
                        and address.latitude is not None
                        else None
                    ),

                    "longitude": (
                        str(address.longitude)
                        if address
                        and address.longitude is not None
                        else None
                    ),

                    "is_default": (
                        address.is_default
                        if address
                        else False
                    ),
                },

                # -----------------------------------------
                # ORDER STATUS
                # -----------------------------------------

                "status": o.status,

                # -----------------------------------------
                # ITEMS
                # -----------------------------------------

                "items": items
            })

        # =====================================================
        # FINAL RESPONSE
        # =====================================================

        return JsonResponse({

            "status": "success",

            "data": data

        }, status=200)



    elif request.method == 'POST':
            try:
                body = json.loads(request.body)
            except Exception as e:
                body = request.POST.dict()

            # =========================================================
            # BULK IMPORT LOGIC
            # =========================================================
            is_bulk = False
            items = []
            
            if isinstance(body, list):
                is_bulk = True
                items = body
            elif isinstance(body, dict) and isinstance(body.get('data'), list):
                first_item = body.get('data')[0] if body.get('data') else None
                if first_item and isinstance(first_item, dict) and 'attributes' in first_item:
                    is_bulk = True
                    items = body.get('data')

            if is_bulk:
                from django.utils.dateparse import parse_datetime
                success_count = 0
                errors = []
                for idx, item in enumerate(items):
                    attrs = item.get("attributes", item)
                    phone_num = str(attrs.get("phoneNum", "")).strip().replace(" ", "")
                    email = str(attrs.get("email", "")).strip()
                    customer_name = attrs.get("customername", "Unknown Customer").strip()

                    if not phone_num:
                        phone_num = f"NO-PHONE-{item.get('id', idx)}"

                    user = None
                    if phone_num:
                        user = User.objects.filter(mobile=phone_num).first()
                    if not user and email:
                        user = User.objects.filter(email=email).first()

                    if not user:
                        try:
                            user = User.objects.create(
                                name=customer_name,
                                mobile=phone_num,
                                email=email if email else None,
                                role='customer',
                                password='import_default_password'
                            )
                        except Exception as e:
                            errors.append(f"User creation failed for {customer_name} ({phone_num}): {str(e)}")
                            continue

                    old_id = item.get("id")
                    invoicenum = attrs.get("invoicenum") or f"OLD-{old_id}"
                    
                    total = float(attrs.get("total", 0) or 0)
                    status = 'shipped' if attrs.get("dispatched") else 'pending'
                    created_at_str = attrs.get("createdAt")
                    parsed_date = parse_datetime(created_at_str) if created_at_str else None

                    existing_order = Order.objects.filter(invoice_number=invoicenum).first()
                    if existing_order:
                        # Update the date instead of skipping
                        if parsed_date:
                            Order.objects.filter(id=existing_order.id).update(created_at=parsed_date)
                        continue

                    try:
                        order = Order.objects.create(
                            id=old_id, # Keep exact ID
                            customer=user,
                            total_amount=total,
                            invoice_number=invoicenum,
                            mode_of_communication=attrs.get("communication", ""),
                            payment_method=attrs.get("payment", ""),
                            status=status
                        )
                        if parsed_date:
                            Order.objects.filter(id=order.id).update(created_at=parsed_date)
                        success_count += 1
                    except Exception as e:
                        errors.append(f"Order creation failed for {invoicenum}: {str(e)}")
                
                return JsonResponse({
                    "success": True, 
                    "message": f"Successfully imported {success_count} orders",
                    "errors": errors
                })

            # =========================================================
            # SINGLE ORDER LOGIC
            # =========================================================

            # -------------------------------------------------
            # CUSTOMER ID
            # -------------------------------------------------

            customer_id = (
                body.get('customer_id')
                or body.get('customer')
            )

            if not customer_id:

                return JsonResponse({
                    "success": False,
                    "message": "Customer ID is required"
                }, status=400)

            # -------------------------------------------------
            # GET CUSTOMER
            # -------------------------------------------------

            try:

                customer = User.objects.get(
                    id=customer_id
                )

            except User.DoesNotExist:

                return JsonResponse({
                    "success": False,
                    "message": "Customer not found"
                }, status=404)

            # -------------------------------------------------
            # AUTOMATIC DEFAULT ADDRESS
            # -------------------------------------------------

            address = Address.objects.filter(
                user=customer,
                is_default=True
            ).first()

            # -------------------------------------------------
            # IF NO DEFAULT ADDRESS
            # USE FIRST ADDRESS
            # -------------------------------------------------

            if not address:

                address = Address.objects.filter(
                    user=customer
                ).first()

            # -------------------------------------------------
            # CREATE ORDER
            # -------------------------------------------------

            total_amount = float(body.get('total_amount', body.get('total_value', 0.00)))
            amount_to_pay = total_amount
            credit_used = 0.00
            
            user_role = (customer.role or '').lower()
            if user_role in ['retailer', 'reseller', 'staff', 'distributor'] or customer.credit_payment_enabled or str(body.get('payment_method', '')).lower() == 'credit':
                avail_credit = float(customer.available_credit or 0)
                if avail_credit > 0:
                    if avail_credit >= total_amount:
                        credit_used = total_amount
                        amount_to_pay = 0.00
                        customer.available_credit = Decimal(str(avail_credit - total_amount))
                    else:
                        credit_used = avail_credit
                        amount_to_pay = total_amount - credit_used
                        customer.available_credit = Decimal("0.00")
                    customer.save()

            order = Order.objects.create(

                customer=customer,

                # Automatically selected address
                address=address,

                invoice_number=body.get(
                    'invoice_number'
                ),

                billing_address=body.get(
                    'billing_address'
                ),

                mode_of_communication=body.get(
                    'mode_of_communication'
                ),

                logistics=body.get(
                    'logistics'
                ),

                remarks=body.get(
                    'remarks'
                ),

                payment_method=body.get(
                    'payment_method'
                ),

                price_category=body.get(
                    'price_category',
                    customer.price_category
                    if hasattr(customer, 'price_category')
                    else 'customer_price'
                ),

                shipping_charges=body.get(
                    'shipping_charges',
                    0.00
                ),

                product_amount=body.get(
                    'product_amount',
                    0.00
                ),

                gst_amount=body.get(
                    'gst_amount',
                    0.00
                ),

                cgst_amount=body.get(
                    'cgst',
                    body.get(
                        'cgst_amount',
                        0.00
                    )
                ),

                sgst_amount=body.get(
                    'sgst',
                    body.get(
                        'sgst_amount',
                        0.00
                    )
                ),

                igst_amount=body.get(
                    'igst',
                    body.get(
                        'igst_amount',
                        0.00
                    )
                ),

                total_amount=total_amount,
                amount_to_pay=amount_to_pay,
                credit_used=credit_used,

                status='confirmed'
            )

            # -------------------------------------------------
            # PRODUCTS / ITEMS
            # -------------------------------------------------

            products = body.get(
                'items',
                body.get(
                    'products',
                    []
                )
            )

            # If frontend sends items as JSON string
            if isinstance(products, str):

                try:

                    products = json.loads(
                        products
                    )

                except json.JSONDecodeError:

                    products = []

            # -------------------------------------------------
            # CREATE ORDER ITEMS
            # -------------------------------------------------

            for p in products:

                product_id = (
                    p.get('product')
                    or p.get('product_id')
                )

                quantity = p.get(
                    'quantity',
                    1
                )

                price = p.get(
                    'price',
                    0.00
                )

                if not product_id:
                    continue

                # ---------------------------------------------
                # PRODUCT
                # ---------------------------------------------

                try:

                    product_obj = Product.objects.get(
                        id=product_id
                    )

                except Product.DoesNotExist:

                    continue

                # ---------------------------------------------
                # VARIATION
                # ---------------------------------------------

                variation = None

                variation_id = p.get(
                    'variation_id'
                )

                if variation_id:

                    try:

                        variation = ProductVariation.objects.get(
                            id=variation_id
                        )

                    except ProductVariation.DoesNotExist:

                        variation = None

                # ---------------------------------------------
                # CREATE ORDER ITEM
                # ---------------------------------------------

                OrderItem.objects.create(

                    order=order,

                    product=product_obj,

                    variation=variation,

                    quantity=quantity,

                    price=price
                )

            # -------------------------------------------------
            # SUCCESS RESPONSE
            # -------------------------------------------------

            return JsonResponse({

                "success": True,

                "message": "Order created successfully",

                "order_id": order.id,

                "invoice_number": (
                    order.invoice_number
                ),

                "customer_id": (
                    customer.id
                ),

                "address_id": (
                    address.id
                    if address
                    else None
                ),

                "address": {

                    "full_name": (
                        address.full_name
                        if address
                        else ''
                    ),

                    "phone": (
                        address.phone
                        if address
                        else ''
                    ),

                    "address": (
                        address.address
                        if address
                        else ''
                    ),

                    "city": (
                        address.city
                        if address
                        else ''
                    ),

                    "state": (
                        address.state
                        if address
                        else ''
                    ),

                    "pincode": (
                        address.pincode
                        if address
                        else ''
                    )
                }

            }, status=201)

    else:

        return JsonResponse({

            "success": False,

            "message": "Method not allowed"

        }, status=405)


@csrf_exempt
def create_paytm_order(request):

    # =====================================================
    # POST ONLY
    # =====================================================

    if request.method != "POST":

        return JsonResponse({

            "success": False,

            "message": "POST method required"

        }, status=405)

    try:

        # =================================================
        # READ REQUEST
        # =================================================

        try:

            data = json.loads(
                request.body
            )

        except json.JSONDecodeError:

            return JsonResponse({

                "success": False,

                "message": "Invalid JSON"

            }, status=400)

        print("\n========================================")
        print("PAYTM CREATE ORDER REQUEST")
        print("DATA:", data)
        print("========================================")

        # =================================================
        # DJANGO ORDER ID
        # =================================================

        ecommerce_order_id = data.get(
            "order_id"
        )

        if not ecommerce_order_id:

            return JsonResponse({

                "success": False,

                "message": "order_id is required"

            }, status=400)

        # =================================================
        # USER ID
        # =================================================

        user_id = data.get(
            "user_id"
        )

        if not user_id:

            return JsonResponse({

                "success": False,

                "message": "user_id is required"

            }, status=400)

        # =================================================
        # FIND DJANGO ORDER
        # =================================================

        try:

            ecommerce_order = Order.objects.get(
                id=int(
                    ecommerce_order_id
                )
            )

        except (
            Order.DoesNotExist,
            ValueError,
            TypeError
        ):

            return JsonResponse({

                "success": False,

                "message": "E-commerce order not found"

            }, status=404)

        # =================================================
        # FIND CUSTOMER
        # =================================================

        try:

            customer = User.objects.get(
                id=int(
                    user_id
                )
            )

        except (
            User.DoesNotExist,
            ValueError,
            TypeError
        ):

            return JsonResponse({

                "success": False,

                "message": "User not found"

            }, status=404)

        # =================================================
        # IMPORTANT
        #
        # GET FINAL AMOUNT FROM DATABASE
        #
        # DO NOT TRUST FRONTEND AMOUNT
        # =================================================

        amount = ecommerce_order.total_amount

        if amount is None:

            return JsonResponse({

                "success": False,

                "message": "Order total amount is missing"

            }, status=400)

        # =================================================
        # CONVERT DECIMAL
        # =================================================

        try:

            amount = Decimal(
                str(amount)
            )

            amount = amount.quantize(
                Decimal("0.01")
            )

        except (
            InvalidOperation,
            ValueError
        ):

            return JsonResponse({

                "success": False,

                "message": "Invalid order total amount"

            }, status=400)

        # =================================================
        # CHECK AMOUNT
        # =================================================

        if amount <= 0:

            return JsonResponse({

                "success": False,

                "message": "Order total amount must be greater than zero"

            }, status=400)

        amount_string = format(
            amount,
            ".2f"
        )

        print("\n========================================")
        print("FINAL PAYMENT AMOUNT")
        print("DJANGO ORDER ID:", ecommerce_order.id)
        print("PRODUCT AMOUNT:", ecommerce_order.product_amount)
        print("GST AMOUNT:", ecommerce_order.gst_amount)
        print("SHIPPING:", ecommerce_order.shipping_charges)
        print("FINAL TOTAL:", amount_string)
        print("PAYTM AMOUNT:", amount_string)
        print("========================================")

        # =================================================
        # PAYTM CONFIG
        # =================================================

        config = get_paytm_config()

        merchant_key = config[
            "MERCHANT_KEY"
        ]

        if not merchant_key:

            return JsonResponse({

                "success": False,

                "message": "PAYTM_MERCHANT_KEY is missing"

            }, status=500)

        # =================================================
        # GENERATE PAYTM ORDER ID
        # =================================================

        paytm_order_id = (
            "ORDER_"
            + uuid.uuid4().hex[:18]
        )

        # =================================================
        # PAYTM INITIATE URL
        # =================================================

        initiate_url = (

            f"{config['INITIATE_URL']}"

            f"?mid={config['MID']}"

            f"&orderId={paytm_order_id}"
        )

        # =================================================
        # PAYTM BODY
        # =================================================

        body = {

            "requestType": "Payment",

            "mid": config[
                "MID"
            ],

            "websiteName": config[
                "WEBSITE"
            ],

            "orderId": paytm_order_id,

            "channelId": config.get(
                "CHANNEL_ID",
                "WEB"
            ),

            # =============================================
            # EXACT FINAL ORDER TOTAL
            # =============================================

            "txnAmount": {

                "value": amount_string,

                "currency": "INR"
            },

            "userInfo": {

                "custId": str(
                    user_id
                )
            },

            "callbackUrl": config[
                "CALLBACK_URL"
            ]
        }

        # =================================================
        # CHECKSUM
        # =================================================

        body_string = json.dumps(

            body,

            separators=(
                ",",
                ":"
            ),

            ensure_ascii=False
        )

        signature = (
            PaytmChecksum.generateSignature(

                body_string,

                merchant_key
            )
        )

        # =================================================
        # FINAL PAYTM PAYLOAD
        # =================================================

        payload = {

            "body": body,

            "head": {

                "signature": signature
            }
        }

        payload_string = json.dumps(

            payload,

            separators=(
                ",",
                ":"
            ),

            ensure_ascii=False
        )

        # =================================================
        # DEBUG
        # =================================================

        print("\n========================================")
        print("PAYTM INITIATE")
        print("URL:", initiate_url)
        print("PAYTM ORDER ID:", paytm_order_id)
        print("DJANGO ORDER ID:", ecommerce_order.id)
        print("PAYMENT AMOUNT:", amount_string)
        print("========================================")

        # =================================================
        # CALL PAYTM
        # =================================================

        response = requests.post(

            initiate_url,

            data=payload_string,

            headers={

                "Content-Type":
                    "application/json"
            },

            timeout=60
        )

        print(
            "PAYTM HTTP STATUS:",
            response.status_code
        )

        print(
            "PAYTM RESPONSE:",
            response.text
        )

        # =================================================
        # PARSE RESPONSE
        # =================================================

        try:

            response_data = response.json()

        except ValueError:

            return JsonResponse({

                "success": False,

                "message":
                    "Invalid response from Paytm",

                "http_status":
                    response.status_code,

                "response":
                    response.text

            }, status=502)

        # =================================================
        # PAYTM RESULT
        # =================================================

        result_info = (

            response_data

            .get(
                "body",
                {}
            )

            .get(
                "resultInfo",
                {}
            )
        )

        result_status = (
            result_info.get(
                "resultStatus"
            )
        )

        # =================================================
        # PAYTM INITIATE SUCCESS
        # =================================================

        if result_status == "S":

            txn_token = (

                response_data

                .get(
                    "body",
                    {}
                )

                .get(
                    "txnToken"
                )
            )

            if not txn_token:

                return JsonResponse({

                    "success": False,

                    "message":
                        "Paytm returned success but txnToken is missing",

                    "details":
                        response_data

                }, status=502)

            # =============================================
            # CREATE PAYMENT
            # =============================================

            payment = Payment.objects.create(

                order=ecommerce_order,

                customer=customer,

                # EXACT ORDER TOTAL
                amount=amount,

                payment_gateway="paytm",

                gateway_order_id=paytm_order_id,

                paytm_order_id=paytm_order_id,

                paytm_txn_token=txn_token,

                status="pending",

                gateway_response=response_data
            )

            print("\n========================================")
            print("PAYMENT CREATED")
            print("PAYMENT ID:", payment.id)
            print("DJANGO ORDER ID:", ecommerce_order.id)
            print("PAYTM ORDER ID:", paytm_order_id)
            print("PAYMENT AMOUNT:", payment.amount)
            print("STATUS:", payment.status)
            print("========================================")

            # =============================================
            # RESPONSE TO FRONTEND
            # =============================================

            return JsonResponse({

                "success": True,

                "message":
                    "Paytm transaction token generated",

                "order_id":
                    ecommerce_order.id,

                "paytm_order_id":
                    paytm_order_id,

                "payment_id":
                    payment.id,

                "payment_status":
                    payment.status,

                "mid":
                    config["MID"],

                "amount":
                    amount_string,

                "txnToken":
                    txn_token

            }, status=200)

        # =================================================
        # PAYTM INITIATE FAILURE
        # =================================================

        return JsonResponse({

            "success": False,

            "message":
                "Failed to generate transaction token",

            "paytm_result_code":
                result_info.get(
                    "resultCode"
                ),

            "paytm_result_message":
                result_info.get(
                    "resultMsg"
                ),

            "details":
                response_data

        }, status=400)

    # =====================================================
    # REQUEST ERROR
    # =====================================================

    except requests.RequestException as e:

        traceback.print_exc()

        return JsonResponse({

            "success": False,

            "message":
                "Unable to connect to Paytm",

            "error":
                str(e)

        }, status=502)

    # =====================================================
    # GENERAL ERROR
    # =====================================================

    except Exception as e:

        traceback.print_exc()

        return JsonResponse({

            "success": False,

            "message":
                "Create Paytm order failed",

            "error":
                str(e)

        }, status=500)

@csrf_exempt
def my_orders(request, user_id):
    if request.method == 'GET':
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return JsonResponse({'message': 'User not found'}, status=404)

        status_filter = request.GET.get('status')
        orders = Order.objects.filter(customer=user).order_by('-created_at')
        if status_filter:
            orders = orders.filter(status=status_filter)

        data = []
        total_orders = len(orders)
        for idx, o in enumerate(orders):
            items = [{
                'product': item.product.name if item.product else 'Deleted',
                'variation_id': item.variation.id if item.variation else None,
                'variation_name': item.variation.variation_name if item.variation else None,
                'product_image': get_image_url(request, item.product.image) if item.product else None,
                'quantity': item.quantity,
                'price': str(item.price),
                'item_total': str(round(float(item.price) * item.quantity, 2))
            } for item in o.items.all()]

            data.append({
                'display_number': total_orders - idx,  # 1, 2, 3... for this specific user
                'order_id': o.id,                      # Keep real database ID for tracking API calls
                'customer_role': user.role,
                'status': o.status,
                'product_amount': str(o.product_amount),
                'cgst': str(o.cgst_amount),
                'sgst': str(o.sgst_amount),
                'igst': str(o.igst_amount),
                'tax_total': str(o.gst_amount),

                'shipping_charges': str(o.shipping_charges),
                'total_amount': str(o.total_amount),
                'address': {
                    'full_name': o.address.full_name if o.address else '',
                    'phone': o.address.phone if o.address else '',
                    'address': o.address.address if o.address else '',
                    'city': o.address.city if o.address else '',
                    'state': o.address.state if o.address else '',
                    'pincode': o.address.pincode if o.address else '',
                },
                'tracking_number': o.tracking_number or '',
                'estimated_delivery': str(o.estimated_delivery) if o.estimated_delivery else '',
                'items': items,
                'item_count': len(items),
                'placed_at': o.created_at.isoformat()
            })

        return JsonResponse({
            'user': user.name,
            'total_orders': len(data),
            'orders': data
        }, safe=False)

    if request.method == 'OPTIONS':
        resp = JsonResponse({'message': 'OK'})
        resp['Access-Control-Allow-Origin'] = '*'
        resp['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        resp['Access-Control-Allow-Headers'] = '*'
        return resp
    return JsonResponse({'message': 'Method not allowed'}, status=405)

# =====================================================
# DASHBOARD HTML VIEW
# =====================================================
def dashboard_view(request):
    today = timezone.now().date()
    first_day_of_month = today.replace(day=1)

    total_products = Product.objects.count()
    total_categories = Category.objects.count()
    total_brands = Brand.objects.count()

    todays_orders = Order.objects.filter(created_at__date=today)
    todays_order_count = todays_orders.count()
    todays_income = todays_orders.aggregate(Sum('total_amount'))['total_amount__sum'] or 0.00

    monthly_orders = Order.objects.filter(created_at__date__gte=first_day_of_month)
    monthly_order_count = monthly_orders.count()
    monthly_income = monthly_orders.aggregate(Sum('total_amount'))['total_amount__sum'] or 0.00

    status_counts = Order.objects.values('status').annotate(count=Count('id'))
    status_breakdown = {item['status']: item['count'] for item in status_counts}

    pending_orders = Order.objects.select_related('customer').prefetch_related('items__product').filter(status='pending').order_by('-created_at')
    all_orders = Order.objects.select_related('customer').prefetch_related('items__product').all().order_by('-created_at')

    products = Product.objects.all().order_by('-id')
    categories = Category.objects.all().order_by('-id')
    
    customers = User.objects.all().order_by('-id')
    notifications = NotificationLog.objects.all().order_by('-created_at')[:25]


    products = Product.objects.all().order_by('-id')
    categories = Category.objects.all().order_by('-id')
    
    customers = User.objects.all().order_by('-id')
    notifications = NotificationLog.objects.all().order_by('-created_at')[:25]

    daily_orders = defaultdict(int)
    for o in monthly_orders:
        daily_orders[o.created_at.date().strftime('%d %b')] += 1
    
    sorted_dates = sorted(daily_orders.keys())[-15:]
    chart_dates = sorted_dates
    chart_orders = [daily_orders[d] for d in sorted_dates]

    user_name = request.session.get('user_name', 'Admin')
    user_email = request.session.get('user_email', 'info.codingboss@gmail.com')

    printable_orders = []
    for o in all_orders:
        printable_orders.append({
            'id': o.id,
            'customer_id': o.customer_id,
            'customer': o.customer.name,
            'mobile': o.customer.mobile,
            'status_raw': o.status,
            'status': o.status.replace('_', ' ').title(),
            'total_amount': str(o.total_amount),
            'address': {
            'full_name': o.address.full_name if o.address else '',
            'phone': o.address.phone if o.address else '',
            'address': o.address.address if o.address else '',
            'city': o.address.city if o.address else '',
            'state': o.address.state if o.address else '',
            'pincode': o.address.pincode if o.address else '',
        },
            'tracking_number': o.tracking_number or '',
            'estimated_delivery': o.estimated_delivery.strftime('%d %b, %Y') if o.estimated_delivery else '',
            'created_at': o.created_at.strftime('%d %b, %Y %I:%M %p'),
            'items': [{
                'id': item.id,
                'product': item.product.name if item.product else 'Deleted Product',
                'quantity': item.quantity,
                'price': str(item.price),
                'total': str(item.price * item.quantity),
            } for item in o.items.all()]
        })

    context = {
        'total_products': total_products,
        'total_categories': total_categories,
        'total_brands': total_brands,
        'todays_orders': todays_order_count,
        'todays_income': todays_income,
        'monthly_orders': monthly_order_count,
        'monthly_income': monthly_income,
        'status_breakdown': status_breakdown,
        'pending_count': pending_orders.count(),
        'all_orders_count': all_orders.count(),
        'pending_orders': pending_orders,
        'all_orders': all_orders,
        'products': products,
        'categories': categories,
        'brands': Brand.objects.all(),
        'customers': customers,
        'notifications': notifications,
        'chart_dates_json': json.dumps(chart_dates),
        'chart_orders_json': json.dumps(chart_orders),
        'status_labels_json': json.dumps(list(status_breakdown.keys())),
        'status_data_json': json.dumps(list(status_breakdown.values())),
        'orders_print_json': json.dumps(printable_orders),
        'sliders': Slider.objects.all().order_by('order'),
        'user_name': user_name,
        'user_email': user_email,
    }

    return render(request, 'herbal/dashboard.html', context)


def dashboard_edit_order(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(Order.objects.select_related('customer').prefetch_related('items__product'), id=order_id)
        customer = order.customer

        customer.name = (request.POST.get('customer_name') or customer.name).strip()
        new_mobile = (request.POST.get('customer_mobile') or customer.mobile).strip()
        if new_mobile == customer.mobile or not User.objects.exclude(id=customer.id).filter(mobile=new_mobile).exists():
            customer.mobile = new_mobile
        customer.save(update_fields=['name', 'mobile'])

        status = request.POST.get('status')
        if status in dict(Order.STATUS_CHOICES):
            order.status = status

        if order.address:
            order.address.address = request.POST.get('shipping_address', '')
            order.address.city = request.POST.get('shipping_city', '')
            order.address.state = request.POST.get('shipping_state', '')
            order.address.pincode = request.POST.get('shipping_pincode', '')
            order.address.phone = request.POST.get('shipping_phone', '')
            order.address.save()
        order.tracking_number = request.POST.get('tracking_number', '')

        total = Decimal('0.00')
        for item in order.items.select_related('product'):
            product_name = (request.POST.get(f'item_name_{item.id}') or '').strip()
            if product_name and item.product:
                item.product.name = product_name
                item.product.save(update_fields=['name'])

            try:
                quantity = int(request.POST.get(f'item_quantity_{item.id}') or item.quantity)
            except (TypeError, ValueError):
                quantity = item.quantity

            try:
                price = Decimal(request.POST.get(f'item_price_{item.id}') or item.price)
            except (InvalidOperation, TypeError):
                price = item.price

            item.quantity = max(quantity, 1)
            item.price = max(price, Decimal('0.00'))
            item.save(update_fields=['quantity', 'price'])
            total += item.price * item.quantity

        order.total_amount = total
        order.save()

    return redirect('/api/dashboard/')


# ================= DASHBOARD CRUD =================

def dashboard_add_category(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        image = request.FILES.get('image')
        if name:
            Category.objects.create(name=name, image=image)
    return redirect('/api/dashboard/')

def dashboard_edit_category(request, category_id):
    if request.method == 'POST':
        category = get_object_or_404(Category, id=category_id)
        name = request.POST.get('name')
        image = request.FILES.get('image')
        if name:
            category.name = name
        if image:
            category.image = image
        category.save()
    return redirect('/api/dashboard/')

def dashboard_delete_category(request, category_id):
    if request.method == 'POST':
        category = get_object_or_404(Category, id=category_id)
        category.delete()
    return redirect('/api/dashboard/')

def dashboard_add_product(request):
    if request.method == 'POST':
        cat_id = request.POST.get('category')
        category = get_object_or_404(Category, id=cat_id) if cat_id else None
        
        brand_id = request.POST.get('brand')
        brand = get_object_or_404(Brand, id=brand_id) if brand_id else None

        name = request.POST.get('name')
        description = request.POST.get('description', '')
        customer_price = request.POST.get('customer_price', 0)
        store_price = request.POST.get('store_price', 0)
        unit = request.POST.get('unit', 'pcs')
        weight_volume = request.POST.get('weight_volume', '')
        stock = request.POST.get('stock', 0)
        image = request.FILES.get('image')

        # New fields
        product_code = request.POST.get('product_code', '')
        barcode = request.POST.get('barcode', '')
        tamil_name = request.POST.get('tamil_name', '')
        product_type = request.POST.get('product_type', '')
        
        gst_percentage = request.POST.get('gst_percentage', 0)
        mrp = request.POST.get('mrp', 0)
        reseller_price = request.POST.get('reseller_price', 0)
        retailer_price = request.POST.get('retailer_price', 0)
        distributor_price = request.POST.get('distributor_price', 0)
        sarvo_price = request.POST.get('sarvo_price', 0)
        drug_price = request.POST.get('drug_price', 0)
        
        is_new = request.POST.get('is_new') == 'on'
        
        if name and category:
            Product.objects.create(
                category=category,
                brand=brand,
                name=name,
                product_code=product_code,
                barcode=barcode,
                tamil_name=tamil_name,
                product_type=product_type,
                description=description,
                gst_percentage=gst_percentage,
                mrp=mrp,
                customer_price=customer_price,
                store_price=store_price,
                reseller_price=reseller_price,
                retailer_price=retailer_price,
                distributor_price=distributor_price,
                sarvo_price=sarvo_price,
                drug_price=drug_price,
                unit=unit,
                weight_volume=weight_volume,
                stock=stock,
                image=image,
                is_new=is_new
            )
    return redirect('/api/dashboard/')

def dashboard_edit_product(request, product_id):
    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id)
        cat_id = request.POST.get('category')
        if cat_id:
            product.category = get_object_or_404(Category, id=cat_id)
            
        brand_id = request.POST.get('brand')
        if brand_id:
            product.brand = get_object_or_404(Brand, id=brand_id)
        elif 'brand' in request.POST and not brand_id:
            product.brand = None
            
        name = request.POST.get('name')
        if name: product.name = name
        
        product.product_code = request.POST.get('product_code', product.product_code)
        product.barcode = request.POST.get('barcode', product.barcode)
        product.tamil_name = request.POST.get('tamil_name', product.tamil_name)
        product.product_type = request.POST.get('product_type', product.product_type)
        
        product.description = request.POST.get('description', product.description)
        
        product.gst_percentage = request.POST.get('gst_percentage', product.gst_percentage)
        product.mrp = request.POST.get('mrp', product.mrp)
        product.customer_price = request.POST.get('customer_price', product.customer_price)
        product.store_price = request.POST.get('store_price', product.store_price)
        product.reseller_price = request.POST.get('reseller_price', product.reseller_price)
        product.retailer_price = request.POST.get('retailer_price', product.retailer_price)
        product.distributor_price = request.POST.get('distributor_price', product.distributor_price)
        product.sarvo_price = request.POST.get('sarvo_price', product.sarvo_price)
        product.drug_price = request.POST.get('drug_price', product.drug_price)
        
        unit = request.POST.get('unit')
        if unit: product.unit = unit
        product.weight_volume = request.POST.get('weight_volume', product.weight_volume)
        
        product.stock = request.POST.get('stock', product.stock)
        
        product.is_new = request.POST.get('is_new') == 'on'
        
        image = request.FILES.get('image')
        if image:
            product.image = image
            
        product.save()
    return redirect('/api/dashboard/')

def dashboard_delete_product(request, product_id):
    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id)
        product.delete()
    return redirect('/api/dashboard/')

def dashboard_add_slider(request):
    if request.method == 'POST':
        title = request.POST.get('title', '')
        subtitle = request.POST.get('subtitle', '')
        image = request.FILES.get('image')
        if image:
            Slider.objects.create(title=title, subtitle=subtitle, image=image)
    return redirect('/api/dashboard/')

def dashboard_edit_slider(request, slider_id):
    if request.method == 'POST':
        slider = get_object_or_404(Slider, id=slider_id)
        slider.title = request.POST.get('title', slider.title)
        slider.subtitle = request.POST.get('subtitle', slider.subtitle)
        image = request.FILES.get('image')
        if image:
            slider.image = image
        slider.save()
    return redirect('/api/dashboard/')

def dashboard_delete_slider(request, slider_id):
    if request.method == 'POST':
        slider = get_object_or_404(Slider, id=slider_id)
        slider.delete()
    return redirect('/api/dashboard/')


def dashboard_add_brand(request):
    if request.method == 'POST':
        name = request.POST.get('name', '')
        image = request.FILES.get('image')
        if name:
            Brand.objects.create(name=name, image=image)
    return redirect('/api/dashboard/')

def dashboard_edit_brand(request, brand_id):
    if request.method == 'POST':
        brand = get_object_or_404(Brand, id=brand_id)
        name = request.POST.get('name')
        if name:
            brand.name = name
        image = request.FILES.get('image')
        if image:
            brand.image = image
        brand.save()
    return redirect('/api/dashboard/')

def dashboard_delete_brand(request, brand_id):
    if request.method == 'POST':
        brand = get_object_or_404(Brand, id=brand_id)
        brand.delete()
    return redirect('/api/dashboard/')

@csrf_exempt
def product_images_list_create(request):

    # GET ALL PRODUCT IMAGES
    if request.method == 'GET':

        product_id = request.GET.get('product_id')

        images = ProductImage.objects.all()

        if product_id:
            images = images.filter(product_id=product_id)

        data = []

        for img in images:
            data.append({
                "id": img.id,
                "product_id": img.product.id if img.product else None,
                "product_name": img.product.name if img.product else None,
                "image": get_image_url(request, img.image),
                "is_active": img.is_active,
                "created_at": img.created_at
            })

        return JsonResponse({
            "success": True,
            "count": len(data),
            "data": data
        })


    # CREATE PRODUCT IMAGE
    elif request.method == 'POST':

        product_id = request.POST.get("product_id")
        image = request.FILES.get("image")
        is_active = request.POST.get("is_active", "false")

        if not product_id:
            return JsonResponse({
                "error": "product_id is required"
            }, status=400)

        try:
            product = Product.objects.get(id=product_id)

        except Product.DoesNotExist:
            return JsonResponse({
                "error": "Product not found"
            }, status=404)

        obj = ProductImage.objects.create(
            product=product,
            image=image,
            is_active=str(is_active).lower() == "true"
        )

        return JsonResponse({
            "success": True,
            "message": "Product image created",
            "data": {
                "id": obj.id,
                "product_id": obj.product.id,
                "product_name": obj.product.name,
                "image": get_image_url(request, obj.image),
                "is_active": obj.is_active,
                "created_at": obj.created_at
            }
        }, status=201)


    return JsonResponse({
        "error": "Method not allowed"
    }, status=405)


@csrf_exempt
def get_product_images(request, product_id):

    if request.method == "GET":

        images = ProductImage.objects.filter(
            product_id=product_id
        )

        if not images.exists():
            return JsonResponse({
                "success": False,
                "message": "No images found"
            }, status=404)

        data = []

        for img in images:
            data.append({
                "id": img.id,
                "product_id": img.product.id,
                "product_name": img.product.name,
                "image": get_image_url(
                    request,
                    img.image
                ),
                "is_active": img.is_active,
                "created_at": img.created_at
            })

        return JsonResponse({
            "success": True,
            "count": len(data),
            "data": data
        })

    return JsonResponse({
        "error": "Method not allowed"
    }, status=405)


@csrf_exempt
def product_images(request, product_id=None, image_id=None):

    # GET
    if request.method == "GET":

        images = ProductImage.objects.filter(
            product_id=product_id
        )

        data = []

        for img in images:
            data.append({
                "id": img.id,
                "product_id": img.product.id,
                "product_name": img.product.name,
                "image": get_image_url(request, img.image),
                "is_active": img.is_active
            })

        return JsonResponse({
            "success": True,
            "data": data
        })


    # EDIT
   
    elif request.method == "PUT":

        try:
            obj = ProductImage.objects.get(
                id=image_id
            )

        except ProductImage.DoesNotExist:
            return JsonResponse({
                "error": "Image not found"
            }, status=404)

        # update active status
        is_active = request.POST.get("is_active")

        if is_active is not None:
            obj.is_active = (
                str(is_active).lower() == "true"
            )

        # update image
        image = request.FILES.get("image")

        if image:
            if obj.image:
                obj.image.delete(save=False)

            obj.image = image

        obj.save()

        return JsonResponse({
            "success": True,
            "message": "Updated",
            "data": {
                "id": obj.id,
                "image": get_image_url(
                    request,
                    obj.image
                ),
                "is_active": obj.is_active
            }
        })



    # DELETE
    elif request.method == "DELETE":

        try:
            obj = ProductImage.objects.get(
                id=image_id
            )

            obj.delete()

            return JsonResponse({
                "success": True,
                "message": "Deleted successfully"
            })

        except ProductImage.DoesNotExist:

            return JsonResponse({
                "error": "Image not found"
            }, status=404)

    return JsonResponse({
        "error": "Method not allowed"
    })


# =============================================================
# TAMIL / ENGLISH TRANSLATION
# =============================================================

def google_translate(text, source='auto', target='ta'):
    """
    Translate text using Google Translate's free REST endpoint,
    with a fallback to MyMemory API if Google blocks the request (e.g. AWS IPs).
    """
    # 1. Try Google Translate First
    url = 'https://translate.googleapis.com/translate_a/single'
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/125.0.0.0 Safari/537.36'
        )
    }
    params = {
        'client': 'gtx',
        'sl': source,
        'tl': target,
        'dt': 't',
        'q': text,
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        translated_text = ''
        if isinstance(result, list) and len(result) > 0 and isinstance(result[0], list):
            for sentence in result[0]:
                if isinstance(sentence, list) and len(sentence) > 0 and sentence[0]:
                    translated_text += str(sentence[0])
                    
        detected_source = source
        if isinstance(result, list) and len(result) > 2 and result[2]:
            detected_source = result[2]
            
        if translated_text:
            return {
                'translated_text': translated_text,
                'source_language': detected_source,
                'target_language': target,
            }
    except Exception:
        pass  # If Google fails (e.g. IP blocked), fall back to MyMemory

    # 2. Fallback to MyMemory API
    if source == 'auto':
        source = 'en'  # MyMemory needs a specific source language, default to English

    mymemory_url = 'https://api.mymemory.translated.net/get'
    mymemory_params = {
        'q': text,
        'langpair': f'{source}|{target}'
    }
    
    response = requests.get(mymemory_url, params=mymemory_params, timeout=15)
    response.raise_for_status()
    result = response.json()
    
    if result.get('responseStatus') == 200:
        translated_text = result.get('responseData', {}).get('translatedText', '')
        return {
            'translated_text': translated_text,
            'source_language': source,
            'target_language': target,
        }
    else:
        raise Exception(f"MyMemory translation failed: {result.get('responseDetails')}")


# =============================================================
# 1.  GENERAL TEXT TRANSLATION
# =============================================================

@csrf_exempt
def translate_text(request):
    """
    POST /translation/translate/

    Translate any text between Tamil and English.

    Body (JSON):
        text   : (required) the text to translate
        source : (optional) source lang code — default 'auto'
        target : (optional) target lang code — default 'ta'

    Supported language codes: 'en', 'ta', 'auto'
    """
    try:
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)

        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'error': 'Invalid JSON body'}, status=400)

        text = body.get('text', '').strip()
        if not text:
            return JsonResponse({'error': 'text field is required'}, status=400)

        source = body.get('source', 'auto').strip().lower()
        target = body.get('target', 'ta').strip().lower()

        # Validate language codes
        if source not in {'en', 'ta', 'auto'}:
            return JsonResponse({
                'error': f"Invalid source language '{source}'. Allowed: en, ta, auto"
            }, status=400)

        if target not in {'en', 'ta'}:
            return JsonResponse({
                'error': f"Invalid target language '{target}'. Allowed: en, ta"
            }, status=400)

        try:
            result = google_translate(text, source=source, target=target)
            return JsonResponse({
                'success': True,
                'translated_text': result['translated_text'],
                'source_language': result['source_language'],
                'target_language': result['target_language'],
            })

        except requests.exceptions.Timeout:
            return JsonResponse({
                'error': 'Translation service timed out. Please try again.'
            }, status=504)

        except requests.exceptions.HTTPError as e:
            return JsonResponse({
                'error': f'Translation service HTTP error: {str(e)}'
            }, status=502)

        except requests.exceptions.RequestException as e:
            return JsonResponse({
                'error': f'Translation service unavailable: {str(e)}'
            }, status=502)

        except Exception as e:
            return JsonResponse({
                'error': f'Translation failed: {str(e)}',
                'detail': traceback.format_exc()
            }, status=500)

    except Exception as e:
        return JsonResponse({
            'error': f'Unexpected server error: {str(e)}',
            'detail': traceback.format_exc()
        }, status=500)

# =============================================================
# 2.  SINGLE PRODUCT AUTO-TRANSLATE
# =============================================================

@csrf_exempt
def product_auto_translate(request, product_id):
    """
    POST /translation/product/<product_id>/translate/

    Translate a product's English name → Tamil and save it as tamil_name.
    If tamil_name already exists, it will be overwritten.
    """
    try:
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return JsonResponse({'error': 'Product not found'}, status=404)

        english_name = (product.name or '').strip()
        if not english_name:
            return JsonResponse({
                'error': 'Product has no English name to translate'
            }, status=400)

        try:
            result = google_translate(english_name, source='en', target='ta')

            product.tamil_name = result['translated_text']
            product.save(update_fields=['tamil_name'])

            return JsonResponse({
                'success': True,
                'product_id': product.id,
                'english_name': english_name,
                'tamil_name': result['translated_text'],
                'message': 'Tamil name updated successfully',
            })

        except requests.exceptions.Timeout:
            return JsonResponse({
                'error': 'Translation service timed out. Please try again.'
            }, status=504)

        except requests.exceptions.HTTPError as e:
            return JsonResponse({
                'error': f'Translation service HTTP error: {str(e)}'
            }, status=502)

        except requests.exceptions.RequestException as e:
            return JsonResponse({
                'error': f'Translation service unavailable: {str(e)}'
            }, status=502)

        except Exception as e:
            return JsonResponse({
                'error': f'Translation failed: {str(e)}',
                'detail': traceback.format_exc()
            }, status=500)

    except Exception as e:
        return JsonResponse({
            'error': f'Unexpected server error: {str(e)}',
            'detail': traceback.format_exc()
        }, status=500)


# =============================================================
# 3.  BULK PRODUCT AUTO-TRANSLATE
# =============================================================

@csrf_exempt
def bulk_product_auto_translate(request):
    """
    POST /translation/products/bulk-translate/

    Translate ALL products whose tamil_name is NULL or empty.
    Each product's English name is translated to Tamil and saved.

    Optional body (JSON):
        force : (bool) if true, re-translate even products that already have a tamil_name
    """
    try:
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)

        # Parse optional body
        force = False
        if request.body:
            try:
                body = json.loads(request.body)
                force = body.get('force', False)
            except (json.JSONDecodeError, ValueError):
                pass  # Ignore malformed body — just use defaults

        # Pick products to translate using Q() for safe MySQL-compatible querying
        try:
            if force:
                products = list(Product.objects.exclude(
                    Q(name__isnull=True) | Q(name__exact='')
                ))
            else:
                products = list(Product.objects.filter(
                    Q(tamil_name__isnull=True) | Q(tamil_name__exact='')
                ).exclude(
                    Q(name__isnull=True) | Q(name__exact='')
                ))
        except Exception as e:
            return JsonResponse({
                'error': f'Database query failed: {str(e)}',
                'detail': traceback.format_exc()
            }, status=500)

        results = []
        translated_count = 0
        skipped_count = 0
        failed_count = 0

        for product in products:
            try:
                result = google_translate(product.name, source='en', target='ta')

                product.tamil_name = result['translated_text']
                product.save(update_fields=['tamil_name'])

                translated_count += 1
                results.append({
                    'product_id': product.id,
                    'english_name': product.name,
                    'tamil_name': result['translated_text'],
                    'status': 'translated',
                })

            except Exception as e:
                failed_count += 1
                results.append({
                    'product_id': product.id,
                    'english_name': product.name,
                    'tamil_name': product.tamil_name or '',
                    'status': 'failed',
                    'error': str(e),
                })

        return JsonResponse({
            'success': True,
            'translated_count': translated_count,
            'skipped_count': skipped_count,
            'failed_count': failed_count,
            'total_processed': translated_count + failed_count,
            'results': results,
        })

    except Exception as e:
        return JsonResponse({
            'error': f'Unexpected server error: {str(e)}',
            'detail': traceback.format_exc()
        }, status=500)



# ================================
#  CRM WISHLIST
# ================================

@csrf_exempt
def crm_wishlist(request, user_id):

    if request.method != "GET":
        return JsonResponse(
            {"message": "GET method required"},
            status=405
        )

    try:
        user = User.objects.get(id=user_id)

        wishlist = Wishlist.objects.filter(
            user=user
        ).select_related("product")

        serializer = WishlistSerializer(
            wishlist,
            many=True,
            context={"request": request}
        )

        return JsonResponse({
            "success": True,
            "count": wishlist.count(),
            "wishlist": serializer.data
        })

    except User.DoesNotExist:
        return JsonResponse({
            "message": "User not found"
        }, status=404)

        
@csrf_exempt
def crm_wishlist_add(request):

    if request.method != "POST":
        return JsonResponse(
            {"message": "POST method required"},
            status=405
        )

    try:

        data = json.loads(request.body)

        user = User.objects.get(
            id=data["user_id"]
        )

        product = Product.objects.get(
            id=data["product_id"]
        )

        wishlist, created = Wishlist.objects.get_or_create(
            user=user,
            product=product
        )

        if not created:
            return JsonResponse({
                "success": False,
                "message": "Already in wishlist"
            })

        serializer = WishlistSerializer(
            wishlist,
            context={"request": request}
        )

        return JsonResponse({
            "success": True,
            "message": "Wishlist added successfully",
            "wishlist": serializer.data
        })

    except User.DoesNotExist:

        return JsonResponse({
            "message": "User not found"
        }, status=404)

    except Product.DoesNotExist:

        return JsonResponse({
            "message": "Product not found"
        }, status=404)

    except Exception as e:

        return JsonResponse({
            "message": str(e)
        }, status=400)


@csrf_exempt
def crm_wishlist_delete(request, pk):

    if request.method != "DELETE":
        return JsonResponse(
            {"message": "DELETE method required"},
            status=405
        )

    try:

        wishlist = Wishlist.objects.get(pk=pk)

        wishlist.delete()

        return JsonResponse({
            "success": True,
            "message": "Wishlist deleted successfully"
        })

    except Wishlist.DoesNotExist:

        return JsonResponse({
            "message": "Wishlist not found"
        }, status=404)


# ================================
#  create_razorpay_order
# ================================

# @csrf_exempt
# def create_razorpay_order(request):

#     if request.method == "POST":

#         try:

#             data = json.loads(request.body)

#             amount = int(data.get("amount", 1)) * 100

#             client = razorpay.Client(
#                 auth=(
#                     settings.RAZORPAY_KEY_ID,
#                     settings.RAZORPAY_KEY_SECRET
#                 )
#             )

#             razorpay_order = client.order.create({
#                 "amount": amount,
#                 "currency": "INR",
#                 "payment_capture": 1
#             })

#             return JsonResponse({
#                 "success": True,
#                 "razorpay_order_id": razorpay_order["id"],
#                 "amount": razorpay_order["amount"],
#                 "key": settings.RAZORPAY_KEY_ID
#             })

#         except Exception as e:

#             return JsonResponse({
#                 "success": False,
#                 "error": str(e)
#             }, status=400)

#     return JsonResponse({
#         "message": "Method not allowed"
#     }, status=405)


@csrf_exempt
@api_view(['POST'])
def submit_product_review(request):
    try:
        data = request.data

        user_id = data.get('user_id')
        order_item_id = data.get('order_item_id')
        rating = data.get('rating')
        review_text = data.get('review_text')

        if not user_id:
            return Response({
                "message": "User id is required"
            }, status=400)

        if not order_item_id:
            return Response({
                "message": "Order item id is required"
            }, status=400)

        if rating is None:
            return Response({
                "message": "Rating is required"
            }, status=400)

        try:
            rating = int(rating)
        except (ValueError, TypeError):
            return Response({
                "message": "Invalid rating"
            }, status=400)

        if rating < 1 or rating > 5:
            return Response({
                "message": "Rating must be between 1 and 5"
            }, status=400)

        customer = User.objects.filter(
            id=user_id
        ).first()

        if not customer:
            return Response({
                "message": "User not found"
            }, status=404)

        order_item = OrderItem.objects.filter(
            id=order_item_id
        ).select_related(
            'order',
            'product',
            'variation'
        ).first()

        if not order_item:
            return Response({
                "message": "Order item not found"
            }, status=404)

        if order_item.order.customer.id != customer.id:
            return Response({
                "message": "This order does not belong to this user"
            }, status=403)

        if order_item.order.status not in [
            'delivered',
            'received'
        ]:
            return Response({
                "message": "Review allowed only after delivery"
            }, status=400)

        product = order_item.product

        if not product:
            return Response({
                "message": "Product not found"
            }, status=404)

        existing_review = ProductReview.objects.filter(
            order_item=order_item
        ).exists()

        if existing_review:
            return Response({
                "message": "You have already reviewed this purchased product."
            }, status=400)

        review = ProductReview.objects.create(
            product=product,
            customer=customer,
            order_item=order_item,
            rating=rating,
            review_text=review_text,
            status='pending'
        )

        serializer = ProductReviewSerializer(review)

        return Response({
            "message": "Review submitted successfully. Waiting for admin approval.",
            "review": serializer.data
        }, status=201)

    except Exception as e:
        import traceback
        traceback.print_exc()

        return Response({
            "message": "Something went wrong",
            "error": str(e)
        }, status=500)
    
@csrf_exempt
@api_view(['GET'])
def product_reviews(request, product_id):
    try:
        reviews = ProductReview.objects.filter(
            product_id=product_id,
            status='approved'
        ).select_related(
            'product',
            'customer',
            'order_item',
            'order_item__variation'
        ).order_by('-created_at')

        serializer = ProductReviewSerializer(
            reviews,
            many=True
        )

        return Response({
            "count": reviews.count(),
            "reviews": serializer.data
        }, status=200)

    except Exception as e:
        import traceback
        traceback.print_exc()

        return Response({
            "message": "Something went wrong",
            "error": str(e)
        }, status=500)


@csrf_exempt
@api_view(['GET'])
def product_review_summary(request, product_id):
    try:
        reviews = ProductReview.objects.filter(
            product_id=product_id,
            status='approved'
        )

        total_reviews = reviews.count()

        if total_reviews == 0:
            return Response({
                "product_id": product_id,
                "total_reviews": 0,
                "average_rating": 0,
                "rating_summary": {
                    "5": 0,
                    "4": 0,
                    "3": 0,
                    "2": 0,
                    "1": 0
                }
            }, status=200)

        rating_counts = reviews.values('rating').annotate(
            count=Count('rating')
        )

        rating_summary = {
            "5": 0,
            "4": 0,
            "3": 0,
            "2": 0,
            "1": 0
        }

        for item in rating_counts:
            rating = str(item['rating'])
            rating_summary[rating] = item['count']

        total_rating = reviews.aggregate(
            total=Sum('rating')
        )['total']

        average_rating = Decimal(total_rating) / Decimal(total_reviews)

        return Response({
            "product_id": product_id,
            "total_reviews": total_reviews,
            "average_rating": round(float(average_rating), 2),
            "rating_summary": rating_summary
        }, status=200)

    except Exception as e:
        import traceback
        traceback.print_exc()

        return Response({
            "message": "Something went wrong",
            "error": str(e)
        }, status=500)




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
import json
import uuid
import traceback
import requests

from decimal import Decimal, InvalidOperation

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import Order, User, Payment

# Make sure these are already imported in your project
# from paytmchecksum import PaytmChecksum
# from .utils import get_paytm_config
@csrf_exempt
def create_paytm_order(request):

    # =====================================================
    # POST ONLY
    # =====================================================

    if request.method != "POST":

        return JsonResponse({

            "success": False,

            "message": "POST method required"

        }, status=405)

    try:

        # =================================================
        # PARSE REQUEST
        # =================================================

        try:

            data = json.loads(
                request.body
            )

        except json.JSONDecodeError:

            return JsonResponse({

                "success": False,

                "message": "Invalid JSON"

            }, status=400)

        # =================================================
        # ORDER ID
        # =================================================

        order_id = data.get(
            "order_id"
        )

        if not order_id:

            return JsonResponse({

                "success": False,

                "message":
                    "order_id is required"

            }, status=400)

        # =================================================
        # USER ID
        # =================================================

        user_id = data.get(
            "user_id"
        )

        if not user_id:

            return JsonResponse({

                "success": False,

                "message":
                    "user_id is required"

            }, status=400)

        # =================================================
        # FIND ORDER
        # =================================================

        try:

            order = Order.objects.select_related(
                "customer"
            ).get(
                id=int(order_id)
            )

        except (
            Order.DoesNotExist,
            ValueError,
            TypeError
        ):

            return JsonResponse({

                "success": False,

                "message":
                    "Order not found"

            }, status=404)

        # =================================================
        # VERIFY CUSTOMER
        # =================================================

        try:

            user_id_int = int(
                user_id
            )

        except (
            ValueError,
            TypeError
        ):

            return JsonResponse({

                "success": False,

                "message":
                    "Invalid user_id"

            }, status=400)

        # =================================================
        # ORDER CUSTOMER VALIDATION
        # =================================================

        if order.customer_id != user_id_int:

            return JsonResponse({

                "success": False,

                "message":
                    "This order does not belong to this customer"

            }, status=403)

        # =================================================
        # CUSTOMER
        # =================================================

        customer = order.customer

        if not customer:

            return JsonResponse({

                "success": False,

                "message":
                    "Customer not found"

            }, status=404)

        # =================================================
        # ORDER STATUS VALIDATION
        # =================================================

        if order.status in [
            "cancelled",
            "cancel",
            "refunded"
        ]:

            return JsonResponse({

                "success": False,

                "message":
                    "Payment cannot be created for this order"

            }, status=400)

        # =================================================
        # GET TOTAL AMOUNT FROM DATABASE
        # =================================================
        #
        # IMPORTANT:
        #
        # DO NOT GET amount FROM FRONTEND
        #
        # DO NOT ADD GST HERE
        #
        # total_amount is already the final amount.
        #
        # Example:
        #
        # product_amount = 0.85
        # gst_amount     = 0.15
        # total_amount   = 1.00
        #
        # Paytm receives = 1.00
        #
        # =================================================

        if order.total_amount is None:

            return JsonResponse({

                "success": False,

                "message":
                    "Order total amount is missing"

            }, status=400)

        # =================================================
        # DECIMAL
        # =================================================

        try:

            raw_amount = order.total_amount
            if hasattr(order, 'amount_to_pay') and (order.credit_used > 0 or order.amount_to_pay > 0):
                raw_amount = order.amount_to_pay

            amount = Decimal(
                str(
                    raw_amount
                )
            )

            amount = amount.quantize(
                Decimal("0.01")
            )

        except (
            InvalidOperation,
            ValueError,
            TypeError
        ):

            return JsonResponse({

                "success": False,

                "message":
                    "Invalid order total amount"

            }, status=400)

        # =================================================
        # AMOUNT VALIDATION
        # =================================================

        if amount <= 0:

            return JsonResponse({

                "success": False,

                "message":
                    "Order total amount must be greater than zero"

            }, status=400)

        amount_string = format(
            amount,
            ".2f"
        )

        # =================================================
        # PAYTM CONFIG
        # =================================================

        config = get_paytm_config()

        # =================================================
        # VALIDATE PAYTM SETTINGS
        # =================================================

        if not config.get("MID"):

            return JsonResponse({

                "success": False,

                "message":
                    "PAYTM_MID is not configured"

            }, status=500)

        if not config.get(
            "MERCHANT_KEY"
        ):

            return JsonResponse({

                "success": False,

                "message":
                    "PAYTM_MERCHANT_KEY is not configured"

            }, status=500)

        if not config.get(
            "INITIATE_URL"
        ):

            return JsonResponse({

                "success": False,

                "message":
                    "PAYTM_INITIATE_URL is not configured"

            }, status=500)

        # =================================================
        # CALLBACK URL
        #
        # BACKEND ONLY
        #
        # FRONTEND CANNOT SEND THIS
        # =================================================

        callback_url = config.get(
            "CALLBACK_URL"
        )

        if not callback_url:

            return JsonResponse({

                "success": False,

                "message":
                    "PAYTM_CALLBACK_URL is not configured"

            }, status=500)

        # =================================================
        # CREATE PAYTM ORDER ID
        # =================================================

        paytm_order_id = (
            "ORDER_"
            + uuid.uuid4().hex[:18]
        )

        # =================================================
        # INITIATE URL
        # =================================================

        initiate_url = (

            f"{config['INITIATE_URL']}"

            f"?mid={config['MID']}"

            f"&orderId={paytm_order_id}"
        )

        # =================================================
        # PAYTM BODY
        # =================================================

        body = {

            "requestType":
                "Payment",

            "mid":
                config["MID"],

            "websiteName":
                config["WEBSITE"],

            "orderId":
                paytm_order_id,

            "channelId":
                config["CHANNEL_ID"],

            # =============================================
            # FINAL ORDER TOTAL
            # =============================================

            "txnAmount": {

                "value":
                    amount_string,

                "currency":
                    "INR"
            },

            # =============================================
            # CUSTOMER
            # =============================================

            "userInfo": {

                "custId":
                    str(customer.id)
            },

            # =============================================
            # CALLBACK
            #
            # SERVER SIDE ONLY
            # =============================================

            "callbackUrl":
                callback_url
        }

        # =================================================
        # CHECKSUM
        # =================================================

        body_string = json.dumps(

            body,

            separators=(
                ",",
                ":"
            ),

            ensure_ascii=False
        )

        signature = (
            PaytmChecksum.generateSignature(

                body_string,

                config["MERCHANT_KEY"]
            )
        )

        # =================================================
        # PAYTM PAYLOAD
        # =================================================

        payload = {

            "body": body,

            "head": {

                "signature":
                    signature
            }
        }

        payload_string = json.dumps(

            payload,

            separators=(
                ",",
                ":"
            ),

            ensure_ascii=False
        )

        # =================================================
        # CALL PAYTM
        # =================================================

        response = requests.post(

            initiate_url,

            data=payload_string,

            headers={

                "Content-Type":
                    "application/json"
            },

            timeout=60
        )

        # =================================================
        # PAYTM RESPONSE
        # =================================================

        try:

            response_data = response.json()

        except ValueError:

            return JsonResponse({

                "success": False,

                "message":
                    "Invalid response from Paytm"

            }, status=502)

        # =================================================
        # RESULT INFO
        # =================================================

        result_info = (

            response_data

            .get(
                "body",
                {}
            )

            .get(
                "resultInfo",
                {}
            )
        )

        result_status = (
            result_info.get(
                "resultStatus"
            )
        )

        # =================================================
        # SUCCESS
        # =================================================

        if result_status == "S":

            txn_token = (

                response_data

                .get(
                    "body",
                    {}
                )

                .get(
                    "txnToken"
                )
            )

            if not txn_token:

                return JsonResponse({

                    "success": False,

                    "message":
                        "Paytm txnToken not received"

                }, status=502)

            # =============================================
            # CREATE PAYMENT
            # =============================================

            payment = Payment.objects.create(

                order=order,

                customer=customer,

                amount=amount,

                payment_gateway="paytm",

                gateway_order_id=
                    paytm_order_id,

                paytm_order_id=
                    paytm_order_id,

                paytm_txn_token=
                    txn_token,

                status="pending",

                gateway_response=
                    response_data
            )

            # =============================================
            # FRONTEND RESPONSE
            #
            # NO CALLBACK URL
            # NO MERCHANT KEY
            # =============================================

            return JsonResponse({

                "success": True,

                "message":
                    "Paytm transaction token generated",

                "order_id":
                    order.id,

                "payment_id":
                    payment.id,

                "paytm_order_id":
                    paytm_order_id,

                "mid":
                    config["MID"],

                "amount":
                    amount_string,

                "payment_status":
                    payment.status,

                "txnToken":
                    txn_token

            }, status=200)

        # =================================================
        # PAYTM FAILED
        # =================================================

        return JsonResponse({

            "success": False,

            "message":
                "Paytm transaction initialization failed",

            "result_code":
                result_info.get(
                    "resultCode"
                ),

            "result_message":
                result_info.get(
                    "resultMsg"
                )

        }, status=400)

    # =====================================================
    # REQUEST ERROR
    # =====================================================

    except requests.RequestException:

        traceback.print_exc()

        return JsonResponse({

            "success": False,

            "message":
                "Unable to connect to Paytm"

        }, status=502)

    # =====================================================
    # GENERAL ERROR
    # =====================================================

    except Exception:

        traceback.print_exc()

        return JsonResponse({

            "success": False,

            "message":
                "Create Paytm order failed"

        }, status=500)

# @csrf_exempt
# def paytm_callback(request):

#     print("\n========================================")
#     print("PAYTM CALLBACK RECEIVED")
#     print("METHOD:", request.method)
#     print("========================================")

#     if request.method != "POST":
#         return JsonResponse({
#             "success": False,
#             "message": "POST method required"
#         }, status=405)

#     try:

#         # =====================================================
#         # READ CALLBACK DATA
#         # =====================================================

#         data = request.POST.dict()

#         if not data:
#             try:
#                 data = json.loads(request.body)
#             except Exception:
#                 data = {}

#         print("PAYTM CALLBACK DATA:")
#         print(json.dumps(data, indent=4))

#         # =====================================================
#         # CHECKSUM
#         # =====================================================

#         checksum = data.get("CHECKSUMHASH")

#         if not checksum:
#             return JsonResponse({
#                 "success": False,
#                 "message": "CHECKSUMHASH missing"
#             }, status=400)

#         verify_data = data.copy()
#         verify_data.pop("CHECKSUMHASH", None)

#         is_valid = PaytmChecksum.verifySignature(
#             verify_data,
#             settings.PAYTM_MERCHANT_KEY.strip(),
#             checksum
#         )

#         print("PAYTM CHECKSUM VALID:", is_valid)

#         if not is_valid:
#             return JsonResponse({
#                 "success": False,
#                 "message": "Invalid Paytm checksum"
#             }, status=400)

#         # =====================================================
#         # GET PAYTM VALUES
#         # =====================================================

#         paytm_order_id = data.get("ORDERID")
#         txn_id = data.get("TXNID")
#         paytm_status = data.get("STATUS")
#         response_code = data.get("RESPCODE")
#         response_message = data.get("RESPMSG")
#         payment_mode = data.get("PAYMENTMODE")
#         bank_txn_id = data.get("BANKTXNID")

#         print("\n========================================")
#         print("PAYTM TRANSACTION")
#         print("ORDER ID:", paytm_order_id)
#         print("TXN ID:", txn_id)
#         print("STATUS:", paytm_status)
#         print("RESPCODE:", response_code)
#         print("RESPMSG:", response_message)
#         print("PAYMENT MODE:", payment_mode)
#         print("BANK TXN ID:", bank_txn_id)
#         print("========================================")

#         # =====================================================
#         # ORDER ID REQUIRED
#         # =====================================================

#         if not paytm_order_id:
#             return JsonResponse({
#                 "success": False,
#                 "message": "ORDERID missing from Paytm callback"
#             }, status=400)

#         # =====================================================
#         # FIND PAYMENT
#         # =====================================================

#         try:

#             payment = Payment.objects.get(
#                 gateway_order_id=paytm_order_id
#             )

#         except Payment.DoesNotExist:

#             print(
#                 "PAYMENT NOT FOUND:",
#                 paytm_order_id
#             )

#             return JsonResponse({
#                 "success": False,
#                 "message": "Payment record not found",
#                 "paytm_order_id": paytm_order_id
#             }, status=404)

#         # =====================================================
#         # SAVE PAYTM RESPONSE
#         # =====================================================

#         payment.gateway_response = data

#         if txn_id:
#             payment.gateway_transaction_id = txn_id

#         if payment_mode:
#             payment.payment_mode = payment_mode

#         if bank_txn_id:
#             payment.paytm_bank_txn_id = bank_txn_id

#         if txn_id:
#             payment.paytm_txn_id = txn_id

#         # =====================================================
#         # AUTOMATIC PAYMENT STATUS
#         # =====================================================

#         if paytm_status == "TXN_SUCCESS":

#             payment.status = "success"

#             print("PAYMENT SUCCESS")

#         elif paytm_status == "TXN_FAILURE":

#             payment.status = "failed"

#             print("PAYMENT FAILED")

#         else:

#             payment.status = "pending"

#             print("PAYMENT PENDING")

#         # =====================================================
#         # SAVE PAYMENT
#         # =====================================================

#         payment.save()

#         print("\n========================================")
#         print("PAYMENT UPDATED")
#         print("PAYMENT ID:", payment.id)
#         print("PAYMENT STATUS:", payment.status)
#         print("========================================")

#         # =====================================================
#         # RESPONSE
#         # =====================================================

#         return JsonResponse({

#             "success": True,

#             "message": "Paytm callback processed successfully",

#             "payment_id": payment.id,

#             "order_id": payment.order.id,

#             "paytm_order_id": paytm_order_id,

#             "transaction_id": txn_id,

#             "payment_status": payment.status,

#             "paytm_status": paytm_status,

#             "response_code": response_code,

#             "response_message": response_message

#         })

#     except Exception as e:

#         traceback.print_exc()

#         return JsonResponse({

#             "success": False,

#             "message": "Callback processing failed",

#             "error": str(e)

#         }, status=500)
    
# @csrf_exempt
# def paytm_callback(request):

#     # =====================================================
#     # POST ONLY
#     # =====================================================

#     if request.method != "POST":

#         return JsonResponse({

#             "success": False,

#             "message":
#                 "POST method required"

#         }, status=405)

#     try:

#         # =================================================
#         # PAYTM DATA
#         # =================================================

#         paytm_data = request.POST.dict()

#         # =================================================
#         # JSON FALLBACK
#         # =================================================

#         if not paytm_data:

#             try:

#                 paytm_data = json.loads(
#                     request.body
#                 )

#             except json.JSONDecodeError:

#                 paytm_data = {}

#         # =================================================
#         # ORDER ID
#         # =================================================

#         paytm_order_id = (

#             paytm_data.get(
#                 "ORDERID"
#             )

#             or paytm_data.get(
#                 "orderId"
#             )

#         )

#         if not paytm_order_id:

#             return JsonResponse({

#                 "success": False,

#                 "message":
#                     "Paytm order ID missing"

#             }, status=400)

#         # =================================================
#         # TRANSACTION ID
#         # =================================================

#         txn_id = (

#             paytm_data.get(
#                 "TXNID"
#             )

#             or paytm_data.get(
#                 "txnId"
#             )

#             or ""
#         )

#         # =================================================
#         # STATUS
#         # =================================================

#         status = (

#             paytm_data.get(
#                 "STATUS"
#             )

#             or paytm_data.get(
#                 "status"
#             )

#             or ""
#         )

#         # =================================================
#         # RESPONSE CODE
#         # =================================================

#         result_code = (

#             paytm_data.get(
#                 "RESPCODE"
#             )

#             or paytm_data.get(
#                 "resultCode"
#             )

#             or ""
#         )

#         # =================================================
#         # RESPONSE MESSAGE
#         # =================================================

#         result_message = (

#             paytm_data.get(
#                 "RESPMSG"
#             )

#             or paytm_data.get(
#                 "resultMsg"
#             )

#             or ""
#         )

#         # =================================================
#         # FIND PAYMENT
#         # =================================================

#         payment = Payment.objects.filter(

#             payment_gateway="paytm"

#         ).filter(

#             paytm_order_id=paytm_order_id

#         ).order_by(
#             "-created_at"
#         ).first()

#         # =================================================
#         # FALLBACK
#         # =================================================

#         if not payment:

#             payment = Payment.objects.filter(

#                 payment_gateway="paytm",

#                 gateway_order_id=
#                     paytm_order_id

#             ).order_by(
#                 "-created_at"
#             ).first()

#         # =================================================
#         # PAYMENT NOT FOUND
#         # =================================================

#         if not payment:

#             return JsonResponse({

#                 "success": False,

#                 "message":
#                     "Payment record not found"

#             }, status=404)

#         # =================================================
#         # SAVE TRANSACTION
#         # =================================================

#         payment.paytm_txn_id = txn_id

#         payment.gateway_transaction_id = txn_id

#         payment.payment_mode = (

#             paytm_data.get(
#                 "PAYMENTMODE"
#             )

#             or paytm_data.get(
#                 "paymentMode"
#             )

#             or payment.payment_mode
#             or ""
#         )

#         payment.gateway_response = (
#             paytm_data
#         )

#         # =================================================
#         # SUCCESS
#         # =================================================

#         if status.upper() == "TXN_SUCCESS":

#             payment.status = "success"

#             payment.save()

#             # =============================================
#             # UPDATE ORDER
#             # =============================================

#             order = payment.order

#             if order:

#                 order.status = "confirmed"

#                 order.save(
#                     update_fields=[
#                         "status"
#                     ]
#                 )

#             return JsonResponse({

#                 "success": True,

#                 "message":
#                     "Payment successful",

#                 "payment_id":
#                     payment.id,

#                 "order_id":
#                     payment.order_id,

#                 "paytm_order_id":
#                     payment.paytm_order_id,

#                 "transaction_id":
#                     payment.paytm_txn_id,

#                 "amount":
#                     str(payment.amount),

#                 "payment_status":
#                     payment.status

#             }, status=200)

#         # =================================================
#         # FAILED
#         # =================================================

#         payment.status = "failed"

#         payment.save()

#         return JsonResponse({

#             "success": False,

#             "message":
#                 "Payment failed",

#             "payment_id":
#                 payment.id,

#             "order_id":
#                 payment.order_id,

#             "paytm_order_id":
#                 payment.paytm_order_id,

#             "transaction_id":
#                 payment.paytm_txn_id,

#             "amount":
#                 str(payment.amount),

#             "payment_status":
#                 payment.status,

#             "result_code":
#                 result_code,

#             "result_message":
#                 result_message

#         }, status=200)

#     except Exception:

#         traceback.print_exc()

#         return JsonResponse({

#             "success": False,

#             "message":
#                 "Paytm callback processing failed"

#         }, status=500)
import json
import traceback

from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from .models import Payment


# @csrf_exempt
# def paytm_callback(request):

#     # =====================================================
#     # POST ONLY
#     # =====================================================

#     if request.method != "POST":

#         return render(
#             request,
#             "payment/payment_result.html",
#             {
#                 "status": "failed",
#                 "message": "Invalid payment request.",
#             },
#             status=405,
#         )

#     try:

#         # =================================================
#         # PAYTM DATA
#         # =================================================

#         paytm_data = request.POST.dict()

#         # =================================================
#         # JSON FALLBACK
#         # =================================================

#         if not paytm_data:

#             try:

#                 paytm_data = json.loads(
#                     request.body
#                 )

#             except json.JSONDecodeError:

#                 paytm_data = {}

#         # =================================================
#         # ORDER ID
#         # =================================================

#         paytm_order_id = (

#             paytm_data.get(
#                 "ORDERID"
#             )

#             or paytm_data.get(
#                 "orderId"
#             )
#         )

#         if not paytm_order_id:

#             return render(
#                 request,
#                 "payment/payment_result.html",
#                 {
#                     "status": "failed",
#                     "message":
#                         "Paytm order ID is missing.",
#                 },
#                 status=400,
#             )

#         # =================================================
#         # TRANSACTION ID
#         # =================================================

#         txn_id = (

#             paytm_data.get(
#                 "TXNID"
#             )

#             or paytm_data.get(
#                 "txnId"
#             )

#             or ""
#         )

#         # =================================================
#         # STATUS
#         # =================================================

#         payment_status = (

#             paytm_data.get(
#                 "STATUS"
#             )

#             or paytm_data.get(
#                 "status"
#             )

#             or ""
#         )

#         # =================================================
#         # RESPONSE CODE
#         # =================================================

#         result_code = (

#             paytm_data.get(
#                 "RESPCODE"
#             )

#             or paytm_data.get(
#                 "resultCode"
#             )

#             or ""
#         )

#         # =================================================
#         # RESPONSE MESSAGE
#         # =================================================

#         result_message = (

#             paytm_data.get(
#                 "RESPMSG"
#             )

#             or paytm_data.get(
#                 "resultMsg"
#             )

#             or ""
#         )

#         # =================================================
#         # PAYMENT MODE
#         # =================================================

#         payment_mode = (

#             paytm_data.get(
#                 "PAYMENTMODE"
#             )

#             or paytm_data.get(
#                 "paymentMode"
#             )

#             or ""
#         )

#         # =================================================
#         # FIND PAYMENT
#         # =================================================

#         payment = (
#             Payment.objects
#             .select_related(
#                 "order",
#                 "customer",
#             )
#             .filter(
#                 payment_gateway="paytm",
#                 paytm_order_id=paytm_order_id,
#             )
#             .order_by(
#                 "-created_at"
#             )
#             .first()
#         )

#         # =================================================
#         # FALLBACK
#         # =================================================

#         if not payment:

#             payment = (
#                 Payment.objects
#                 .select_related(
#                     "order",
#                     "customer",
#                 )
#                 .filter(
#                     payment_gateway="paytm",
#                     gateway_order_id=
#                         paytm_order_id,
#                 )
#                 .order_by(
#                     "-created_at"
#                 )
#                 .first()
#             )

#         # =================================================
#         # PAYMENT NOT FOUND
#         # =================================================

#         if not payment:

#             return render(
#                 request,
#                 "payment/payment_result.html",
#                 {
#                     "status": "failed",
#                     "message":
#                         "Payment record not found.",
#                     "paytm_order_id":
#                         paytm_order_id,
#                 },
#                 status=404,
#             )

#         # =================================================
#         # SAVE TRANSACTION DETAILS
#         # =================================================

#         payment.paytm_txn_id = txn_id

#         payment.gateway_transaction_id = txn_id

#         if payment_mode:

#             payment.payment_mode = payment_mode

#         payment.gateway_response = paytm_data

#         # =================================================
#         # SUCCESS
#         # =================================================

#         if payment_status.upper() == "TXN_SUCCESS":

#             payment.status = "success"

#             payment.save()

#             # =============================================
#             # UPDATE ORDER
#             # =============================================

#             order = payment.order

#             if order:

#                 order.status = "confirmed"

#                 order.save(
#                     update_fields=[
#                         "status"
#                     ]
#                 )

#             # =============================================
#             # SUCCESS PAGE
#             # =============================================

#             return render(
#                 request,
#                 "payment/payment_result.html",
#                 {
#                     "status": "success",

#                     "message":
#                         "Payment completed successfully.",

#                     "payment": payment,

#                     "order": order,

#                     "paytm_order_id":
#                         paytm_order_id,

#                     "transaction_id":
#                         txn_id,

#                     "payment_mode":
#                         payment_mode,

#                     "amount":
#                         payment.amount,

#                     "result_code":
#                         result_code,

#                     "result_message":
#                         result_message,
#                 },
#                 status=200,
#             )

#         # =================================================
#         # FAILED
#         # =================================================

#         payment.status = "failed"

#         payment.save()

#         # =================================================
#         # FAILED PAGE
#         # =================================================

#         return render(
#             request,
#             "payment/payment_result.html",
#             {
#                 "status": "failed",

#                 "message":
#                     "Payment failed.",

#                 "payment": payment,

#                 "order": payment.order,

#                 "paytm_order_id":
#                     paytm_order_id,

#                 "transaction_id":
#                     txn_id,

#                 "payment_mode":
#                     payment_mode,

#                 "amount":
#                     payment.amount,

#                 "result_code":
#                     result_code,

#                 "result_message":
#                     result_message,
#             },
#             status=200,
#         )

#     # =====================================================
#     # ERROR
#     # =====================================================

#     except Exception:

#         traceback.print_exc()

#         return render(
#             request,
#             "payment/payment_result.html",
#             {
#                 "status": "failed",

#                 "message":
#                     "Unable to process payment.",

#             },
#             status=500,
#         )

import json
import traceback

from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from .models import Payment


# =========================================================
# PAYTM CALLBACK
# =========================================================

@csrf_exempt
def paytm_callback(request):

    # =====================================================
    # POST ONLY
    # =====================================================

    if request.method != "POST":

        return render(
            request,
            "payment/payment_result.html",
            {
                "status": "failed",
                "message": "Invalid payment request.",
            },
            status=405,
        )

    try:

        # =================================================
        # GET PAYTM DATA
        # =================================================

        paytm_data = request.POST.dict()

        # =================================================
        # JSON FALLBACK
        # =================================================

        if not paytm_data:

            try:

                paytm_data = json.loads(
                    request.body
                )

            except json.JSONDecodeError:

                paytm_data = {}

        # =================================================
        # PAYTM ORDER ID
        # =================================================

        paytm_order_id = (

            paytm_data.get("ORDERID")

            or paytm_data.get("orderId")

        )

        if not paytm_order_id:

            return render(
                request,
                "payment/payment_result.html",
                {
                    "status": "failed",
                    "message":
                        "Paytm order ID is missing.",
                },
                status=400,
            )

        # =================================================
        # TRANSACTION ID
        # =================================================

        txn_id = (

            paytm_data.get("TXNID")

            or paytm_data.get("txnId")

            or ""

        )

        # =================================================
        # PAYMENT STATUS
        # =================================================

        payment_status = (

            paytm_data.get("STATUS")

            or paytm_data.get("status")

            or ""

        )

        # =================================================
        # RESPONSE CODE
        # =================================================

        result_code = (

            paytm_data.get("RESPCODE")

            or paytm_data.get("resultCode")

            or ""

        )

        # =================================================
        # RESPONSE MESSAGE
        # =================================================

        result_message = (

            paytm_data.get("RESPMSG")

            or paytm_data.get("resultMsg")

            or ""

        )

        # =================================================
        # PAYMENT MODE
        # =================================================

        payment_mode = (

            paytm_data.get("PAYMENTMODE")

            or paytm_data.get("paymentMode")

            or ""

        )

        # =================================================
        # FIND PAYMENT
        # =================================================

        payment = (

            Payment.objects

            .select_related(
                "order",
                "customer",
            )

            .filter(
                payment_gateway="paytm",
                paytm_order_id=paytm_order_id,
            )

            .order_by(
                "-created_at"
            )

            .first()
        )

        # =================================================
        # FALLBACK
        # =================================================

        if not payment:

            payment = (

                Payment.objects

                .select_related(
                    "order",
                    "customer",
                )

                .filter(
                    payment_gateway="paytm",
                    gateway_order_id=paytm_order_id,
                )

                .order_by(
                    "-created_at"
                )

                .first()
            )

        # =================================================
        # PAYMENT NOT FOUND
        # =================================================

        if not payment:

            return render(
                request,
                "payment/payment_result.html",
                {
                    "status": "failed",

                    "message":
                        "Payment record not found.",

                    "paytm_order_id":
                        paytm_order_id,
                },
                status=404,
            )

        # =================================================
        # SAVE TRANSACTION ID
        # =================================================

        payment.paytm_txn_id = txn_id

        payment.gateway_transaction_id = txn_id

        # =================================================
        # SAVE PAYMENT MODE
        # =================================================

        if payment_mode:

            payment.payment_mode = payment_mode

        # =================================================
        # SAVE PAYTM RESPONSE
        # =================================================

        payment.gateway_response = paytm_data

        # =================================================
        # PAYMENT SUCCESS
        # =================================================

        if payment_status.upper() == "TXN_SUCCESS":

            # =============================================
            # UPDATE PAYMENT
            # =============================================

            payment.status = "success"

            payment.save()

            # =============================================
            # UPDATE ORDER
            # =============================================

            order = payment.order

            if order:

                order.status = "confirmed"

                order.save(
                    update_fields=[
                        "status"
                    ]
                )

            # =============================================
            # SHOW SUCCESS PAGE
            #
            # NO REDIRECT HERE
            # =============================================

            return render(
                request,
                "payment/payment_result.html",
                {
                    "status": "success",

                    "message":
                        "Your payment has been completed successfully.",

                    "payment": payment,

                    "order": order,

                    "paytm_order_id":
                        paytm_order_id,

                    "transaction_id":
                        txn_id,

                    "payment_mode":
                        payment_mode,

                    "amount":
                        payment.amount,

                    "result_code":
                        result_code,

                    "result_message":
                        result_message,
                },
                status=200,
            )

        # =================================================
        # PAYMENT FAILED
        # =================================================

        payment.status = "failed"

        payment.save()

        # =================================================
        # SHOW FAILED PAGE
        #
        # NO REDIRECT HERE
        # =================================================

        return render(
            request,
            "payment/payment_result.html",
            {
                "status": "failed",

                "message":
                    result_message
                    or "Your payment could not be completed.",

                "payment": payment,

                "order": payment.order,

                "paytm_order_id":
                    paytm_order_id,

                "transaction_id":
                    txn_id,

                "payment_mode":
                    payment_mode,

                "amount":
                    payment.amount,

                "result_code":
                    result_code,

                "result_message":
                    result_message,
            },
            status=200,
        )

    # =====================================================
    # GENERAL ERROR
    # =====================================================

    except Exception:

        traceback.print_exc()

        return render(
            request,
            "payment/payment_result.html",
            {
                "status": "failed",

                "message":
                    "Something went wrong while processing your payment.",
            },
            status=500,
        )

@csrf_exempt
def paytm_status(request):

    if request.method != "POST":
        return JsonResponse({
            "success": False,
            "message": "POST method required"
        }, status=405)

    try:

        data = json.loads(request.body)

        paytm_order_id = data.get("paytm_order_id")

        if not paytm_order_id:
            return JsonResponse({
                "success": False,
                "message": "paytm_order_id is required"
            }, status=400)

        # ==========================================
        # PAYTM CONFIG
        # ==========================================

        config = get_paytm_config()

        merchant_key = config["MERCHANT_KEY"]

        if not merchant_key:
            return JsonResponse({
                "success": False,
                "message": "PAYTM_MERCHANT_KEY is missing"
            }, status=500)

        # ==========================================
        # STATUS BODY
        # ==========================================

        body = {
            "mid": config["MID"],
            "orderId": paytm_order_id
        }

        body_string = json.dumps(
            body,
            separators=(",", ":"),
            ensure_ascii=False
        )

        signature = PaytmChecksum.generateSignature(
            body_string,
            merchant_key
        )

        payload = {
            "body": body,
            "head": {
                "signature": signature
            }
        }

        # ==========================================
        # PAYTM STATUS URL
        # ==========================================

        status_url = config.get(
            "STATUS_URL"
        )

        if not status_url:
            status_url = (
                "https://securegw.paytm.in/"
                "v3/order/status"
            )

        print("\n========================================")
        print("PAYTM STATUS")
        print("ORDER ID:", paytm_order_id)
        print("URL:", status_url)
        print("PAYLOAD:", json.dumps(payload, indent=4))
        print("========================================")

        response = requests.post(
            status_url,
            json=payload,
            headers={
                "Content-Type": "application/json"
            },
            timeout=60
        )

        print("PAYTM STATUS HTTP:", response.status_code)
        print("PAYTM STATUS RESPONSE:", response.text)

        try:
            response_data = response.json()
        except ValueError:
            return JsonResponse({
                "success": False,
                "message": "Invalid response from Paytm",
                "response": response.text
            }, status=502)

        # ==========================================
        # UPDATE PAYMENT RECORD
        # ==========================================

        try:

            payment = Payment.objects.get(
                gateway_order_id=paytm_order_id
            )

            payment.gateway_response = response_data

            result_status = (
                response_data
                .get("body", {})
                .get("resultInfo", {})
                .get("resultStatus")
            )

            if result_status == "TXN_SUCCESS":

                payment.status = "success"

            elif result_status in [
                "TXN_FAILURE",
                "F"
            ]:

                payment.status = "failed"

            else:

                payment.status = "pending"

            payment.save()

        except Payment.DoesNotExist:

            payment = None

        return JsonResponse({
            "success": True,
            "paytm_order_id": paytm_order_id,
            "payment_status": (
                payment.status
                if payment
                else None
            ),
            "paytm_response": response_data
        })

    except json.JSONDecodeError:

        return JsonResponse({
            "success": False,
            "message": "Invalid JSON"
        }, status=400)

    except requests.RequestException as e:

        traceback.print_exc()

        return JsonResponse({
            "success": False,
            "message": "Unable to connect to Paytm",
            "error": str(e)
        }, status=502)

    except Exception as e:

        traceback.print_exc()

        return JsonResponse({
            "success": False,
            "message": "Paytm status check failed",
            "error": str(e)
        }, status=500)


@csrf_exempt
def paytm_refund(request):

    if request.method != "POST":
        return JsonResponse({
            "success": False,
            "message": "POST method required"
        }, status=405)

    try:

        data = json.loads(request.body)

        paytm_order_id = data.get("paytm_order_id")
        refund_amount_raw = data.get("refund_amount")

        if not paytm_order_id:
            return JsonResponse({
                "success": False,
                "message": "paytm_order_id is required"
            }, status=400)

        if refund_amount_raw is None:
            return JsonResponse({
                "success": False,
                "message": "refund_amount is required"
            }, status=400)

        # ==========================================
        # FIND PAYMENT
        # ==========================================

        try:

            payment = Payment.objects.get(
                gateway_order_id=paytm_order_id
            )

        except Payment.DoesNotExist:

            return JsonResponse({
                "success": False,
                "message": "Payment record not found"
            }, status=404)

        # ==========================================
        # VERIFY PAYMENT
        # ==========================================

        if payment.status != "success":

            return JsonResponse({
                "success": False,
                "message": "Only successful payments can be refunded",
                "payment_status": payment.status
            }, status=400)

        # ==========================================
        # VALIDATE REFUND AMOUNT
        # ==========================================

        try:

            refund_amount = Decimal(
                str(refund_amount_raw)
            ).quantize(Decimal("0.01"))

        except (InvalidOperation, ValueError):

            return JsonResponse({
                "success": False,
                "message": "Invalid refund amount"
            }, status=400)

        if refund_amount <= 0:

            return JsonResponse({
                "success": False,
                "message": "Refund amount must be greater than zero"
            }, status=400)

        if refund_amount > payment.amount:

            return JsonResponse({
                "success": False,
                "message": "Refund amount cannot exceed payment amount"
            }, status=400)

        # ==========================================
        # PAYTM CONFIG
        # ==========================================

        config = get_paytm_config()

        merchant_key = config["MERCHANT_KEY"]

        # ==========================================
        # GENERATE REFUND ID
        # ==========================================

        refund_id = (
            "REFUND_"
            + uuid.uuid4().hex[:18]
        )

        # ==========================================
        # REFUND BODY
        # ==========================================

        body = {

            "mid": config["MID"],

            "txnType": "REFUND",

            "orderId": paytm_order_id,

            "txnId": payment.gateway_transaction_id,

            "refId": refund_id,

            "refundAmount": format(
                refund_amount,
                ".2f"
            )
        }

        body_string = json.dumps(
            body,
            separators=(",", ":"),
            ensure_ascii=False
        )

        signature = PaytmChecksum.generateSignature(
            body_string,
            merchant_key
        )

        payload = {
            "body": body,
            "head": {
                "signature": signature
            }
        }

        # ==========================================
        # REFUND URL
        # ==========================================

        refund_url = config.get(
            "REFUND_URL"
        )

        if not refund_url:
            refund_url = (
                "https://securegw.paytm.in/"
                "refund/apply"
            )

        print("\n========================================")
        print("PAYTM REFUND")
        print("ORDER ID:", paytm_order_id)
        print("TXN ID:", payment.gateway_transaction_id)
        print("REFUND ID:", refund_id)
        print("AMOUNT:", refund_amount)
        print("========================================")

        response = requests.post(
            refund_url,
            json=payload,
            headers={
                "Content-Type": "application/json"
            },
            timeout=60
        )

        print("REFUND HTTP:", response.status_code)
        print("REFUND RESPONSE:", response.text)

        try:
            response_data = response.json()
        except ValueError:

            return JsonResponse({
                "success": False,
                "message": "Invalid Paytm refund response",
                "response": response.text
            }, status=502)

        result_info = (
            response_data
            .get("body", {})
            .get("resultInfo", {})
        )

        return JsonResponse({
            "success": True,
            "refund_id": refund_id,
            "paytm_order_id": paytm_order_id,
            "refund_amount": format(
                refund_amount,
                ".2f"
            ),
            "result_status": result_info.get(
                "resultStatus"
            ),
            "result_code": result_info.get(
                "resultCode"
            ),
            "result_message": result_info.get(
                "resultMsg"
            ),
            "paytm_response": response_data
        })

    except json.JSONDecodeError:

        return JsonResponse({
            "success": False,
            "message": "Invalid JSON"
        }, status=400)

    except requests.RequestException as e:

        traceback.print_exc()

        return JsonResponse({
            "success": False,
            "message": "Unable to connect to Paytm",
            "error": str(e)
        }, status=502)

    except Exception as e:

        traceback.print_exc()

        return JsonResponse({
            "success": False,
            "message": "Refund failed",
            "error": str(e)
        }, status=500)


@csrf_exempt
def paytm_webhook(request):

    print("\n========================================")
    print("PAYTM WEBHOOK RECEIVED")
    print("METHOD:", request.method)
    print("========================================")

    if request.method != "POST":

        return JsonResponse({
            "success": False,
            "message": "POST method required"
        }, status=405)

    try:

        # ==========================================
        # READ WEBHOOK DATA
        # ==========================================

        data = request.POST.dict()

        if not data:

            try:
                data = json.loads(
                    request.body
                )
            except Exception:
                data = {}

        print("WEBHOOK DATA:")
        print(
            json.dumps(
                data,
                indent=4
            )
        )

        # ==========================================
        # CHECKSUM
        # ==========================================

        checksum = data.get(
            "CHECKSUMHASH"
        )

        if checksum:

            verify_data = data.copy()

            verify_data.pop(
                "CHECKSUMHASH",
                None
            )

            is_valid = (
                PaytmChecksum.verifySignature(
                    verify_data,
                    settings.PAYTM_MERCHANT_KEY.strip(),
                    checksum
                )
            )

            print(
                "WEBHOOK CHECKSUM:",
                is_valid
            )

            if not is_valid:

                return JsonResponse({
                    "success": False,
                    "message": "Invalid Paytm checksum"
                }, status=400)

        # ==========================================
        # VALUES
        # ==========================================

        paytm_order_id = data.get(
            "ORDERID"
        )

        txn_id = data.get(
            "TXNID"
        )

        status = data.get(
            "STATUS"
        )

        payment_mode = data.get(
            "PAYMENTMODE"
        )

        # ==========================================
        # PAYMENT
        # ==========================================

        if paytm_order_id:

            try:

                payment = Payment.objects.get(
                    gateway_order_id=paytm_order_id
                )

                payment.gateway_response = data

                if txn_id:
                    payment.gateway_transaction_id = txn_id

                if payment_mode:
                    payment.payment_mode = payment_mode

                if status == "TXN_SUCCESS":

                    payment.status = "success"

                elif status == "TXN_FAILURE":

                    payment.status = "failed"

                else:

                    payment.status = "pending"

                payment.save()

                print(
                    "PAYMENT UPDATED:",
                    payment.id
                )

            except Payment.DoesNotExist:

                print(
                    "PAYMENT NOT FOUND:",
                    paytm_order_id
                )

        # ==========================================
        # RESPONSE
        # ==========================================

        return JsonResponse({
            "success": True,
            "message": "Webhook received",
            "order_id": paytm_order_id,
            "txn_id": txn_id,
            "status": status
        })

    except Exception as e:

        traceback.print_exc()

        return JsonResponse({
            "success": False,
            "message": "Webhook processing failed",
            "error": str(e)
        }, status=500)


# # ==========================================
# # OTP GENERATION AND VERIFICATION
# # ==========================================

    
# @csrf_exempt
# def generate_otp(request):

#     if request.method != "POST":
#         return JsonResponse({
#             "success": False,
#             "message": "Only POST method is allowed"
#         }, status=405)

#     mobile = request.POST.get("mobile")

#     if not mobile:
#         return JsonResponse({
#             "success": False,
#             "message": "Mobile number is required"
#         }, status=400)

#     mobile = str(mobile).strip()

#     # Generate 6-digit OTP
#     otp = str(random.randint(100000, 999999))

#     # OTP valid for 30 minutes
#     expires_at = timezone.now() + timedelta(minutes=30)

#     # Remove previous OTP for this mobile number
#     OTPVerification.objects.filter(mobile=mobile).delete()

#     # Save new OTP
#     OTPVerification.objects.create(
#         mobile=mobile,
#         otp=otp,
#         expires_at=expires_at
#     )

#     print("GENERATED OTP:", otp)

#     # Send SMS
#     sms_response = send_sms_otp(mobile, otp)

#     if sms_response is None:
#         return JsonResponse({
#             "success": False,
#             "message": "OTP generated, but SMS could not be sent"
#         }, status=500)

#     return JsonResponse({
#         "success": True,
#         "message": "OTP generated and SMS sent successfully"
#     })



# #otp verification (old otp code)
# @csrf_exempt
# def verify_otp_old(request):

#     if request.method != "POST":
#         return JsonResponse({
#             "success": False,
#             "message": "Only POST method is allowed"
#         }, status=405)

#     mobile = request.POST.get("mobile")
#     entered_otp = request.POST.get("otp")

#     if not mobile or not entered_otp:
#         return JsonResponse({
#             "success": False,
#             "message": "Mobile number and OTP are required"
#         }, status=400)

#     mobile = str(mobile).strip()
#     entered_otp = str(entered_otp).strip()

#     # Get OTP from database
#     otp_record = OTPVerification.objects.filter(
#         mobile=mobile
#     ).first()

#     if otp_record is None:
#         return JsonResponse({
#             "success": False,
#             "message": "OTP not found"
#         }, status=400)

#     # Check expiry
#     if timezone.now() > otp_record.expires_at:
#         otp_record.delete()

#         return JsonResponse({
#             "success": False,
#             "message": "OTP has expired"
#         }, status=400)

#     # Compare OTP
#     if entered_otp != otp_record.otp:
#         return JsonResponse({
#             "success": False,
#             "message": "Invalid OTP"
#         }, status=400)

#     # OTP is correct -> delete it
#     otp_record.delete()

#     return JsonResponse({
#         "success": True,
#         "message": "OTP verified successfully"
#     })



# =========================================================
# OTP SMS FUNCTION
# =========================================================

# def send_sms_otp(mobile, otp):

#     try:

#         start = time.time()

#         mobile = str(mobile).strip()

#         message = (
#             f"OTP for Login/Transaction on Dharani Herbbals is {otp} "
#             f"and valid for 30 minutes. "
#             f"Do not share this OTP with anyone for security reasons."
#         )

#         # =================================================
#         # SMS GATEWAY URL
#         # =================================================

#         url = (
#             f"{settings.SMS_API_URL}"
#             f"username={settings.SMS_USERNAME}"
#             f"&password={settings.SMS_PASSWORD}"
#             f"&sender_id={settings.SMS_SENDER_ID}"
#             f"&route=T"
#             f"&phonenumber={mobile}"
#             f"&message={requests.utils.quote(message)}"
#         )

#         print("\n========================================")
#         print("CALLING SMS API")
#         print("MOBILE:", mobile)
#         print("========================================")

#         response = requests.get(
#             url,
#             timeout=10
#         )

#         end = time.time()

#         print("SMS STATUS:", response.status_code)
#         print("SMS RESPONSE:", response.text)
#         print(
#             "SMS TIME:",
#             round(end - start, 2),
#             "seconds"
#         )

#         return response

#     except requests.exceptions.RequestException as e:

#         print("SMS REQUEST ERROR:", e)

#         return None

#     except Exception as e:

#         print("SMS ERROR:", e)

#         return None
import time
import requests
from django.conf import settings


def send_sms_otp(mobile, otp, purpose="registration"):

    try:

        start = time.time()

        mobile = str(mobile).strip()
        otp = str(otp).strip()

        # =================================================
        # TEMPLATE ID & MESSAGE
        # =================================================

        if purpose == "user_login":
            template_id = "1777179128828939213"
            message = (
                f"<#> {otp} is your OTP to securely log in to your Dharani Herbals account. "
                f"This OTP is valid for 5 minutes. Do not share it with anyone.\n"
                f"@dharaniherbbals.in # {otp}"
            )
        else:
            template_id = settings.SMS_TEMPLATE_ID
            message = (
                f"OTP for Login/Transaction on Dharani Herbbals is {otp} "
                f"and valid for {settings.SMS_OTP_EXPIRY_MINUTES} minutes. "
                f"Do not share this OTP with anyone for security reasons."
            )

        if not template_id:
            print("SMS_TEMPLATE_ID is not configured")
            return None

        # =================================================
        # SMS GATEWAY URL
        # =================================================

        url = (
            f"{settings.SMS_API_URL}"
            f"username={settings.SMS_USERNAME}"
            f"&password={settings.SMS_PASSWORD}"
            f"&sender_id={settings.SMS_SENDER_ID}"
            f"&route=T"
            f"&phonenumber={mobile}"
            f"&message={requests.utils.quote(message)}"
            f"&template_id={template_id}"
        )

        # =================================================
        # CALL SMS API
        # =================================================

        response = requests.get(
            url,
            timeout=30
        )

        if 200 <= response.status_code < 300:
            return response

        return None

    except requests.exceptions.RequestException:
        return None

    except Exception:
        return None


# =========================================================
# BACKGROUND SMS FUNCTION
# =========================================================

def send_sms_background(mobile, otp, purpose="registration"):
    try:
        send_sms_otp(
            mobile,
            otp,
            purpose
        )
    except Exception:
        pass


# =========================================================
# GENERATE OTP
# =========================================================

@csrf_exempt
def generate_otp(request):

    print("\n>>> GENERATE OTP VIEW CALLED <<<")

    # =====================================================
    # METHOD CHECK
    # =====================================================

    if request.method != "POST":

        return JsonResponse({

            "success": False,

            "message":
                "Only POST method is allowed"

        }, status=405)

    try:

        # =================================================
        # GET MOBILE
        # =================================================

        mobile = request.POST.get("mobile")

        # =================================================
        # SUPPORT JSON BODY ALSO
        # =================================================

        if not mobile:

            try:

                data = json.loads(
                    request.body
                )

                mobile = data.get(
                    "mobile"
                )

            except Exception:

                pass

        # =================================================
        # MOBILE VALIDATION
        # =================================================

        if not mobile:

            return JsonResponse({

                "success": False,

                "message":
                    "Mobile number is required"

            }, status=400)

        mobile = str(
            mobile
        ).strip()

        # =================================================
        # BASIC MOBILE VALIDATION
        # =================================================

        if not mobile.isdigit():

            return JsonResponse({

                "success": False,

                "message":
                    "Invalid mobile number"

            }, status=400)

        if len(mobile) != 10:

            return JsonResponse({

                "success": False,

                "message":
                    "Mobile number must be 10 digits"

            }, status=400)

        # =================================================
        # GENERATE 6 DIGIT OTP
        # =================================================

        otp = str(
            random.randint(
                100000,
                999999
            )
        )

        print(
            "GENERATED OTP:",
            otp
        )

        # =================================================
        # OTP VALID FOR 30 MINUTES
        # =================================================

        expires_at = (
            timezone.now()
            + timedelta(
                minutes=30
            )
        )

        # =================================================
        # DELETE PREVIOUS OTP
        # =================================================

        OTPVerification.objects.filter(
            mobile=mobile
        ).delete()

        # =================================================
        # SAVE NEW OTP
        # =================================================

        OTPVerification.objects.create(

            mobile=mobile,

            otp=otp,

            expires_at=expires_at

        )

        print(
            "OTP SAVED TO DATABASE"
        )

        # =================================================
        # START SMS IN BACKGROUND
        # =================================================

        threading.Thread(

            target=send_sms_background,

            args=(
                mobile,
                otp
            ),

            daemon=True

        ).start()

        print(
            "SMS THREAD STARTED"
        )

        # =================================================
        # IMMEDIATE RESPONSE
        # =================================================

        return JsonResponse({

            "success": True,

            "message":
                "OTP sent successfully"

        }, status=200)

    except Exception as e:

        print(
            "GENERATE OTP ERROR:",
            e
        )

        return JsonResponse({

            "success": False,

            "message": str(e)

        }, status=500)


# =========================================================
# RESEND OTP
# =========================================================

@csrf_exempt
def resend_otp(request):

    print("\n>>> RESEND OTP VIEW CALLED <<<")

    # =====================================================
    # METHOD CHECK
    # =====================================================

    if request.method != "POST":

        return JsonResponse({

            "success": False,

            "message":
                "Only POST method is allowed"

        }, status=405)

    try:

        # =================================================
        # GET MOBILE
        # =================================================

        mobile = request.POST.get(
            "mobile"
        )

        # =================================================
        # SUPPORT JSON
        # =================================================

        if not mobile:

            try:

                data = json.loads(
                    request.body
                )

                mobile = data.get(
                    "mobile"
                )

            except Exception:

                pass

        # =================================================
        # VALIDATION
        # =================================================

        if not mobile:

            return JsonResponse({

                "success": False,

                "message":
                    "Mobile number is required"

            }, status=400)

        mobile = str(
            mobile
        ).strip()

        # =================================================
        # GENERATE NEW OTP
        # =================================================

        otp = str(
            random.randint(
                100000,
                999999
            )
        )

        print(
            "NEW RESEND OTP:",
            otp
        )

        # =================================================
        # NEW EXPIRY
        # =================================================

        expires_at = (
            timezone.now()
            + timedelta(
                minutes=30
            )
        )

        # =================================================
        # DELETE OLD OTP
        # =================================================

        OTPVerification.objects.filter(
            mobile=mobile
        ).delete()

        # =================================================
        # SAVE NEW OTP
        # =================================================

        OTPVerification.objects.create(

            mobile=mobile,

            otp=otp,

            expires_at=expires_at

        )

        # =================================================
        # SEND SMS BACKGROUND
        # =================================================

        threading.Thread(

            target=send_sms_background,

            args=(
                mobile,
                otp
            ),

            daemon=True

        ).start()

        # =================================================
        # IMMEDIATE RESPONSE
        # =================================================

        return JsonResponse({

            "success": True,

            "message":
                "OTP resent successfully",
             "otp": otp

        }, status=200)

    except Exception as e:

        print(
            "RESEND OTP ERROR:",
            e
        )

        return JsonResponse({

            "success": False,

            "message": str(e)

        }, status=500)


# =========================================================
# VERIFY OTP
# =========================================================

@csrf_exempt
def verify_otp(request):

    print("\n>>> VERIFY OTP VIEW CALLED <<<")

    # =====================================================
    # METHOD CHECK
    # =====================================================

    if request.method != "POST":

        return JsonResponse({

            "success": False,

            "message":
                "Only POST method is allowed"

        }, status=405)

    try:

        # =================================================
        # GET DATA
        # =================================================

        mobile = request.POST.get(
            "mobile"
        )

        entered_otp = request.POST.get(
            "otp"
        )

        # =================================================
        # SUPPORT JSON BODY
        # =================================================

        if not mobile or not entered_otp:

            try:

                data = json.loads(
                    request.body
                )

                mobile = (
                    mobile
                    or data.get("mobile")
                )

                entered_otp = (
                    entered_otp
                    or data.get("otp")
                )

            except Exception:

                pass

        # =================================================
        # VALIDATION
        # =================================================

        if not mobile or not entered_otp:

            return JsonResponse({

                "success": False,

                "message":
                    "Mobile number and OTP are required"

            }, status=400)

        mobile = str(
            mobile
        ).strip()

        entered_otp = str(
            entered_otp
        ).strip()

        print(
            "VERIFY MOBILE:",
            mobile
        )

        print(
            "ENTERED OTP:",
            entered_otp
        )

        # =================================================
        # VERIFY OTP (REGISTRATION OR LOGIN)
        # =================================================

        # 1. Check Registration OTP (OTPVerification)
        otp_record = OTPVerification.objects.filter(mobile=mobile).order_by("-id").first()
        
        # 2. Check Login OTP (EmailOTP)
        user = User.objects.filter(mobile=mobile).exclude(role='customer').first()
        if not user:
            user = User.objects.filter(mobile=mobile).first()
        email_otp_record = None
        if user:
            email_otp_record = EmailOTP.objects.filter(
                user=user,
                purpose="user_login",
                is_verified=False
            ).order_by("-created_at").first()

        if otp_record and entered_otp == otp_record.otp:
            # Match Registration OTP
            if timezone.now() > otp_record.expires_at:
                otp_record.delete()
                return JsonResponse({"success": False, "message": "OTP has expired"}, status=400)
            
            pending_user = PendingRegistration.objects.filter(mobile=mobile).first()
            if not pending_user:
                return JsonResponse({"success": False, "message": "Pending registration not found"}, status=404)
                
            if User.objects.filter(email=pending_user.email).exists():
                pending_user.delete()
                otp_record.delete()
                return JsonResponse({"success": False, "message": "User already exists"}, status=400)
                
            user = User.objects.create(
                name=pending_user.name,
                mobile=pending_user.mobile,
                email=pending_user.email,
                password=pending_user.password,
                role=pending_user.role,
                is_verified=True
            )
            
            if user.email:
                try:
                    context = {"name": user.name, "mobile": user.mobile, "role": user.role}
                    html_content = render_to_string("email/register_success.html", context)
                    email_msg = EmailMultiAlternatives(
                        subject="Registration Successful",
                        body="Registration Successful",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        to=[user.email]
                    )
                    email_msg.attach_alternative(html_content, "text/html")
                    email_msg.send()
                except Exception as email_err:
                    print(f"Failed to send registration email: {email_err}")
            
            pending_user.delete()
            otp_record.delete()
            print("OTP VERIFIED SUCCESSFULLY (Registration)")
            return JsonResponse({
                "success": True, 
                "message": "Account verified successfully",
                "user_id": user.id,
                "user": {
                    "id": user.id,
                    "name": user.name,
                    "mobile": user.mobile,
                    "role": user.role,
                    "is_store_member": user.role == "staff"
                }
            }, status=200)

        elif email_otp_record and entered_otp == email_otp_record.otp:
            # Match Login OTP
            if timezone.now() > email_otp_record.created_at + timedelta(minutes=30):
                return JsonResponse({"success": False, "message": "OTP has expired"}, status=400)
            
            email_otp_record.is_verified = True
            email_otp_record.save()
            print("OTP VERIFIED SUCCESSFULLY (Login)")
            return JsonResponse({
                "success": True, 
                "message": "OTP verified successfully", 
                "user_id": user.id,
                "user": {
                    "id": user.id,
                    "name": user.name,
                    "mobile": user.mobile,
                    "role": user.role,
                    "is_store_member": user.role == "staff"
                }
            }, status=200)

        else:
            # Neither matched
            if not otp_record and not email_otp_record:
                return JsonResponse({"success": False, "message": "OTP not found"}, status=400)
            else:
                return JsonResponse({"success": False, "message": "Invalid OTP"}, status=400)

    except Exception as e:

        print(
            "VERIFY OTP ERROR:",
            e
        )

        return JsonResponse({

            "success": False,

            "message": str(e)

        }, status=500)


from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .models import Product


@api_view(['GET'])
def product_by_barcode(request):

    barcode = request.GET.get('barcode')

    if not barcode:
        return Response({
            "success": False,
            "message": "Barcode is required"
        }, status=status.HTTP_400_BAD_REQUEST)

    barcode = barcode.strip()

    try:
        product = Product.objects.select_related(
            'category',
            'brand'
        ).get(
            barcode=barcode
        )

    except Product.DoesNotExist:
        return Response({
            "success": False,
            "message": "Product not found",
            "barcode": barcode
        }, status=status.HTTP_404_NOT_FOUND)

    data = {

        # ==============================
        # PRODUCT DETAILS
        # ==============================

        "id": product.id,

        "name": product.name,

        "tamil_name": product.tamil_name or "",

        "product_code": product.product_code or "",

        "barcode": product.barcode or "",

        # "description": product.description or "",

        # "product_type": product.product_type or "",

        # ==============================
        # IMAGE
        # ==============================

        # "image": (
        #     get_image_url(request, product.image)
        #     if product.image
        #     else ""
        # ),

        # ==============================
        # CATEGORY
        # ==============================

        "category": {
            "id": (
                product.category.id
                if product.category
                else None
            ),

            "name": (
                product.category.name
                if product.category
                else ""
            )
        },

        # ==============================
        # BRAND
        # ==============================

        # "brand": {
        #     "id": (
        #         product.brand.id
        #         if product.brand
        #         else None
        #     ),

        #     "name": (
        #         product.brand.name
        #         if product.brand
        #         else ""
        #     )
        # },

        # ==============================
        # PRICING
        # ==============================

        "pricing": {

            "purchase_price": str(
                product.purchase_price
            ),

            "mrp": str(
                product.mrp
            ),

            "customer_price": str(
                product.customer_price
            ),

            "store_price": str(
                product.store_price
            ),

            "reseller_price": str(
                product.reseller_price
            ),

            "retailer_price": str(
                product.retailer_price
            ),

            "distributor_price": str(
                product.distributor_price
            ),

            "sarvo_price": str(
                product.sarvo_price
            ),

            "drug_price": str(
                product.drug_price
            )
        },

        # ==============================
        # GST
        # ==============================

        "gst_percentage": str(
            product.gst_percentage
        ),

        # ==============================
        # STOCK
        # ==============================

        "stock": product.stock,

        "reorder_level": product.reorder_level,

        # ==============================
        # UNIT
        # ==============================

        "unit": product.unit,

        "unit_display": product.get_unit_display(),

        "weight_volume": (
            product.weight_volume or ""
        ),

        # ==============================
        # OTHER DETAILS
        # ==============================

        # "manufacturer": (
        #     product.manufacturer or ""
        # ),

        # "batch_number": (
        #     product.batch_number or ""
        # ),

        # "expiry_date": (
        #     product.expiry_date.isoformat()
        #     if product.expiry_date
        #     else None
        # ),

        # ==============================
        # FLAGS
        # ==============================

        # "is_new": product.is_new,

        # "is_public": product.is_public,

        # "is_active": product.is_active,

        # ==============================
        # CREATED DATE
        # ==============================

        "created_at": (
            product.created_at.isoformat()
        )
    }

    return Response({
        "success": True,
        "message": "Product found",
        "data": data
    }, status=status.HTTP_200_OK)


def get_payment(request, payment_id):

    # =====================================================
    # GET ONLY
    # =====================================================

    if request.method != "GET":

        return JsonResponse({

            "success": False,

            "message":
                "GET method required"

        }, status=405)

    # =====================================================
    # GET PAYMENT
    # =====================================================

    try:

        payment = Payment.objects.select_related(
            "order",
            "customer"
        ).get(
            id=payment_id
        )

    except Payment.DoesNotExist:

        return JsonResponse({

            "success": False,

            "message":
                "Payment not found",

            "payment_id":
                payment_id

        }, status=404)

    # =====================================================
    # ORDER
    # =====================================================

    order = payment.order

    # =====================================================
    # CUSTOMER
    # =====================================================

    customer = payment.customer

    # =====================================================
    # RESPONSE
    # =====================================================

    return JsonResponse({

        "success": True,

        "message":
            "Payment details fetched successfully",

        "data": {

            "payment_id":
                payment.id,

            "amount":
                str(payment.amount),

            "status":
                payment.status,

            "status_display":
                payment.get_status_display(),

            "payment_gateway":
                payment.payment_gateway,

            "payment_gateway_display":
                payment.get_payment_gateway_display(),

            "payment_mode":
                payment.payment_mode or "",

            # =============================================
            # ORDER
            # =============================================

            "order": {

                "id":
                    order.id
                    if order
                    else None,

                "invoice_number":
                    order.invoice_number
                    if order
                    else "",

                "status":
                    order.status
                    if order
                    else "",

                "product_amount":
                    str(order.product_amount)
                    if order
                    else "0.00",

                "gst_amount":
                    str(order.gst_amount)
                    if order
                    else "0.00",

                "shipping_charges":
                    str(order.shipping_charges)
                    if order
                    else "0.00",

                "total_amount":
                    str(order.total_amount)
                    if order
                    else "0.00"
            },

            # =============================================
            # CUSTOMER
            # =============================================

            "customer": {

                "id":
                    customer.id
                    if customer
                    else None,

                "name":
                    customer.name
                    if customer
                    else "",

                "mobile":
                    customer.mobile
                    if customer
                    else "",

                "email":
                    customer.email
                    if customer
                    else ""
            },

            # =============================================
            # PAYTM
            # =============================================

            "paytm": {

                "order_id":
                    payment.paytm_order_id
                    or "",

                "txn_id":
                    payment.paytm_txn_id
                    or "",

                "bank_txn_id":
                    payment.paytm_bank_txn_id
                    or "",

                "payment_mode":
                    payment.payment_mode
                    or ""
            },

            # =============================================
            # COMMON
            # =============================================

            "gateway": {

                "order_id":
                    payment.gateway_order_id
                    or "",

                "transaction_id":
                    payment.gateway_transaction_id
                    or ""
            },

            # =============================================
            # DATES
            # =============================================

            "created_at":
                payment.created_at.isoformat(),

            "updated_at":
                payment.updated_at.isoformat()
        }

    }, status=200)
# import requests
# from django.conf import settings

# # ==========================================
# # WATI LOGIN WHATSAPP
# # ==========================================

# def send_login_whatsapp(customer):

#     mobile = str(customer.mobile).strip()

#     if mobile.startswith("+91"):
#         whatsapp_number = mobile[1:]

#     elif mobile.startswith("91") and len(mobile) == 12:
#         whatsapp_number = mobile

#     elif len(mobile) == 10:
#         whatsapp_number = "91" + mobile

#     else:
#         raise ValueError(
#             f"Invalid mobile number: {mobile}"
#         )

#     url = (
#         f"{settings.WATI_BASE_URL}"
#         f"/api/v1/sendTemplateMessage"
#     )

#     headers = {
#         "Authorization": f"Bearer {settings.WATI_API_TOKEN}",
#         "Content-Type": "application/json",
#     }

#     payload = {
#         "whatsappNumber": whatsapp_number,
#         "template_name": "YOUR_LOGIN_TEMPLATE",
#         "broadcast_name": "customer_login",
#         "parameters": [
#             {
#                 "name": "name",
#                 "value": customer.name or "வாடிக்கையாளர்"
#             }
#         ]
#     }

#     response = requests.post(
#         url,
#         headers=headers,
#         json=payload,
#         timeout=15
#     )

#     print("========== WATI LOGIN ==========")
#     print("NUMBER:", whatsapp_number)
#     print("STATUS:", response.status_code)
#     print("RESPONSE:", response.text)

#     return response


def get_paytm_config():

    return {

        "MID": settings.PAYTM_MID,

        "MERCHANT_KEY": settings.PAYTM_MERCHANT_KEY,

        "WEBSITE": settings.PAYTM_WEBSITE,

        "CHANNEL_ID": settings.PAYTM_CHANNEL_ID,

        "INITIATE_URL": settings.PAYTM_INITIATE_URL,

        # BACKEND ONLY
        "CALLBACK_URL": settings.PAYTM_CALLBACK_URL,
    }

import json
import uuid
from decimal import Decimal

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .payglocal import create_payglocal_payment

import json
import uuid
from decimal import Decimal

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .payglocal import create_payglocal_payment


# @csrf_exempt
# def payglocal_create_payment(request):

#     # --------------------------------------------------
#     # METHOD CHECK
#     # --------------------------------------------------
#     if request.method != "POST":
#         return JsonResponse(
#             {
#                 "success": False,
#                 "message": "POST method required",
#             },
#             status=405,
#         )

#     try:
#         # --------------------------------------------------
#         # READ REQUEST JSON
#         # --------------------------------------------------
#         try:
#             data = json.loads(
#                 request.body.decode("utf-8")
#             )
#         except json.JSONDecodeError:
#             return JsonResponse(
#                 {
#                     "success": False,
#                     "message": "Invalid JSON request",
#                 },
#                 status=400,
#             )

#         # --------------------------------------------------
#         # GET PAYMENT DATA
#         # --------------------------------------------------
#         amount = data.get("amount")
#         currency = data.get("currency", "INR")

#         customer_name = data.get(
#             "customer_name",
#             ""
#         )

#         customer_email = data.get(
#             "customer_email",
#             ""
#         )

#         customer_phone = data.get(
#             "customer_phone",
#             ""
#         )

#         description = data.get(
#             "description",
#             "Herbal Order"
#         )

#         # --------------------------------------------------
#         # AMOUNT REQUIRED
#         # --------------------------------------------------
#         if amount is None:
#             return JsonResponse(
#                 {
#                     "success": False,
#                     "message": "amount is required",
#                 },
#                 status=400,
#             )

#         # --------------------------------------------------
#         # VALIDATE AMOUNT
#         # --------------------------------------------------
#         try:
#             amount_decimal = Decimal(
#                 str(amount)
#             ).quantize(
#                 Decimal("0.01")
#             )

#         except Exception as e:
#             return JsonResponse(
#                 {
#                     "success": False,
#                     "message": "Invalid amount",
#                     "error": str(e),
#                 },
#                 status=400,
#             )

#         # --------------------------------------------------
#         # AMOUNT MUST BE GREATER THAN ZERO
#         # --------------------------------------------------
#         if amount_decimal <= 0:
#             return JsonResponse(
#                 {
#                     "success": False,
#                     "message": "Amount must be greater than 0",
#                 },
#                 status=400,
#             )

#         amount = str(amount_decimal)

#         # --------------------------------------------------
#         # CREATE UNIQUE MERCHANT TRANSACTION ID
#         # --------------------------------------------------
#         merchant_txn_id = (
#             "HERBAL_"
#             + uuid.uuid4().hex[:20].upper()
#         )

#         # --------------------------------------------------
#         callback_url = "https://api.uat.payglocal.in/gl/v1/payments/merchantCallback"


#         # --------------------------------------------------
#         # PAYGLOCAL PAYLOAD
#         # --------------------------------------------------
#         payload = {
#             "merchantTxnId": merchant_txn_id,
#             "merchantCallbackURL": callback_url,
#             "paymentData": {
#                 "totalAmount": str(amount),
#                 "txnCurrency": currency,
#                 "billingData": {
#                     "firstName": customer_name,
#                     "emailId": customer_email,
#                     "phone": customer_phone,
#                 },
#             },
#         }

#         # --------------------------------------------------
#         # CALL PAYGLOCAL
#         # --------------------------------------------------
#         try:
#             response = create_payglocal_payment(
#                 payload
#             )

#         except Exception as e:
#             # This catches PEM/JWE/JWS/key errors
#             return JsonResponse(
#                 {
#                     "success": False,
#                     "message": "PayGlocal key/token creation failed",
#                     "error_type": type(e).__name__,
#                     "error": str(e),
#                 },
#                 status=500,
#             )

#         # --------------------------------------------------
#         # READ PAYGLOCAL RESPONSE
#         # --------------------------------------------------
#         try:
#             response_data = response.json()

#         except Exception:
#             response_data = {
#                 "raw_response": response.text
#             }

#         # --------------------------------------------------
#         # PAYGLOCAL ERROR RESPONSE
#         # --------------------------------------------------
#         if response.status_code not in [200, 201]:
#             return JsonResponse(
#                 {
#                     "success": False,
#                     "message": "PayGlocal payment creation failed",
#                     "http_status": response.status_code,
#                     "merchant_txn_id": merchant_txn_id,
#                     "response": response_data,
#                 },
#                 status=400,
#             )

#         # --------------------------------------------------
#         # SUCCESS
#         # --------------------------------------------------
#         return JsonResponse(
#             {
#                 "success": True,
#                 "message": "PayGlocal payment created",
#                 "merchant_txn_id": merchant_txn_id,
#                 "response": response_data,
#             },
#             status=200,
#         )

#     # --------------------------------------------------
#     # UNEXPECTED ERROR
#     # --------------------------------------------------
#     except Exception as e:
#         return JsonResponse(
#             {
#                 "success": False,
#                 "message": "Failed to create PayGlocal payment",
#                 "error_type": type(e).__name__,
#                 "error": str(e),
#             },
#             status=500,
#         )



import json
import uuid
import base64
import urllib.parse
import requests

from decimal import Decimal

from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt

from .models import Payment, Order, User


# ============================================================
# PAYGLOCAL CREATE PAYMENT
# ============================================================

@csrf_exempt
def payglocal_create_payment(request):

    if request.method != "POST":

        return JsonResponse(
            {
                "success": False,
                "message": "POST method required",
            },
            status=405,
        )

    try:

        # =====================================================
        # READ REQUEST JSON
        # =====================================================

        try:

            data = json.loads(
                request.body.decode("utf-8")
            )

        except json.JSONDecodeError:

            return JsonResponse(
                {
                    "success": False,
                    "message": "Invalid JSON request",
                },
                status=400,
            )

        # =====================================================
        # PAYMENT DATA
        # =====================================================

        amount = data.get("amount")
        currency = data.get(
            "currency",
            "INR",
        )

        customer_name = data.get(
            "customer_name",
            "",
        )

        customer_email = data.get(
            "customer_email",
            "",
        )

        customer_phone = data.get(
            "customer_phone",
            "",
        )

        description = data.get(
            "description",
            "Herbal Order",
        )

        # =====================================================
        # VALIDATE AMOUNT
        # =====================================================

        if amount is None:

            return JsonResponse(
                {
                    "success": False,
                    "message": "amount is required",
                },
                status=400,
            )

        # =====================================================
        # ORDER / USER
        # =====================================================

        order_id = data.get("order_id")
        user_id = data.get("user_id")

        order_obj = None
        customer_obj = None

        if order_id and user_id:

            try:

                order_obj = Order.objects.get(
                    id=order_id
                )

                customer_obj = User.objects.get(
                    id=user_id
                )

                raw_amount = order_obj.total_amount

                if (
                    hasattr(
                        order_obj,
                        "amount_to_pay",
                    )
                    and (
                        order_obj.credit_used > 0
                        or order_obj.amount_to_pay > 0
                    )
                ):

                    raw_amount = (
                        order_obj.amount_to_pay
                    )

                amount = str(raw_amount)

            except (
                Order.DoesNotExist,
                User.DoesNotExist,
            ):

                pass

        # =====================================================
        # DECIMAL AMOUNT
        # =====================================================

        try:

            amount_decimal = Decimal(
                str(amount)
            ).quantize(
                Decimal("0.01")
            )

        except Exception as e:

            return JsonResponse(
                {
                    "success": False,
                    "message": "Invalid amount",
                    "error": str(e),
                },
                status=400,
            )

        if amount_decimal <= 0:

            return JsonResponse(
                {
                    "success": False,
                    "message": "Amount must be greater than 0",
                },
                status=400,
            )

        amount = str(amount_decimal)

        # =====================================================
        # UNIQUE MERCHANT TRANSACTION ID
        # =====================================================

        merchant_txn_id = (
            "HERBAL_"
            + uuid.uuid4().hex[:20].upper()
        )

        # =====================================================
        # PAYGLOCAL CALLBACK
        # =====================================================

        callback_url = (
            "https://api.codingboss.in/"
            "herbal/payglocal/callback/"
        )

        # =====================================================
        # PAYGLOCAL PAYLOAD
        # =====================================================

        payload = {

            "merchantTxnId":
                merchant_txn_id,

            "merchantCallbackURL":
                callback_url,

            "paymentData": {

                "totalAmount":
                    amount,

                "txnCurrency":
                    currency,

                "billingData": {

                    "firstName":
                        customer_name,

                    "emailId":
                        customer_email,

                    "phone":
                        customer_phone,
                },
            },
        }

        print(
            "\n======================================"
        )

        print(
            "PAYGLOCAL CREATE PAYMENT"
        )

        print(
            "======================================"
        )

        print(
            json.dumps(
                payload,
                indent=4,
                default=str,
            )
        )

        # =====================================================
        # CALL PAYGLOCAL
        # =====================================================

        try:

            response = create_payglocal_payment(
                payload
            )

        except Exception as e:

            print(
                "PAYGLOCAL CREATE ERROR:",
                str(e),
            )

            return JsonResponse(
                {
                    "success": False,
                    "message":
                        "PayGlocal key/token creation failed",
                    "error_type":
                        type(e).__name__,
                    "error":
                        str(e),
                },
                status=500,
            )

        # =====================================================
        # RESPONSE
        # =====================================================

        try:

            response_data = response.json()

        except Exception:

            response_data = {
                "raw_response":
                    response.text
            }

        print(
            "\nPAYGLOCAL RESPONSE:"
        )

        print(
            json.dumps(
                response_data,
                indent=4,
                default=str,
            )
        )

        # =====================================================
        # PAYGLOCAL ERROR
        # =====================================================

        if response.status_code not in [
            200,
            201,
        ]:

            return JsonResponse(
                {
                    "success": False,
                    "message":
                        "PayGlocal payment creation failed",
                    "http_status":
                        response.status_code,
                    "merchant_txn_id":
                        merchant_txn_id,
                    "response":
                        response_data,
                },
                status=400,
            )

        # =====================================================
        # GET GID
        # =====================================================

        gl_txn_id = (
            response_data
            .get("data", {})
            .get("gid")
            or response_data.get("gid")
            or response_data.get("glTxnId")
        )

        # =====================================================
        # CREATE LOCAL PAYMENT
        # =====================================================

        if order_obj and customer_obj:

            payment = Payment.objects.create(

                order=order_obj,

                customer=customer_obj,

                amount=amount_decimal,

                payment_gateway="payglocal",

                gateway_order_id=
                    merchant_txn_id,

                gateway_transaction_id=
                    gl_txn_id,

                status="pending",

                gateway_response=
                    response_data,
            )

            print(
                "LOCAL PAYMENT CREATED:",
                payment.id,
            )

        # =====================================================
        # RETURN RESPONSE
        # =====================================================

        return JsonResponse(
            {
                "success": True,
                "message":
                    "PayGlocal payment created",

                "merchant_txn_id":
                    merchant_txn_id,

                "callback_url":
                    callback_url,

                "gid":
                    gl_txn_id,

                "response":
                    response_data,
            },
            status=200,
        )

    except Exception as e:

        print(
            "PAYGLOCAL CREATE UNEXPECTED ERROR:",
            str(e),
        )

        return JsonResponse(
            {
                "success": False,
                "message":
                    "Failed to create PayGlocal payment",
                "error_type":
                    type(e).__name__,
                "error":
                    str(e),
            },
            status=500,
        )


# ============================================================
# PAYGLOCAL CALLBACK
# ============================================================

@csrf_exempt
def payglocal_callback(request):

    print(
        "\n======================================"
    )
    print(
        "PAYGLOCAL CALLBACK RECEIVED"
    )
    print(
        "METHOD:",
        request.method,
    )
    print(
        "GET:",
        dict(request.GET),
    )

    try:
        raw_body = request.body
        print("BODY:", raw_body)
    except Exception as e:
        raw_body = b""
        print("BODY ERROR:", str(e))

    print(
        "======================================"
    )

    try:

        callback_data = {}

        # =====================================================
        # EXTRACT TOKEN
        # =====================================================

        token = ""

        if request.method == "GET":

            callback_data = request.GET.dict()
            token = request.GET.get("x-gl-token", "")

            print(
                "GET CALLBACK DATA:"
            )

            print(
                json.dumps(
                    callback_data,
                    indent=4,
                    default=str,
                )
            )

        elif request.method == "POST":

            raw_body_str = (
                raw_body
                .decode("utf-8")
            )

            print(
                "POST CALLBACK RAW:"
            )

            print(
                raw_body_str
            )

            parsed = (
                urllib.parse
                .parse_qs(raw_body_str)
            )

            token = (
                parsed
                .get(
                    "x-gl-token",
                    [""],
                )[0]
            )

        else:

            return JsonResponse(
                {
                    "success": False,
                    "message":
                        "GET or POST method required",
                },
                status=405,
            )

        # =====================================================
        # DECODE TOKEN
        # =====================================================

        if token:

            print(
                "x-gl-token FOUND"
            )

            parts = token.split(".")

            if len(parts) >= 2:

                payload_b64 = parts[1]

                payload_b64 += (
                    "="
                    * (
                        (
                            4
                            - len(
                                payload_b64
                            ) % 4
                        ) % 4
                    )
                )

                try:

                    payload_json = (
                        base64
                        .urlsafe_b64decode(
                            payload_b64
                        )
                        .decode("utf-8")
                    )

                    callback_data = (
                        json.loads(
                            payload_json
                        )
                    )

                    print(
                        "DECODED TOKEN:"
                    )

                    print(
                        json.dumps(
                            callback_data,
                            indent=4,
                            default=str,
                        )
                    )

                except Exception as e:

                    print(
                        "TOKEN DECODE ERROR:",
                        str(e),
                    )

        # =====================================================
        # JSON FALLBACK
        # =====================================================

        if not callback_data and request.method == "POST":

            try:

                callback_data = (
                    json.loads(
                        raw_body
                    )
                )

            except Exception:

                callback_data = {
                    "raw":
                        raw_body
                }

        # =====================================================
        # CALLBACK DATA
        # =====================================================

        print(
            "\nFINAL CALLBACK DATA:"
        )

        print(
            json.dumps(
                callback_data,
                indent=4,
                default=str,
            )
        )

        # =====================================================
        # EXTRACT VALUES
        # =====================================================

        status = (
            callback_data.get("status")
            or callback_data.get("Status")
            or callback_data.get("paymentStatus")
            or callback_data.get("order_status")
            or "UNKNOWN"
        )

        status = str(status).upper()

        if status in ["SENT_FOR_CAPTURE", "CAPTURED"]:
            status = "SUCCESS"

        merchant_txn_id = (
            callback_data.get(
                "merchantTxnId"
            )
            or callback_data.get(
                "merchant_txn_id"
            )
            or callback_data.get(
                "merchantTransactionId"
            )
            or callback_data.get(
                "order_id"
            )
        )

        gid = (
            callback_data.get("gid")
            or callback_data.get("glTxnId")
            or callback_data.get("txnId")
        )

        amount = (
            callback_data.get("Amount")
            or callback_data.get("amount")
            or callback_data.get(
                "totalAmount"
            )
            or "0.00"
        )

        print(
            "\nPAYGLOCAL PAYMENT INFORMATION"
        )

        print(
            "STATUS:",
            status,
        )

        print(
            "MERCHANT TXN ID:",
            merchant_txn_id,
        )

        print(
            "GID:",
            gid,
        )

        print(
            "AMOUNT:",
            amount,
        )

        # =====================================================
        # FIND LOCAL PAYMENT
        # =====================================================

        payment = None

        if merchant_txn_id:

            payment = (
                Payment.objects
                .filter(
                    gateway_order_id=
                        merchant_txn_id
                )
                .first()
            )

        # =====================================================
        # UPDATE PAYMENT
        # =====================================================

        if payment:

            print(
                "PAYMENT FOUND:",
                payment.id,
            )

            # -------------------------------------------------
            # SUCCESS
            # -------------------------------------------------

            if status == "SUCCESS":

                payment.status = "success"

            # -------------------------------------------------
            # FAILED
            # -------------------------------------------------

            elif status in [
                "FAILED",
                "FAILURE",
                "CANCELLED",
                "CUSTOMER_CANCELLED",
                "PAYMENT_FAILED",
            ]:

                payment.status = "failed"

            # -------------------------------------------------
            # OTHER / PENDING
            # -------------------------------------------------

            else:

                payment.status = "pending"

            # -------------------------------------------------
            # TRANSACTION ID
            # -------------------------------------------------

            if gid:

                payment.gateway_transaction_id = (
                    gid
                )

            # -------------------------------------------------
            # STORE COMPLETE RESPONSE
            # -------------------------------------------------

            payment.gateway_response = (
                callback_data
            )

            payment.save()

            print(
                "PAYMENT STATUS UPDATED:",
                payment.status,
            )

            # =================================================
            # UPDATE ORDER
            # =================================================

            if payment.status == "success":

                order = payment.order

                order.status = "confirmed"

                order.save()

                print(
                    "ORDER STATUS UPDATED:",
                    order.id,
                    "confirmed",
                )

        else:

            print(
                "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
            )

            print(
                "PAYMENT NOT FOUND"
            )

            print(
                "MERCHANT TXN ID:",
                merchant_txn_id,
            )

            print(
                "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
            )

        # =====================================================
        # RESULT PAGE
        # =====================================================

        if status == "SUCCESS":

            color = "#4CAF50"

            status_text = (
                "Payment Successful!"
            )

            message = (
                "Thank you for your order. "
                "Your transaction has been "
                "completed successfully."
            )

            icon = "✓"

        elif status in [
            "CUSTOMER_CANCELLED",
            "CANCELLED",
        ]:

            color = "#FF9800"

            status_text = (
                "Payment Cancelled"
            )

            message = (
                "You have cancelled the "
                "transaction. No charges were made."
            )

            icon = "!"

        else:

            color = "#F44336"

            status_text = (
                "Payment Failed"
            )

            message = (
                "Unfortunately, your transaction "
                "could not be processed."
            )

            icon = "×"

        # =====================================================
        # FRONTEND REDIRECT
        # =====================================================

        if request.method == "GET":

            from django.http import HttpResponseRedirect

            frontend_url = (
                "https://dharaniherbbals.in/checkout"
            )

            return HttpResponseRedirect(
                f"{frontend_url}"
                f"?order_status={status.lower()}"
                f"&order_id={merchant_txn_id}"
            )

        redirect_url = (
            "https://dharaniherbbals.in/"
        )

        # =====================================================
        # HTML RESPONSE
        # =====================================================

        html_content = f"""
        <!DOCTYPE html>

        <html>

        <head>

            <meta charset="utf-8">

            <meta
                name="viewport"
                content="width=device-width, initial-scale=1"
            >

            <meta
                http-equiv="refresh"
                content="5;url={redirect_url}"
            >

            <title>
                {status_text}
            </title>

            <style>

                body {{
                    font-family: Arial, sans-serif;
                    background: #f5f7fa;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    margin: 0;
                }}

                .card {{
                    background: white;
                    width: 90%;
                    max-width: 450px;
                    padding: 40px;
                    border-radius: 20px;
                    text-align: center;
                    box-shadow:
                        0 10px 30px
                        rgba(0,0,0,0.10);
                }}

                .icon {{
                    width: 80px;
                    height: 80px;
                    border-radius: 50%;
                    background: {color};
                    color: white;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    margin: auto;
                    font-size: 45px;
                    font-weight: bold;
                }}

                h1 {{
                    color: #2c3e50;
                    margin-top: 25px;
                }}

                p {{
                    color: #7f8c8d;
                    line-height: 1.6;
                }}

                .details {{
                    background: #f8f9fa;
                    padding: 20px;
                    border-radius: 12px;
                    margin-top: 25px;
                    text-align: left;
                }}

                .row {{
                    display: flex;
                    justify-content: space-between;
                    margin-bottom: 12px;
                }}

                .label {{
                    color: #888;
                }}

                .value {{
                    font-weight: bold;
                    color: #333;
                    text-align: right;
                    word-break: break-word;
                }}

                .btn {{
                    display: block;
                    margin-top: 25px;
                    padding: 15px;
                    background: {color};
                    color: white;
                    text-decoration: none;
                    border-radius: 10px;
                    font-weight: bold;
                }}

                .redirect {{
                    margin-top: 15px;
                    font-size: 13px;
                    color: #aaa;
                }}

            </style>

        </head>

        <body>

            <div class="card">

                <div class="icon">
                    {icon}
                </div>

                <h1>
                    {status_text}
                </h1>

                <p>
                    {message}
                </p>

                <div class="details">

                    <div class="row">

                        <span class="label">
                            Amount
                        </span>

                        <span class="value">
                            ₹ {amount}
                        </span>

                    </div>

                    <div class="row">

                        <span class="label">
                            Transaction ID
                        </span>

                        <span class="value">
                            {merchant_txn_id or "N/A"}
                        </span>

                    </div>

                    <div class="row">

                        <span class="label">
                            Gateway ID
                        </span>

                        <span class="value">
                            {gid or "N/A"}
                        </span>

                    </div>

                    <div class="row">

                        <span class="label">
                            Status
                        </span>

                        <span
                            class="value"
                            style="color:{color}"
                        >
                            {status}
                        </span>

                    </div>

                </div>

                <a
                    href="{redirect_url}"
                    class="btn"
                >
                    Return to Dharani Herbbals
                </a>

                <div class="redirect">
                    Redirecting you automatically
                    in 5 seconds...
                </div>

            </div>

        </body>

        </html>
        """

        return HttpResponse(
            html_content
        )

    except Exception as e:

        print(
            "PAYGLOCAL CALLBACK ERROR:",
            str(e),
        )

        return HttpResponse(
            f"""
            <h3>
                Error processing callback
            </h3>

            <p>
                {str(e)}
            </p>
            """,
            status=500,
        )


# ============================================================
# PAYGLOCAL STATUS
# ============================================================

@csrf_exempt
def payglocal_status(request):

    if request.method != "POST":

        return JsonResponse(
            {
                "success": False,
                "message":
                    "POST method required",
            },
            status=405,
        )

    try:

        # =====================================================
        # READ REQUEST
        # =====================================================

        try:

            data = json.loads(
                request.body.decode("utf-8")
            )

        except json.JSONDecodeError:

            return JsonResponse(
                {
                    "success": False,
                    "message":
                        "Invalid JSON request",
                },
                status=400,
            )

        gid = data.get("gid")

        merchant_txn_id = data.get(
            "merchant_txn_id"
        )

        # =====================================================
        # VALIDATE
        # =====================================================

        if not gid and not merchant_txn_id:

            return JsonResponse(
                {
                    "success": False,
                    "message":
                        "gid or merchant_txn_id is required",
                },
                status=400,
            )

        # =====================================================
        # FIND PAYMENT
        # =====================================================

        payment = None

        if merchant_txn_id:

            payment = (
                Payment.objects
                .filter(
                    gateway_order_id=
                        merchant_txn_id
                )
                .first()
            )

        # =====================================================
        # PAYGLOCAL STATUS URL
        # =====================================================

        if gid:

            url = (
                settings.PAYGLOCAL_BASE_URL
                + f"/gl/v1/payments/{gid}/status"
            )

        else:

            url = (
                settings.PAYGLOCAL_BASE_URL
                + "/gl/v1/payments/status"
            )

        print(
            "\n======================================"
        )

        print(
            "PAYGLOCAL STATUS CHECK"
        )

        print(
            "URL:",
            url,
        )

        print(
            "GID:",
            gid,
        )

        print(
            "MERCHANT TXN:",
            merchant_txn_id,
        )

        print(
            "======================================"
        )

        # =====================================================
        # REQUEST PAYGLOCAL
        # =====================================================

        response = requests.get(

            url,

            headers={
                "Accept":
                    "application/json",

                "x-gl-auth":
                    settings.PAYGLOCAL_API_KEY,
            },

            timeout=30,
        )

        # =====================================================
        # RESPONSE
        # =====================================================

        try:

            response_data = (
                response.json()
            )

        except Exception:

            response_data = {
                "raw_response":
                    response.text
            }

        print(
            "PAYGLOCAL STATUS RESPONSE:"
        )

        print(
            json.dumps(
                response_data,
                indent=4,
                default=str,
            )
        )

        # =====================================================
        # EXTRACT STATUS
        # =====================================================

        gateway_status = (

            response_data.get(
                "status"
            )

            or response_data.get(
                "Status"
            )

            or response_data
            .get("data", {})
            .get("status")

            or response_data
            .get("paymentData", {})
            .get("status")
        )

        if gateway_status:

            gateway_status = str(
                gateway_status
            ).upper()

        gateway_gid = (

            response_data.get(
                "gid"
            )

            or response_data
            .get("data", {})
            .get("gid")

            or response_data.get(
                "glTxnId"
            )

            or gid
        )

        # =====================================================
        # UPDATE LOCAL DATABASE
        # =====================================================

        if payment:

            print(
                "LOCAL PAYMENT FOUND:",
                payment.id,
            )

            # -------------------------------------------------
            # SUCCESS
            # -------------------------------------------------

            if gateway_status == "SUCCESS":

                payment.status = (
                    "success"
                )

            # -------------------------------------------------
            # FAILED
            # -------------------------------------------------

            elif gateway_status in [
                "FAILED",
                "FAILURE",
                "CANCELLED",
                "CUSTOMER_CANCELLED",
                "PAYMENT_FAILED",
            ]:

                payment.status = (
                    "failed"
                )

            # -------------------------------------------------
            # PENDING
            # -------------------------------------------------

            else:

                payment.status = (
                    "pending"
                )

            # -------------------------------------------------
            # GID
            # -------------------------------------------------

            if gateway_gid:

                payment.gateway_transaction_id = (
                    gateway_gid
                )

            # -------------------------------------------------
            # SAVE RESPONSE
            # -------------------------------------------------

            payment.gateway_response = (
                response_data
            )

            payment.save()

            print(
                "LOCAL PAYMENT STATUS:",
                payment.status,
            )

            # =================================================
            # UPDATE ORDER
            # =================================================

            if payment.status == "success":

                order = payment.order

                order.status = "confirmed"

                order.save()

                print(
                    "ORDER CONFIRMED:",
                    order.id,
                )

        else:

            print(
                "LOCAL PAYMENT NOT FOUND"
            )

        # =====================================================
        # RETURN RESPONSE
        # =====================================================

        return JsonResponse(
            {
                "success":
                    response.ok,

                "http_status":
                    response.status_code,

                "gateway_status":
                    gateway_status,

                "merchant_txn_id":
                    merchant_txn_id,

                "gid":
                    gateway_gid,

                "local_payment_id":
                    payment.id
                    if payment
                    else None,

                "local_payment_status":
                    payment.status
                    if payment
                    else None,

                "data":
                    response_data,
            },
            status=response.status_code,
        )

    except requests.exceptions.Timeout:

        return JsonResponse(
            {
                "success": False,
                "message":
                    "PayGlocal status request timed out",
            },
            status=504,
        )

    except requests.exceptions.RequestException as e:

        print(
            "PAYGLOCAL STATUS REQUEST ERROR:",
            str(e),
        )

        return JsonResponse(
            {
                "success": False,
                "message":
                    "Failed to connect to PayGlocal",
                "error":
                    str(e),
            },
            status=502,
        )

    except Exception as e:

        print(
            "PAYGLOCAL STATUS ERROR:",
            str(e),
        )

        return JsonResponse(
            {
                "success": False,
                "message":
                    "Failed to check payment status",
                "error_type":
                    type(e).__name__,
                "error":
                    str(e),
            },
            status=500,
        )
    
# @csrf_exempt
# def payglocal_create_payment(request):
    

#     if request.method != "POST":
#         return JsonResponse(
#             {
#                 "success": False,
#                 "message": "POST method required",
#             },
#             status=405,
#         )
    
#     try:
    
#         # --------------------------------------------------
#         # READ REQUEST JSON
#         # --------------------------------------------------
    
#         try:
#             data = json.loads(
#                 request.body.decode("utf-8")
#             )
    
#         except json.JSONDecodeError:
#             return JsonResponse(
#                 {
#                     "success": False,
#                     "message": "Invalid JSON request",
#                 },
#                 status=400,
#             )
    
#         # --------------------------------------------------
#         # PAYMENT DATA
#         # --------------------------------------------------
    
#         amount = data.get("amount")
#         currency = data.get("currency", "INR")
    
#         customer_name = data.get(
#             "customer_name",
#             "",
#         )
    
#         customer_email = data.get(
#             "customer_email",
#             "",
#         )
    
#         customer_phone = data.get(
#             "customer_phone",
#             "",
#         )
    
#         description = data.get(
#             "description",
#             "Herbal Order",
#         )
    
#         # --------------------------------------------------
#         # AMOUNT REQUIRED
#         # --------------------------------------------------
    
#         if amount is None:
#             return JsonResponse(
#                 {
#                     "success": False,
#                     "message": "amount is required",
#                 },
#                 status=400,
#             )
    
#         # --------------------------------------------------
#         # VALIDATE AMOUNT & HANDLE ORDER
#         # --------------------------------------------------
    
#         order_id = data.get("order_id")
#         user_id = data.get("user_id")
#         order_obj = None
#         customer_obj = None
        
#         if order_id and user_id:
#             try:
#                 order_obj = Order.objects.get(id=order_id)
#                 customer_obj = User.objects.get(id=user_id)
                
#                 raw_amount = order_obj.total_amount
#                 if hasattr(order_obj, 'amount_to_pay') and (order_obj.credit_used > 0 or order_obj.amount_to_pay > 0):
#                     raw_amount = order_obj.amount_to_pay
                    
#                 amount = str(raw_amount)
#             except (Order.DoesNotExist, User.DoesNotExist):
#                 pass

#         try:
    
#             amount_decimal = Decimal(
#                 str(amount)
#             ).quantize(
#                 Decimal("0.01")
#             )
    
#         except Exception as e:
    
#             return JsonResponse(
#                 {
#                     "success": False,
#                     "message": "Invalid amount",
#                     "error": str(e),
#                 },
#                 status=400,
#             )
    
#         if amount_decimal <= 0:
#             return JsonResponse(
#                 {
#                     "success": False,
#                     "message": "Amount must be greater than 0",
#                 },
#                 status=400,
#             )
    
#         amount = str(amount_decimal)
    
#         # --------------------------------------------------
#         # UNIQUE MERCHANT TRANSACTION ID
#         # --------------------------------------------------
    
#         merchant_txn_id = (
#             "HERBAL_"
#             + uuid.uuid4().hex[:20].upper()
#         )
    
#         # --------------------------------------------------
#         # YOUR DJANGO CALLBACK URL
#         # --------------------------------------------------
    
#         callback_url = "https://api.codingboss.in/herbal/payglocal/callback/"
    
#         # --------------------------------------------------
#         # PAYGLOCAL PAYLOAD
#         # --------------------------------------------------
    
#         payload = {
#             "merchantTxnId": merchant_txn_id,
    
#             "merchantCallbackURL": callback_url,
    
#             "paymentData": {
#                 "totalAmount": amount,
    
#                 "txnCurrency": currency,
    
#                 "billingData": {
#                     "firstName": customer_name,
#                     "emailId": customer_email,
#                     "phone": customer_phone,
#                 },
#             },
#         }
    
#         print(
#             "PAYGLOCAL REQUEST PAYLOAD:"
#         )
    
#         print(
#             json.dumps(
#                 payload,
#                 indent=4,
#             )
#         )
    
#         # --------------------------------------------------
#         # CALL PAYGLOCAL
#         # --------------------------------------------------
    
#         try:
    
#             response = create_payglocal_payment(
#                 payload
#             )
    
#         except Exception as e:
    
#             return JsonResponse(
#                 {
#                     "success": False,
#                     "message": (
#                         "PayGlocal key/token "
#                         "creation failed"
#                     ),
#                     "error_type": type(e).__name__,
#                     "error": str(e),
#                 },
#                 status=500,
#             )
    
#         # --------------------------------------------------
#         # READ RESPONSE
#         # --------------------------------------------------
    
#         try:
    
#             response_data = response.json()
    
#         except Exception:
    
#             response_data = {
#                 "raw_response": response.text
#             }
    
#         print(
#             "PAYGLOCAL RESPONSE:"
#         )
    
#         print(
#             json.dumps(
#                 response_data,
#                 indent=4,
#                 default=str,
#             )
#         )
    
#         # --------------------------------------------------
#         # PAYGLOCAL ERROR
#         # --------------------------------------------------
    
#         if response.status_code not in [
#             200,
#             201,
#         ]:
    
#             return JsonResponse(
#                 {
#                     "success": False,
#                     "message": (
#                         "PayGlocal payment "
#                         "creation failed"
#                     ),
#                     "http_status": response.status_code,
#                     "merchant_txn_id": merchant_txn_id,
#                     "response": response_data,
#                 },
#                 status=400,
#             )
    
#         # --------------------------------------------------
#         # SUCCESS
#         # --------------------------------------------------
    
#         if order_obj and customer_obj:
#             gl_txn_id = response_data.get("data", {}).get("gid") or response_data.get("gid")
#             Payment.objects.create(
#                 order=order_obj,
#                 customer=customer_obj,
#                 amount=amount_decimal,
#                 payment_gateway="payglocal",
#                 gateway_order_id=merchant_txn_id,
#                 gateway_transaction_id=gl_txn_id,
#                 status="pending",
#                 gateway_response=response_data
#             )

#         return JsonResponse(
#             {
#                 "success": True,
#                 "message": (
#                     "PayGlocal payment created"
#                 ),
#                 "merchant_txn_id": merchant_txn_id,
#                 "callback_url": callback_url,
#                 "response": response_data,
#             },
#             status=200,
#         )
    
#     # --------------------------------------------------
#     # UNEXPECTED ERROR
#     # --------------------------------------------------
    
#     except Exception as e:
    
#         return JsonResponse(
#             {
#                 "success": False,
#                 "message": (
#                     "Failed to create "
#                     "PayGlocal payment"
#                 ),
#                 "error_type": type(e).__name__,
#                 "error": str(e),
#             },
#             status=500,
#         )
    

# @csrf_exempt
# def payglocal_callback(request):

#     if request.method != "POST":

#         return JsonResponse(
#             {
#                 "success": False,
#                 "message": "POST method required"
#             },
#             status=405
#         )

#     try:
#         import urllib.parse
#         import base64
        
#         raw_body = request.body.decode("utf-8")
#         print("PAYGLOCAL CALLBACK RAW:", raw_body)

#         # Extract token from form data
#         parsed = urllib.parse.parse_qs(raw_body)
#         token = parsed.get("x-gl-token", [""])[0]
        
#         callback_data = {}
#         if token:
#             parts = token.split(".")
#             if len(parts) >= 2:
#                 payload_b64 = parts[1]
#                 payload_b64 += "=" * ((4 - len(payload_b64) % 4) % 4)
#                 try:
#                     payload_json = base64.urlsafe_b64decode(payload_b64).decode('utf-8')
#                     callback_data = json.loads(payload_json)
#                 except Exception as e:
#                     print("Failed to decode token payload:", e)
        
#         # If no token, fallback to JSON body if possible
#         if not callback_data:
#             try:
#                 callback_data = json.loads(raw_body)
#             except Exception:
#                 callback_data = {"raw": raw_body}

#         status = callback_data.get("status", "UNKNOWN")
#         amount = callback_data.get("Amount", "0.00")
#         txn_id = callback_data.get("merchantTxnId", "N/A")
        
#         if status == "SUCCESS":
#             color = "#4CAF50"
#             icon_html = """
#             <svg class="animate-svg checkmark" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 52 52">
#               <circle class="checkmark__circle" cx="26" cy="26" r="25" fill="none"/>
#               <path class="checkmark__check" fill="none" d="M14.1 27.2l7.1 7.2 16.7-16.8"/>
#             </svg>
#             """
#             status_text = "Payment Successful!"
#             message = "Thank you for your order. Your transaction has been completed successfully."
#         elif status == "CUSTOMER_CANCELLED":
#             color = "#FF9800"
#             icon_html = """
#             <svg class="animate-svg warning" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 52 52">
#               <circle class="warning__circle" cx="26" cy="26" r="25" fill="none"/>
#               <path class="warning__line" fill="none" d="M26 15 v14"/>
#               <circle class="warning__dot" cx="26" cy="38" r="2" fill="#FF9800"/>
#             </svg>
#             """
#             status_text = "Payment Cancelled"
#             message = "You have cancelled the transaction. No charges were made."
#         else:
#             color = "#F44336"
#             icon_html = """
#             <svg class="animate-svg cross" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 52 52">
#               <circle class="cross__circle" cx="26" cy="26" r="25" fill="none"/>
#               <path class="cross__path cross__path--right" fill="none" d="M16,16 l20,20" />
#               <path class="cross__path cross__path--left" fill="none" d="M16,36 l20,-20" />
#             </svg>
#             """
#             status_text = "Payment Failed"
#             message = "Unfortunately, your transaction could not be processed at this time."

#         # Update Payment record if exists
#         try:
#             payment = Payment.objects.filter(gateway_order_id=txn_id).first()
#             if payment:
#                 if status == "SUCCESS":
#                     payment.status = "success"
#                 else:
#                     payment.status = "failed"
                    
#                 # Save the Payglocal transaction ID (gid / glTxnId)
#                 gl_txn_id = callback_data.get("gid") or callback_data.get("glTxnId") or callback_data.get("txnId")
#                 if gl_txn_id:
#                     payment.gateway_transaction_id = gl_txn_id
                
#                 payment.gateway_response = callback_data
#                 payment.save()
                
#                 # Update order status if payment successful
#                 if payment.status == "success":
#                     order = payment.order
#                     order.status = "confirmed"
#                     order.save()
#         except Exception as e:
#             print("Error updating payment in callback:", e)

#         redirect_url = "https://erp.dharaniherbbals.in/"

#         html_content = f"""
#         <!DOCTYPE html>
#         <html>
#         <head>
#             <meta charset="utf-8">
#             <meta name="viewport" content="width=device-width, initial-scale=1">
#             <meta http-equiv="refresh" content="5;url={redirect_url}" />
#             <title>{status_text}</title>
#             <style>
#                 @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap');
                
#                 body {{
#                     font-family: 'Poppins', sans-serif;
#                     background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
#                     display: flex;
#                     justify-content: center;
#                     align-items: center;
#                     height: 100vh;
#                     margin: 0;
#                     overflow: hidden;
#                 }}
                
#                 .card {{
#                     background: white;
#                     padding: 40px;
#                     border-radius: 20px;
#                     box-shadow: 0 15px 35px rgba(0,0,0,0.1);
#                     text-align: center;
#                     max-width: 420px;
#                     width: 90%;
#                     transform: translateY(30px);
#                     opacity: 0;
#                     animation: slideUpFade 0.6s ease-out forwards;
#                 }}

#                 @keyframes slideUpFade {{
#                     to {{ transform: translateY(0); opacity: 1; }}
#                 }}

#                 h1 {{
#                     color: #2c3e50;
#                     font-size: 26px;
#                     margin: 15px 0 10px;
#                     font-weight: 600;
#                     opacity: 0;
#                     animation: fadeIn 0.5s ease-out 0.4s forwards;
#                 }}

#                 p {{
#                     color: #7f8c8d;
#                     font-size: 15px;
#                     margin-bottom: 25px;
#                     line-height: 1.6;
#                     opacity: 0;
#                     animation: fadeIn 0.5s ease-out 0.5s forwards;
#                 }}

#                 .details {{
#                     background: #f8f9fa;
#                     padding: 20px;
#                     border-radius: 12px;
#                     text-align: left;
#                     margin-bottom: 30px;
#                     border: 1px solid #edf2f7;
#                     opacity: 0;
#                     animation: fadeIn 0.5s ease-out 0.6s forwards;
#                 }}

#                 .details-row {{ display: flex; justify-content: space-between; margin-bottom: 12px; }}
#                 .details-row:last-child {{ margin-bottom: 0; }}
#                 .details-label {{ color: #95a5a6; font-weight: 500; font-size: 14px; }}
#                 .details-value {{ color: #2c3e50; font-weight: 600; font-size: 14px; text-align: right; }}

#                 .btn {{
#                     display: block;
#                     padding: 15px 20px;
#                     background-color: {color};
#                     color: white;
#                     text-decoration: none;
#                     border-radius: 10px;
#                     font-weight: 600;
#                     font-size: 16px;
#                     transition: transform 0.2s, box-shadow 0.2s;
#                     opacity: 0;
#                     animation: fadeIn 0.5s ease-out 0.7s forwards;
#                     box-shadow: 0 4px 15px {color}40;
#                 }}

#                 .btn:hover {{ transform: translateY(-2px); box-shadow: 0 6px 20px {color}60; }}
                
#                 .redirect-msg {{
#                     margin-top: 15px;
#                     font-size: 13px;
#                     color: #bdc3c7;
#                     opacity: 0;
#                     animation: fadeIn 0.5s ease-out 0.8s forwards;
#                 }}

#                 @keyframes fadeIn {{ to {{ opacity: 1; }} }}

#                 /* SVG Animations */
#                 .animate-svg {{ width: 80px; height: 80px; margin: 0 auto; display: block; }}
                
#                 /* Checkmark */
#                 .checkmark__circle {{ stroke-dasharray: 166; stroke-dashoffset: 166; stroke-width: 2; stroke-miterlimit: 10; stroke: {color}; fill: none; animation: stroke 0.6s cubic-bezier(0.65, 0, 0.45, 1) forwards; }}
#                 .checkmark__check {{ transform-origin: 50% 50%; stroke-dasharray: 48; stroke-dashoffset: 48; stroke-width: 3; stroke-linecap: round; stroke-linejoin: round; stroke: {color}; animation: stroke 0.3s cubic-bezier(0.65, 0, 0.45, 1) 0.6s forwards; }}
                
#                 /* Cross */
#                 .cross__circle {{ stroke-dasharray: 166; stroke-dashoffset: 166; stroke-width: 2; stroke-miterlimit: 10; stroke: {color}; fill: none; animation: stroke 0.6s cubic-bezier(0.65, 0, 0.45, 1) forwards; }}
#                 .cross__path {{ stroke-dasharray: 48; stroke-dashoffset: 48; stroke-width: 3; stroke-linecap: round; stroke-linejoin: round; stroke: {color}; }}
#                 .cross__path--right {{ animation: stroke 0.3s cubic-bezier(0.65, 0, 0.45, 1) 0.5s forwards; }}
#                 .cross__path--left {{ animation: stroke 0.3s cubic-bezier(0.65, 0, 0.45, 1) 0.7s forwards; }}
                
#                 /* Warning */
#                 .warning__circle {{ stroke-dasharray: 166; stroke-dashoffset: 166; stroke-width: 2; stroke-miterlimit: 10; stroke: {color}; fill: none; animation: stroke 0.6s cubic-bezier(0.65, 0, 0.45, 1) forwards; }}
#                 .warning__line {{ stroke-dasharray: 20; stroke-dashoffset: 20; stroke-width: 3; stroke-linecap: round; stroke: {color}; animation: stroke 0.3s cubic-bezier(0.65, 0, 0.45, 1) 0.5s forwards; }}
                
#                 @keyframes stroke {{ 100% {{ stroke-dashoffset: 0; }} }}
#             </style>
#         </head>
#         <body>
#             <div class="card">
#                 {icon_html}
#                 <h1>{status_text}</h1>
#                 <p>{message}</p>
#                 <div class="details">
#                     <div class="details-row">
#                         <span class="details-label">Amount</span>
#                         <span class="details-value">₹ {amount}</span>
#                     </div>
#                     <div class="details-row">
#                         <span class="details-label">Transaction ID</span>
#                         <span class="details-value">{txn_id}</span>
#                     </div>
#                     <div class="details-row">
#                         <span class="details-label">Status</span>
#                         <span class="details-value" style="color: {color}">{status}</span>
#                     </div>
#                 </div>
#                 <a href="{redirect_url}" class="btn">Return to Dharani Herbbals</a>
#                 <div class="redirect-msg">Redirecting you automatically in 5 seconds...</div>
#             </div>
#         </body>
#         </html>
#         """
        
#         from django.http import HttpResponse
#         return HttpResponse(html_content)

#     except Exception as e:
#         from django.http import HttpResponse
#         return HttpResponse(f"<h3>Error processing callback: {str(e)}</h3>", status=500)

# @csrf_exempt
# def payglocal_status(request):

#     if request.method != "POST":

#         return JsonResponse(
#             {
#                 "success": False,
#                 "message": "POST method required"
#             },
#             status=405
#         )

#     try:

#         data = json.loads(
#             request.body.decode("utf-8")
#         )

#         gid = data.get("gid")
#         merchant_txn_id = data.get(
#             "merchant_txn_id"
#         )

#         if not gid and not merchant_txn_id:

#             return JsonResponse(
#                 {
#                     "success": False,
#                     "message": (
#                         "gid or merchant_txn_id "
#                         "is required"
#                     )
#                 },
#                 status=400
#             )

#         if gid:

#             url = (
#                 settings.PAYGLOCAL_BASE_URL
#                 + f"/gl/v1/payments/{gid}/status"
#             )

#         else:

#             url = (
#                 settings.PAYGLOCAL_BASE_URL
#                 + "/gl/v1/payments/status"
#             )

#         response = requests.get(
#             url,
#             headers={
#                 "Accept": "application/json",
#                 "x-gl-auth": (
#                     settings.PAYGLOCAL_API_KEY
#                 )
#             },
#             timeout=30
#         )

#         try:
#             response_data = response.json()
#         except Exception:
#             response_data = {
#                 "raw_response": response.text
#             }

#         return JsonResponse(
#             {
#                 "success": response.ok,
#                 "http_status": response.status_code,
#                 "data": response_data
#             },
#             status=response.status_code
#         )

#     except Exception as e:

#         return JsonResponse(
#             {
#                 "success": False,
#                 "message": "Failed to check payment status",
#                 "error": str(e)
#             },
#             status=500
#         )

#     import requests

# from django.http import JsonResponse
# from django.views.decorators.csrf import csrf_exempt


ERP_BASE_URL = "http://cland.southindia.cloudapp.azure.com/InvNETWebApiV3"


@csrf_exempt
def erp_proxy(request):
    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "message": "POST method required",
            },
            status=405,
        )

    try:
        data = json.loads(request.body.decode("utf-8"))

        path = data.get("path", "")
        method = data.get("method", "GET").upper()
        headers = data.get("headers", {})
        payload = data.get("payload", {})

        if not path:
            return JsonResponse(
                {
                    "success": False,
                    "message": "ERP path is required",
                },
                status=400,
            )

        # Security: allow only ERP API paths
        if not path.startswith("/api/"):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Invalid ERP path",
                },
                status=400,
            )

        # Prevent frontend from overriding the target server
        headers.pop("Host", None)
        headers.pop("Content-Length", None)

        erp_url = f"{ERP_BASE_URL}{path}"

        response = requests.request(
            method=method,
            url=erp_url,
            headers=headers,
            json=payload,
            timeout=60,
        )

        # Return ERP response as-is
        return JsonResponse(
            response.json(),
            status=response.status_code,
            safe=False,
        )

    except requests.exceptions.Timeout:
        return JsonResponse(
            {
                "success": False,
                "message": "ERP server timeout",
            },
            status=504,
        )

    except requests.exceptions.RequestException as e:
        return JsonResponse(
            {
                "success": False,
                "message": "ERP connection failed",
                "error": str(e),
            },
            status=502,
        )

    except json.JSONDecodeError:
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid JSON request",
            },
            status=400,
        )

    except Exception as e:
        return JsonResponse(
            {
                "success": False,
                "message": "ERP proxy error",
                "error": str(e),
            },
            status=500,
        )