from django.urls import path
from accounts.views import UserViewSet

urlpatterns = [
    path("<int:pk>/", UserViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update"}), name="user-detail"),
]