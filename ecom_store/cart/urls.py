from django.urls import path
from .views import CartView

urlpatterns = [
    path("", CartView.as_view(), name="cart"),
    path("<int:pk>/", CartView.as_view(), name="cart"),
    path("add-to-cart/<int:product_id>/", CartView.as_view(), name="add_to_cart"),
]