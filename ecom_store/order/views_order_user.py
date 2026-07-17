from rest_framework import status as rest_status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import OrderItem, RefundRequest
from .serializers import OrderItemSerializer, OrderSerializer, RefundRequestDetailSerializer


class GetOrderByFilter(APIView):
    def get(self, request):
        status = request.query_params.get("status")
        payment_status = request.query_params.get("payment_status")

        if not status and not payment_status:
            return Response(
                {"detail": "Filter parameter required."},
                status=rest_status.HTTP_400_BAD_REQUEST,
            )

        filter_parameter = {"is_archived": False, "order__user": request.user}
        if status:
            filter_parameter["order__status"] = status
        if payment_status:
            filter_parameter["order__payment_status"] = payment_status

        queryset = (
            OrderItem.objects.select_related("order", "product")
            .filter(**filter_parameter)
            .exclude(order__shipping__isnull=True)
            .order_by("-created_at")
        )
        serializer = OrderItemSerializer(queryset, many=True)
        return Response(serializer.data)


class GetOrderDetail(APIView):
    def get(self, request, order_id):
        filter_parameter = {
            "is_archived": False,
            "order__user": request.user,
            "order__order_id": order_id,
        }

        order_items = (
            OrderItem.objects.select_related("order", "product")
            .filter(**filter_parameter)
            .exclude(order__shipping__isnull=True)
            .order_by("created_at")
        )
        if not order_items.exists():
            return Response(
                {"detail": "Order item not found"},
                status=rest_status.HTTP_404_NOT_FOUND,
            )

        order = order_items.first().order
        order_serializer = OrderSerializer(order)
        order_item_serializer = OrderItemSerializer(order_items, many=True)

        order_item_data = order_item_serializer.data
        for item in order_item_data:
            item.pop("order_id", None)

        data = dict(order_serializer.data)
        data["items"] = order_item_serializer.data
        return Response(data)

    def delete(self, request, order_id):
        filter_parameter = {
            "is_archived": False,
            "order__user": request.user,
            "order__order_id": order_id,
        }

        order_items = OrderItem.objects.filter(**filter_parameter)
        if not order_items.exists():
            return Response(
                {"detail": "Order item not found"},
                status=rest_status.HTTP_404_NOT_FOUND,
            )

        order_items.update(is_archived=True)
        return Response(status=rest_status.HTTP_204_NO_CONTENT)

class RefundRequestByItemView(APIView):

    def get(self, request, order_item_id):
        refund_request = RefundRequest.objects.filter(
            order_item_id=order_item_id,
            order_item__order__user=request.user,
        ).order_by("-requested_at").first()

        if not refund_request:
            return Response({"detail": "Belum ada refund request untuk item ini."}, status=404)

        return Response(RefundRequestDetailSerializer(refund_request).data)