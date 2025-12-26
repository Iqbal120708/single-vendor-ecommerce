from .models import  Order
import logging
from .utils import fetch_order_rajaongkir, reduce_product_stock
import json
from django.conf import settings
import hashlib

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
                Order.objects
                .select_for_update()
                .prefetch_related("items__product")
                .get(order_id=self.payload.get("order_id"))
            )
        except Order.DoesNotExist as e:
            logger_error.error(
                "Order not found",
                extra={
                    "event_type": "transaction",
                    "order_id": self.payload.get("order_id"),
                    "payload": self.payload,
                }
            )
            raise 

        
    def change_payment_status_order(self):
        transaction_status = self.payload.get("transaction_status")
        fraud_status = self.payload.get("fraud_status")
        
        if transaction_status in ["settlement", "capture"]:
            if fraud_status == "accept": 
                self.order.payment_status = "paid"
        elif transaction_status in ["deny", "cancel", "expire"]:
            self.order.payment_status = "failed"
        elif transaction_status == "refund":
            self.order.payment_status = "refunded"
    
        if self.order.payment_status != "paid":
            logger_error.info(
                "Payment not completed",
                extra={
                    "event_type": "transaction",
                    "order_id": self.order.order_id,
                    "transaction_status": transaction_status,
                }
            )
            self.order.save()
            
            raise Exception("Payment not completed.")
            
    def create_order_ro(self):
        try:
            self.res = fetch_order_rajaongkir(self.order)
        except Exception as e:
            logger_error.exception(
                "Failed to call RajaOngkir API",
                extra={
                    "event_type": "transaction",
                    "order_id": self.order.order_id,
                }
            )
            raise
    
        if self.res.status_code != 201:
            print(self.res.text)
            logger_error.error(
                "RajaOngkir order creation failed",
                extra={
                    "event_type": "transaction",
                    "order_id": self.order.order_id,
                    "status_code": self.res.status_code,
                    "response": self.res.text,
                }
            )
            raise Exception("RajaOngkir order creation failed")
            
    def update_order_from_rajaongkir_response(self):
        try:
            data = self.res.json()["data"]
        except (ValueError, KeyError) as e:
            logger_error.exception(
                "Invalid RajaOngkir response format",
                extra={
                    "event_type": "transaction",
                    "order_id": self.order.order_id,
                    "response": self.res.text,
                }
            )
            raise
    
        self.order.order_id_ro = data["order_id"]
        self.order.order_no_ro = data["order_no"]
        self.order.save()
        
    def reduce_stock(self):
        try:
            reduce_product_stock(
                self.order.items.all()
            )
        except Exception as e:
            logger_error.exception(
                "Failed to reserve stock",
                extra={
                    "event_type": "transaction",
                    "order_id": self.order.order_id,
                }
            )
            raise 