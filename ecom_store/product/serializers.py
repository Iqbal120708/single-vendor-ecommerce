from rest_framework import serializers
from .models import Category, Product


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "desc", "created_at", "updated_at"]


class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    # category_id = serializers.PrimaryKeyRelatedField(
    #     queryset=Category.objects.all(),
    #     source="category",
    # )

    class Meta:
        model = Product
        fields = [
            "id", "name", "category", #"category_id"
            "weight", "stock", "price", "created_at", "updated_at"
        ]


