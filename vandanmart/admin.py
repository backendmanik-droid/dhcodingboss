from django.contrib import admin
from .models import *
from import_export.admin import ImportExportModelAdmin

@admin.register(User)
class UserAdmin(ImportExportModelAdmin):
    list_display = ("id", "name", "mobile", "email", "role", "can_send_notifications", "is_verified", "created_at")
    list_filter = ("role", "is_verified", "can_send_notifications", "created_at")
    search_fields = ("name", "mobile", "email")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
    list_per_page = 25

@admin.register(Address)
class AddressAdmin(ImportExportModelAdmin):
    list_display = ("id", "user", "full_name", "phone", "city", "state", "pincode", "latitude", "longitude", "is_default")
    list_filter = ("state", "city", "is_default")
    search_fields = ("user__name", "full_name", "phone", "city", "state", "pincode")
    ordering = ("-id",)
    list_editable = ("is_default",)
    list_per_page = 25

@admin.register(Category)
class CategoryAdmin(ImportExportModelAdmin):
    list_display = ("id", "name", "image", "created_at")
    search_fields = ("name",)
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
    list_per_page = 25

@admin.register(Brand)
class BrandAdmin(ImportExportModelAdmin):
    list_display = ("id", "name", "image", "created_at")
    search_fields = ("name",)
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
    list_per_page = 25

@admin.register(Product)
class ProductAdmin(ImportExportModelAdmin):
    list_display = (
        "id", "name", "category", "brand", "product_code", "barcode",
        "customer_price", "retailer_price", "distributor_price",
        "stock", "unit", "is_new", "is_public", "is_active", "created_at"
    )
    list_filter = (
        "category", "brand", "unit",
        "is_new", "is_public", "is_active"
    )
    search_fields = (
        "name", "product_code", "barcode",
        "tamil_name", "manufacturer", "batch_number"
    )
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
    list_editable = ("is_new", "is_public", "is_active")
    list_per_page = 25

@admin.register(ProductImage)
class ProductImageAdmin(ImportExportModelAdmin):
    list_display = ("id", "product", "image", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("product__name",)
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
    list_editable = ("is_active",)
    list_per_page = 25

@admin.register(ProductVariation)
class ProductVariationAdmin(ImportExportModelAdmin):
    list_display = (
        "id", "product", "variation_name", "sku", "barcode",
        "customer_price", "retailer_price", "distributor_price",
        "stock", "discount", "weight_volume", "is_active", "created_at"
    )
    list_filter = ("product", "is_active", "created_at")
    search_fields = ("product__name", "variation_name", "sku", "barcode")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
    list_editable = ("is_active",)
    list_per_page = 25

@admin.register(ProductKeyPoint)
class ProductKeyPointAdmin(ImportExportModelAdmin):
    list_display = ("id","product","title","display_order","is_active","created_at",)
    list_filter = ("is_active","product",)
    search_fields = ("title","product__name",)
    ordering = ("product","display_order",)


@admin.register(MostLovedProduct)
class MostLovedProductAdmin(ImportExportModelAdmin):
    list_display = ("id","product","display_order","is_active","created_at",)
    list_filter = ("is_active",)
    search_fields = ("product__name","product__product_code",)
    ordering = ("display_order","id",)

@admin.register(Slider)
class SliderAdmin(ImportExportModelAdmin):
    list_display = ("id", "title", "subtitle", "image", "is_active", "order", "created_at")
    list_filter = ("is_active",)
    search_fields = ("title", "subtitle")
    ordering = ("order",)
    readonly_fields = ("created_at",)
    list_editable = ("is_active", "order")
    list_per_page = 25

@admin.register(Order)
class OrderAdmin(ImportExportModelAdmin):
    list_display = (
        "id", "invoice_number", "customer", "price_category", "payment_method",
        "product_amount", "gst_amount", "shipping_charges",
        "total_amount", "status", "tracking_number", "created_at"
    )
    list_filter = ("status", "payment_method", "created_at")
    search_fields = (
        "invoice_number",
        "customer__name",
        "customer__mobile",
        "tracking_number",
    )
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")
    list_editable = ("status",)
    list_per_page = 25

@admin.register(ShippingCharge)
class ShippingChargeAdmin(ImportExportModelAdmin):
    list_display = ("id", "state_name", "state_code", "shipping_amount", "free_above", "min_order")
    search_fields = ("state_name", "state_code")
    ordering = ("state_name",)
    list_per_page = 25


@admin.register(OrderItem)
class OrderItemAdmin(ImportExportModelAdmin):

    list_display = (
        'id',
        'order',
        'product',
        'variation',
        'quantity',
        'price'
    )

    search_fields = (
        'product__name',
        'order__id',
    )

    list_filter = (
        'product',
    )

@admin.register(ProductReview)
class ProductReviewAdmin(ImportExportModelAdmin):

    list_display = (
        'id',
        'product',
        'customer',
        'order_item',
        'rating',
        'status',
        'created_at'
    )

    search_fields = (
        'product__name',
        'customer__name',
    )

    list_filter = (
        'status',
        'rating',
    )

    readonly_fields = (
        'created_at',
        'updated_at',
        'approved_at',
    )


from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "order",
        "customer",
        "amount",
        "payment_gateway",
        "status",
        "gateway_order_id",
        "gateway_transaction_id",
        "created_at",
        "updated_at",
    )

    list_filter = (
        "payment_gateway",
        "status",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "id",
        "order__id",
        "customer__name",
        "customer__email",
        "razorpay_order_id",
        "razorpay_payment_id",
        "paytm_order_id",
        "paytm_txn_id",
        "paytm_bank_txn_id",
        "gateway_order_id",
        "gateway_transaction_id",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Basic Payment Information",
            {
                "fields": (
                    "order",
                    "customer",
                    "amount",
                    "payment_gateway",
                    "status",
                )
            },
        ),

        (
            "Common Gateway Information",
            {
                "fields": (
                    "gateway_order_id",
                    "gateway_transaction_id",
                    "gateway_response",
                )
            },
        ),

        (
            "Razorpay Information",
            {
                "fields": (
                    "razorpay_order_id",
                    "razorpay_payment_id",
                    "razorpay_signature",
                )
            },
        ),

        (
            "Paytm Information",
            {
                "fields": (
                    "paytm_order_id",
                    "paytm_txn_id",
                    "paytm_bank_txn_id",
                    "paytm_txn_token",
                    "payment_mode",
                )
            },
        ),

        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    ordering = ("-created_at",)