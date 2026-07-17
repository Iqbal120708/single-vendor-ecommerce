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
        #CANCELED = "canceled", "Canceled"

    class PaymentStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        UNPAID = "unpaid", "Unpaid"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        #REFUNDED = "refunded", "Refunded"

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

    reduced_stock = models.BooleanField(
        default=False,
        editable=False,
        help_text="True setelah reduce_stock() webhook sukses sekali. Tidak berubah saat refund/cancel per item — cek RefundRequest untuk status stock item.",
    )

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
            
    @property
    def refund_status(self):
        items = list(self.items.all())
        refunded_items = [i for i in items if i.is_refunded]
        if not refunded_items:
            return None
        if len(refunded_items) == len(items):
            return "refunded"
        return "partially_refunded"

    @property
    def is_fully_canceled(self):
        return all(
            item.refund_requests.filter(
                status=RefundRequest.Status.COMPLETED,
                reason=RefundRequest.Reason.CUSTOMER_CANCEL,
            ).exists()
            for item in self.items.all()
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

    # order_id_ro = models.CharField(
    #     max_length=20,
    #     null=True,
    #     blank=True,
    # )

    # order_no_ro = models.CharField(
    #     max_length=50,
    #     null=True,
    #     blank=True,
    # )

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
    def is_refunded(self):
        return self.refund_requests.filter(
            status=RefundRequest.Status.COMPLETED
        ).exists()

    @property
    def has_active_refund(self):
        return self.refund_requests.filter(
            status__in=[RefundRequest.Status.REQUESTED, RefundRequest.Status.APPROVED]
        ).exists()
        
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

class RefundRequest(BaseModel):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        COMPLETED = "completed", "Completed"

    class Reason(models.TextChoices):
        CUSTOMER_CANCEL = "customer_cancel", "Dibatalkan Customer"
        OUT_OF_STOCK = "out_of_stock", "Stok Habis"
        RETURN = "return", "Retur Pasca-Kirim"
        OTHER = "other", "Lainnya"

    class DestinationType(models.TextChoices):
        BANK = "bank", "Transfer Bank"
        EWALLET = "ewallet", "E-Wallet"

    class Provider(models.TextChoices):
        BCA = "bca", "BCA"
        MANDIRI = "mandiri", "Mandiri"
        BNI = "bni", "BNI"
        BRI = "bri", "BRI"
        PERMATA = "permata", "Permata"
        CIMB = "cimb", "CIMB Niaga"
        GOPAY = "gopay", "GoPay"
        SHOPEEPAY = "shopeepay", "ShopeePay"
        DANA = "dana", "DANA"
        OVO = "ovo", "OVO"

    BANK_PROVIDERS = {"bca", "mandiri", "bni", "bri", "permata", "cimb"}
    EWALLET_PROVIDERS = {"gopay", "shopeepay", "dana", "ovo"}

    order_item = models.ForeignKey(
        OrderItem,
        on_delete=models.PROTECT,
        related_name="refund_requests",
    )

    amount = models.PositiveIntegerField(
        editable=False,
        help_text="Diambil otomatis dari subtotal order_item, tidak bisa diisi customer.",
    )

    reason = models.CharField(
        max_length=30,
        choices=Reason.choices,
        help_text=(
            "Otomatis diisi CUSTOMER_CANCEL/RETURN saat customer mengajukan. "
            "Admin bisa ubah manual (mis. jadi OUT_OF_STOCK) sebelum status COMPLETED."
        ),
    )

    note = models.TextField(
        blank=True,
        help_text="Catatan tambahan dari customer saat mengajukan refund.",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.REQUESTED,
    )

    destination_type = models.CharField(max_length=10, choices=DestinationType.choices)
    destination_provider = models.CharField(max_length=20, choices=Provider.choices)
    destination_number = models.CharField(
        max_length=50,
        help_text="Nomor rekening atau nomor HP e-wallet tujuan refund.",
    )
    account_holder_name = models.CharField(
        max_length=150,
        help_text="Nama pemilik rekening/e-wallet, untuk verifikasi admin sebelum transfer manual.",
    )

    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    @property
    def order(self):
        return self.order_item.order

    def __str__(self):
        return f"Refund {self.order_item} - {self.status}"