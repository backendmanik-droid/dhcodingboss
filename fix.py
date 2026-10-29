import os

file_path = 'D:/codingboss/payment/api-codingboss/herbal/crm_views.py'
with open(file_path, 'rb') as f:
    content = f.read()

target = b"return JsonResponse(\r\n            {'message': 'Wishlist not found'},\r\n            status=404\r\n        )"
idx = content.find(target)

if idx == -1:
    # Try another format (Unix line endings)
    target = b"return JsonResponse(\n            {'message': 'Wishlist not found'},\n            status=404\n        )"
    idx = content.find(target)

if idx != -1:
    truncate_idx = idx + len(target)
    with open(file_path, 'wb') as f:
        f.write(content[:truncate_idx])
    
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write('''

@csrf_exempt
def crm_cart_report(request):
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'GET method required'}, status=405)

    from ecomapp.models import Cart
    from django.utils import timezone
    from django.db.models import Sum

    carts = Cart.objects.prefetch_related('items__product_variation__product').select_related('user').all()
    
    data = []
    for cart in carts:
        # Get total item count for the user
        items_count = cart.items.aggregate(total=Sum('quantity'))['total'] or 0
        
        # Only include users who actually have items in their cart
        if items_count > 0:
            cart_items = [
                f"{item.product_variation.product.name} × {item.quantity}"
                for item in cart.items.all()
            ]
            
            # Format datetime as requested: "DD/MM/YYYY\\nHH:MM AM/PM"
            local_dt = timezone.localtime(cart.created_at)
            last_updated = local_dt.strftime("%d/%m/%Y\\n%I:%M %p")
            
            data.append({
                'id': cart.user.id,
                'name': cart.user.username or "",
                'phone': cart.user.mobile_number or "",
                'email': cart.user.email or "",
                'itemsCount': items_count,
                'cartItems': cart_items,
                'lastUpdated': last_updated
            })

    return JsonResponse({
        'success': True,
        'message': 'User cart report fetched successfully.',
        'data': data
    })

@csrf_exempt
def crm_wishlist_report(request):
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'GET method required'}, status=405)

    from ecomapp.models import Wishlist, Customer
    from django.utils import timezone
    
    wishlists = Wishlist.objects.select_related('user', 'product').all()
    
    user_data = {}
    for item in wishlists:
        user_id = item.user.id
        if user_id not in user_data:
            user_data[user_id] = {
                'id': user_id,
                'name': item.user.username or "",
                'phone': item.user.mobile_number or "",
                'email': item.user.email or "",
                'itemsCount': 0,
                'products': [],
                'lastUpdated': timezone.localtime(timezone.now()).strftime("%d/%m/%Y\\n%I:%M %p")
            }
        
        user_data[user_id]['products'].append(item.product.name)
        user_data[user_id]['itemsCount'] += 1

    return JsonResponse({
        'success': True,
        'message': 'Wishlist report fetched successfully.',
        'data': list(user_data.values())
    })
''')
    print('Truncated and rebuilt successfully.')
else:
    print('Target not found!')
