from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, serializers

from product.models import Product
from .models import Cart
from .serializers import CartSerializer


class CartView(APIView):

    def get(self, request):
        queryset = Cart.objects.filter(user=request.user).order_by("id")
        serializer = CartSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request, product_id):
        product = Product.objects.filter(pk=product_id).first()
        if not product:
            return Response(
                {"detail": "Product not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        data = {
            "product_id": product.id,
            "qty": 1,
        }

        serializer = CartSerializer(
            data=data,
            context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )
        
    def patch(self, request, pk):
        cart_item = Cart.objects.filter(
            pk=pk
        ).first()
    
        if not cart_item:
            return Response(
                {"detail": "Item not found in cart"},
                status=status.HTTP_404_NOT_FOUND
            )

        if "qty" not in request.data:
            raise serializers.ValidationError({
                "qty": ["Field qty is required."]
            })
                
        serializer = CartSerializer(
            cart_item,
            data={"qty": request.data.get("qty")},
            partial=True
        )
    
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
    
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    def delete(self, request, pk):
        cart_item = Cart.objects.filter(
            pk=pk
        ).first()
    
        if not cart_item:
            return Response(
                {"detail": "Item not found in cart"},
                status=status.HTTP_404_NOT_FOUND
            )
    
        cart_item.delete()
    
        return Response({"detail": "Item deleted"}, status=status.HTTP_204_NO_CONTENT)
        