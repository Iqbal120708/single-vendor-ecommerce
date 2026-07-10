from django.shortcuts import render
from order.models import OrderItem
from product.models import Product
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Comment
from .serializers import CommentSerializer


# Create your views here.
class CommentView(APIView):
    def get(self, request, product_id):
        queryset = Comment.objects.select_related("product", "user").filter(
            user=request.user, is_archived=False, product__id=product_id
        )

        serializer = CommentSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request, product_id):
        product = Product.objects.filter(pk=product_id).first()
        if not product:
            return Response(
                {"detail": "Product not found"}, status=status.HTTP_404_NOT_FOUND
            )

        order = OrderItem.objects.filter(
            order__user=request.user, product=product, order__status="delivered"
        )
        if not order.exists():
            raise PermissionDenied("User belum pernah membeli product")

        existing_comment = Comment.objects.filter(
            user=request.user, product=product
        ).first()
        if existing_comment and not existing_comment.is_archived:
            return Response(
                {"detail": "Anda sudah pernah memberi komentar untuk produk ini"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = request.data.copy()
        data["product_id"] = product.id

        if existing_comment:
            # Row lama sudah di-archive (soft-deleted). unique_together
            # (user, product) di level database tidak membedakan
            # archived/tidak, jadi row lama harus di-reuse (di-update
            # dan di-unarchive), bukan bikin row Comment baru.
            serializer = CommentSerializer(
                existing_comment, data=data, context={"request": request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save(is_archived=False)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        serializer = CommentSerializer(data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def put(self, request, product_id):
        comment = Comment.objects.filter(
            user=request.user, product__id=product_id, is_archived=False
        ).first()
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
        comment = Comment.objects.filter(
            user=request.user, product__id=product_id, is_archived=False
        ).first()
        if not comment:
            return Response(
                {"detail": "Comment not found"}, status=status.HTTP_404_NOT_FOUND
            )

        comment.is_archived = True
        comment.save()

        return Response(status=status.HTTP_204_NO_CONTENT)
