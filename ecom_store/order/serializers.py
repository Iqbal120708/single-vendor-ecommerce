from rest_framework import serializers
from django.core.validators import MinValueValidator

class ShippingSerializer(serializers.Serializer):
    checkout_id = serializers.CharField(max_length=36)
    code = serializers.CharField(max_length=20)
    #name = serializers.CharField(max_length=50)
    service = serializers.CharField(max_length=20)
    #description = serializers.CharField(max_length=255)
    cost = serializers.IntegerField(
        validators=[MinValueValidator(1)]
    )
    #etd = serializers.CharField(max_length=10)