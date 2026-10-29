from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from herbal.models import OrderItem
from herbal.views import send_reorder_template


class Command(BaseCommand):

    help = "Send WhatsApp reorder reminders"

    def handle(self, *args, **kwargs):

        today = timezone.now()

        order_items = OrderItem.objects.filter(
            order__status="delivered",
            order__delivered_at__lte=today - timedelta(days=30),
            reorder_reminder_sent=False
        ).select_related(
            "order",
            "order__customer",
            "product",
            "variation"
        )

        for item in order_items:

            customer = item.order.customer

            phone = str(customer.mobile).strip()

            phone = (
                phone
                .replace("+", "")
                .replace("-", "")
                .replace(" ", "")
            )

            if not phone.startswith("91"):
                phone = "91" + phone

            product_name = (
                item.variation.variation_name
                if item.variation
                else item.product.name
            )

            product_link = (
                f"https://www.vedanmart.com/product/{item.product.id}"
            )


            try:

                send_reorder_template(
                    phone=phone,
                    customer_name=customer.name,
                    product_name=product_name,
                    product_link=product_link
                )

                item.reorder_reminder_sent = True
                item.reorder_reminder_sent_at = timezone.now()
                item.save()

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Reminder sent for OrderItem {item.id}"
                    )
                )

            except Exception as e:

                self.stdout.write(
                    self.style.ERROR(
                        f"OrderItem {item.id} : {e}"
                    )
                )