from datetime import timedelta
from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MEDIA_ROOT = os.path.join(BASE_DIR, "media")

SECRET_KEY = "django-insecure-qy99_@e#dcu^cbt$=dazit$_)5yz)f_6cmkpxu9r-a9)iq90"

# whatsapp key

WATI_BASE_URL  = "https://live-mt-server.wati.io/10121744"

WATI_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1bmlxdWVfbmFtZSI6InN1bmRhcnBweUBnbWFpbC5jb20iLCJuYW1laWQiOiJzdW5kYXJwcHlAZ21haWwuY29tIiwiZW1haWwiOiJzdW5kYXJwcHlAZ21haWwuY29tIiwiYXV0aF90aW1lIjoiMDcvMDIvMjAyNiAxMzoxMTozNCIsInRlbmFudF9pZCI6IjEwMTIxNzQ0IiwiZGJfbmFtZSI6Im10LXByb2QtVGVuYW50cyIsImh0dHA6Ly9zY2hlbWFzLm1pY3Jvc29mdC5jb20vd3MvMjAwOC8wNi9pZGVudGl0eS9jbGFpbXMvcm9sZSI6IkFETUlOSVNUUkFUT1IiLCJleHAiOjI1MzQwMjMwMDgwMCwiaXNzIjoiQ2xhcmVfQUkiLCJhdWQiOiJDbGFyZV9BSSJ9.BSpNmRZ0jglpffHNYxfARbZyX9q6vFP93G3HaqvmCOs"

# ================================
# WATI CONFIGURATION
# ================================

import os

WATI_BASE_URL = os.getenv(
    "WATI_BASE_URL",
    "https://live-mt-server.wati.io/10121744"
)

WATI_API_TOKEN = os.getenv(
    "WATI_API_TOKEN"
)

# WhatsApp Order Placed Template
WATI_ORDER_PLACED_TEMPLATE_ID = "6ad274a51a7a62edb55f5e2e"
WATI_ORDER_PLACED_TEMPLATE_NAME = "dharani_order_placed"

# ==========================================
# WATI DEBUG
# ==========================================

# print("========== WATI SETTINGS ==========")
# print("WATI BASE URL:", WATI_BASE_URL)
# print("WATI TOKEN EXISTS:", bool(WATI_API_TOKEN))
# print("WATI TOKEN LENGTH:", len(WATI_API_TOKEN or ""))


# WATI_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1bmlxdWVfbmFtZSI6InN1bmRhcnBweUBnbWFpbC5jb20iLCJuYW1laWQiOiJzdW5kYXJwcHlAZ21haWwuY29tIiwiZW1haWwiOiJzdW5kYXJwcHlAZ21haWwuY29tIiwiYXV0aF90aW1lIjoiMDcvMDIvMjAyNiAxMjo0MDowMyIsInRlbmFudF9pZCI6IjEwMTIxNzQ0IiwiZGJfbmFtZSI6Im10LXByb2QtVGVuYW50cyIsImh0dHA6Ly9zY2hlbWFzLm1pY3Jvc29mdC5jb20vd3MvMjAwOC8wNi9pZGVudGl0eS9jbGFpbXMvcm9sZSI6IkFETUlOSVNUUkFUT1IiLCJleHAiOjI1MzQwMjMwMDgwMCwiaXNzIjoiQ2xhcmVfQUkiLCJhdWQiOiJDbGFyZV9BSSJ9.JEGP8jA8D9yOZw-79ye6mH1LrPI6329CkXbEMTxzAUw"
# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True
# DEBUG = False

# APPEND_SLASH = False

import os
from pathlib import Path

# ===============================
# Java environment for compiler
# ===============================
JAVA_HOME = "/usr/lib/jvm/java-17-openjdk-amd64"
os.environ["JAVA_HOME"] = JAVA_HOME

# Make sure javac/java are in PATH
os.environ["PATH"] = f"/usr/bin:/bin:/usr/local/bin:{JAVA_HOME}/bin:{os.environ.get('PATH', '')}"


# ALLOWED_HOSTS =[
#     "147.93.27.229",
#     "145.79.13.8",
#     "localhost",
#     "172.18.16.1",
#     "192.168.1.7",
#     "127.0.0.1",
#     "api.codingboss.in",
#     "api-dev.thiran360ai.com",
#     "192.168.1.100",
#     "192.168.1.48",
#     "192.168.1.36",
#     "59.97.51.97",
#     "api-dev.thiran360ai.com",
#     "codingboss.in",
#     "59.97.51.97:8081",
#     "192.168.1.33:8082",
#     "192.168.1.33",
#     "manojsteels.com",
#     '192.168.43.50',
#     "www.raanuvaveeranspokenhindiacademy.com",
#     "store.rubywellnesscenter.com",
#     "raanuvaveeranspokenhindiacademy.com",
#     "coding-boss.vercel.app",
#     "crm.stgesports.in",
#     "mail.codingboss.in",
#     "127.0.0.1",
#     "localhost",
#     "vedanmart.com",
#     "localhost:5173",
#     "eb4b-223-182-207-69.ngrok-free.app"
# ]
ALLOWED_HOSTS = [
    "api.codingboss.in",
    "api-dev.thiran360ai.com",
    "codingboss.in",
    "localhost",
    "127.0.0.1",
    "145.79.13.8",
    "147.93.27.229",
    "59.97.51.97",
    "192.168.1.33",
    "192.168.1.36",
    "192.168.1.48",
    "192.168.1.100",
    "192.168.43.50",
    "manojsteels.com",
    "crm.vedanmart.com",
    "vedanmart.com",
    "coding-boss.vercel.app",
    "melany-countable-patti.ngrok-free.dev",
    "crm.gobi360",
    "gobi360",
    "ramcare.in",
    "crm.ramcare.in",
    "api.prod.payglocal.in",
    "dharaniherbbals.in",
    "erp.dharaniherbbals.in",
    "crmerp.dharaniherbbals.in",
    "cland.southindia.cloudapp.azure.com",
    "179.197.251.47",
    "179.197.251.47:30080",
    
]

CORS_ALLOW_HEADERS = [
    "Accept",
    "Accept-Encoding",
    "Accept-Language",
    "Connection",
    "Content-Length",
    "Content-Type",
    "Host",
    "Origin",
    "Referer",
    "User-Agent",
    "ngrok-skip-browser-warning",
    "strict-origin-when-cross-origin",
    "viral-motto-customs.ngrok-free.dev",
    'concise-egomaniac-starved.ngrok-free.dev',
    "company-shaping-explode.ngrok-free.dev",
    "primary-sculpture-empathy.ngrok-free.dev",
]


CSRF_TRUSTED_ORIGINS = [
    
    "https://codingboss.in",
    "http://179.197.251.47",
    "https://www.codingboss.in",
    "https://api.codingboss.in",
    "http://localhost:5173",
    "http://localhost:5174",
    "https://www.raanuvaveeranspokenhindiacademy.com",
    "https://raanuvaveeranspokenhindiacademy.com",
    "https://store.rubywellnesscenter.com",
    "https://ecom.thiran360ai.com/",
    "https://coding-boss.vercel.app",
    "https://user-concerned-deduct.ngrok-free.dev",
    "https://eb4b-223-182-207-69.ngrok-free.app",
    "https://manojsteels.com",
    "https://hindi-academy-virid.vercel.app/",
    "https://crm.gobi360/",
    "https://gobi360/",
    "http://127.0.0.1:8000",
    "https://dharaniherbbals.in",
    "https://erp.dharaniherbbals.in",
    "https://crmerp.dharaniherbbals.in",
    "https://a5f7-103-175-108-105.ngrok-free.app",
    "https://melany-countable-patti.ngrok-free.dev",
    "http://crm.stgesports.in",
    "https://mail.codingboss.in",
    "https://crm.vedanmart.com/",
    "https://vedanmart.com/",
    "https://api.prod.payglocal.in",
    "https://crm.ramcare.in",
    "https://f58f-103-175-108-212.ngrok-free.app",
    "https://viral-motto-customs.ngrok-free.dev/api/paytm/callback/",
    "http://cland.southindia.cloudapp.azure.com",
    
]

CORS_ALLOWED_ORIGINS = [
    "http://179.197.251.47",
    "https://dharaniherbbals.in",
    "https://erp.dharaniherbbals.in",
    "https://crmerp.dharaniherbbals.in",
    "https://f58f-103-175-108-212.ngrok-free.app",
    "https://www.raanuvaveeranspokenhindiacademy.com",
    "https://melany-countable-patti.ngrok-free.dev",
    "http://192.168.1.33:8082",
    'https://f4e4-103-175-108-30.ngrok-free.app',
    'https://snappier-reapply-kieth.ngrok-free.dev',
    "https://store.rubywellnesscenter.com",
    "https://codingboss.in",
    "https://www.codingboss.in",
    "https://api.codingboss.in",
    "http://api.codingboss.in",
    "http://api.codingboss.in",
    "https://www.codingboss.in",
    "https://www.codingboss.in",
    "https://api-dev.thiran360ai.com",
    "http://192.168.1.240:8899",
    "https://dev.thiran360ai.com",
    "https://25db-59-97-51-97.ngrok-free.app",
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    "http://localhost:3003",
    "http://localhost:3004",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://59.97.51.97:8081",
    "http://localhost:8090",
    "https://thiran360ai.github.io",
    "http://127.0.0.1",
    "http://127.0.0.1:8080",
    "http://ngrok-skip-browser-warning",  # Add scheme and netloc for 'ngrok-skip-browser-warning'
    "https://gokulrajalp.github.io",
    "http://192.168.1.3", 
    "http://crm.stgesports.in",
    "http://192.168.43.50:8080",
    "https://googlemeeting.vercel.app",
    "https://raanuvaveeranspokenhindiacademy.com",
    "https://store.rubywellnesscenter.com",
    "https://ecom.thiran360ai.com",
    "https://coding-boss.vercel.app",
    "https://mail.codingboss.in",
    "https://ungreased-repulsive-consuming.ngrok-free.dev",
    "https://crm.vedanmart.com",
    "https://api.prod.payglocal.in",
     "https://crm.gobi360",
    "https://gobi360",
    "https://ramcare.in",
    "https://crm.ramcare.in",
    "http://cland.southindia.cloudapp.azure.com",

]

CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

# # Allow specific headers
# from corsheaders.defaults import default_headers
# CORS_ALLOW_HEADERS = list(default_headers) + [
#     "ngrok-skip-browser-warning",
#     "strict-origin-when-cross-origin",
#     "cache-control",
#     "pragma",
#     "bypass-tunnel-reminder",
#     "https://flatbed-overcast-bolster.ngrok-free.dev"
# ]

# Allow credentials (if needed)
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = True  # Allow frontend/ngrok media fetches from any origin

# ─── Proxy / ngrok support ───────────────────────────────────────────────────
# Makes request.build_absolute_uri() return the ngrok/domain URL
# instead of http://127.0.0.1:8000 when behind a reverse-proxy.
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

LOGIN_REDIRECT_URL = "/dashboard/"  # Redirect users after login



# settings.py
# AUTH_USER_MODEL = "Quizapp.CustomUser"

INSTALLED_APPS = [
    # Django defaults
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "jazzmin",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "rest_framework.authtoken",
    "corsheaders",
    "import_export",
    "vandanmart",
    "herbal",
    "django_celery_beat",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "Quiz.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "Quiz.wsgi.application"
ASGI_APPLICATION = 'Quiz.asgi.application'



from decouple import config


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": config("DB_NAME"),
        "USER": config("DB_USER"),
        "PASSWORD": config("DB_PASSWORD"),
        "HOST": config("DB_HOST"),
        "PORT": 3306,
        "CONN_MAX_AGE": 60,  # ✅ Best value
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}


EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
# EMAIL_HOST_USER = "stgstrongtiesgaming40k@gmail.com"
# EMAIL_HOST_PASSWORD = "pjyo vyax hrwa ctnc"
TOURNAMENT_EMAIL_HOST_USER = "stgstrongtiesgaming40k@gmail.com"
TOURNAMENT_EMAIL_HOST_PASSWORD = "pjyo vyax hrwa ctnc"



EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
EMAIL_HOST_USER = "info.codingboss@gmail.com"  # Your email
EMAIL_HOST_PASSWORD = "rthe lmaq ykbz scdq"  # App password
DEFAULT_FROM_EMAIL = "info.codingboss@gmail.com"

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587

EMAIL_USE_TLS = True
EMAIL_USE_SSL = False

# Primary Mail
EMAIL_HOST_USER = "dharaniherbal783@gmail.com"
EMAIL_HOST_PASSWORD = "xydo jvki akto orqt"

# Secondary Mail
EMAIL_HOST_USER_2 = "admindharaniherbal@gmail.com"
EMAIL_HOST_PASSWORD_2 = "ejnw lvfy tbab ccom"

# Default sender
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER




# EMAIL_HOST_USER = "admin.dharaniherbbals@gmail.com"  # Your email
# EMAIL_HOST_PASSWORD = "ypcn lhrx mgvc fmsq"  # App password

# DEFAULT_FROM_EMAIL = "admin.dharaniherbbals@gmail.com"

SMS_USERNAME = "sundarppy@gmail.com"
SMS_PASSWORD = "Dharani123"
SMS_SENDER_ID = "DHHERB"

SMS_TEMPLATE_ID = "6990f1b1-6a28-4cb4-a8ed-35a450a6b59d"
SMS_OTP_EXPIRY_MINUTES = 30

# TWILIO_ACCOUNT_SID = config("TWILIO_ACCOUNT_SID", default="")
# TWILIO_AUTH_TOKEN = config("TWILIO_AUTH_TOKEN", default="")
# TWILIO_PHONE_NUMBER = config("TWILIO_PHONE_NUMBER", default="")

# AUTH_PASSWORD_VALIDATORS = [
#     {
#         'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
#     },
#     {
#         'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
#     },
#     {
#         'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
#     },
#     {
#         'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
#     },
# ]


# Internationalization
# https://docs.djangoproject.com/en/4.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Asia/Kolkata"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.1/howto/static-files/

# settings.py
MEDIA_URL = "/media/" 
# MEDIA_ROOT = os.path.join(BASE_DIR)
MEDIA_ROOT = os.path.join(BASE_DIR, "media")


STATIC_URL = "static/"
STATIC_URL = "static/"
# MEDIA_ROOT=os.path.join(BASE_DIR,'image')
# MEDIA_URL='/images/'
# MEDIA_ROOT=BASE_DIR/'static'

# STATICFILES_DIRS=[
#     BASE_DIR/'static'
# ]

# Default primary key field type
# https://docs.djangoproject.com/en/4.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# CSRF_COOKIE_DOMAIN = ".codingboss.in"
# SESSION_COOKIE_DOMAIN = ".codingboss.in"



# PAYMENT & FIREBASE CONFIG (Production)

# CASHFREE CONFIG
CASHFREE_APP_ID = config("CASHFREE_APP_ID", default="")
CASHFREE_SECRET_KEY = config("CASHFREE_SECRET_KEY", default="")
CASHFREE_ENV = config("CASHFREE_ENV", default="PROD")

# FIREBASE CONFIG
FCM_SERVER_KEY = config("FCM_SERVER_KEY", default="")

FIREBASE_CRED_PATH = os.path.join(BASE_DIR, "firebase_service_key.json")





# ============================
# CASHFREE + UPI SETTINGS
# ============================

#  UPI Merchant Details
UPI_MERCHANT_VPA = "cashfree@icici"          # your actual UPI ID
UPI_MERCHANT_NAME = "THIRAN360AI"         # your registered display name

# Cashfree Credentials
CASHFREE_CLIENT_ID = config("CASHFREE_CLIENT_ID", default="")
CASHFREE_CLIENT_SECRET = config("CASHFREE_CLIENT_SECRET", default="")

# Mode: 'PROD' for real transactions, 'TEST' for sandbox
CASHFREE_MODE = "PROD"

# Cashfree Base URL
if CASHFREE_MODE == "PROD":
    CASHFREE_BASE_URL = "https://api.cashfree.com/pg/orders"
else:
    CASHFREE_BASE_URL = "https://sandbox.cashfree.com/pg/orders"

# Webhook Endpoint
CASHFREE_WEBHOOK_URL = "https://api.codingboss.in/kovais/payment/webhook/"




REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],

    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],

    "DEFAULT_PAGINATION_CLASS":
        "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,

    "DEFAULT_THROTTLE_RATES": {
        "anon": "30/minute",
        "user": "1000/day",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}



# CHANNELS CONFIGURATION

CHANNEL_LAYERS = {

    "default": {

        "BACKEND": "channels.layers.InMemoryChannelLayer"

    }
}


# SESSION SETTINGS

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False


# SECURITY HEADERS (optional)

X_FRAME_OPTIONS = "ALLOWALL"



CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("127.0.0.1", 6379)],
        },
    },
}

# ============================
# IMPORT/EXPORT PERFORMANCE
# ============================
IMPORT_EXPORT_SKIP_ADMIN_LOG = True
IMPORT_EXPORT_IMPORT_PERMISSION_CODE = None



RAZORPAY_KEY_ID = "rzp_live_T2kchpa1l23YSF"

RAZORPAY_KEY_SECRET = "4seXSuoR6813FlcfW1wYVF8i"


# ============================
# Celery Configuration
# ============================
CELERY_BROKER_URL = "redis://127.0.0.1:6379/0"          # Redis as message broker
CELERY_RESULT_BACKEND = "redis://127.0.0.1:6379/0"      # Store task results in Redis
CELERY_TIMEZONE = "Asia/Kolkata"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

# ── Celery Beat Schedule ─────────────────────────────────────────────────────
# Runs delete_expired_live_videos every 1 minute.
# It checks all ENDED videos and deletes those past their delete_after time.
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'cleanup-expired-otps': {
        'task': 'your_app.tasks.delete_old_otps',
        'schedule': crontab(minute=0, hour=0), # Runs daily at midnight
    },
    'clear-abandoned-carts': {
        'task': 'your_app.tasks.clear_carts',
        'schedule': crontab(minute='*/15'), # Runs every 15 minutes
    },
    'delete-expired-live-videos': {
        'task': 'military.tasks.delete_expired_live_videos',
        'schedule': crontab(minute='*/1'),   # Runs every 1 minute
    },
}
# ============================
# Paytm Settings 'STAGING'
# ============================

# Paytm Staging Credentials
# PAYTM_ENV='STAGING'
# PAYTM_MID='QFaOHR88474428830379'
# PAYTM_MERCHANT_KEY='ID1Pqqo%v2Id_F7R'
# PAYTM_WEBSITE='WEBSTAGING'
# PAYTM_INDUSTRY_TYPE='Retail'
# PAYTM_CHANNEL_ID='WEB'
# PAYTM_CHANNEL_ID_MOBILE='WAP'
# PAYTM_CALLBACK_URL="https://guidance-glorifier-mango.ngrok-free.dev/api/payment/callback/"

# # Paytm URLs

# PAYTM_INITIATE_URL = ("https://securegw-stage.paytm.in/""theia/api/v1/initiateTransaction")

# PAYTM_STATUS_URL = ("https://securegw-stage.paytm.in/""v3/order/status")

# PAYTM_REFUND_URL = ("https://securegw-stage.paytm.in/""v2/refund")


# ============================
# Paytm Settings PRODUCTION
# ============================

PAYTM_ENV = "PRODUCTION"

PAYTM_MID = "YyffBp11837369316995"

PAYTM_MERCHANT_KEY = "cfImuygR10&ZzAOZ"

PAYTM_WEBSITE = "DEFAULT"

PAYTM_INDUSTRY_TYPE = "Retail"

PAYTM_CHANNEL_ID = "WEB"

PAYTM_CHANNEL_ID_MOBILE = "WAP"

PAYTM_CALLBACK_URL = ("https://api.codingboss.in/herbal/paytm/callback/")

PAYTM_INITIATE_URL = ("https://secure.paytmpayments.com/theia/api/v1/initiateTransaction")

PAYTM_STATUS_URL = ("https://secure.paytmpayments.com/v3/order/status")

PAYTM_REFUND_URL = ("https://secure.paytmpayments.com/v2/refund")

# ============================
# SMS API
# ============================

SMS_API_URL = "http://smsc.biz/httpapi/send?"




# PayGlocal Configuration

# PAYGLOCAL_MERCHANT_ID = "ptplarumugam4099"

# PAYGLOCAL_PUBLIC_KEY_ID = "8cc91c8d-8030-4660-a9c7-33de886fb495"

# PAYGLOCAL_PRIVATE_KEY_ID = "kId-qCWAxfZXWFSvuNOi"

# PAYGLOCAL_PRIVATE_KEY_PATH = "/secure/payglocal/merchant_private.pem"

# PAYGLOCAL_PUBLIC_KEY_PATH = "/secure/payglocal/payglocal_public.pem"

# PAYGLOCAL_BASE_URL = "https://api.prod.payglocal.in"
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


PAYGLOCAL_PRIVATE_KEY_PATH = BASE_DIR / "herbal" / "payglocal" / "merchant_private.pem"
PAYGLOCAL_PUBLIC_KEY_PATH = BASE_DIR / "herbal" / "payglocal" / "payglocal_public.pem"

PAYGLOCAL_MERCHANT_ID = "ptplarumugam4099"
PAYGLOCAL_PUBLIC_KEY_ID = "8cc91c8d-8030-4660-a9c7-33de886fb495"
PAYGLOCAL_PRIVATE_KEY_ID = "kId-jMkIcUq5AhQQIbC4"
PAYGLOCAL_BASE_URL = "https://api.prod.payglocal.in"
