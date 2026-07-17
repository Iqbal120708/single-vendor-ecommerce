from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
import logging

from order.models import Order, OrderItem, RefundRequest
from product.models import Product
from order.tasks import send_refund_status_email, send_refund_anomaly_email

logger_error = logging.getLogger("order_error")

class RefundService:
    def __init__(self, refund_request: RefundRequest):
        self.refund_request = refund_request

    def approve(self):
        refund_request = self.refund_request
    
        if refund_request.status != RefundRequest.Status.REQUESTED:
            raise ValidationError(
                "Hanya request berstatus REQUESTED yang bisa di-approve."
            )
    
        refund_request.status = RefundRequest.Status.APPROVED
        refund_request.approved_at = timezone.now()
        refund_request.save(update_fields=["status", "approved_at"])
        
        send_refund_status_email.delay(refund_request.id)
    
    def reject(self):
        refund_request = self.refund_request
    
        if refund_request.status != RefundRequest.Status.REQUESTED:
            raise ValidationError(
                "Hanya request berstatus REQUESTED yang bisa di-reject."
            )
    
        refund_request.status = RefundRequest.Status.REJECTED
        refund_request.approved_at = timezone.now()
        refund_request.save(update_fields=["status", "approved_at"])
        
        send_refund_status_email.delay(refund_request.id)

    def complete(self):
        refund_request = self.refund_request

        with transaction.atomic():
            order_item = OrderItem.objects.select_for_update().get(
                pk=refund_request.order_item_id
            )
            order = Order.objects.select_for_update().get(pk=order_item.order_id)

            if refund_request.status != RefundRequest.Status.APPROVED:
                raise ValidationError(
                    "Hanya request berstatus APPROVED yang bisa di-complete."
                )

            valid_statuses = [
                Order.Status.PENDING, Order.Status.PROCESSING,
                Order.Status.SHIPPED, Order.Status.DELIVERED,
            ]
            if order.status not in valid_statuses:
                raise ValidationError(
                    f"Order status {order.status}, refund dibatalkan."
                )

            if order.payment_status == Order.PaymentStatus.FAILED:
                raise ValidationError(
                    "Pembayaran gagal, barang tidak jadi dikirim -- "
                    "tidak ada yang perlu direfund."
                )

            if order.payment_status == Order.PaymentStatus.PAID and not order.reduced_stock:
                logger_error.critical(
                    "Refund diblokir - order PAID tapi reduced_stock False, butuh review manual",
                    extra={
                        "event_type": "refund",
                        "order_id": order.order_id,
                        "refund_request_id": refund_request.id,
                        "payment_status": order.payment_status,
                        "reduced_stock": order.reduced_stock,
                    },
                )
                send_refund_anomaly_email.delay(order.id, refund_request.id)
                raise ValidationError(
                    "Order dalam status anomali (dibayar tapi stock belum diproses) -- "
                    "butuh review admin sebelum refund bisa diproses."
                )

            refund_request.status = RefundRequest.Status.COMPLETED
            refund_request.completed_at = timezone.now()
            refund_request.save(update_fields=["status", "completed_at"])

            product = Product.objects.select_for_update().get(pk=order_item.product_id)
            if order.reduced_stock:
                product.stock += order_item.qty
            else:
                product.reserved_stock -= order_item.qty
            product.save()
            
        send_refund_status_email.delay(refund_request.id)