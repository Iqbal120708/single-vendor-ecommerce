import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from config.models import BaseModel


# Create your models here.
class Courier(BaseModel):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} - {self.code}"


class Order(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        # PAID = "paid", "Paid"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELED = "canceled", "Canceled"

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "Unpaid"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    class PaymentMethod(models.TextChoices):
        BANK_TRANSFER = "BANK TRANSFER", "Bank Transfer"
        COD = "COD", "Cash On Delivery"

    id = models.BigAutoField(primary_key=True)

    order_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders"
    )

    store = models.ForeignKey(
        "store.Store", on_delete=models.PROTECT, related_name="orders"
    )

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )

    delivered_at = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)

    is_archived = models.BooleanField(default=False)

    shipping_cost = models.PositiveIntegerField(default=0)
    shipping_cashback = models.PositiveIntegerField(default=0)

    courier_code = models.CharField(max_length=10)
    shipping_type = models.CharField(max_length=20)

    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    payment_status = models.CharField(
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID
    )

    service_fee = models.PositiveIntegerField(default=0)
    additional_cost = models.PositiveIntegerField(default=0)
    cod_value = models.PositiveIntegerField(null=True, blank=True)

    #insurance_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    origin_ro = models.IntegerField()
    origin_address = models.TextField()

    destination_ro = models.IntegerField()
    destination_address = models.TextField()
    
    order_id_ro = models.CharField(max_length=20, null=True, blank=True)
    order_no_ro = models.CharField(max_length=50, null=True, blank=True)

    @property
    def grand_total(self):
        orderitems = self.items.all()
        total = (
            int(sum(orderitem.subtotal for orderitem in orderitems))
            + self.shipping_cost
            - self.shipping_cashback
            + self.insurance_value
        )
        return int(total)

    @property
    def insurance_value(self, admin_fee=2000):
        """
        Menghitung premi asuransi pengiriman.
        Default rate: 0.2% (0.002)
        Default admin: Rp 2.000
        """
        orderitems = self.items.all()
        total_item_value = sum(orderitem.subtotal for orderitem in orderitems)

        if total_item_value <= 0:
            return 0.0

        insurance_rate = 0.002
        premium = (int(total_item_value) * insurance_rate) + admin_fee
        return round(float(premium), 2)

    def clean(self):
        if (
            self.payment_status == "unpaid"
            and self.status != "pending"
            and self.payment_method != "COD"
        ):
            raise ValidationError(
                "Status order harus 'pending' jika payment masih 'unpaid' di pembayaran selain COD."
            )

    def save(self, *args, **kwargs):
        self.clean()

        if self.payment_method != "cod":
            self.cod_value = 0
        else:
            self.cod_value == self.grand_total

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order {self.order_id}"


class OrderItem(BaseModel):
    id = models.BigAutoField(primary_key=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("product.Product", on_delete=models.PROTECT)
    product_price = models.DecimalField(max_digits=18, decimal_places=2)
    qty = models.PositiveIntegerField()

    @property
    def subtotal(self):
        return self.qty * self.product_price

    def __str__(self):
        return f"{self.product} x {self.qty}"

class CheckoutSession(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    cart_ids = models.JSONField()
    destination = models.ForeignKey("shipping_address.ShippingAddress", on_delete=models.PROTECT)
    store = models.ForeignKey("store.Store", on_delete=models.PROTECT)
    expires_at = models.DateTimeField()