from rest_framework import serializers
from .models import Cart
from product.models import Product
from product.serializers import ProductSerializer

class CartSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source="product",
        write_only=True
    )
    
    def validate(self, attrs):
        product = attrs.get("product") or getattr(self.instance, "product", None)
        
        if not product:
            raise serializers.ValidationError({
                "product": "Product is required."
            })
    
        qty = attrs.get("qty")
    
        # Validasi qty harus > 0
        if qty is not None and qty <= 0:
            raise serializers.ValidationError({
                "qty": "Quantity must be greater than 0."
            })
    
        # Validasi stok
        if qty is not None and qty > product.stock:
            raise serializers.ValidationError({
                "qty": f"Quantity cannot exceed stock {product.stock}."
            })
    
        return attrs
    
    
    class Meta:
        model = Cart
        fields = [
            "id", "user", "product", "product_id", "qty", "created_at", "updated_at"
        ]
        read_only_fields = ["user", "created_at", "updated_at"]

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)