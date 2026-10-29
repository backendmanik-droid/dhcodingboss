from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from herbal.models import Cart
from herbal.views import send_cart_template


class Command(BaseCommand):

    help = "Send WhatsApp cart reminders"

    def handle(self, *args, **kwargs):

        now = timezone.now()

        carts = Cart.objects.filter(
            added_at__lte=now - timedelta(minutes=160),   # Change to minutes=1 for testing
            cart_reminder_sent=False
        ).select_related(
            "user",
            "product",
            "variation"
        )
        print(carts.count())

        for cart in carts:

            user = cart.user

            phone = str(user.mobile).strip()

            phone = (
                phone
                .replace("+", "")
                .replace("-", "")
                .replace(" ", "")
            )

            if not phone.startswith("91"):
                phone = "91" + phone

            try:

                send_cart_template(phone)

                cart.cart_reminder_sent = True
                cart.cart_reminder_sent_at = timezone.now()
                cart.save()

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Cart reminder sent for Cart {cart.id}"
                    )
                )

            except Exception as e:

                self.stdout.write(
                    self.style.ERROR(
                        f"Cart {cart.id}: {e}"
                    )
                )