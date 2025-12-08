from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Category, Product
from .serializers import CategorySerializer, ProductSerializer


class CategoryList(APIView):
    def get(self, request):
        queryset = Category.objects.all().order_by("id")
        serializer = CategorySerializer(queryset, many=True)
        return Response(serializer.data)


class ProductList(APIView):
    def get(self, request):
        queryset = Product.objects.all().order_by("id")
        serializer = ProductSerializer(queryset, many=True)
        return Response(serializer.data)


class ProductDetail(APIView):
    def get(self, request, pk):
        product = Product.objects.filter(pk=pk).first()
        if not product:
            return Response(
                {"detail": "Product not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ProductSerializer(product)
        return Response(serializer.data)