from rest_framework import filters, viewsets

from apps.promotions.models import Promotion
from apps.promotions.serializers import PromotionSerializer
from accounts.permissions import HasResourcePermission
from accounts.soft_delete import LogicalDeleteViewSetMixin


class PromotionViewSet(LogicalDeleteViewSetMixin, viewsets.ModelViewSet):
    queryset = (
        Promotion.objects.select_related(
            "hotel_settings",
            "discount_type",
            "service",
            "package",
        ).order_by("-id")
    )
    serializer_class = PromotionSerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["promotions.read"]

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "name",
        "code",
        "description",
        "hotel_settings__hotel_name",
        "discount_type__name",
        "discount_type__code",
        "service__name",
        "package__name",
    ]
    ordering_fields = [
        "id",
        "name",
        "code",
        "discount_value",
        "start_date",
        "end_date",
        "created_at",
        "updated_at",
    ]
    ordering = ["-id"]

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["promotions.write"]
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()
