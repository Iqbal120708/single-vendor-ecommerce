from rest_framework import status as rest_status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import OrderItem
from .serializers import OrderItemSerializer, OrderSerializer


class GetOrderByFilter(APIView):
    def get(self, request):
        status = request.query_params.get("status")
        payment_status = request.query_params.get("payment_status")

        queryset = OrderItem.objects.select_related("order", "product")

        filter_parameter = {"is_archived": False, "order__user": request.user}
        if status:
            queryset = queryset.filter(order__status=status, **filter_parameter)
        elif payment_status:
            queryset = queryset.filter(
                order__payment_status=payment_status, **filter_parameter
            )
        else:
            return Response(
                {"detail": "Filter parameter required."},
                status=rest_status.HTTP_400_BAD_REQUEST,
            )

        queryset = queryset.order_by("-created_at")
        serializer = OrderItemSerializer(queryset, many=True)
        return Response(serializer.data)


class GetOrderDetail(APIView):
    def get(self, request, order_id):
        filter_parameter = {
            "is_archived": False,
            "order__user": request.user,
            "order__order_id": order_id,
        }

        queryset = (
            OrderItem.objects.select_related("order", "product")
            .filter(**filter_parameter)
            .first()
        )
        if not queryset:
            return Response(
                {"detail": "Order item not found"},
                status=rest_status.HTTP_404_NOT_FOUND,
            )

        order_serializer = OrderSerializer(queryset.order)
        order_item_serializer = OrderItemSerializer(queryset)

        order_item_data = dict(order_item_serializer.data)
        order_item_data["orderitem_created_at"] = order_item_data.pop("created_at")

        data = {
            **order_serializer.data,
            **order_item_data,
        }
        return Response(data)

    def delete(self, request, order_id):
        filter_parameter = {
            "is_archived": False,
            "order__user": request.user,
            "order__order_id": order_id,
        }

        queryset = OrderItem.objects.filter(**filter_parameter).first()
        if not queryset:
            return Response(
                {"detail": "Order item not found"},
                status=rest_status.HTTP_404_NOT_FOUND,
            )

        queryset.is_archived = True
        queryset.save()
        return Response(status=rest_status.HTTP_204_NO_CONTENT)
