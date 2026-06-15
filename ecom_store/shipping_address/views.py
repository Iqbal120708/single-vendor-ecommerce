from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import City, District, Province, ShippingAddress, SubDistrict
from .serializers import (
    CitySerializer,
    DistrictSerializer,
    ProvinceSerializer,
    ShippingAddressSerializer,
    SubDistrictSerializer,
)
from .utils import get_destination_id


class BaseAddressView(APIView):
    def get(self, request, pk=None):
        model = self.Meta.model
        cls_serializer = self.Meta.serializer

        if pk is not None:
            instance = get_object_or_404(model, pk=pk)
            serializer = cls_serializer(instance)
            return Response(serializer.data)

        name = request.GET.get("name")
        queryset = model.objects.all()

        select_related = getattr(self.Meta, "select_related", [])
        if select_related:
            queryset.select_related(*select_related)

        if name:
            queryset = queryset.filter(name__iexact=name)

        queryset = queryset.order_by("id")
        serializer = cls_serializer(queryset, many=True)
        return Response(serializer.data)


class ProvinceView(BaseAddressView):
    class Meta:
        model = Province
        serializer = ProvinceSerializer


class CityView(BaseAddressView):
    class Meta:
        model = City
        serializer = CitySerializer
        select_related = ["province"]


class DistrictView(BaseAddressView):
    class Meta:
        model = District
        serializer = DistrictSerializer
        select_related = ["city"]


class SubDistrictView(BaseAddressView):
    class Meta:
        model = SubDistrict
        serializer = SubDistrictSerializer

    def get(self, request, pk=None):
        if pk:
            return super().get(request, pk)

        zip_code = request.GET.get("zip_code")
        name = request.GET.get("name")
        model = self.Meta.model

        queryset = model.objects.all().select_related("district")

        if zip_code:
            queryset = queryset.filter(zip_code=zip_code)

        if name:
            queryset = queryset.filter(name__iexact=name)

        queryset = queryset.order_by("id")
        serializer = self.Meta.serializer(queryset, many=True)
        return Response(serializer.data)


class ShippingAddressView(APIView):
    def get(self, request, pk=None):
        if pk:
            instance = (
                ShippingAddress.objects.filter(pk=pk, user=request.user)
                .select_related(
                    "province",
                    "city",
                    "district",
                    "subdistrict",
                )
                .first()
            )
            if not instance:
                return Response({})
            serializer = ShippingAddressSerializer(instance)
            return Response(serializer.data)

        queryset = ShippingAddress.objects.filter(user=request.user).select_related(
            "province",
            "city",
            "district",
            "subdistrict",
        )
        serializer = ShippingAddressSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        with transaction.atomic():
            serializer = ShippingAddressSerializer(
                data=request.data, context={"request": request}
            )
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            destination_id = get_destination_id(data)
            serializer.save(destination_id=destination_id)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def put(self, request, pk):
        with transaction.atomic():
            instance = (
                ShippingAddress.objects.filter(pk=pk, user=request.user)
                .select_for_update()
                .select_related(
                    "province",
                    "city",
                    "district",
                    "subdistrict",
                )
                .first()
            )
            if not instance:
                return Response(
                    {"detail": "Item not found in cart"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = ShippingAddressSerializer(
                instance, data=request.data, context={"request": request}
            )

            serializer.is_valid(raise_exception=True)

            data = serializer.validated_data

            need_refresh_destination = any(
                [
                    instance.province != data["province"],
                    instance.city != data["city"],
                    instance.district != data["district"],
                    instance.subdistrict != data["subdistrict"],
                ]
            )

            if need_refresh_destination:
                destination_id = get_destination_id(data)
            else:
                destination_id = instance.destination_id

            serializer.save(destination_id=destination_id)

        return Response(serializer.data)

    def delete(self, request, pk):
        instance = ShippingAddress.objects.filter(pk=pk, user=request.user).first()

        if not instance:
            return Response(
                {"detail": "Item not found in cart"}, status=status.HTTP_404_NOT_FOUND
            )

        instance.delete()

        return Response({"detail": "Item deleted"}, status=status.HTTP_204_NO_CONTENT)
