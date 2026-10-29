from django.db import models


class User(models.Model):

    ROLE_CHOICES = (
        ('customer', 'Customer'),
        ('retailer', 'Retailer'),
        ('distributor', 'Distributor'),
        ('staff', 'Staff'),
        ('admin', 'Admin'),
    )

    name = models.CharField(max_length=100)

    mobile = models.CharField(
        max_length=15,
        unique=True
    )

    email = models.EmailField(
        unique=True,
        null=True,
        blank=True
    )

    password = models.CharField(max_length=100)

    store_name = models.CharField(
        max_length=150,
        blank=True,
        null=True
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='customer'
    )

    PRICE_CATEGORY_CHOICES = (
        ('customer_price', 'Customer'),
        ('store_price', 'Store'),
        ('reseller_price', 'Reseller'),
        ('retailer_price', 'Retailer'),
        ('distributor_price', 'Distributor'),
        ('sarvo_price', 'Sarvo'),
        ('drug_price', 'Ayush'),
    )

    price_category = models.CharField(
        max_length=20,
        choices=PRICE_CATEGORY_CHOICES,
        default='customer_price'
    )

    can_send_notifications = models.BooleanField(default=False)

    is_verified = models.BooleanField(default=False)

    # CRM Fields
    customer_code = models.CharField(max_length=50, null=True, blank=True)
    alternate_phone = models.CharField(max_length=15, null=True, blank=True)
    default_logistics = models.CharField(max_length=100, null=True, blank=True)
    preferred_payment_method = models.CharField(max_length=50, null=True, blank=True)
    mode_of_communication = models.CharField(max_length=50, null=True, blank=True)
    credit_payment_enabled = models.BooleanField(default=False)
    credit_limit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    available_credit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    gst_number = models.CharField(max_length=50, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

# =========================
# ADDRESS MODEL
# =========================

class Address(models.Model):
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name="addresses")
    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=15)
    address_type = models.CharField(max_length=256, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)

    latitude = models.DecimalField(max_digits=9,decimal_places=6,null=True,blank=True)

    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )

    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.name} - {self.state}"
    
# =========================
# PENDING_REGISTRATION MODEL
# =========================

class PendingRegistration(models.Model):
    name = models.CharField(max_length=100)
    mobile = models.CharField(max_length=15)
    email = models.EmailField()
    password = models.CharField(max_length=100)
    role = models.CharField(max_length=20, default='customer')
    created_at = models.DateTimeField(auto_now_add=True)

# =========================
# EMAIL_OTP MODEL
# =========================

class EmailOTP(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    otp = models.CharField(max_length=6)

    purpose = models.CharField(
        max_length=20,
        default='login'
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    is_verified = models.BooleanField(
        default=False
    )

    def __str__(self):
        return f"{self.user.email} - {self.otp}"
    
# =========================
# CATEGORY MODEL
# =========================

class Category(models.Model):

    name = models.CharField(max_length=100)

    image = models.ImageField(upload_to='categories/', max_length=256, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name



# =========================
# BRAND MODEL
# =========================

class Brand(models.Model):

    name = models.CharField(max_length=100)

    image = models.ImageField(upload_to='brands/', max_length=256, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# =========================
# PRODUCT MODEL
# =========================

class Product(models.Model):

    UNIT_CHOICES = (
        ('mg', 'Milligram'),
        ('g', 'Gram'),
        ('kg', 'Kilogram'),
        ('qtl', 'Quintal'),
        ('ton', 'Ton'),
        ('ml', 'Milliliter'),
        ('l', 'Liter'),
        ('pcs', 'Piece'),
        ('nos', 'Number'),
        ('pack', 'Pack'),
        ('box', 'Box'),
        ('bottle', 'Bottle'),
        ('jar', 'Jar'),
        ('tube', 'Tube'),
        ('sachet', 'Sachet'),
        ('bundle', 'Bundle'),
        ('carton', 'Carton'),
        ('dozen', 'Dozen'),
        ('mm', 'Millimeter'),
        ('cm', 'Centimeter'),
        ('m', 'Meter'),
        ('km', 'Kilometer'),
    )

    # ================= REQUIRED FIELDS =================
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        related_name='products',
        null=True,
        blank=True
    )

    name = models.CharField(max_length=200)  # REQUIRED

    image = models.ImageField(upload_to='products/', max_length=256, null=True, blank=True)

    # ================= OPTIONAL RELATIONS =================
    brand = models.ForeignKey(
        Brand,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products'
    )

    # ================= OPTIONAL IDENTIFIERS =================
    product_code = models.CharField(max_length=100, null=True, blank=True)
    barcode = models.CharField(max_length=100, null=True, blank=True)

    # ================= TEXT INFO =================
    description = models.TextField(null=True, blank=True)
    tamil_name = models.CharField(max_length=200, null=True, blank=True)
    product_type = models.CharField(max_length=50, null=True, blank=True)

    # ================= PRICING (BASE PRODUCT PRICE) =================
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    mrp = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    customer_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    store_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    reseller_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    retailer_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    distributor_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    sarvo_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    drug_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    erp_item_id = models.CharField(max_length=100, null=True, blank=True)
    # ================= BUSINESS DATA =================
    gst_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)

    stock = models.IntegerField(default=0)
    reorder_level = models.IntegerField(default=10)

    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default='pcs')

    weight_volume = models.CharField(max_length=50, null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    batch_number = models.CharField(max_length=100, null=True, blank=True)

    manufacturer = models.CharField(
        max_length=200,
        default='Dharani Herbals',
        null=True,
        blank=True
    )

    # ================= FLAGS =================
    is_new = models.BooleanField(default=False)
    is_public = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

# =========================
# PRODUCT_IMAGE MODEL
# =========================

class ProductImage(models.Model):
    product = models.ForeignKey(Product,on_delete=models.CASCADE,related_name='extra_images',null=True,blank=True)
    image = models.ImageField(upload_to='products/extra/', max_length=256, null=True, blank=True)
    is_active = models.BooleanField(default=False)   # inactive by default))
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"{self.product.name} - Image {self.id}"

# =========================
# VARIATION MODEL
# =========================

class ProductVariation(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="variations"
    )

    variation_name = models.CharField(max_length=100, null=True, blank=True)

    erp_item_id = models.CharField(max_length=256, null=True, blank=True)

    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True, blank=True)
    mrp = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True, blank=True)
    customer_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True, blank=True)
    store_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True, blank=True)
    reseller_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True, blank=True)
    retailer_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True, blank=True)
    distributor_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True, blank=True)
    sarvo_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True, blank=True)
    drug_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True, blank=True)

    gst_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, null=True, blank=True)

    stock = models.IntegerField(default=0, null=True, blank=True)

    sku = models.CharField(max_length=100, null=True, blank=True)

    barcode = models.CharField(max_length=100, null=True, blank=True)

    discount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        null=True,
        blank=True
    )

    weight_volume = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product.name} - {self.variation_name}"

class ProductKeyPoint(models.Model):

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="key_points",
        null=True,
        blank=True,
    )

    title = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    display_order = models.PositiveIntegerField(
        default=1,
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = [
            "display_order",
            "id",
        ]

    def __str__(self):
        return (
            self.title
            or f"Key Point {self.id}"
        )


class Cart(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='cart_items'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='cart_items'
    )
    variation = models.ForeignKey(
        ProductVariation,
        on_delete=models.SET_NULL,
        related_name='cart_items',
        null=True,
        blank=True
    )
    quantity = models.IntegerField(default=1)
    price_at_add = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    role_at_add = models.CharField(max_length=20, default='customer')
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    cart_reminder_sent = models.BooleanField(default=False)
    cart_reminder_sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.name} - {self.product.name}"


class MostLovedProduct(models.Model):

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='most_loved')

    display_order = models.PositiveIntegerField(default=1)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

# =========================
# SLIDER MODEL
# =========================

class Slider(models.Model):

    title = models.CharField(max_length=200, blank=True, null=True)

    subtitle = models.CharField(max_length=300, blank=True, null=True)

    image = models.ImageField(upload_to='sliders/', max_length=256, null=True, blank=True)

    is_active = models.BooleanField(default=True)

    order = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title or f"Slider {self.id}"

# =========================
# NOTIFICATION MODEL
# =========================

class Notification(models.Model):

    TYPE_CHOICES = (
        ('email', 'Email'),
        ('whatsapp', 'WhatsApp'),
    )

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    )

    customer = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    notification_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES
    )

    subject = models.CharField(
        max_length=200,
        blank=True
    )

    message = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    sent_at = models.DateTimeField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.notification_type} to {self.customer.name} - {self.status}"


# =========================
# NOTIFICATION LOG MODEL
# =========================

class NotificationLog(models.Model):

    customer = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    notification_type = models.CharField(
        max_length=20
    )

    message = models.TextField()

    status = models.CharField(
        max_length=20
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"Log: {self.notification_type} to {self.customer.name}"


# =========================
# ORDER SYSTEM MODELS
# =========================

class Order(models.Model):

    STATUS_CHOICES = (
        ('pending',    'Pending'),
        ('confirmed',  'Confirmed'),
        ('processing', 'Processing'),
        ('shipped',    'Shipped'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered',  'Delivered'),
        ('received',   'Received'),
        ('cancelled',  'Cancelled'),
        ('damaged',    'Damaged'),
        ('returned',   'Returned'),
    )

    customer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='orders'
    )

    # ---- Order Entry Form Fields ----
    invoice_number = models.CharField(max_length=100, null=True, blank=True)
    billing_address = models.TextField(null=True, blank=True)
    mode_of_communication = models.CharField(max_length=100, null=True, blank=True)
    logistics = models.CharField(max_length=200, null=True, blank=True)
    remarks = models.TextField(null=True, blank=True)
    payment_method = models.CharField(max_length=100, null=True, blank=True)
    
    price_category = models.CharField(
        max_length=20,
        choices=User.PRICE_CATEGORY_CHOICES,
        default='customer_price',
        null=True,
        blank=True
    )

    shipping_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    product_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )

    gst_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )
    cgst_amount = models.DecimalField(
    max_digits=10,
    decimal_places=2,
    default=0.00
    )

    sgst_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )

    igst_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )

    credit_used = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )
    
    amount_to_pay = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )


    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    address = models.ForeignKey(
    Address,
    on_delete=models.SET_NULL,
    null=True,
    blank=True
)

    # ---- Location (GPS) ----
    latitude  = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    # ---- Damage / Cancellation ----
    cancel_reason = models.TextField(null=True, blank=True)
    damage_notes  = models.TextField(null=True, blank=True)

    # ---- Tracking ----
    estimated_delivery = models.DateField(null=True, blank=True)
    tracking_number    = models.CharField(max_length=100, null=True, blank=True)

    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    delivered_at = models.DateTimeField(null=True,blank=True)

    def __str__(self):
        return f"Order #{self.id} - {self.customer.name} - {self.status}"

# =========================
# ORDER_ITEM MODEL
# =========================

class OrderItem(models.Model):

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items'
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True
    )
    variation = models.ForeignKey(
        ProductVariation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items"
    )

    quantity = models.IntegerField(default=1)

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    reorder_reminder_sent = models.BooleanField(default=False)
    reorder_reminder_sent_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.quantity}x {self.product.name if self.product else 'Deleted Product'} in Order #{self.order.id}"

class ProductReview(models.Model):

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')

    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='product_reviews')

    order_item = models.ForeignKey(OrderItem,on_delete=models.CASCADE,related_name="reviews")

    rating = models.PositiveSmallIntegerField()

    review_text = models.TextField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_reviews')

    approved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product.name} - {self.customer.name} ({self.rating}★)"

# =========================
# SHIPPING MODEL
# =========================

class ShippingCharge(models.Model):
    state_name = models.CharField(max_length=100, unique=True)
    state_code = models.CharField(max_length=10)

    shipping_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    free_above = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    min_order = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    def __str__(self):
        return self.state_name
    

# =========================
# ORDER TRACKING LOG
# =========================

class OrderTracking(models.Model):
    '''Records every status change for an order — full history.'''

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='tracking_history'
    )

    status = models.CharField(max_length=20)
    note   = models.TextField(null=True, blank=True)

    # GPS at the time of status update (e.g. courier location)
    latitude  = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_name = models.CharField(max_length=200, null=True, blank=True)

    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.order.id} → {self.status} at {self.created_at:%Y-%m-%d %H:%M}"


# =========================
# BILLING MODELS
# =========================

class Quotation(models.Model):
    customer = models.ForeignKey(User, on_delete=models.CASCADE)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    items_json = models.TextField(default='[]')  # Stores JSON serialization of items
    status = models.CharField(max_length=20, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Quotation #{self.id} for {self.customer.name}"


class Invoice(models.Model):
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True)
    customer = models.ForeignKey(User, on_delete=models.CASCADE)
    invoice_number = models.CharField(max_length=100, unique=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, default='unpaid')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.customer.name}"


class Bill(models.Model):
    vendor_name = models.CharField(max_length=200)
    bill_number = models.CharField(max_length=100)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Bill {self.bill_number} - {self.vendor_name}"
    
# =========================
# PAYMENT MODEL
# =========================

class Payment(models.Model):

    GATEWAY_CHOICES = (
        ("razorpay", "Razorpay"),
        ("paytm", "Paytm"),
        ("payglocal", "PayGlocal"),
    )

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    )

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="payments"
    )

    customer = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    # -------------------------
    # Razorpay
    # -------------------------
    razorpay_order_id = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    razorpay_payment_id = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    razorpay_signature = models.CharField(
        max_length=500,
        blank=True,
        null=True
    )

    # -------------------------
    # Paytm
    # -------------------------
    paytm_order_id = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    paytm_txn_id = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    paytm_bank_txn_id = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    paytm_txn_token = models.TextField(
        blank=True,
        null=True
    )

    payment_mode = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    # -------------------------
    # Common Gateway Fields
    # -------------------------
    payment_gateway = models.CharField(
        max_length=20,
        choices=GATEWAY_CHOICES,
        default="razorpay"
    )

    gateway_order_id = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    gateway_transaction_id = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    gateway_response = models.JSONField(
        default=dict,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"{self.order.id} - {self.payment_gateway} - {self.status}"
    

from django.db import models
from .models import User, Product

#-------------------------
# WISHLIST MODEL
# -------------------------

class Wishlist(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="wishlist"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="wishlist"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "product")

    def __str__(self):
        return f"{self.user} - {self.product}"
    
class OTPVerification(models.Model):
    mobile = models.CharField(
        max_length=15,
        db_index=True
    )

    otp = models.CharField(
        max_length=6
    )

    expires_at = models.DateTimeField()

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"OTP - {self.mobile}"
