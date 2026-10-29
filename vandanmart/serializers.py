from rest_framework import serializers
from .models import *
from rest_framework import serializers


class ProductKeyPointSerializer(serializers.ModelSerializer):

    class Meta:
        model = ProductKeyPoint
        fields = "__all__"

class CartVariationSerializer(serializers.ModelSerializer):

    product_id = serializers.IntegerField(source="product.id", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)

    variation_id = serializers.SerializerMethodField()
    variation_name = serializers.SerializerMethodField()

    category_name = serializers.CharField(
        source="product.category.name",
        read_only=True
    )

    product_image = serializers.SerializerMethodField()

    price = serializers.SerializerMethodField()

    role = serializers.CharField(
        source="role_at_add",
        read_only=True
    )

    item_total = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = (
            "id",
            "product_id",
            "product_name",
            "variation_id",
            "variation_name",
            "product_image",
            "category_name",
            "price",
            "role",
            "quantity",
            "item_total",
            "added_at",
        )

    def get_variation_id(self, obj):
        return obj.variation.id if obj.variation else None

    def get_variation_name(self, obj):
        return obj.variation.variation_name if obj.variation else None

    def get_product_image(self, obj):
        image = obj.product.image

        if not image:
            return None

        request = self.context.get("request")

        if hasattr(image, "url"):
            try:
                if request:
                    return request.build_absolute_uri(image.url)
                return f"https://api.codingboss.in{image.url}"
            except Exception:
                pass

        image_str = str(image).strip()
        if not image_str:
            return None

        # Already a full URL
        if image_str.startswith("http://") or image_str.startswith("https://"):
            return image_str

        if request:
            if image_str.startswith("/"):
                return request.build_absolute_uri(image_str)
            return request.build_absolute_uri("/" + image_str)

        return image_str

    def get_price(self, obj):
        return str(obj.price_at_add)

    def get_item_total(self, obj):
        return str(obj.price_at_add * obj.quantity)
    

class ProductReviewSerializer(serializers.ModelSerializer):

    customer_name = serializers.CharField(
        source='customer.name',
        read_only=True
    )

    product_name = serializers.CharField(
        source='product.name',
        read_only=True
    )

    variation_name = serializers.SerializerMethodField()

    def get_variation_name(self, obj):
        if obj.order_item and obj.order_item.variation:
            return obj.order_item.variation.variation_name
        return None

    product_code = serializers.CharField(
        source='product.product_code',
        read_only=True
    )

    order_id = serializers.IntegerField(
        source='order_item.order.id',
        read_only=True
    )

    class Meta:

        model = ProductReview

        fields = [
            'id',
            'product',
            'product_name',
            'product_code',
            'variation_name',
            'customer',
            'customer_name',
            'order_item',
            'order_id',
            'rating',
            'review_text',
            'status',
            'approved_by',
            'approved_at',
            'created_at',
            'updated_at'
        ]

        read_only_fields = [
            'status',
            'approved_by',
            'approved_at',
            'created_at',
            'updated_at'
        ]


from rest_framework import serializers

class ProductReviewCRMSerializer(serializers.ModelSerializer):

    productName = serializers.CharField(source='product.name', read_only=True)

    sku = serializers.CharField(source='product.product_code', read_only=True)

    customerName = serializers.CharField(source='customer.name', read_only=True)

    comment = serializers.CharField(source='review_text')

    date = serializers.DateTimeField(
        source='created_at',
        format="%d-%b-%Y %I:%M:%S %p",
        read_only=True
    )

    approved = serializers.SerializerMethodField()

    class Meta:
        model = ProductReview
        fields = (
            'id',
            'productName',
            'sku',
            'customerName',
            'rating',
            'comment',
            'date',
            'approved',
        )

    def get_approved(self, obj):
        return obj.status == "approved"

        from rest_framework import serializers

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):

    class Meta:

        model = Payment

        fields = "__all__"
        

class WishlistSerializer(serializers.ModelSerializer):

    product_name = serializers.CharField(
        source="product.name",
        read_only=True
    )

    product_image = serializers.SerializerMethodField()

    customer_price = serializers.DecimalField(
        source="product.customer_price",
        max_digits=10,
        decimal_places=2,
        read_only=True
    )

    class Meta:
        model = Wishlist
        fields = [
            "id",
            "user",
            "product",
            "product_name",
            "product_image",
            "customer_price",
            "created_at"
        ]

    def get_product_image(self, obj):
        request = self.context.get("request")

        if not obj.product.image:
            return None

        image = obj.product.image

        if hasattr(image, "url"):
            try:
                if request:
                    return request.build_absolute_uri(image.url)
                return f"https://api.codingboss.in{image.url}"
            except Exception:
                pass

        image_str = str(image).strip()
        if not image_str:
            return None

        # If image is already a full URL
        if image_str.startswith("http://") or image_str.startswith("https://"):
            return image_str

        # If image is stored as a relative path/string
        if request:
            if image_str.startswith("/"):
                return request.build_absolute_uri(image_str)
            return request.build_absolute_uri(f"/media/{image_str}")
        return f"https://api.codingboss.in/media/{image_str}"