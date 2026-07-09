import uuid

from config.models import BaseModel
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

# Create your models here.
# class Courier(BaseModel):
#     code = models.CharField(max_length=20, unique=True)
#     name = models.CharField(max_length=50)
#     is_active = models.BooleanField(default=True)

#     def __str__(self):
#         return f"{self.name} - {self.code}"


class ShippingInsurance(BaseModel):
    shipping = models.CharField(max_length=50, unique=True)
    rate = models.DecimalField(max_digits=5, decimal_places=4)
    admin_fee = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.shipping


class Order(BaseModel):
    class Status(models.TextChoices):
        # DRAFT = "draft", "Draft"
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELED = "canceled", "Canceled"

    class PaymentStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        UNPAID = "unpaid", "Unpaid"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    class PaymentMethod(models.TextChoices):
        BANK_TRANSFER = "BANK TRANSFER", "Bank Transfer"
        COD = "COD", "Cash On Delivery"

    id = models.BigAutoField(primary_key=True)

    order_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
    )

    store = models.ForeignKey(
        "store.Store",
        on_delete=models.PROTECT,
        related_name="orders",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    delivered_at = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)

    payment_method = models.CharField(
        max_length=20, choices=PaymentMethod.choices, null=True, blank=True
    )

    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )

    grand_total = models.PositiveIntegerField(
        default=0,
        editable=False,
        help_text=(
            "Snapshot total pembayaran saat order dibuat. "
            "Tidak berubah meskipun konfigurasi toko atau kurir berubah."
        ),
    )

    net_income = models.PositiveIntegerField(
        default=0,
        editable=False,
        help_text=(
            "Snapshot pendapatan bersih hasil perhitungan ongkir " "saat order dibuat."
        ),
    )

    actual_net_income = models.PositiveIntegerField(
        editable=False,
        default=0,
        help_text=(
            "Snapshot pendapatan bersih akhir yang diterima toko saat order dibuat."
        ),
    )

    reduced_stock = models.BooleanField(default=False, editable=False)

    def clean(self):
        super().clean()

        if (
            self.payment_status == self.PaymentStatus.UNPAID
            and self.status not in [self.Status.PENDING]
            and self.payment_method != self.PaymentMethod.COD
        ):
            raise ValidationError(
                "Selain COD, status order harus 'pending' jika pembayaran masih unpaid."
            )

    def save(self, *args, **kwargs):
        self.full_clean()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order {self.order_id}"


class OrderShipping(BaseModel):
    order = models.OneToOneField(
        Order, related_name="shipping", on_delete=models.CASCADE
    )

    # courier
    shipping_name = models.CharField(
        max_length=30,
        help_text="Nama kurir yang dipilih saat checkout.",
    )

    service_name = models.CharField(
        max_length=50,
        help_text="Layanan pengiriman yang dipilih saat checkout.",
    )

    shipping_weight = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=0,
        editable=False,
        help_text="Snapshot berat total (Kg) pesanan saat checkout.",
    )
    etd = models.CharField(
        max_length=50,
        help_text="Estimasi waktu pengiriman.",
    )

    # cost
    shipping_cost = models.PositiveIntegerField(default=0)
    shipping_cashback = models.PositiveIntegerField(default=0)
    shipping_cost_net = models.PositiveIntegerField(
        help_text="Snapshot ongkir setelah dikurangi cashback.",
    )
    insurance_value = models.PositiveIntegerField(
        default=0,
        editable=False,
        help_text=(
            "Snapshot biaya asuransi saat order dibuat. "
            "Tidak berubah meskipun konfigurasi toko atau kurir berubah."
        ),
    )
    service_fee = models.PositiveIntegerField()
    additional_cost = models.PositiveIntegerField(default=0)

    # rajaongkir
    origin_ro = models.IntegerField()
    origin_address = models.TextField()

    destination_ro = models.IntegerField()
    destination_address = models.TextField()

    order_id_ro = models.CharField(
        max_length=20,
        null=True,
        blank=True,
    )

    order_no_ro = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )

    # cod
    cod_value = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    tracking_number = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Nomor resi pengiriman dari kurir, diisi manual oleh admin setelah packing.",
    )


class OrderItem(BaseModel):
    id = models.BigAutoField(primary_key=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("product.Product", on_delete=models.PROTECT)
    product_price = models.DecimalField(max_digits=18, decimal_places=2)
    qty = models.PositiveIntegerField()
    is_archived = models.BooleanField(default=False)

    @property
    def subtotal(self):
        return self.qty * self.product_price

    def __str__(self):
        return f"{self.product} x {self.qty}"


class CheckoutSession(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    cart_ids = models.JSONField()
    destination = models.ForeignKey(
        "shipping_address.ShippingAddress", on_delete=models.PROTECT
    )
    store = models.ForeignKey("store.Store", on_delete=models.PROTECT)
    expires_at = models.DateTimeField()
    order = models.OneToOneField(
        Order,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.user} - {self.id}"
