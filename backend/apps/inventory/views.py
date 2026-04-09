from rest_framework import filters, viewsets

from apps.inventory.models import Item, InventoryMovement, RoomInventory
from apps.inventory.serializers import ItemSerializer, InventoryMovementSerializer, RoomInventorySerializer
from accounts.permissions import HasResourcePermission


class ItemViewSet(viewsets.ModelViewSet):
    queryset = (
        Item.objects.select_related(
            "hotel_settings",
            "item_type",
            "unit_measure",
        ).order_by("-id")
    )
    serializer_class = ItemSerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["items.read"]

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "name",
        "sku",
        "description",
        "hotel_settings__hotel_name",
        "item_type__name",
        "item_type__code",
        "unit_measure__name",
        "unit_measure__code",
    ]
    ordering_fields = [
        "id",
        "name",
        "stock",
        "minimum_stock",
        "cost_price",
        "sale_price",
        "created_at",
        "updated_at",
    ]
    ordering = ["-id"]

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["items.write"]
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()
    
class InventoryMovementViewSet(viewsets.ModelViewSet):
    queryset = (
        InventoryMovement.objects.select_related(
            "item",
            "movement_type",
        ).order_by("-id")
    )
    serializer_class = InventoryMovementSerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["inventory-movements.read"]

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "item__name",
        "reference",
        "notes",
        "movement_type__name",
        "movement_type__code",
    ]
    ordering_fields = [
        "id",
        "quantity",
        "previous_stock",
        "new_stock",
        "movement_date",
        "created_at",
        "updated_at",
    ]
    ordering = ["-id"]

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["inventory-movements.write"]
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()
    
class RoomInventoryViewSet(viewsets.ModelViewSet):
    queryset = (
        RoomInventory.objects.select_related(
            "room",
            "item",
        ).order_by("-id")
    )
    serializer_class = RoomInventorySerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["room-inventory.read"]

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "room__number",
        "item__name",
        "item__sku",
        "notes",
    ]
    ordering_fields = [
        "id",
        "quantity",
        "minimum_quantity",
        "created_at",
        "updated_at",
    ]
    ordering = ["-id"]

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["room-inventory.write"]
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()