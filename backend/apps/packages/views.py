from rest_framework import filters, viewsets

from apps.packages.models import Package, PackageService
from apps.packages.serializers import PackageSerializer, PackageServiceSerializer
from accounts.permissions import HasResourcePermission
from accounts.soft_delete import LogicalDeleteViewSetMixin


class PackageViewSet(LogicalDeleteViewSetMixin, viewsets.ModelViewSet):
    queryset = (
        Package.objects.select_related(
            "hotel_settings",
            "room_type",
        )
        .prefetch_related(
            "package_services__service",
            "package_services__service__service_type",
        )
        .order_by("-id")
    )
    serializer_class = PackageSerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["packages.read"]

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "name",
        "description",
        "hotel_settings__hotel_name",
        "room_type__name",
        "room_type__code",
    ]
    ordering_fields = [
        "id",
        "name",
        "base_price",
        "start_date",
        "end_date",
        "created_at",
        "updated_at",
    ]
    ordering = ["-id"]

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["packages.write"]
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()


class PackageServiceViewSet(LogicalDeleteViewSetMixin, viewsets.ModelViewSet):
    queryset = (
        PackageService.objects.select_related(
            "package",
            "service",
            "service__service_type",
        ).order_by("id")
    )
    serializer_class = PackageServiceSerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["packages.read"]

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "package__name",
        "service__name",
        "service__service_type__name",
    ]
    ordering_fields = [
        "id",
        "quantity",
        "created_at",
    ]
    ordering = ["id"]

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["packages.write"]
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()
