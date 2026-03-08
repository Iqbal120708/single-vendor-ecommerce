from rest_framework import serializers
from .models import Comment
from product.models import Product

class CommentSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)

    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source="product", write_only=True
    )
    class Meta:
        model = Comment
        fields = ["id", "product_id", "product_name", "username", "content", "rating", "created_at", "updated_at"]
        read_only_fields = ["user", "created_at", "updated_at"]
        
    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)
    