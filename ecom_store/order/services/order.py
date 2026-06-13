from decimal import Decimal
from math import ceil
from order.models import ShippingInsurance, Order, OrderShipping, OrderItem
from django.db import transaction

def calculate_insurance(order, order_shipping):
    total_item_value = int(
        sum(item.subtotal for item in order.items.all())
    )

    use_insurance = (
        order.store.enable_insurance
        and total_item_value >= order.store.insurance_threshold
    )

    if not use_insurance:
        return 0

    try:
        shipping_insurance = ShippingInsurance.objects.get(
            shipping=order_shipping.shipping_name
        )

        rate = shipping_insurance.rate
        admin_fee = shipping_insurance.admin_fee

    except ShippingInsurance.DoesNotExist:
        rate = Decimal("0.002")
        admin_fee = 2000

    return ceil(
        (total_item_value * float(rate))
        + admin_fee
    )

def calculate_grand_total(order, order_shipping):
    subtotal = int(
        sum(item.subtotal for item in order.items.all())
    )

    insurance_cost = 0

    if order.store.insurance_paid_by_customer:
        insurance_cost = calculate_insurance(order, order_shipping)

    return (
        subtotal
        + order_shipping.shipping_cost
        + order_shipping.service_fee
        + order_shipping.additional_cost
        + insurance_cost
    )
    
class OrderService:
    def __init__(self, checkout, carts):
        self.checkout = checkout
        self.carts = carts
        self.order = None
        
    def create_order(self):
        self.order = Order.objects.create(
            user=self.checkout.user,
            store=self.checkout.store,
        )
        
        
    def create_order_item(self):
        for cart in self.carts:
            order_item = OrderItem.objects.create(
                order=self.order,
                product=cart.product,
                product_price=cart.product.price,
                qty=cart.qty,
            )
        
    def execute(self):
        # with transaction.atomic():
        self.create_order()
        self.create_order_item()
        return self.order

class OrderShippingService:
    def __init__(self, order, serializer_data, checkout):
        self.order = order
        self.serializer_data = serializer_data
        self.checkout = checkout
        self.order_shipping = None
    
    def create_order_shipping(self):
        self.order_shipping = OrderShipping.objects.create(
            order=self.order,
            shipping_name=self.serializer_data["shipping_name"],
            service_name=self.serializer_data["service_name"],
            shipping_weight=self.serializer_data["shipping_weight"],
            etd=self.serializer_data["etd"],
            shipping_cost=self.serializer_data["shipping_cost"],
            shipping_cashback=self.serializer_data["shipping_cashback"],
            shipping_cost_net=self.serializer_data["shipping_cost_net"],
            service_fee=self.serializer_data["service_fee"],
            origin_ro=self.checkout.store.shipping_address.destination_id,
            origin_address=self.checkout.store.shipping_address.formatted_address,
            destination_ro=self.checkout.destination.destination_id,
            destination_address=self.checkout.destination.formatted_address,
            insurance_value=calculate_insurance(self.order, self.order_shipping)
        )
        
    def finalize_order(self):
        payment_method = (
            Order.PaymentMethod.COD
            if self.serializer_data["is_cod"]
            else Order.PaymentMethod.BANK_TRANSFER
        )
        self.order.payment_method = payment_method
        self.order.grand_total = calculate_grand_total(self.order, self.order_shipping)
        #self.order.status = Order.Status.PENDING
        
        net_income = self.serializer_data["net_income"]
        self.order.net_income = net_income
        if not self.order.store.insurance_paid_by_customer:
            self.order.actual_net_income = (
                net_income - self.order_shipping.insurance_value
            )
        else:
            self.order.actual_net_income = net_income
            
        self.order.save(update_fields=["payment_method", "grand_total", "status", "net_income", "actual_net_income"])
        
    def execute(self):
        with transaction.atomic():
            self.create_order_shipping()
            self.finalize_order()
        return self.order_shipping