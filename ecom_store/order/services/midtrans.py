import hashlib
import json
import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from order.models import Order, RefundRequest
from product.models import Product
from order.utils import (
    fetch_order_rajaongkir,
    reduce_product_stock,
    restore_product_stock,
    get_unrefunded_items
)

logger = logging.getLogger("order")
logger_error = logging.getLogger("order_error")


class InvalidMidtransPayload(Exception):
    pass


class InvalidMidtransSignature(Exception):
    pass


class WebhookMidtrans:
    def validate_signature(self, payload):
        try:
            self.payload = json.loads(payload)
        except json.JSONDecodeError:
            raise InvalidMidtransPayload("Invalid JSON payload")

        order_id = str(self.payload.get("order_id"))
        status = str(self.payload.get("status_code"))
        gross_amount = str(self.payload.get("gross_amount"))
        signature = self.payload.get("signature_key")

        raw = f"{order_id}{status}{gross_amount}{settings.MIDTRANS_SERVER_KEY}"
        expected_signature = hashlib.sha512(raw.encode()).hexdigest()

        if signature != expected_signature:
            raise InvalidMidtransSignature("Invalid Midtrans signature")
        return self.payload

    def get_order(self):
        try:
            self.order = (
                Order.objects.select_for_update()
                .prefetch_related("items__product")
                .get(order_id=self.payload.get("order_id"))
            )
        except (Order.DoesNotExist, ValidationError) as e:
            logger_error.error(
                "Order not found",
                extra={
                    "event_type": "transaction",
                    "order_id": self.payload.get("order_id"),
                    "payload": self.payload,
                },
            )
            raise

    def change_payment_status_order(self):
        """
        Update payment_status based on Midtrans transaction_status.

        Transition rules:
            pending -> paid/failed : normal
            paid -> failed         : reversal (e.g. Permata/Mandiri/Indomaret
                                      settlement reversed within 1-5 minutes)
            failed -> paid         : blocked, failed is final in this direction
            X -> X                 : duplicate webhook, no-op

        fraud_status None is treated as accepted since non-card payment
        methods (QRIS, bank transfer, etc.) are not evaluated by Midtrans'
        Fraud Detection System and never send this field.

        Always sets self.old_status / self.new_status on every return path.
        The view relies on both to decide whether release_reservation()
        should run.

        Returns True if new_status == "paid".
        """
        transaction_status = self.payload.get("transaction_status")
        fraud_status = self.payload.get("fraud_status")
        old_status = self.order.payment_status

        if transaction_status in ["settlement", "capture"]:
            new_status = "paid" if fraud_status in (None, "accept") else "failed"
        elif transaction_status in ["deny", "cancel", "expire"]:
            new_status = "failed"
        else:
            self.old_status = old_status
            self.new_status = old_status  # tidak ada transisi, status tetap sama
            return old_status == "paid"

        if old_status == "failed" and new_status == "paid":
            logger_error.warning(
                "Order sudah failed, transaksi mencoba jadi paid - diabaikan",
                extra={
                    "event_type": "transaction",
                    "order_id": self.order.order_id,
                    "transaction_status": transaction_status,
                },
            )
            self.old_status = old_status
            self.new_status = old_status  # diblokir, status tetap failed
            return False

        if old_status != new_status:
            self.order.payment_status = new_status
            self.order.save(update_fields=["payment_status"])

        self.old_status = old_status
        self.new_status = new_status
        return new_status == "paid"

    def reduce_stock(self):
        """
        Permanently reduce product stock and clear the matching reservation.
        Idempotent via self.order.reduced_stock, safe to call on webhook
        retries. Exceptions are logged and re-raised so the view returns
        500, letting Midtrans retry the webhook.
        """
        try:
            if not self.order.reduced_stock:
                reduce_product_stock(self.order.items.all())
                self.order.reduced_stock = True
                self.order.save(update_fields=["reduced_stock"])
        except Exception as e:
            logger_error.exception(
                "Failed to reserve stock",
                extra={
                    "event_type": "transaction",
                    "order_id": self.order.order_id,
                },
            )
            raise

    def reverse_stock(self):
        """
        Restore product stock on payment reversal (paid -> failed).
        No-op if reduced_stock is False (nothing was ever deducted).

        Skips restocking if the order is already SHIPPED/DELIVERED, since
        the goods have physically left the warehouse; logs critical for
        manual review instead of auto-restocking.

        Idempotent via reduced_stock, which is cleared after a successful
        restore. Exceptions are logged and re-raised, same rationale as
        reduce_stock.
        """
        if not self.order.reduced_stock:
            return

        if self.order.status in [Order.Status.SHIPPED, Order.Status.DELIVERED]:
            logger_error.critical(
                "Reversal payment tapi order sudah shipped/delivered - "
                "TIDAK auto-restock, butuh review manual",
                extra={
                    "event_type": "transaction",
                    "order_id": self.order.order_id,
                    "order_status": self.order.status,
                },
            )
            return

        try:
            items_to_restore = get_unrefunded_items(self.order)
            restore_product_stock(items_to_restore)
            self.order.reduced_stock = False
            self.order.save(update_fields=["reduced_stock"])
            logger.warning(
                "Stok dikembalikan karena reversal payment (paid -> failed)",
                extra={"event_type": "transaction", "order_id": self.order.order_id},
            )
        except Exception:
            logger_error.exception(
                "Gagal mengembalikan stok setelah reversal",
                extra={"event_type": "transaction", "order_id": self.order.order_id},
            )
            raise

    def release_reservation(self):
        """
        Release reserved_stock for orders that fail before ever reaching
        reduce_stock (pending -> failed). Without this, abandoned checkouts
        would leave reserved_stock permanently inflated.

        Caller contract: the view must only invoke this when
        new_status == "failed" and old_status not in ("paid", "failed") --
        i.e. a genuinely new failure, not a reversal or duplicate webhook.
        This can't be determined from reduced_stock alone, since
        reverse_stock() (called earlier in the same request) may have
        already flipped it to False as a side effect.

        The reduced_stock check below is a secondary safeguard, not the
        primary guard -- do not remove it, but do not rely on it alone
        either.
        """
        if self.order.reduced_stock:
            return
        
        order_items = get_unrefunded_items(self.order)
        if not order_items:
            return
        
        product_ids = order_items.values_list("product_id", flat=True)
        
        products = (
            Product.objects.select_for_update().filter(id__in=product_ids).order_by("id")
        )
        
        product_map = {p.id: p for p in products}

        for item in order_items:
            product = product_map[item.product_id]
            product.reserved_stock -= item.qty
            product.save(update_fields=["reserved_stock"])
            

    # def create_order_ro(self):
    #     try:
    #         self.res = fetch_order_rajaongkir(self.order)
    #     except Exception as e:
    #         logger_error.exception(
    #             "Failed to call RajaOngkir API",
    #             extra={
    #                 "event_type": "transaction",
    #                 "order_id": self.order.order_id,
    #             },
    #         )
    #         raise

    #     if self.res.status_code != 201:
    #         logger_error.error(
    #             "RajaOngkir order creation failed",
    #             extra={
    #                 "event_type": "transaction",
    #                 "order_id": self.order.order_id,
    #                 "status_code": self.res.status_code,
    #                 "response": self.res.text,
    #             },
    #         )
    #         raise Exception("RajaOngkir order creation failed")

    # def update_order_from_rajaongkir_response(self):
    #     try:
    #         data = self.res.json()["data"]
    #     except (ValueError, KeyError) as e:
    #         logger_error.exception(
    #             "Invalid RajaOngkir response format",
    #             extra={
    #                 "event_type": "transaction",
    #                 "order_id": self.order.order_id,
    #                 "response": self.res.text,
    #             },
    #         )
    #         raise

    #     self.order.order_id_ro = data["order_id"]
    #     self.order.order_no_ro = data["order_no"]
    #     self.order.save()
