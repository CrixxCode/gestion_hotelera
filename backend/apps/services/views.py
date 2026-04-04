from rest_framework import filters, viewsets

from apps.services.models import Service
from apps.services.serializers import ServiceSerializer
from accounts.permissions import HasResourcePermission


class ServiceViewSet(viewsets.ModelViewSet):
    queryset = (
        Service.objects.select_related(
            "hotel_settings",
            "service_type",
        ).order_by("-id")
    )
    serializer_class = ServiceSerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["services.read"]

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "name",
        "description",
        "hotel_settings__hotel_name",
        "service_type__name",
        "service_type__code",
    ]
    ordering_fields = [
        "id",
        "name",
        "base_price",
        "created_at",
        "updated_at",
    ]
    ordering = ["-id"]

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["services.write"]
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()