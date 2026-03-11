from django.urls import path

from .views import CommentView

urlpatterns = [path("<int:product_id>/", CommentView.as_view(), name="comment")]
