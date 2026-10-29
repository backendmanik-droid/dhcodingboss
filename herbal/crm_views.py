import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.db.models import Sum, Count
from django.utils import timezone
from .models import *
from .views import get_image_url, create_and_send_notification, get_role, send_sms_otp, send_email_with_fallback
import random
from django.core.mail import send_mail
from django.conf import settings
from .serializers import ProductReviewCRMSerializer
from rest_framework.decorators import api_view
from rest_framework.response import Response

# 
# CRM LOGIN / LOGOUT / PROFILE
# 

@csrf_exempt
def crm_login(request):
    """
    CRM Login Endpoint
    POST /api/crm/login/
    Body: { "mobile": "9999999999", "password": "yourpassword" }
    Returns: user details + role
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            mobile   = (data.get('mobile') or '').strip()
            password = (data.get('password') or '').strip()

            if not mobile or not password:
                return JsonResponse({'success': False, 'message': 'Mobile and password are required.'}, status=400)

            user = User.objects.filter(mobile=mobile).first()

            if not user:
                return JsonResponse({'success': False, 'message': 'User not found.'}, status=404)

            if user.password != password:
                return JsonResponse({'success': False, 'message': 'Invalid mobile or password.'}, status=401)
            return JsonResponse({
                "success": True,
                "message": "Login successful",
                "user": {
                    "id": user.id,
                    "name": user.name,
                    "mobile": user.mobile,
                    "email": user.email,
                    "role": user.role,
                    "can_send_notifications": user.can_send_notifications,
                    "created_at": user.created_at.strftime("%Y-%m-%d"),
                },
                "permissions": {
                    "add_products": user.role == "admin",
                    "edit_products": user.role == "admin",
                    "delete_products": user.role == "admin",
                    "change_prices": user.role == "admin",
                    "manage_orders": user.role in ["admin", "staff"],
                    "manage_customers": user.role in ["admin", "staff"],
                    "manage_staff": user.role == "admin",
                    "send_whatsapp": user.role == "admin",
                    "send_emails": user.role == "admin",
                    "view_reports": user.role in ["admin", "staff"],
                    "print_bills": user.role in ["admin", "staff"],
                    "full_access": user.role == "admin",
                }
            }, status=200)

        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)

    return JsonResponse({'message': 'Method not allowed'}, status=405)


@csrf_exempt
def admin_login(request):

    if request.method == 'POST':
        try:
            data = json.loads(request.body)

            mobile = (data.get('mobile') or '').strip()
            password = (data.get('password') or '').strip()

            if not mobile or not password:
                return JsonResponse(
                    {
                        'success': False,
                        'message': 'Mobile and password are required.'
                    },
                    status=400
                )

            user = User.objects.filter(mobile=mobile).first()

            if not user:
                return JsonResponse(
                    {
                        'success': False,
                        'message': 'User not found.'
                    },
                    status=404
                )

            if user.password != password:
                return JsonResponse(
                    {
                        'success': False,
                        'message': 'Invalid mobile or password.'
                    },
                    status=401
                )

            if user.role != 'admin':
                return JsonResponse(
                    {
                        'success': False,
                        'message': 'Access denied. Admin login only.'
                    },
                    status=403
                )

            return JsonResponse({
                "success": True,
                "message": "Admin login successful",
                "user": {
                    "id": user.id,
                    "name": user.name,
                    "mobile": user.mobile,
                    "email": user.email,
                    "role": user.role,
                    "can_send_notifications": user.can_send_notifications,
                    "created_at": user.created_at.strftime("%Y-%m-%d"),
                }
            }, status=200)

        except Exception as e:
            return JsonResponse(
                {
                    'success': False,
                    'message': str(e)
                },
                status=500
            )

    return JsonResponse(
        {
            'message': 'Method not allowed'
        },
        status=405
    )

@csrf_exempt
def crm_logout(request):
    """
    CRM Logout Endpoint
    POST /api/crm/logout/
    Returns: logout confirmation
    """
    if request.method == 'POST':
        return JsonResponse({'success': True, 'message': 'Logged out successfully.'})
    return JsonResponse({'message': 'Method not allowed'}, status=405)


@csrf_exempt
def crm_profile(request):
    """
    Get user profile by ID
    GET /api/crm/profile/<id>/
    """
    if request.method == 'GET':
        user_id = request.GET.get('user_id')
        if not user_id:
            return JsonResponse({'error': 'user_id is required'}, status=400)
        user = get_object_or_404(User, id=user_id)
        return JsonResponse({
            'id':     user.id,
            'name':   user.name,
            'mobile': user.mobile,
            'email':  user.email,
            'role':   user.role,
            'created_at': user.created_at.strftime('%Y-%m-%d'),
        })
    return JsonResponse({'message': 'Method not allowed'}, status=405)


@csrf_exempt
def crm_users(request):
    """
    List all users (admin + staff + customers)
    GET /api/crm/users/?role=admin|staff|customer
    """
    if request.method == 'GET':
        role = request.GET.get('role')
        qs = User.objects.all().order_by('-id')
        if role:
            qs = qs.filter(role=role)
        data = [{
            'id':     u.id,
            'name':   u.name,
            'mobile': u.mobile,
            'email':  u.email,
            'role':   u.role,
            'created_at': u.created_at.strftime('%Y-%m-%d'),
        } for u in qs]
        return JsonResponse(data, safe=False)
    return JsonResponse({'message': 'Method not allowed'}, status=405)

# Helper to check staff or admin role
def is_admin_or_staff(request):
    role = (request.headers.get('X-Role') or request.GET.get('role') or 'customer').lower()
    return role in ['admin', 'staff']

# Helper to check admin role only
def is_admin(request):
    role = (request.headers.get('X-Role') or request.GET.get('role') or 'customer').lower()
    return role == 'admin'

# 
# PRODUCT ENDPOINTS
# 
@csrf_exempt
def crm_products(request):
    if request.method == 'GET':
        products = Product.objects.all().order_by('-id')
        data = []
        for p in products:
            data.append({
                'id': p.id,
                'name': p.name,
                'category': p.category.name if p.category else None,
                'category_id': p.category.id if p.category else None,
                'brand': p.brand.name if p.brand else None,
                'brand_id': p.brand.id if p.brand else None,
                'description': p.description,
                'product_code': p.product_code,
                'barcode': p.barcode,
                'tamil_name': p.tamil_name,
                'product_type': p.product_type,
                'unit': p.unit,
                'weight_volume': p.weight_volume,
                'purchase_price': str(p.purchase_price) if p.purchase_price else '0',
                'mrp': str(p.mrp),
                'customer_price': str(p.customer_price),
                'store_price': str(p.store_price) if p.store_price else '0',
                'reseller_price': str(p.reseller_price) if p.reseller_price else '0',
                'retailer_price': str(p.retailer_price),
                'distributor_price': str(p.distributor_price),
                'sarvo_price': str(p.sarvo_price) if p.sarvo_price else '0',
                'drug_price': str(p.drug_price) if p.drug_price else '0',
                'gst_percentage': str(p.gst_percentage) if p.gst_percentage else '0',
                'stock': p.stock,
                'erp_item_id': p.erp_item_id,
                'reorder_level': p.reorder_level,
                'expiry_date': str(p.expiry_date) if p.expiry_date else None,
                'batch_number': p.batch_number,
                'manufacturer': p.manufacturer,
                'image': get_image_url(request, p.image),
                'is_new': p.is_new,
                'is_public': p.is_public,
                'status': 'active' if p.is_active else 'inactive',
                'created_at': p.created_at.isoformat()
            })
        return JsonResponse(data, safe=False, json_dumps_params={'ensure_ascii': False})

    elif request.method == 'POST':
        # Create a new product (Admin only)
        # Temporarily bypassed for frontend testing: if not is_admin(request):
        #     return JsonResponse({'error': 'Unauthorized'}, status=403)
        try:
            try:
                data = json.loads(request.body)
            except (json.JSONDecodeError, UnicodeDecodeError):
                from django.http import QueryDict
                data = request.POST if request.POST else QueryDict(request.body)

            category_id = data.get('category')
            if not category_id:
                return JsonResponse({'error': 'category ID is required'}, status=400)

            category = get_object_or_404(Category, id=category_id)
            brand = Brand.objects.filter(id=data.get('brand')).first() if data.get('brand') else None

            p = Product.objects.create(
                category=category,
                brand=brand,
                name=data.get('name'),
                erp_item_id=data.get('erp_item_id') or None,
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
                mrp=data.get('mrp', 0.00),
                customer_price=data.get('customer_price', 0.00),
                store_price=data.get('store_price', 0.00),
                reseller_price=data.get('reseller_price', 0.00),
                retailer_price=data.get('retailer_price', 0.00),
                distributor_price=data.get('distributor_price', 0.00),
                sarvo_price=data.get('sarvo_price', 0.00),
                drug_price=data.get('drug_price', 0.00),
                gst_percentage=data.get('gst_percentage') or data.get('gst') or 0,
                expiry_date=data.get('expiry_date') or None,
                batch_number=data.get('batch_number') or None,
                manufacturer=data.get('manufacturer') or 'Dharani Herbals',
                image=request.FILES.get('image'),
                is_new=data.get('is_new', 'false') if isinstance(data.get('is_new'), bool) else str(data.get('is_new', 'false')).lower() in ['true', 'on'],
                is_public=data.get('is_public', 'true') if isinstance(data.get('is_public'), bool) else str(data.get('is_public', 'true')).lower() in ['true', 'on'],
                is_active=data.get('is_active', 'true') if isinstance(data.get('is_active'), bool) else str(data.get('is_active', 'true')).lower() in ['true', 'on']
            )
            return JsonResponse({'message': 'Product added successfully', 'id': p.id}, status=201)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': f'Failed to create product: {str(e)}'}, status=400)

@csrf_exempt
def crm_product_detail(request, pk):
    product = get_object_or_404(Product, id=pk)
    
    if request.method == 'GET':
        return JsonResponse({
            'id': product.id,
            'name': product.name,
            'category': product.category.name if product.category else None,
            'category_id': product.category.id if product.category else None,
            'brand': product.brand.name if product.brand else None,
            'brand_id': product.brand.id if product.brand else None,
            'description': product.description,
            'product_code': product.product_code,
            'barcode': product.barcode,
            'tamil_name': product.tamil_name,
            'erp_item_id': product.erp_item_id,
            'product_type': product.product_type,
            'unit': product.unit,
            'weight_volume': product.weight_volume,
            'purchase_price': str(product.purchase_price) if product.purchase_price else '0',
            'mrp': str(product.mrp),
            'customer_price': str(product.customer_price),
            'store_price': str(product.store_price) if product.store_price else '0',
            'reseller_price': str(product.reseller_price) if product.reseller_price else '0',
            'retailer_price': str(product.retailer_price),
            'distributor_price': str(product.distributor_price),
            'sarvo_price': str(product.sarvo_price) if product.sarvo_price else '0',
            'drug_price': str(product.drug_price) if product.drug_price else '0',
            'gst_percentage': str(product.gst_percentage) if product.gst_percentage else '0',
            'stock': product.stock,
            'reorder_level': product.reorder_level,
            'expiry_date': str(product.expiry_date) if product.expiry_date else None,
            'batch_number': product.batch_number,
            'manufacturer': product.manufacturer,
            'image': get_image_url(request, product.image),
            'is_new': product.is_new,
            'is_public': product.is_public,
            'status': 'active' if product.is_active else 'inactive',
            'created_at': product.created_at.isoformat()
        }, json_dumps_params={'ensure_ascii': False})

    elif request.method == 'PUT':
        # Temporarily bypassed for frontend testing: if not is_admin(request):
        #     return JsonResponse({'error': 'Unauthorized'}, status=403)
        try:

            if request.content_type and "multipart/form-data" in request.content_type:
                data = request.POST
            else:
                try:
                    data = json.loads(request.body)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    from django.http import QueryDict
                    data = QueryDict(request.body)
                
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
            if data.get('erp_item_id') is not None:
                product.erp_item_id = data.get('erp_item_id') or None

            for field_name in ['mrp', 'customer_price', 'store_price', 'reseller_price',
                               'retailer_price', 'distributor_price', 'sarvo_price',
                               'drug_price', 'gst_percentage', 'purchase_price']:
                raw_val = data.get(field_name)
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

            for bool_field in ['is_new', 'is_public', 'is_active']:
                raw_val = data.get(bool_field)
                if raw_val is not None and raw_val != '':
                    if isinstance(raw_val, str):
                        setattr(product, bool_field, raw_val.lower() in ('true', 'on'))
                    else:
                        setattr(product, bool_field, bool(raw_val))
            
            # If they pass a new category, update it
            if data.get('category'):
                category = Category.objects.filter(id=data.get('category')).first()
                if category:
                    product.category = category

            print("CONTENT TYPE:", request.content_type)
            print("FILES:", request.FILES)

            image = request.FILES.get("image")
            print("IMAGE:", image)

            if image:
                product.image = image

            product.save()
            return JsonResponse({'message': 'Product updated successfully'})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': f'Failed to parse PUT data: {str(e)}'}, status=400)

    elif request.method == 'DELETE':
        # Temporarily bypassed for frontend testing: if not is_admin(request):
        #     return JsonResponse({'error': 'Unauthorized'}, status=403)
        product.delete()
        return JsonResponse({'message': 'Product deleted successfully'})

@csrf_exempt
def crm_product_upload_image(request, pk):
    if request.method == 'POST':
        if not is_admin(request):
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        product = get_object_or_404(Product, id=pk)
        image = request.FILES.get('image')
        if not image:
            return JsonResponse({'error': 'No image file uploaded'}, status=400)
        product.image = image
        product.save()
        return JsonResponse({'message': 'Image uploaded successfully', 'url': get_image_url(request, product.image)})
    
# =
# PRODUCT VARIATION POST, GET
# =

def get_valid_price(val):
    if val and float(val) > 0:
        return str(val)
    return None

@csrf_exempt
def product_variations(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    # === GET (CRM + WEB) ===
    if request.method == "GET":

        role = get_role(request)

        variations = ProductVariation.objects.filter(product=product)

        data = []

        for v in variations:

            item = {
                "id": v.id,
                "product_id": product.id,
                "variation_name": v.variation_name,
                "sku": v.sku,
                "barcode": v.barcode,
                "discount": str(v.discount or 0),
                "weight_volume": v.weight_volume,
                "erp_item_id": v.erp_item_id,
                "mrp": str(v.mrp),
                "gst_percentage": str(v.gst_percentage),
                "stock": v.stock,
                "is_active": v.is_active,
                "price": None
            }

            if role == "admin":

                item.update({
                    "price": get_valid_price(v.customer_price),
                    "purchase_price": get_valid_price(v.purchase_price),
                    "customer_price": get_valid_price(v.customer_price),
                    "store_price": get_valid_price(v.store_price),
                    "reseller_price": get_valid_price(v.reseller_price),
                    "retailer_price": get_valid_price(v.retailer_price),
                    "distributor_price": get_valid_price(v.distributor_price),
                    "sarvo_price": get_valid_price(v.sarvo_price),
                    "drug_price": get_valid_price(v.drug_price),
                })

            elif role == "staff":

                item["price"] = get_valid_price(v.store_price)
                item["store_price"] = get_valid_price(v.store_price)

            elif role == "retailer":

                item["price"] = get_valid_price(v.retailer_price) or get_valid_price(v.customer_price)
                item["retailer_price"] = get_valid_price(v.retailer_price)

            elif role == "distributor":

                item["price"] = get_valid_price(v.distributor_price) or get_valid_price(v.customer_price)
                item["distributor_price"] = get_valid_price(v.distributor_price)

            else:

                item["price"] = get_valid_price(v.customer_price)
                item["customer_price"] = get_valid_price(v.customer_price)

            data.append(item)

        return JsonResponse(data, safe=False)
    # === POST (CRM only) ===
    elif request.method == "POST":
        try:
            if request.content_type and "application/json" in request.content_type:
                data = json.loads(request.body.decode("utf-8")) if request.body else {}
            else:
                data = request.POST

            variation = ProductVariation.objects.create(
                product=product,
                variation_name=data.get("variation_name") or data.get("attribute_value"),
                sku=data.get("sku"),
                barcode=data.get("barcode"),
                discount=data.get("discount", 0),
                weight_volume=data.get("weight_volume"),
                erp_item_id=data.get("erp_item_id"),

                purchase_price=data.get("purchase_price", 0),
                mrp=data.get("mrp", 0),
                customer_price=data.get("customer_price", 0),
                store_price=data.get("store_price", 0),
                reseller_price=data.get("reseller_price", 0),
                retailer_price=data.get("retailer_price", 0),
                distributor_price=data.get("distributor_price", 0),
                sarvo_price=data.get("sarvo_price", 0),
                drug_price=data.get("drug_price", 0),

                gst_percentage=data.get("gst_percentage", 0),
                stock=data.get("stock", 0),
                is_active=data.get("is_active", True),
            )

            return JsonResponse({
                "message": "Variation created",
                "id": variation.id
            }, status=201)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
        
# ====
# VARIATION PUT,DELETE
# ====


@csrf_exempt
def product_variation_detail(request, id):
    variation = get_object_or_404(ProductVariation, id=id)

    # === PUT ===
    if request.method == "PUT":
        try:
            data = request.POST if request.POST else json.loads(request.body)

            variation.variation_name = (
                data.get("variation_name")
                or data.get("attribute_value")
                or variation.variation_name
            )
            variation.sku = data.get(
                "sku",
                variation.sku
            )

            variation.barcode = data.get(
                "barcode",
                variation.barcode
            )

            variation.discount = data.get(
                "discount",
                variation.discount
            )

            variation.weight_volume = data.get(
                "weight_volume",
                variation.weight_volume
            )

            variation.purchase_price = data.get("purchase_price", variation.purchase_price)
            variation.mrp = data.get("mrp", variation.mrp)
            variation.customer_price = data.get("customer_price", variation.customer_price)
            variation.store_price = data.get("store_price", variation.store_price)
            variation.reseller_price = data.get("reseller_price", variation.reseller_price)
            variation.retailer_price = data.get("retailer_price", variation.retailer_price)
            variation.distributor_price = data.get("distributor_price", variation.distributor_price)
            variation.sarvo_price = data.get("sarvo_price", variation.sarvo_price)
            variation.drug_price = data.get("drug_price", variation.drug_price)

            variation.gst_percentage = data.get("gst_percentage", variation.gst_percentage)
            variation.stock = data.get("stock", variation.stock)
            variation.is_active = data.get("is_active", variation.is_active)

            variation.erp_item_id = data.get("erp_item_id", variation.erp_item_id)

            variation.save()

            return JsonResponse({"message": "Variation updated"})

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    # === DELETE ===
    elif request.method == "DELETE":
        variation.delete()
        return JsonResponse({"message": "Variation deleted"})



@csrf_exempt
def crm_product_print(request, pk):
    product = get_object_or_404(Product, id=pk)
    return JsonResponse({
        'id': product.id,
        'name': product.name,
        'barcode': product.barcode or f"BAR-{product.id:06d}",
        'mrp': str(product.mrp),
        'customer_price': str(product.customer_price)
    })


# 
# CATEGORY ENDPOINTS
# 

@csrf_exempt
def crm_categories(request):

    # 
    # GET - List Categories
    # 
    if request.method == "GET":

        categories = Category.objects.all().order_by("name")

        data = []

        for category in categories:

            data.append({
                "id": category.id,
                "name": category.name,
                "image": get_image_url(request, category.image),
                "status": "active"
            })

        return JsonResponse({
            "success": True,
            "total": len(data),
            "data": data
        }, status=200)

    # 
    # POST - Create Category
    # 
    elif request.method == "POST":

        try:

            name = request.POST.get("name")
            image = request.FILES.get("image")

            if not name:
                return JsonResponse({
                    "success": False,
                    "message": "Category name is required"
                }, status=400)

            if Category.objects.filter(name=name).exists():
                return JsonResponse({
                    "success": False,
                    "message": "Category already exists"
                }, status=400)

            category = Category.objects.create(
                name=name,
                image=image
            )

            return JsonResponse({
                "success": True,
                "message": "Category created successfully",
                "id": category.id,
                "name": category.name,
                "image": get_image_url(request, category.image)
            }, status=201)

        except Exception as e:

            return JsonResponse({
                "success": False,
                "message": str(e)
            }, status=400)

    return JsonResponse({
        "message": "Method not allowed"
    }, status=405)

@csrf_exempt
def crm_category_detail(request, category_id):

    category = get_object_or_404(
        Category,
        id=category_id
    )

    # 
    # PUT - Update Category
    # 
    if request.method == "PUT":

        try:

            data = request.POST if request.POST else json.loads(request.body)

            category.name = data.get(
                "name",
                category.name
            )

            if request.FILES.get("image"):
                category.image = request.FILES.get("image")

            category.save()

            return JsonResponse({
                "success": True,
                "message": "Category updated successfully",
                "id": category.id,
                "name": category.name,
                "image": get_image_url(request, category.image)
            })

        except Exception as e:

            return JsonResponse({
                "success": False,
                "message": str(e)
            }, status=400)

    # 
    # DELETE - Delete Category
    # 
    elif request.method == "DELETE":

        category.delete()

        return JsonResponse({
            "success": True,
            "message": "Category deleted successfully"
        })

    return JsonResponse({
        "message": "Method not allowed"
    }, status=405)

# 
# BRAND ENDPOINTS
# 

@csrf_exempt
def crm_brands(request):

    # GET → Public
    if request.method == 'GET':
        brands = Brand.objects.all()

        data = [
            {
                'id': b.id,
                'name': b.name,
                'logo': get_image_url(request, b.image),
                'status': 'active'
            }
            for b in brands
        ]

        return JsonResponse({
            'success': True,
            'data': data
        })

    # POST → Public (No admin check)
    elif request.method == 'POST':

        name = request.POST.get('name')
        logo = request.FILES.get('logo') or request.FILES.get('image')

        if not name:
            return JsonResponse({
                'error': 'Brand Name is required'
            }, status=400)

        brand = Brand.objects.create(
            name=name,
            image=logo
        )

        return JsonResponse({
            'success': True,
            'message': 'Brand added successfully',
            'id': brand.id,
            'name': brand.name,
            'logo': get_image_url(request, brand.image)
        }, status=201)

    return JsonResponse({
        'error': 'Method not allowed'
    }, status=405)

@csrf_exempt
def crm_brand_detail(request, brand_id):

    brand = get_object_or_404(
        Brand,
        id=brand_id
    )

    # 
    # PUT - Update Brand
    # 
    if request.method == "PUT":

        try:

            data = request.POST if request.POST else json.loads(request.body)

            brand.name = data.get(
                "name",
                brand.name
            )

            if request.FILES.get("logo"):
                brand.image = request.FILES.get("logo")

            elif request.FILES.get("image"):
                brand.image = request.FILES.get("image")

            brand.save()

            return JsonResponse({
                "success": True,
                "message": "Brand updated successfully",
                "id": brand.id,
                "name": brand.name,
                "logo": get_image_url(request, brand.image)
            })

        except Exception as e:

            return JsonResponse({
                "success": False,
                "message": str(e)
            }, status=400)

    # 
    # DELETE - Delete Brand
    # 
    elif request.method == "DELETE":

        brand.delete()

        return JsonResponse({
            "success": True,
            "message": "Brand deleted successfully"
        })

    return JsonResponse({
        "message": "Method not allowed"
    }, status=405)

@csrf_exempt
def crm_brand_detail(request, brand_id):

    brand = get_object_or_404(Brand, id=brand_id)

    if request.method == "PUT":

        name = request.POST.get("name")

        if not name:
            try:
                data = json.loads(request.body)
                name = data.get("name")
            except:
                pass

        if name:
            brand.name = name

        if request.FILES.get("logo"):
            brand.image = request.FILES.get("logo")

        elif request.FILES.get("image"):
            brand.image = request.FILES.get("image")

        brand.save()

        return JsonResponse({
            "success": True,
            "message": "Brand updated successfully"
        })

    elif request.method == "DELETE":

        brand.delete()

        return JsonResponse({
            "success": True,
            "message": "Brand deleted successfully"
        })

    return JsonResponse({
        "error": "Method not allowed"
    }, status=405)

# 
# SLIDER ENDPOINTS
# 
@csrf_exempt
def crm_sliders(request):
    if request.method == 'GET':
        sliders = Slider.objects.filter(is_active=True).order_by('order')
        data = [{
            'id': s.id,
            'title': s.title,
            'image': get_image_url(request, s.image),
            'status': 'active'
        } for s in sliders]
        return JsonResponse(data, safe=False)

    elif request.method == 'POST':
        if not is_admin(request):
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        title = request.POST.get('title', '')
        subtitle = request.POST.get('subtitle', '')
        image = request.FILES.get('image')
        if not image:
            return JsonResponse({'error': 'Slider Image is required'}, status=400)
        s = Slider.objects.create(title=title, subtitle=subtitle, image=image)
        return JsonResponse({'message': 'Slider added successfully', 'id': s.id}, status=201)

@csrf_exempt
def crm_slider_detail(request, pk):
    slider = get_object_or_404(Slider, id=pk)
    if request.method == 'PUT':
        if not is_admin(request):
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        data = json.loads(request.body)
        slider.title = data.get('title', slider.title)
        slider.subtitle = data.get('subtitle', slider.subtitle)
        slider.is_active = data.get('is_active', slider.is_active)
        slider.save()
        return JsonResponse({'message': 'Slider updated successfully'})
    
    elif request.method == 'DELETE':
        if not is_admin(request):
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        slider.delete()
        return JsonResponse({'message': 'Slider deleted successfully'})

# 
# CUSTOMER ENDPOINTS
# 
@csrf_exempt
def crm_customers(request):
    if request.method == 'GET':
        customers = User.objects.filter(role='customer').order_by('-id')
        data = [{
            'id': c.id,
            'name': c.name,
            'mobile': c.mobile,
            'email': c.email,
            'price_category': c.price_category,
            'creditPaymentEnabled': getattr(c, 'credit_payment_enabled', False),
            'creditLimit': float(getattr(c, 'credit_limit', 0.00)),
            'balance': float(getattr(c, 'credit_limit', 0.00) - getattr(c, 'available_credit', 0.00)),
            'available_credit': float(getattr(c, 'available_credit', 0.00)),
            'status': 'active'
        } for c in customers]
        return JsonResponse({"success": True, "data": data}, safe=False)

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            current_user_role = (request.headers.get('X-Role') or request.GET.get('role') or 'customer').lower()
            target_role = data.get('userType') or data.get('role', 'customer').lower()

            if current_user_role == 'admin':
                allowed_roles = ['staff', 'retailer', 'distributor', 'customer']
            elif current_user_role == 'staff':
                allowed_roles = ['retailer', 'distributor', 'customer']
            elif current_user_role in ['retailer', 'distributor']:
                allowed_roles = ['customer']
            else:
                return JsonResponse({'error': 'Permission denied'}, status=403)

            if target_role not in allowed_roles:
                return JsonResponse({'error': f'You cannot create {target_role}'}, status=403)

            c = User.objects.create(
                name=data.get('name') or data.get('full_name'),
                mobile=data.get('phone') or data.get('mobile'),
                email=data.get('email'),
                password=data.get('password', '12345678'),
                role=target_role,
                
                customer_code=data.get('customer_code'),
                alternate_phone=data.get('alternate_phone'),
                default_logistics=data.get('default_logistics'),
                preferred_payment_method=data.get('preferred_payment_method'),
                mode_of_communication=data.get('mode_of_communication'),
                credit_payment_enabled=data.get('creditPayment') or data.get('creditPaymentEnabled', False),
                credit_limit=data.get('credit_limit') or data.get('creditLimit') or 0.00,
                available_credit=data.get('available_credit') or data.get('credit_limit') or data.get('creditLimit') or 0.00,
                gst_number=data.get('gst_number')
            )
            
            # Add Addresses
            addresses = data.get("addresses", [])
            for addr in addresses:
                Address.objects.create(
                    user=c,
                    full_name=c.name,
                    phone=c.mobile,
                    address_type=addr.get("type", ""),
                    address=addr.get("address", ""),
                    city=addr.get("city", ""),
                    state=addr.get("state", ""),
                    pincode=addr.get("pincode", "")
                )
                
            return JsonResponse({'message': f'{target_role.capitalize()} registered successfully', 'id': c.id}, status=201)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
        
import json
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def crm_customer_detail(request, pk):
    customer = get_object_or_404(User, id=pk, role="customer")

    if request.method == "GET":
        # Get Address (using first address for both billing and shipping as fallback)
        address_obj = customer.addresses.first()
        address_data = None
        if address_obj:
            address_data = {
                "address": address_obj.address,
                "area": "", # Not in model, leave empty or map to address
                "city": address_obj.city,
                "state": address_obj.state,
                "country": "India", # Default
                "pincode": address_obj.pincode
            }

        # Get Purchase History
        orders = Order.objects.filter(customer=customer).order_by('-created_at')
        purchase_history = []
        for o in orders:
            purchase_history.append({
                "order_id": f"ORD-{o.created_at.year}-{o.id}",
                "invoice_number": o.invoice_number or "",
                "date": o.created_at.strftime('%Y-%m-%d'),
                "amount": float(o.total_amount),
                "status": dict(Order.STATUS_CHOICES).get(o.status, o.status)
            })

        return JsonResponse({
            "id": customer.id,
            "customer_code": customer.customer_code,
            "name": customer.name,
            "phone": customer.mobile, # Frontend expects phone
            "alternate_phone": customer.alternate_phone,
            "email": customer.email,
            "userType": customer.role, # Map role to userType
            
            "billing_address": address_data,
            "shipping_address": address_data,
            
            "default_logistics": customer.default_logistics,
            "preferred_payment_method": customer.preferred_payment_method,
            "mode_of_communication": customer.mode_of_communication,
            
            "creditPaymentEnabled": customer.credit_payment_enabled,
            "creditLimit": float(customer.credit_limit),
            "balance": float(customer.credit_limit - customer.available_credit),
            "available_credit": float(customer.available_credit),
            
            "gst_number": customer.gst_number,
            "status": "active",
            
            "purchase_history": purchase_history
        })

    elif request.method in ["PUT", "PATCH"]:
        try:
            data = json.loads(request.body)

            if "name" in data:
                customer.name = data["name"]

            if "phone" in data or "mobile" in data:
                mobile = data.get("phone") or data.get("mobile")
                if User.objects.exclude(id=customer.id).filter(mobile=mobile).exists():
                    return JsonResponse({"error": "Mobile already exists."}, status=400)
                customer.mobile = mobile

            if "email" in data:
                if User.objects.exclude(id=customer.id).filter(email=data["email"]).exists():
                    return JsonResponse({"error": "Email already exists."}, status=400)
                customer.email = data["email"]
                
            if "userType" in data:
                customer.role = data["userType"]

            # Update CRM fields
            if "customer_code" in data: customer.customer_code = data["customer_code"]
            if "alternate_phone" in data: customer.alternate_phone = data["alternate_phone"]
            if "default_logistics" in data: customer.default_logistics = data["default_logistics"]
            if "preferred_payment_method" in data: customer.preferred_payment_method = data["preferred_payment_method"]
            if "mode_of_communication" in data: customer.mode_of_communication = data["mode_of_communication"]
            if "creditPayment" in data: customer.credit_payment_enabled = data["creditPayment"]
            if "creditPaymentEnabled" in data: customer.credit_payment_enabled = data["creditPaymentEnabled"]
            if "creditLimit" in data: customer.credit_limit = Decimal(str(data["creditLimit"] or 0))
            if "available_credit" in data: customer.available_credit = Decimal(str(data["available_credit"] or 0))
            elif "balance" in data: customer.available_credit = customer.credit_limit - Decimal(str(data["balance"] or 0))
            if "gst_number" in data: customer.gst_number = data["gst_number"]

            customer.save()
            
            # Update Addresses
            if "addresses" in data:
                # Safest way to update nested addresses without tracking IDs is to recreate them
                customer.addresses.all().delete()
                
                for addr in data["addresses"]:
                    Address.objects.create(
                        user=customer,
                        full_name=customer.name,
                        phone=customer.mobile,
                        address_type=addr.get("type", ""),
                        address=addr.get("address", ""),
                        city=addr.get("city", ""),
                        state=addr.get("state", ""),
                        pincode=addr.get("pincode", "")
                    )

            return JsonResponse({
                "message": "Customer updated successfully."
            })

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    elif request.method == "DELETE":
        customer.delete()
        return JsonResponse({
            "message": "Customer deleted successfully."
        })

    return JsonResponse({"error": "Method Not Allowed"}, status=405)

@csrf_exempt
def crm_customer_print(request, pk):
    customer = get_object_or_404(User, id=pk, role='customer')
    orders = Order.objects.filter(customer=customer).order_by('-created_at')
    orders_data = [{
    'id': o.id,
    # 'product_amount': str(o.product_amount),
    # 'gst_amount': str(o.gst_amount),
    # 'shipping_charges': str(o.shipping_charges),
    'total': str(o.total_amount),
    'status': o.status,
    'date': o.created_at.strftime('%Y-%m-%d')
} for o in orders]
    return JsonResponse({
        'customer': {
            'name': customer.name,
            'mobile': customer.mobile,
            'email': customer.email
        },
        'ledger': orders_data
    })


@csrf_exempt
def crm_most_loved_products(request):

    if request.method == "GET":

        loved_products = MostLovedProduct.objects.select_related(
            "product"
        ).order_by(
            "display_order",
            "-id"
        )

        data = []

        for obj in loved_products:

            p = obj.product

            data.append({

                "id": obj.id,

                "product_id": p.id,

                "product_name": p.name,

                "product_code": p.product_code,

                "display_order": obj.display_order,

                "is_active": obj.is_active,

                "image": get_image_url(request, p.image),

                "created_at": obj.created_at.isoformat()

            })

        return JsonResponse(
            data,
            safe=False,
            json_dumps_params={"ensure_ascii": False}
        )

    return JsonResponse(
        {
            "message": "Method not allowed"
        },
        status=405
    )

@csrf_exempt
def crm_update_most_loved(request):

    if request.method != "PUT":
        return JsonResponse({"message": "Method not allowed"}, status=405)

    try:

        data = json.loads(request.body)

        product_id = data.get("product_id")
        is_active = data.get("is_active", True)
        display_order = data.get("display_order", 0)

        if not product_id:
            return JsonResponse({"message": "Product id is required"}, status=400)

        product = Product.objects.filter(id=product_id).first()

        if not product:
            return JsonResponse({"message": "Product not found"}, status=404)

        loved, created = MostLovedProduct.objects.get_or_create(
            product=product,
            defaults={
                "is_active": is_active,
                "display_order": display_order
            }
        )

        if not created:
            loved.is_active = is_active
            loved.display_order = display_order
            loved.save()

        return JsonResponse({
            "message": "Most Loved updated successfully",
            "data": {
                "id": loved.id,
                "product_id": product.id,
                "product_name": product.name,
                "is_active": loved.is_active,
                "display_order": loved.display_order
            }
        })

    except Exception as e:
        return JsonResponse({"message": str(e)}, status=400)

# 
# CART ENDPOINTS
# 
@csrf_exempt
def crm_cart_add(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user = get_object_or_404(User, id=data.get('user_id'))
            product = get_object_or_404(Product, id=data.get('product_id'))
            qty = int(data.get('quantity', 1))

            cart_item, created = Cart.objects.get_or_create(user=user, product=product)
            if not created:
                cart_item.quantity += qty
            else:
                cart_item.quantity = qty
            cart_item.save()
            return JsonResponse({'message': 'Item added to cart', 'quantity': cart_item.quantity})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

@csrf_exempt
def crm_cart_update(request):
    if request.method == 'PUT':
        try:
            data = json.loads(request.body)
            user = get_object_or_404(User, id=data.get('user_id'))
            product = get_object_or_404(Product, id=data.get('product_id'))
            qty = int(data.get('quantity'))

            cart_item = get_object_or_404(Cart, user=user, product=product)
            if qty <= 0:
                cart_item.delete()
                return JsonResponse({'message': 'Item removed from cart'})
            cart_item.quantity = qty
            cart_item.save()
            return JsonResponse({'message': 'Cart updated successfully', 'quantity': cart_item.quantity})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

@csrf_exempt
def crm_cart_remove(request, pk):
    if request.method == 'DELETE':
        cart_item = get_object_or_404(Cart, id=pk)
        cart_item.delete()
        return JsonResponse({'message': 'Item removed from cart'})

@csrf_exempt
def crm_cart(request):
    if request.method == 'GET':
        user_id = request.GET.get('user_id')
        if not user_id:
            return JsonResponse({'error': 'User ID required'}, status=400)
        user = get_object_or_404(User, id=user_id)
        items = Cart.objects.filter(user=user)
        data = [{
            'id': item.id,
            'product_id': item.product.id,
            'product_name': item.product.name,
            'quantity': item.quantity,
            'price': str(item.product.customer_price),
            'total': str(item.product.customer_price * item.quantity)
        } for item in items]
        return JsonResponse(data, safe=False)

# 
# ORDER ENDPOINTS
# 
@csrf_exempt
def crm_orders(request):
    if request.method == 'GET':
        role = request.GET.get("role")

        orders = Order.objects.all().order_by("-id")

        if role:
            orders = orders.filter(customer__role=role.lower())

        data = [{
            'id': o.id,
            'customer': o.customer.name,
            'customer_role': o.customer.role,
            'product_amount': str(o.product_amount),
            'cgst': str(o.cgst_amount),
            'sgst': str(o.sgst_amount),
            'igst': str(o.igst_amount),
            'tax_total': str(o.gst_amount),
            'shipping_charges': str(o.shipping_charges),
            'total': str(o.total_amount),
            'credit_used': str(getattr(o, 'credit_used', '0.00')),
            'amount_to_pay': str(getattr(o, 'amount_to_pay', '0.00')),
            'status': o.status,
            'date': o.created_at.strftime('%Y-%m-%d %H:%M')
        } for o in orders]
        return JsonResponse(data, safe=False)

# @csrf_exempt
# def crm_order_detail(request, pk):
#     order = get_object_or_404(Order, id=pk)

#     role = request.GET.get("role")

#     if role and order.customer.role.lower() != role.lower():
#         return JsonResponse(
#             {"message": "Order not found"},
#             status=404
#         )

#     if request.method == 'GET':
#         address = order.customer.addresses.filter(
#             is_default=True
#         ).first()

#         if not address:
#             address = order.customer.addresses.first()
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt


# @csrf_exempt
# def crm_order_detail(request, pk):

#     order = get_object_or_404(
#         Order.objects.select_related("customer", "address"),
#         id=pk
#     )

#     role = request.GET.get("role")

#     # -------------------------------------------------
#     # ROLE CHECK
#     # -------------------------------------------------
#     customer_role = getattr(order.customer, "role", "") or ""

#     if role and customer_role.lower() != role.lower():
#         return JsonResponse(
#             {
#                 "success": False,
#                 "message": "Order not found"
#             },
#             status=404
#         )

#     # -------------------------------------------------
#     # GET ORDER DETAILS
#     # -------------------------------------------------
#     if request.method == "GET":

#         try:
#             customer = order.customer

#             # -----------------------------------------
#             # CUSTOMER
#             # -----------------------------------------
#             customer_data = {
#                 "id": customer.id,
#                 "full_name": getattr(customer, "full_name", None),
#                 "name": getattr(customer, "name", None),
#                 "mobile": getattr(customer, "mobile", None),
#                 "email": getattr(customer, "email", None),
#                 "role": getattr(customer, "role", None),
#             }

#             # -----------------------------------------
#             # ADDRESS
#             # -----------------------------------------
#             address = None

#             try:
#                 address = customer.addresses.filter(
#                     is_default=True
#                 ).first()

#                 if not address:
#                     address = customer.addresses.first()

#             except Exception:
#                 address = getattr(order, "address", None)

#             address_data = None

#             if address:
#                 address_data = {
#                     "id": getattr(address, "id", None),
#                     "full_name": getattr(address, "full_name", None),
#                     "name": getattr(address, "name", None),
#                     "phone": getattr(address, "phone", None),
#                     "address": getattr(address, "address", None),
#                     "city": getattr(address, "city", None),
#                     "state": getattr(address, "state", None),
#                     "pincode": getattr(address, "pincode", None),
#                     "postal_code": getattr(address, "postal_code", None),
#                 }

#             # -----------------------------------------
#             # ORDER ITEMS
#             # -----------------------------------------
#             items_data = []

#             for item in order.items.all():

#                 product = getattr(item, "product", None)
#                 variation = getattr(item, "variation", None)

#                 quantity = getattr(item, "quantity", 0)
#                 price = getattr(item, "price", 0)

#                 try:
#                     total = float(price) * int(quantity)
#                 except Exception:
#                     total = getattr(item, "total", 0)

#                 item_data = {
#                     "id": getattr(item, "id", None),

#                     "product_id": getattr(
#                         product,
#                         "id",
#                         None
#                     ),

#                     "product_name": getattr(
#                         product,
#                         "name",
#                         None
#                     ),

#                     "variation_id": getattr(
#                         variation,
#                         "id",
#                         None
#                     ) if variation else None,

#                     "variation": str(
#                         variation
#                     ) if variation else None,

#                     "quantity": quantity,

#                     "price": price,

#                     "total": total,
#                 }

#                 items_data.append(item_data)

#             # -----------------------------------------
#             # ORDER DATA
#             # -----------------------------------------
#             order_data = {
#                 "id": order.id,

#                 "order_id": order.id,

#                 "invoice_number": getattr(
#                     order,
#                     "invoice_number",
#                     None
#                 ),

#                 # CUSTOMER
#                 "customer_id": customer.id,

#                 "customer": customer_data,

#                 # ADDRESS
#                 "address_id": getattr(
#                     getattr(order, "address", None),
#                     "id",
#                     None
#                 ),

#                 "address": address_data,

#                 # BILLING
#                 "billing_address": getattr(
#                     order,
#                     "billing_address",
#                     None
#                 ),

#                 # ORDER DETAILS
#                 "mode_of_communication": getattr(
#                     order,
#                     "mode_of_communication",
#                     None
#                 ),

#                 "logistics": getattr(
#                     order,
#                     "logistics",
#                     None
#                 ),

#                 "remarks": getattr(
#                     order,
#                     "remarks",
#                     None
#                 ),

#                 "payment_method": getattr(
#                     order,
#                     "payment_method",
#                     None
#                 ),

#                 "price_category": getattr(
#                     order,
#                     "price_category",
#                     None
#                 ),

#                 # AMOUNTS
#                 "shipping_charges": getattr(
#                     order,
#                     "shipping_charges",
#                     0
#                 ),

#                 "product_amount": getattr(
#                     order,
#                     "product_amount",
#                     0
#                 ),

#                 "gst_amount": getattr(
#                     order,
#                     "gst_amount",
#                     0
#                 ),

#                 "cgst_amount": getattr(
#                     order,
#                     "cgst_amount",
#                     0
#                 ),

#                 "sgst_amount": getattr(
#                     order,
#                     "sgst_amount",
#                     0
#                 ),

#                 "igst_amount": getattr(
#                     order,
#                     "igst_amount",
#                     0
#                 ),

#                 "total_amount": getattr(
#                     order,
#                     "total_amount",
#                     0
#                 ),
                
#                 "credit_used": getattr(
#                     order,
#                     "credit_used",
#                     0
#                 ),
                
#                 "amount_to_pay": getattr(
#                     order,
#                     "amount_to_pay",
#                     0
#                 ),

#                 # STATUS
#                 "status": getattr(
#                     order,
#                     "status",
#                     None
#                 ),

#                 # ITEMS
#                 "items": items_data,

#                 # DATES
#                 "created_at": (
#                     order.created_at.isoformat()
#                     if getattr(order, "created_at", None)
#                     else None
#                 ),

#                 "updated_at": (
#                     order.updated_at.isoformat()
#                     if getattr(order, "updated_at", None)
#                     else None
#                 ),
#             }

#             return JsonResponse(
#                 {
#                     "success": True,
#                     "message": "Order details fetched successfully",
#                     "data": order_data
#                 },
#                 status=200
#             )

#         except Exception as e:

#             return JsonResponse(
#                 {
#                     "success": False,
#                     "message": "Failed to fetch order details",
#                     "error": str(e)
#                 },
#                 status=500
#             )

#     # -------------------------------------------------
#     # OTHER METHODS
#     # -------------------------------------------------
#     return JsonResponse(
#         {
#             "success": False,
#             "message": "Method not allowed"
#         },
#         status=405
#     )


import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def crm_order_detail(request, pk):

    order = get_object_or_404(
        Order.objects.select_related(
            "customer",
            "address"
        ),
        id=pk
    )

    role = request.GET.get("role")

    # =================================================
    # ROLE CHECK
    # =================================================
    customer_role = getattr(
        order.customer,
        "role",
        ""
    ) or ""

    if role and customer_role.lower() != role.lower():

        return JsonResponse(
            {
                "success": False,
                "message": "Order not found"
            },
            status=404
        )

    # =================================================
    # GET - ORDER DETAILS
    # =================================================
    if request.method == "GET":

        try:

            customer = order.customer

            # -----------------------------------------
            # CUSTOMER
            # -----------------------------------------
            customer_data = {
                "id": customer.id,

                "full_name": getattr(
                    customer,
                    "full_name",
                    None
                ),

                "name": getattr(
                    customer,
                    "name",
                    None
                ),

                "mobile": getattr(
                    customer,
                    "mobile",
                    None
                ),

                "email": getattr(
                    customer,
                    "email",
                    None
                ),

                "role": getattr(
                    customer,
                    "role",
                    None
                ),
            }

            # -----------------------------------------
            # ADDRESS
            # -----------------------------------------
            address = None

            try:

                address = customer.addresses.filter(
                    is_default=True
                ).first()

                if not address:
                    address = customer.addresses.first()

            except Exception:

                address = getattr(
                    order,
                    "address",
                    None
                )

            address_data = None

            if address:

                address_data = {
                    "id": getattr(
                        address,
                        "id",
                        None
                    ),

                    "full_name": getattr(
                        address,
                        "full_name",
                        None
                    ),

                    "name": getattr(
                        address,
                        "name",
                        None
                    ),

                    "phone": getattr(
                        address,
                        "phone",
                        None
                    ),

                    "address": getattr(
                        address,
                        "address",
                        None
                    ),

                    "city": getattr(
                        address,
                        "city",
                        None
                    ),

                    "state": getattr(
                        address,
                        "state",
                        None
                    ),

                    "pincode": getattr(
                        address,
                        "pincode",
                        None
                    ),

                    "postal_code": getattr(
                        address,
                        "postal_code",
                        None
                    ),
                }

            # -----------------------------------------
            # ORDER ITEMS
            # -----------------------------------------
            items_data = []

            for item in order.items.all():

                product = getattr(
                    item,
                    "product",
                    None
                )

                variation = getattr(
                    item,
                    "variation",
                    None
                )

                quantity = getattr(
                    item,
                    "quantity",
                    0
                )

                price = getattr(
                    item,
                    "price",
                    0
                )

                try:

                    total = (
                        float(price) *
                        int(quantity)
                    )

                except Exception:

                    total = getattr(
                        item,
                        "total",
                        0
                    )

                item_data = {

                    "id": getattr(
                        item,
                        "id",
                        None
                    ),

                    "product_id": getattr(
                        product,
                        "id",
                        None
                    ),

                    "product_name": getattr(
                        product,
                        "name",
                        None
                    ),

                    "variation_id": (
                        getattr(
                            variation,
                            "id",
                            None
                        )
                        if variation
                        else None
                    ),

                    "variation": (
                        str(variation)
                        if variation
                        else None
                    ),

                    "quantity": quantity,

                    "price": price,

                    "total": total,
                }

                items_data.append(
                    item_data
                )

            # -----------------------------------------
            # ORDER DATA
            # -----------------------------------------
            order_data = {

                "id": order.id,

                "order_id": order.id,

                "invoice_number": getattr(
                    order,
                    "invoice_number",
                    None
                ),

                # -------------------------------------
                # CUSTOMER
                # -------------------------------------
                "customer_id": customer.id,

                "customer": customer_data,

                # -------------------------------------
                # ADDRESS
                # -------------------------------------
                "address_id": getattr(
                    getattr(
                        order,
                        "address",
                        None
                    ),
                    "id",
                    None
                ),

                "address": address_data,

                # -------------------------------------
                # BILLING
                # -------------------------------------
                "billing_address": getattr(
                    order,
                    "billing_address",
                    None
                ),

                # -------------------------------------
                # ORDER DETAILS
                # -------------------------------------
                "mode_of_communication": getattr(
                    order,
                    "mode_of_communication",
                    None
                ),

                "logistics": getattr(
                    order,
                    "logistics",
                    None
                ),

                "remarks": getattr(
                    order,
                    "remarks",
                    None
                ),

                "payment_method": getattr(
                    order,
                    "payment_method",
                    None
                ),

                "price_category": getattr(
                    order,
                    "price_category",
                    None
                ),

                # -------------------------------------
                # AMOUNTS
                # -------------------------------------
                "shipping_charges": getattr(
                    order,
                    "shipping_charges",
                    0
                ),

                "product_amount": getattr(
                    order,
                    "product_amount",
                    0
                ),

                "gst_amount": getattr(
                    order,
                    "gst_amount",
                    0
                ),

                "cgst_amount": getattr(
                    order,
                    "cgst_amount",
                    0
                ),

                "sgst_amount": getattr(
                    order,
                    "sgst_amount",
                    0
                ),

                "igst_amount": getattr(
                    order,
                    "igst_amount",
                    0
                ),

                "total_amount": getattr(
                    order,
                    "total_amount",
                    0
                ),

                "credit_used": getattr(
                    order,
                    "credit_used",
                    0
                ),

                "amount_to_pay": getattr(
                    order,
                    "amount_to_pay",
                    0
                ),

                # -------------------------------------
                # STATUS
                # -------------------------------------
                "status": getattr(
                    order,
                    "status",
                    None
                ),

                # -------------------------------------
                # ITEMS
                # -------------------------------------
                "items": items_data,

                # -------------------------------------
                # DATES
                # -------------------------------------
                "created_at": (
                    order.created_at.isoformat()
                    if getattr(
                        order,
                        "created_at",
                        None
                    )
                    else None
                ),

                "updated_at": (
                    order.updated_at.isoformat()
                    if getattr(
                        order,
                        "updated_at",
                        None
                    )
                    else None
                ),
            }

            return JsonResponse(
                {
                    "success": True,
                    "message": (
                        "Order details fetched "
                        "successfully"
                    ),
                    "data": order_data
                },
                status=200
            )

        except Exception as e:

            return JsonResponse(
                {
                    "success": False,
                    "message": (
                        "Failed to fetch "
                        "order details"
                    ),
                    "error": str(e)
                },
                status=500
            )

    # =================================================
    # PUT - UPDATE ORDER STATUS
    # =================================================
    elif request.method == "PUT":

        try:

            # -----------------------------------------
            # PARSE JSON
            # -----------------------------------------
            try:

                data = json.loads(
                    request.body
                )

            except json.JSONDecodeError:

                return JsonResponse(
                    {
                        "success": False,
                        "message": (
                            "Invalid JSON payload"
                        )
                    },
                    status=400
                )

            # -----------------------------------------
            # GET STATUS
            # -----------------------------------------
            status_value = data.get("status")

            if status_value is None:

                return JsonResponse(
                    {
                        "success": False,
                        "message": (
                            "status is required"
                        )
                    },
                    status=400
                )

            # -----------------------------------------
            # VALIDATE EMPTY STATUS
            # -----------------------------------------
            if str(status_value).strip() == "":

                return JsonResponse(
                    {
                        "success": False,
                        "message": (
                            "status cannot be empty"
                        )
                    },
                    status=400
                )

            # -----------------------------------------
            # UPDATE STATUS
            # -----------------------------------------
            order.status = status_value

            order.save(
                update_fields=[
                    "status"
                ]
            )

            # -----------------------------------------
            # SUCCESS RESPONSE
            # -----------------------------------------
            return JsonResponse(
                {
                    "success": True,
                    "message": (
                        "Order status updated "
                        "successfully"
                    ),
                    "data": {
                        "order_id": order.id,
                        "status": order.status
                    }
                },
                status=200
            )

        except Exception as e:

            return JsonResponse(
                {
                    "success": False,
                    "message": (
                        "Failed to update "
                        "order status"
                    ),
                    "error": str(e)
                },
                status=500
            )

    # =================================================
    # OTHER METHODS
    # =================================================
    return JsonResponse(
        {
            "success": False,
            "message": "Method not allowed"
        },
        status=405
    )




@csrf_exempt
def crm_update_credit(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id') or data.get('customer_id') or data.get('staff_id')
            
            if not user_id:
                return JsonResponse({"success": False, "message": "user_id is required"}, status=400)
                
            customer = get_object_or_404(User, id=user_id)
            
            if 'credit_limit' in data or 'creditLimit' in data:
                limit = data.get('credit_limit') if 'credit_limit' in data else data.get('creditLimit')
                customer.credit_limit = Decimal(str(limit or 0))
                
            if 'available_credit' in data:
                customer.available_credit = Decimal(str(data['available_credit'] or 0))
            elif 'balance' in data:
                customer.available_credit = customer.credit_limit - Decimal(str(data['balance'] or 0))
                
            if 'credit_payment_enabled' in data or 'creditPaymentEnabled' in data:
                enabled = data.get('credit_payment_enabled') if 'credit_payment_enabled' in data else data.get('creditPaymentEnabled')
                customer.credit_payment_enabled = bool(enabled)
                
            customer.save()
            
            return JsonResponse({
                "success": True,
                "message": "Credit updated successfully",
                "data": {
                    "user_id": customer.id,
                    "credit_limit": str(customer.credit_limit),
                    "available_credit": str(customer.available_credit),
                    "balance": str(customer.credit_limit - customer.available_credit),
                    "credit_payment_enabled": customer.credit_payment_enabled
                }
            })
            
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=400)
    
    return JsonResponse({"success": False, "message": "POST method required"}, status=405)


@csrf_exempt
def fix_all_credits(request):
    """
    Endpoint to manually fix all users who have credit_limit > 0 but available_credit = 0
    """
    if request.method == 'GET' or request.method == 'POST':
        try:
            from decimal import Decimal
            users = User.objects.filter(credit_limit__gt=0, available_credit=0)
            count = 0
            for u in users:
                u.available_credit = u.credit_limit
                u.save()
                count += 1
            return JsonResponse({
                "success": True,
                "message": f"Successfully updated {count} users with missing available_credit!"
            })
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=400)
    
    return JsonResponse({"success": False, "message": "Method not allowed"}, status=405)


@csrf_exempt
def crm_order_create(request):

    if request.method == 'POST':

        try:
            data = json.loads(request.body)



            # =
            # CUSTOMER
            # =

            customer_id = data.get('customer_id') or data.get('customer') or data.get('user_id')
            customer = get_object_or_404(
                User,
                id=customer_id
            )



            # =
            # ADDRESS
            # =

            address_id = data.get('address_id')
            if address_id:
                address = get_object_or_404(
                    Address,
                    id=address_id,
                    user=customer
                )
            else:
                address = Address.objects.filter(user=customer, is_default=True).first()
                if not address:
                    address = Address.objects.filter(user=customer).first()


            # Get admin/staff price category

            # =
            # PRICE CATEGORY
            # =

            current_user_role = request.headers.get(
                'X-Role',
                'customer'
            ).lower()

            if current_user_role in ['admin', 'staff']:



                price_category = data.get(
                    'price_category',
                    customer.price_category
                )

            else:
                price_category = customer.price_category

            items = data.get('items', [])

            if not price_category:
                price_category = 'customer_price'

            # =
            # ITEMS
            # =

            items = data.get('items', data.get('products', []))
            
            if isinstance(items, str):
                try:
                    items = json.loads(items)
                except json.JSONDecodeError:
                    items = []

            if not items:
                return JsonResponse(
                    {
                        'status': False,
                        'error': 'At least one item is required'
                    },
                    status=400
                )

            # =
            # AMOUNT VARIABLES
            # =

            from decimal import Decimal, ROUND_HALF_UP

            product_amount = Decimal('0.00')
            cgst_amount = Decimal('0.00')
            sgst_amount = Decimal('0.00')
            igst_amount = Decimal('0.00')

            # =
            # BUSINESS STATE
            # =

            # Example:
            # business_state = "Tamil Nadu"

            business_state = data.get(
                'business_state',
                ''
            ).strip().lower()

            customer_state = (
                address.state or ''
            ).strip().lower()

            # =
            # CREATE ORDER
            # =

            order = Order.objects.create(
                customer=customer,
                address=address,

                billing_address=(
                    f"{address.full_name}, "
                    f"{address.address or ''}, "
                    f"{address.city}, "
                    f"{address.state} - "
                    f"{address.pincode}"
                ),

                price_category=price_category,

                product_amount=Decimal('0.00'),
                cgst_amount=Decimal('0.00'),
                sgst_amount=Decimal('0.00'),
                igst_amount=Decimal('0.00'),
                gst_amount=Decimal('0.00'),

                shipping_charges=Decimal('0.00'),
                total_amount=Decimal('0.00')
            )

            # =
            # PROCESS ITEMS
            # =

            product_amount = Decimal('0')

            # Create order first
            order = Order.objects.create(
                customer=customer,
                address=address,
                product_amount=0,
                gst_amount=0,
                cgst_amount=0,
                sgst_amount=0,
                igst_amount=0,
                shipping_charges=0,
                total_amount=0,
                price_category=price_category
            )

            # Create order items
            for item in items:

                product_id = item.get('product') or item.get('product_id')

                product = get_object_or_404(
                    Product,
                    id=product_id
                )


                qty = int(item.get('quantity', 1))

                qty = int(
                    item.get('quantity', 1)
                )

                if qty <= 0:
                    raise ValueError(
                        'Quantity must be greater than 0'
                    )

                variation = None

                # =
                # GET PRICE + GST
                # =

                if item.get('variation_id'):

                    variation = get_object_or_404(
                        ProductVariation,
                        id=item.get('variation_id'),
                        product=product
                    )

                    price = getattr(
                        variation,
                        price_category,
                        0
                    )

                    gst_percentage = (
                        variation.gst_percentage
                        if variation.gst_percentage is not None
                        else product.gst_percentage
                    )

                else:

                    price = getattr(
                        product,
                        price_category,
                        0
                    )

                    gst_percentage = product.gst_percentage


                if price is None:
                    price = 0

                price = Decimal(str(price))

                row_total = price * qty

                product_amount += row_total

                # =
                # DECIMAL CONVERSION
                # =

                price = Decimal(
                    str(price or 0)
                )

                gst_percentage = Decimal(
                    str(gst_percentage or 0)
                )

                # =
                # PRODUCT SUBTOTAL
                # =

                item_total = (
                    price * qty
                ).quantize(
                    Decimal('0.01'),
                    rounding=ROUND_HALF_UP
                )

                product_amount += item_total

                # =
                # GST
                # =

                item_gst = (
                    item_total * gst_percentage
                    / Decimal('100')
                ).quantize(
                    Decimal('0.01'),
                    rounding=ROUND_HALF_UP
                )

                # =
                # CGST + SGST OR IGST
                # =

                if (
                    business_state
                    and customer_state
                    and business_state == customer_state
                ):

                    item_cgst = (
                        item_gst / Decimal('2')
                    ).quantize(
                        Decimal('0.01'),
                        rounding=ROUND_HALF_UP
                    )

                    item_sgst = (
                        item_gst - item_cgst
                    )

                    cgst_amount += item_cgst
                    sgst_amount += item_sgst

                else:

                    igst_amount += item_gst

                # =
                # ORDER ITEM
                # =

                OrderItem.objects.create(
                    order=order,
                    product=product,
                    variation=variation,
                    quantity=qty,
                    price=price
                )


            # 
            # GST CALCULATION
            # 

            gst_rate = Decimal('18')

            gst_amount = (
                product_amount * gst_rate / Decimal('100')
            )

            cgst_amount = gst_amount / Decimal('2')
            sgst_amount = gst_amount / Decimal('2')
            igst_amount = Decimal('0')

            # Shipping
            shipping_charges = Decimal(
                str(data.get('shipping_charges', 0) or 0)
            )

            # IMPORTANT:
            # GST is NOT added to total_amount
            total_amount = product_amount + shipping_charges

            # 
            # UPDATE ORDER
            # 

            order.product_amount = product_amount
            order.gst_amount = gst_amount
            order.cgst_amount = cgst_amount
            order.sgst_amount = sgst_amount
            order.igst_amount = igst_amount
            order.shipping_charges = shipping_charges

            # GST excluded from total
            order.total_amount = total_amount

            order.price_category = price_category

            order.save()


            # =
            # TOTAL GST
            # =

            gst_amount = (
                cgst_amount
                + sgst_amount
                + igst_amount
            ).quantize(
                Decimal('0.01'),
                rounding=ROUND_HALF_UP
            )

            # =
            # SHIPPING
            # =

            shipping_charges = Decimal(
                str(
                    data.get(
                        'shipping_charges',
                        0
                    ) or 0
                )
            )

            shipping_charges = shipping_charges.quantize(
                Decimal('0.01'),
                rounding=ROUND_HALF_UP
            )

            # =
            # FINAL TOTAL
            # =

            total_amount = (
                product_amount
                + gst_amount
                + shipping_charges
            ).quantize(
                Decimal('0.01'),
                rounding=ROUND_HALF_UP
            )

            # =
            # SAVE ALL ORDER AMOUNTS
            # =

            order.product_amount = product_amount
            order.cgst_amount = cgst_amount
            order.sgst_amount = sgst_amount
            order.igst_amount = igst_amount
            order.gst_amount = gst_amount
            order.shipping_charges = shipping_charges
            order.total_amount = total_amount

            # =
            # OTHER ORDER FIELDS
            # =

            order.invoice_number = data.get(
                'invoice_number'
            )

            order.mode_of_communication = data.get(
                'mode_of_communication'
            )

            order.logistics = data.get(
                'logistics'
            )

            order.payment_method = data.get(
                'payment_method'
            )

            order.remarks = data.get(
                'remarks'
            )

            order.tracking_number = data.get(
                'tracking_number'
            )

            # =
            # CREDIT LOGIC
            # =
            
            user_role = (customer.role or '').lower()
            if user_role in ['retailer', 'reseller', 'staff', 'distributor'] or customer.credit_payment_enabled or str(data.get('payment_method', '')).lower() == 'credit':
                avail_credit = float(customer.available_credit or 0)
                if avail_credit > 0:
                    total_amount_float = float(total_amount)
                    if avail_credit >= total_amount_float:
                        order.credit_used = total_amount_float
                        order.amount_to_pay = 0.00
                        customer.available_credit = Decimal(str(avail_credit - total_amount_float))
                    else:
                        order.credit_used = avail_credit
                        order.amount_to_pay = total_amount_float - avail_credit
                        customer.available_credit = Decimal("0.00")
                    customer.save()

            order.save()

            # =
            # TRACKING
            # =

            OrderTracking.objects.create(
                order=order,
                status='pending',
                note='Order Placed Successfully.'
            )


            return JsonResponse({
                'message': 'Order created successfully',
                'order_id': order.id
            }, status=201)

        except Exception as e:
            return JsonResponse(
                {'error': str(e)},
                status=400
            )



            # =
            # RESPONSE
            # =

            return JsonResponse(
                {
                    'status': True,
                    'message': 'Order created successfully',
                    'order_id': order.id,

                    'product_amount': str(
                        order.product_amount
                    ),

                    'cgst': str(
                        order.cgst_amount
                    ),

                    'sgst': str(
                        order.sgst_amount
                    ),

                    'igst': str(
                        order.igst_amount
                    ),

                    'tax_total': str(
                        order.gst_amount
                    ),

                    'shipping_charges': str(
                        order.shipping_charges
                    ),

                    'total_amount': str(
                        order.total_amount
                    ),

                    'credit_used': str(getattr(order, 'credit_used', '0.00')),
                    'amount_to_pay': str(getattr(order, 'amount_to_pay', order.total_amount)),
                    'available_credit_remaining': str(customer.available_credit),
                    'balance': str(customer.credit_limit - customer.available_credit),

                    'billing_address':
                        order.billing_address,

                    'address': {
                        'id': address.id,
                        'full_name':
                            address.full_name or '',
                        'phone':
                            address.phone or '',
                        'address':
                            address.address or '',
                        'city':
                            address.city or '',
                        'state':
                            address.state or '',
                        'pincode':
                            address.pincode or ''
                    }
                },
                status=201
            )

        except Exception as e:

            return JsonResponse(
                {
                    'status': False,
                    'error': str(e)
                },
                status=400
            )



# 
# BILLING ENDPOINTS (Bills, Invoices, Quotations)
# 
@csrf_exempt
def crm_bills(request):
    if request.method == 'GET':
        bills = Bill.objects.all().order_by('-id')
        data = [{
            'id': b.id,
            'vendor_name': b.vendor_name,
            'bill_number': b.bill_number,
            'total': str(b.total_amount),
            'status': b.status,
            'created_at': b.created_at.strftime('%Y-%m-%d')
        } for b in bills]
        return JsonResponse(data, safe=False)

@csrf_exempt
def crm_bill_create(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            b = Bill.objects.create(
                vendor_name=data.get('vendor_name'),
                bill_number=data.get('bill_number'),
                total_amount=data.get('total_amount'),
                status=data.get('status', 'pending')
            )
            return JsonResponse({'message': 'Bill created successfully', 'id': b.id}, status=201)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

@csrf_exempt
def crm_bill_print(request, pk):
    bill = get_object_or_404(Bill, id=pk)
    return JsonResponse({
        'id': bill.id,
        'vendor_name': bill.vendor_name,
        'bill_number': bill.bill_number,
        'total': str(bill.total_amount),
        'status': bill.status,
        'date': bill.created_at.strftime('%Y-%m-%d')
    })

@csrf_exempt
def crm_invoices(request):
    if request.method == 'GET':
        invoices = Invoice.objects.all().order_by('-id')
        data = [{
            'id': i.id,
            'invoice_number': i.invoice_number,
            'customer': i.customer.name,
            'total': str(i.total_amount),
            'status': i.status,
            'created_at': i.created_at.strftime('%Y-%m-%d')
        } for i in invoices]
        return JsonResponse(data, safe=False)

@csrf_exempt
def crm_invoice_create(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            customer = get_object_or_404(User, id=data.get('user_id'))
            order = Order.objects.filter(id=data.get('order_id')).first() if data.get('order_id') else None
            
            i = Invoice.objects.create(
                order=order,
                customer=customer,
                invoice_number=data.get('invoice_number', f"INV-{timezone.now().strftime('%Y%m%d%H%M%S')}"),
                total_amount=data.get('total_amount'),
                tax_amount=data.get('tax_amount', 0.00),
                status=data.get('status', 'unpaid')
            )
            return JsonResponse({'message': 'Invoice created successfully', 'id': i.id}, status=201)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

@csrf_exempt
def crm_invoice_print(request, pk):
    invoice = get_object_or_404(Invoice, id=pk)
    return JsonResponse({
        'id': invoice.id,
        'invoice_number': invoice.invoice_number,
        'customer_name': invoice.customer.name,
        'total': str(invoice.total_amount),
        'tax': str(invoice.tax_amount),
        'status': invoice.status,
        'date': invoice.created_at.strftime('%Y-%m-%d')
    })

@csrf_exempt
def crm_quotations(request):
    if request.method == 'GET':
        quotations = Quotation.objects.all().order_by('-id')
        data = [{
            'id': q.id,
            'customer': q.customer.name,
            'total': str(q.total_amount),
            'status': q.status,
            'created_at': q.created_at.strftime('%Y-%m-%d')
        } for q in quotations]
        return JsonResponse(data, safe=False)

@csrf_exempt
def crm_quotation_create(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            customer = get_object_or_404(User, id=data.get('user_id'))
            
            q = Quotation.objects.create(
                customer=customer,
                total_amount=data.get('total_amount'),
                items_json=json.dumps(data.get('items', [])),
                status=data.get('status', 'draft')
            )
            return JsonResponse({'message': 'Quotation created successfully', 'id': q.id}, status=201)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

@csrf_exempt
def crm_quotation_print(request, pk):
    q = get_object_or_404(Quotation, id=pk)
    return JsonResponse({
        'id': q.id,
        'customer_name': q.customer.name,
        'total': str(q.total_amount),
        'items': json.loads(q.items_json),
        'status': q.status,
        'date': q.created_at.strftime('%Y-%m-%d')
    })


#=================================
# NOTIFICATION ENDPOINTS
#=================================

import requests
from django.conf import settings

#===============================
# WATI CONTACT MANAGEMENT
#===============================

def save_customer_to_wati(customer):
    """
    Automatically save/update customer in WATI.
    """

    mobile = str(customer.mobile).strip()

    # Indian number conversion
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
        "name": customer.name or "வாடிக்கையாளர்",
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=15
    )

    print("=== WATI CONTACT ===")
    print("CUSTOMER:", customer.id)
    print("NAME:", customer.name)
    print("MOBILE:", mobile)
    print("WATI NUMBER:", whatsapp_number)
    print("STATUS:", response.status_code)
    print("RESPONSE:", response.text)

    return response


# ========================
# WATI LOGIN MESSAGE
# ========================
def send_login_whatsapp(customer):

    mobile = str(customer.mobile).strip()

    # Indian number conversion
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
        f"{settings.WATI_BASE_URL.rstrip('/')}"
        f"/api/v1/sendTemplateMessage"
    )

    headers = {
        "Authorization": f"Bearer {settings.WATI_API_TOKEN}",
        "Content-Type": "application/json",
    }

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

    params = {
        "whatsappNumber": whatsapp_number
    }

    print("\n========================================")
    print("WATI LOGIN REQUEST")
    print("========================================")
    print("CUSTOMER:", customer.id)
    print("NAME:", customer.name)
    print("MOBILE:", mobile)
    print("WATI NUMBER:", whatsapp_number)
    print("TEMPLATE:", payload["template_name"])
    print("PARAMETERS:", payload["parameters"])
    print("========================================")

    response = requests.post(
        url,
        headers=headers,
        params=params,
        json=payload,
        timeout=15
    )

    print("\n========================================")
    print("WATI LOGIN RESPONSE")
    print("========================================")
    print("STATUS:", response.status_code)
    print("RESPONSE:", response.text)
    print("========================================")

    return response


#=====================================
# WHATSAPP NOTIFICATION ENDPOINT
#=====================================

@csrf_exempt
def crm_whatsapp_notif(request, ntype):

    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Only POST method is allowed'
        }, status=405)

    try:
        data = json.loads(request.body)

        user_id = data.get('user_id')

        if not user_id:
            return JsonResponse({
                'success': False,
                'message': 'user_id is required'
            }, status=400)

        # IMPORTANT:
        # Use herbal.models.User
        customer = get_object_or_404(
            User,
            id=user_id
        )

        customer_name = customer.name or "வாடிக்கையாளர்"

        templates = {

            'cart': f"""வணக்கம் {customer_name},

நீங்கள் பொருட்களை உங்கள் கார்ட்டில் சேர்த்துள்ளீர்கள்.

உங்கள் ஆர்டரை முடிக்க எங்கள் இணையதளத்தை பார்வையிடுங்கள்.

நன்றி,
தரணி ஹெர்பல்ஸ்""",

            'order': f"""வணக்கம் {customer_name},

உங்கள் ஆர்டர் வெற்றிகரமாக பதிவு செய்யப்பட்டது.

ஆர்டர் எண்: {data.get('order_no', 'N/A')}

நன்றி,
தரணி ஹெர்பல்ஸ்""",

            'delivery': f"""வணக்கம் {customer_name},

உங்கள் ஆர்டர் அனுப்பப்பட்டுள்ளது.

Tracking No: {data.get('tracking_no', 'N/A')}

நன்றி,
தரணி ஹெர்பல்ஸ்""",

            'festival': """இனிய தீபாவளி நல்வாழ்த்துக்கள்.

உங்கள் குடும்பத்துடன் மகிழ்ச்சியாக கொண்டாட வாழ்த்துகள்.

அன்புடன்,
தரணி ஹெர்பல்ஸ்"""
        }

        if ntype not in templates:
            return JsonResponse({
                'success': False,
                'message': 'Invalid notification type',
                'allowed_types': [
                    'cart',
                    'order',
                    'delivery',
                    'festival'
                ]
            }, status=400)

        msg = templates[ntype]

        create_and_send_notification(
            customer,
            'whatsapp',
            'Notification',
            msg
        )

        return JsonResponse({
            'success': True,
            'message': f'WhatsApp notification sent for {ntype}',
            'user_id': customer.id,
            'customer_name': customer_name,
            'mobile': customer.mobile
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON'
        }, status=400)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)

#============================== 
# EMAIL NOTIFICATION ENDPOINT
#==============================


@csrf_exempt
def crm_email_notif(request, ntype):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            customer = get_object_or_404(User, id=data.get('user_id'))
            
            templates = {
                'cart': f"Dear {customer.name},\n\nYou have items left in your shopping cart. Visit our store to complete your purchase.\n\nThanks,\nDharani Herbals",
                'order': f"Dear {customer.name},\n\nYour order has been confirmed successfully.\nOrder ID: {data.get('order_id', 'N/A')}\n\nThanks,\nDharani Herbals",
                'invoice': f"Dear {customer.name},\n\nPlease find attached the tax invoice for your order.\nInvoice Ref: {data.get('invoice_no', 'N/A')}\n\nThanks,\nDharani Herbals",
                'festival': "Happy Diwali!\n\nWishing you and your family a prosperous and healthy life.\n\nWarm regards,\nDharani Herbals"
            }
            
            msg = templates.get(ntype, '')
            subject = f"Dharani Herbals - {ntype.title()} Notification"
            create_and_send_notification(customer, 'email', subject, msg)
            return JsonResponse({'message': f'Email notification log triggered for {ntype}'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

#===============================
# REPORT ENDPOINTS
#===============================
@csrf_exempt
def crm_reports(request, rtype):
    if request.method == 'GET':
        if rtype == 'sales':
            total_sales = Order.objects.aggregate(total=Sum('total_amount'))['total'] or 0.00
            today_sales = Order.objects.filter(created_at__date=timezone.now().date()).aggregate(total=Sum('total_amount'))['total'] or 0.00
            return JsonResponse({'total_sales': str(total_sales), 'today_sales': str(today_sales)})
        
        elif rtype == 'customers':
            total_customers = User.objects.filter(role='customer').count()
            top_customers = Order.objects.values('customer__name').annotate(total=Sum('total_amount')).order_by('-total')[:5]
            return JsonResponse({
                'total_customers': total_customers,
                'top_customers': list(top_customers)
            })
        
        elif rtype == 'products':
            total_products = Product.objects.count()
            low_stock = Product.objects.filter(stock__lte=models.F('reorder_level')).values('name', 'stock')
            return JsonResponse({
                'total_products': total_products,
                'low_stock_alerts': list(low_stock)
            })
            
        elif rtype == 'orders':
            total_orders = Order.objects.count()
            breakdown = dict(Order.objects.values('status').annotate(count=Count('id')).values_list('status', 'count'))
            return JsonResponse({
                'total_orders': total_orders,
                'breakdown': breakdown
            })
            
        elif rtype == 'inventory':
            total_stock_value = Product.objects.aggregate(total=Sum('stock'))['total'] or 0
            return JsonResponse({'total_stock_units': total_stock_value})

        return JsonResponse({'error': 'Report type not found'}, status=404)

# 
# STUBS FOR NEW ENDPOINTS
# 

@csrf_exempt
def change_password(request):
    return JsonResponse({'message': 'Change password endpoint working. Logic pending.'})

# @csrf_exempt
# def forgot_password(request):
#     return JsonResponse({'message': 'Forgot password endpoint working. Logic pending.'})



@csrf_exempt
def crm_tracking(request, order_id=None):
    if request.method == 'GET':
        try:
            from django.shortcuts import get_object_or_404
            order = get_object_or_404(Order, id=order_id)
            history = order.tracking_history.all().order_by('created_at')

            tracking_steps = []
            for h in history:
                tracking_steps.append({
                    'status': h.status,
                    'note': h.note or '',
                    'location_name': h.location_name or '',
                    'latitude': str(h.latitude) if h.latitude else '',
                    'longitude': str(h.longitude) if h.longitude else '',
                    'updated_by': h.updated_by.name if h.updated_by else 'System',
                    'time': h.created_at.isoformat()
                })

            items = []

            for i in order.items.select_related('product', 'variation'):

                items.append({

                    'order_item_id': i.id,

                    'product_id': i.product.id if i.product else None,

                    'product_name': i.product.name if i.product else 'Deleted Product',

                    'variation_id': i.variation.id if i.variation else None,

                    'variation_name': i.variation.variation_name if i.variation else None,

                    'quantity': i.quantity,

                    'price': str(i.price),

                    'total_price': str(i.price * i.quantity),

                    'image': get_image_url(request, i.product.image) if i.product and i.product.image else None,
                })

            return JsonResponse({
                'order_id': order.id,
                'customer_name': order.customer.name,
                'customer_mobile': order.customer.mobile,
                'status': order.status,
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
                'items': items,
                'tracking_history': tracking_steps,
                'created_at': order.created_at.isoformat()
            }, status=200)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def crm_tracking_update(request, order_id=None):
    return JsonResponse({'message': f'Tracking update for order {order_id} working. Logic pending.'})

@csrf_exempt
def crm_inventory(request):
    return JsonResponse({'message': 'Inventory GET working. Logic pending.'})

@csrf_exempt
def crm_inventory_action(request, action=None):
    return JsonResponse({'message': f'Inventory action {action} working. Logic pending.'})

@csrf_exempt
def crm_customer_ledger(request, customer_id=None):
    return JsonResponse({'message': f'Customer ledger for {customer_id} working. Logic pending.'})

@csrf_exempt
def crm_payments(request, pk=None):
    return JsonResponse({'message': f'Payments GET working. Logic pending.'})

@csrf_exempt
def crm_payments_add(request):
    return JsonResponse({'message': 'Payments add working. Logic pending.'})

@csrf_exempt
def crm_payments_receipt(request, pk=None):
    return JsonResponse({'message': f'Payments receipt for {pk} working. Logic pending.'})


@csrf_exempt
@api_view(['GET'])
def crm_reviews(request):

    reviews = ProductReview.objects.select_related(
        'product',
        'customer',
        'order_item'
    ).order_by('-created_at')

    serializer = ProductReviewCRMSerializer(
        reviews,
        many=True
    )

    return Response(
        serializer.data,
        status=200
    )


@csrf_exempt
@api_view(['GET', 'PUT', 'DELETE'])
def crm_review_detail(request, pk):

    review = ProductReview.objects.select_related(
        'product',
        'customer',
        'order_item'
    ).filter(id=pk).first()

    if not review:
        return Response(
            {
                "message": "Review not found"
            },
            status=404
        )

    # ---------------- GET ----------------

    if request.method == 'GET':

        serializer = ProductReviewCRMSerializer(review)

        return Response(
            serializer.data,
            status=200
        )

    # ---------------- PUT ----------------

    elif request.method == 'PUT':

        data = request.data

        status_value = data.get("status")
        user_id = data.get("user_id")

        if status_value not in [
            "approved",
            "rejected"
        ]:
            return Response(
                {
                    "message": "Status must be approved or rejected"
                },
                status=400
            )

        admin_user = User.objects.filter(
            id=user_id
        ).first()

        if not admin_user:
            return Response(
                {
                    "message": "Admin user not found"
                },
                status=404
            )

        review.status = status_value
        review.approved_by = admin_user
        review.approved_at = timezone.now()

        review.save()

        serializer = ProductReviewCRMSerializer(review)

        return Response(
            {
                "message": f"Review {status_value} successfully.",
                "review": serializer.data
            },
            status=200
        )

    # ---------------- DELETE ----------------

    elif request.method == 'DELETE':

        review.delete()

        return Response(
            {
                "message": "Review deleted successfully."
            },
            status=200
        )





from .models import Wishlist, Product, User
from .serializers import WishlistSerializer


# ===================
# CRM WISHLIST LIST
# ===================
@csrf_exempt
def crm_wishlist(request, user_id=None):
    if request.method != 'GET':
        return JsonResponse(
            {'message': 'GET method required'},
            status=405
        )

    if not user_id:
        user_id = request.GET.get('user_id')

    if not user_id:
        return JsonResponse(
            {'message': 'user_id is required'},
            status=400
        )

    try:

        user = User.objects.get(id=user_id)

        wishlist = Wishlist.objects.filter(
            user=user
        ).select_related('product')

        serializer = WishlistSerializer(
            wishlist,
            many=True,
            context={'request': request}
        )

        return JsonResponse({
            'success': True,
            'count': wishlist.count(),
            'wishlist': serializer.data
        })

    except User.DoesNotExist:

        return JsonResponse(
            {'message': 'User not found'},
            status=404
        )


# ====
# CRM WISHLIST ADD
# ====
@csrf_exempt
def crm_wishlist_add(request):

    if request.method != 'POST':
        return JsonResponse(
            {'message': 'POST method required'},
            status=405
        )

    try:

        data = json.loads(request.body)

        user = User.objects.get(
            id=data['user_id']
        )

        product = Product.objects.get(
            id=data['product_id']
        )

        wishlist, created = Wishlist.objects.get_or_create(
            user=user,
            product=product
        )

        if not created:
            return JsonResponse({
                'success': False,
                'message': 'Already in wishlist'
            })

        serializer = WishlistSerializer(
            wishlist,
            context={'request': request}
        )

        return JsonResponse({
            'success': True,
            'message': 'Wishlist added successfully',
            'wishlist': serializer.data
        })

    except User.DoesNotExist:

        return JsonResponse(
            {'message': 'User not found'},
            status=404
        )

    except Product.DoesNotExist:

        return JsonResponse(
            {'message': 'Product not found'},
            status=404
        )

    except Exception as e:

        return JsonResponse(
            {'message': str(e)},
            status=400
        )


# ====
# CRM WISHLIST DELETE
# ====
@csrf_exempt
def crm_wishlist_delete(request, pk):

    if request.method != 'DELETE':
        return JsonResponse(
            {'message': 'DELETE method required'},
            status=405
        )

    try:

        wishlist = Wishlist.objects.get(pk=pk)

        wishlist.delete()

        return JsonResponse({
            'success': True,
            'message': 'Wishlist deleted successfully'
        })

    except Wishlist.DoesNotExist:

        return JsonResponse(
            {'message': 'Wishlist not found'},
            status=404
        )

# @csrf_exempt
# def crm_cart_report(request):
#     if request.method != 'GET':
#         return JsonResponse({'success': False, 'message': 'GET method required'}, status=405)

#     from ecomapp.models import Cart
#     from django.utils import timezone
#     from django.db.models import Sum

#     carts = Cart.objects.prefetch_related('items__product_variation__product').select_related('user').all()
    
#     data = []
#     for cart in carts:
#         # Get total item count for the user
#         items_count = cart.items.aggregate(total=Sum('quantity'))['total'] or 0
        
#         # Only include users who actually have items in their cart
#         if items_count > 0:
#             cart_items = [
#                 f"{item.product_variation.product.name} × {item.quantity}"
#                 for item in cart.items.all()
#             ]
            
#             # Format datetime as requested: "DD/MM/YYYY\nHH:MM AM/PM"
#             local_dt = timezone.localtime(cart.created_at)
#             last_updated = local_dt.strftime("%d/%m/%Y\n%I:%M %p")
            
#             data.append({
#                 'id': cart.user.id,
#                 'name': cart.user.username or "",
#                 'phone': cart.user.mobile_number or "",
#                 'email': cart.user.email or "",
#                 'itemsCount': items_count,
#                 'cartItems': cart_items,
#                 'lastUpdated': last_updated
#             })

#     return JsonResponse({
#         'success': True,
#         'message': 'User cart report fetched successfully.',
#         'data': data
#     })

@csrf_exempt
def crm_wishlist_report(request):
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'GET method required'}, status=405)

    from herbal.models import Wishlist
    from django.utils import timezone
    
    wishlists = Wishlist.objects.select_related(
        'user', 
        'product', 
        'product__category', 
        'product__brand'
    ).order_by('-created_at')
    
    user_data = {}
    for item in wishlists:
        user_id = item.user.id
        if user_id not in user_data:
            user_data[user_id] = {
                'customer_id': user_id,
                'customer_name': item.user.name or "",
                'phone': item.user.mobile or "",
                'email': item.user.email or "",
                'items_count': 0,
                'products': [],
                'wishlist_items': [],
                'last_updated': timezone.localtime(item.created_at).strftime("%d/%m/%Y %I:%M %p") if hasattr(item, 'created_at') else ""
            }
        
        user_data[user_id]['products'].append(item.product.name if item.product else 'Deleted')
        user_data[user_id]['wishlist_items'].append({
            'product_id': item.product.id if item.product else None,
            'product_name': item.product.name if item.product else 'Deleted',
            'variation': "",
            'category': item.product.category.name if item.product and item.product.category else "",
            'brand': item.product.brand.name if item.product and getattr(item.product, 'brand', None) else "",
            'price': float(item.product.customer_price) if item.product else 0.00,
            'image': get_image_url(request, item.product.image) if item.product and getattr(item.product, 'image', None) else "",
            'added_at': item.created_at.isoformat() if hasattr(item, 'created_at') else ""
        })
        user_data[user_id]['items_count'] += 1

    return JsonResponse({
        'success': True,
        'message': 'Wishlist report fetched successfully.',
        'data': list(user_data.values())
    })
