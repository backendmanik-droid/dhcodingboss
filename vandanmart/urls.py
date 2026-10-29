from django.urls import path
from .views import *
from .crm_views import *
from .payglocal_checkin import payglocal_checkin

urlpatterns = [
    path('', api_home),
    path('dashboard/', dashboard_view),
    # path('cart-report/', crm_cart_report),
    path('wishlist-report/', crm_wishlist_report),
    path('all-wishlists/', crm_wishlist_report, name='crm_all_wishlists'),
    # ================= AUTHENTICATION & USERS =================
    path('register/', register),
    path('login/', crm_login),
    path('admin-login/', admin_login),
    path('store/register/', store_register),
    path('store/login/', store_login),
    path('store/products/', store_products),
    path('store/products/<int:product_id>/', store_products),
    path('logout/', crm_logout),
    path('change-password/', change_password),
    # path('forgot-password/', forgot_password),
    path('address/', address_management),
    path('address/<int:user_id>/', address_management),

    # ================= OTP =================

    path('generate-otp/',generate_otp,name='generate_otp'),

    path('resend-otp/',resend_otp,name='resend_otp'),

    path('verify-otp/',verify_otp,name='verify_otp'),

    # ================= USER LOGIN OTP =================

    path('user-login/', user_login),
    path('reset-password/', reset_password),
    path('verify-user-login-otp/',verify_user_login_otp),
    path("delete/store-staff/<int:staff_id>/",delete_store_staff,name="delete_store_staff"),

    # ================= CUSTOMERS =================
    path('customers/', crm_customers),
    path('customers/<int:pk>/', crm_customer_detail),
    path('customers/add/', crm_customers),
    path('customers/edit/<int:pk>/', crm_customer_detail),
    path('customers/delete/<int:pk>/', crm_customer_detail),
    path('customers/print/<int:pk>/', crm_customer_print),

    # ================= PRODUCTS =================
    path('products/', customer_products),
    path('products/<int:pk>/', public_product_detail),
    path('category-products/<int:category_id>/', products_by_category),
    path('admin/dashboard/product/add/', dashboard_add_product),
    path('admin/dashboard/product/edit/<int:product_id>/', dashboard_edit_product),
    path('admin/dashboard/product/delete/<int:product_id>/', dashboard_delete_product),
    path("products/<int:product_id>/variations/", product_variations), # POST & GET
    path("product-variation/<int:id>/", product_variation_detail), # DELETE & PUT
    path("products/<int:product_id>/key-points/",product_key_points), # POST & GET keypoint
    path("product-key-point/<int:id>/",product_key_point_detail), # PUT & DELETE
    path("shipping-charge/", shipping_charge_management),
    path("shipping-charge/<int:shipping_id>/", shipping_charge_detail),

    # ================= CATEGORIES =================
    path("categories/", crm_categories),                 # GET, POST
    path("categories/<int:category_id>/", crm_category_detail),   # PUT, DELETE

    # ================= BRANDS =================
    path('brands/', crm_brands),
    path("brands/<int:brand_id>/", crm_brand_detail),
    path('admin/dashboard/brand/add/', dashboard_add_brand),
    path('admin/dashboard/brand/edit/<int:brand_id>/', dashboard_edit_brand),
    path('admin/dashboard/brand/delete/<int:brand_id>/', dashboard_delete_brand),

    # ================= SLIDERS =================
    path('sliders/', slider_list_create),
    path('sliders/<int:pk>/', slider_detail), 
    path('admin/dashboard/slider/add/', dashboard_add_slider),
    path('admin/dashboard/slider/edit/<int:slider_id>/', dashboard_edit_slider),
    path('admin/dashboard/slider/delete/<int:slider_id>/', dashboard_delete_slider),

    # ================= CART =================
    path("carts/", cart_variation, name="cart_variation"),
    path('cart/', cart_list_add),
    # path("send-template/", send_template),


    path('cart/<int:pk>/', cart_detail),
    path('cart/clear/<int:user_id>/', cart_clear),

    # ================= WISHLIST =================
    path("wishlist/<int:user_id>/", crm_wishlist),
    path('wishlist/add/', crm_wishlist_add),
    path('wishlist/delete/<int:pk>/', crm_wishlist_delete),
    path("crm/most-loved/",crm_most_loved_products),
    path("crm/most-loved/update/", crm_update_most_loved),
    path("most-loved/", most_loved_products),

    # ================= ORDERS =================
    path('orders/', admin_all_orders),

    path('products/barcode/',product_by_barcode, name='product_by_barcode'),

    path('orders/<int:pk>/', crm_order_detail),
    path('crm/orders/create/', crm_order_create),
    path('crm/staff/update-credit/', crm_update_credit),
    path('crm/staff/fix-all-credits/', fix_all_credits),
    path('my-orders/<int:user_id>/', my_orders),
    path('checkout/', checkout),
    path('orders/<int:order_id>/track/', track_order),
    path('orders/<int:order_id>/update-status/', update_order_status),

    # ================= BILLING =================
    path('bills/', crm_bills),
    path('bills/create/', crm_bill_create),
    path('bills/<int:bill_id>/', crm_bill_print),
    path('bills/print/<int:bill_id>/', crm_bill_print),
    path('bills/pdf/<int:bill_id>/', crm_bill_print),

    # ================= INVOICES =================
    path('invoices/', crm_invoices),
    path('invoices/create/', crm_invoice_create),
    path('invoices/<int:invoice_id>/', crm_invoice_print),
    path('invoices/print/<int:invoice_id>/', crm_invoice_print),
    path('invoices/pdf/<int:invoice_id>/', crm_invoice_print),

    # ================= QUOTATIONS =================
    path('quotations/', crm_quotations),
    path('quotations/create/', crm_quotation_create),
    path('quotations/<int:quotation_id>/', crm_quotation_print),
    path('quotations/print/<int:quotation_id>/', crm_quotation_print),
    path('quotations/pdf/<int:quotation_id>/', crm_quotation_print),

    # ================= TRACKING =================
    path('tracking/<int:order_id>/', crm_tracking),
    path('tracking/update/<int:order_id>/', crm_tracking_update),

    # ================= INVENTORY =================
    path('inventory/', crm_inventory),
    path('inventory/add-stock/', crm_inventory_action, {'action': 'add-stock'}),
    path('inventory/remove-stock/', crm_inventory_action, {'action': 'remove-stock'}),
    path('inventory/adjust-stock/', crm_inventory_action, {'action': 'adjust-stock'}),
    path('inventory/low-stock/', crm_inventory_action, {'action': 'low-stock'}),

    # ================= REPORTS =================
    path('reports/<str:rtype>/', crm_reports),

    # ================= EMAIL NOTIFICATIONS =================
    path('email/<str:ntype>/', crm_email_notif),

    # ================= WHATSAPP NOTIFICATIONS =================
    path('whatsapp/<str:ntype>/', crm_whatsapp_notif),
    # path("test-reorder-whatsapp/", test_reorder_whatsapp),

    # ================= NOTIFICATION HISTORY =================
    path('admin/notifications/', admin_notification_history),
    path('staff/notifications/', staff_notifications),

    # ================= CUSTOMER LEDGER =================
    path('customer-ledger/', crm_customer_ledger),
    path('customer-ledger/<int:customer_id>/', crm_customer_ledger),
    path('customer-ledger/print/<int:customer_id>/', crm_customer_ledger),

    # ================= PAYMENTS =================
    path('payments/', crm_payments),
    path('payments/add/', crm_payments_add),
    path('payments/<int:pk>/', crm_payments),
    path('payments/receipt/<int:pk>/', crm_payments_receipt),

    # ================= STAFF MANAGEMENT =================
    path('admin/staff/', staff_list),
    path('admin/staff/add/', staff_list),
    path('admin/staff/edit/<int:staff_id>/', staff_list),
    path('admin/staff/delete/<int:staff_id>/', staff_list),
    path('product-images/', product_images_list_create),
    path("product-images/<int:product_id>/", get_product_images ),
    path("product-image/edit/<int:image_id>/",product_images),
    path("product-image/delete/<int:image_id>/",product_images),
    # path("product-image/<int:product_id>/", product_images ), # PUT DELETE path( "product-image/<int:image_id>/", product_images ),

    # ================= TRANSLATION =================
    path('translation/translate/', translate_text),
    path('translation/product/<int:product_id>/translate/', product_auto_translate),
    path('translation/products/bulk-translate/', bulk_product_auto_translate),
    # path('create-paytm-order/',create_paytm_order),
    # path('create-razorpay-order/',create_razorpay_order),
    # path('verify-payment/',verify_payment),

    path('reviews/submit/',submit_product_review,name='submit_product_review'),
    path('products/<int:product_id>/reviews/', product_reviews, name='product_reviews'),
    path('products/<int:product_id>/review-summary/',product_review_summary,name='product_review_summary'),
    path('crm/reviews/',crm_reviews,name='crm_reviews'),
    path('crm/reviews/<int:pk>/',crm_review_detail,name='crm_review_detail'),

# ================= ONLINE PAYMENTS =================

# Razorpay
# path('create-razorpay-order/',create_razorpay_order,name='create_razorpay_order'),
# path('verify-payment/',verify_payment,name='verify_payment'),

# Paytm
    # ================= PAYTM =================
    
    # Create Paytm order / generate txnToken
    path("create-paytm-order/",create_paytm_order,name="create_paytm_order"),

    # Paytm callback
    path("paytm/callback/",paytm_callback,name="paytm_callback"),

    # Check Paytm payment status
    path("paytm/status/",paytm_status,name="paytm_status"),

    # Refund
    path("paytm/refund/",paytm_refund,name="paytm_refund"),

    # Webhook
    path("paytm/webhook/",paytm_webhook,name="paytm_webhook"),

    path("paytm/webhook/<int:payment_id>/",get_payment,name="get_payment"),


    path("payglocal/create/",payglocal_create_payment,name="payglocal_create_payment"),

    path("payglocal/callback/",payglocal_callback,name="payglocal_callback"),

    path("payglocal/status/", payglocal_status, name="payglocal_status"),

    # PayGlocal Checkin API
    path("payglocal/checkin/", payglocal_checkin, name="payglocal_checkin"),

    path("erp-proxy/",erp_proxy, name="erp_proxy"),

]