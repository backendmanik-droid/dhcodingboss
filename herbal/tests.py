from django.test import SimpleTestCase
from . import models as herbal_models
from . import views as herbal_views


class CartModelImportTests(SimpleTestCase):
    def test_cart_model_is_available_from_models_module(self):
        self.assertTrue(hasattr(herbal_models, "Cart"))
        self.assertIn("quantity", [field.name for field in herbal_models.Cart._meta.fields])


class PaytmViewImportTests(SimpleTestCase):
    def test_views_payment_refers_to_django_model(self):
        self.assertIs(herbal_views.Payment, herbal_models.Payment)
