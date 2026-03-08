from django.shortcuts import render
from rest_framework.views import APIView
from .models import Comment
from product.models import Product
from order.models import OrderItem
from .serializers import CommentSerializer
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import PermissionDenied

# Create your views here.
class CommentView(APIView):
    def get(self, request, product_id):
        queryset = Comment.objects.select_related("product", "user").filter(user=request.user, is_archived=False, product__id=product_id)
        
        serializer = CommentSerializer(queryset, many=True)
        return Response(serializer.data)
        
    def post(self, request, product_id):
        product = Product.objects.filter(pk=product_id).first()
        if not product:
            return Response(
                {"detail": "Product not found"}, status=status.HTTP_404_NOT_FOUND
            )
            
        order = OrderItem.objects.filter(order__user=request.user, product=product, order__status="delivered")
        if not order.exists():
            raise PermissionDenied("User belum pernah membeli product")
        
        data = request.data.copy()
        data["product_id"] = product.id
        
        serializer = CommentSerializer(data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)
        
    def put(self, request, product_id):
        comment = Comment.objects.filter(user=request.user, product__id=product_id).first()
        if not comment:
            return Response(
                {"detail": "Comment not found"}, status=status.HTTP_404_NOT_FOUND
            )
            
        if not comment.is_editable():
            raise PermissionDenied("Komentar sudah tidak bisa diedit setelah 24 jam")
            
        data = request.data.copy()
        data["product_id"] = product_id
        
        serializer = CommentSerializer(comment, data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    def delete(self, request, product_id):
        comment = Comment.objects.filter(user=request.user, product__id=product_id).first()
        if not comment:
            return Response(
                {"detail": "Comment not found"}, status=status.HTTP_404_NOT_FOUND
            )
            
        comment.is_archived = True
        comment.save()
        
        return Response(status=status.HTTP_204_NO_CONTENT)