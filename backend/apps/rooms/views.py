from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import RoomType, Rate, Amenity, Room, MaintenanceOrder, CleaningTask
from .serializers import (
    RoomTypeSerializer,
    RateSerializer,
    AmenitySerializer,
    RoomSerializer,
    MaintenanceOrderSerializer,
    CleaningTaskSerializer,
    RoomPanelSerializer,
)
from accounts.permissions import HasResourcePermission

class RoomTypeViewSet(viewsets.ModelViewSet):
    queryset = RoomType.objects.all().order_by("name")
    serializer_class = RoomTypeSerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["room_type.read"]

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description", "bed_type"]
    ordering_fields = ["id", "name", "capacity", "created_at"]
    ordering = ["name"]

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["room_type.write"]
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()

class RateViewSet(viewsets.ModelViewSet):
    queryset = Rate.objects.select_related("room_type").all().order_by("-created_at")
    serializer_class = RateSerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["rates.read"]

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "room_type__name"]
    ordering_fields = ["id", "name", "price", "start_date", "end_date", "created_at"]
    ordering = ["-created_at"]

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["rates.write"]
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()

class AmenityViewSet(viewsets.ModelViewSet):
    queryset = Amenity.objects.all().order_by("name")
    serializer_class = AmenitySerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["amenities.read"]

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description", "icon"]
    ordering_fields = ["id", "name", "created_at"]
    ordering = ["name"]

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["amenities.write"]
        return self.required_scopes

    def get_permission(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()

class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.select_related("room_type", "floor").prefetch_related("amenities", "maintenance_orders").all().order_by("number")
    serializer_class = RoomSerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["rooms.read"]

    filter_backend = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["number", "room_type_name", "floor_name", "notes", "status"]
    ordering_fields = ["id", "number", "status", "created_at"]
    ordering = ["number"]

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["rooms.write"]
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()

    @action(detail=True, methods=["GET"], name="panel")
    def panel(self, request, pk=None):
        """
        Devuelve un detalle enriquecido de la habitacion
        """
        room = self.get_object()
        serializer = RoomPanelSerializer(room, context=self.get_serializer_context())
        return Response(serializer.data)

class MaintenanceOrderViewSet(viewsets.ModelViewSet):
    queryset = MaintenanceOrder.objects.select_related("room").all().order_by("-reported_at")
    serializer_class = MaintenanceOrderSerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["maintenance_orders.read"]

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "description", "room__number", "priority", "status"]
    ordering_fields = ["id", "priority", "status", "reported_at", "completed_at"]
    ordering = ["-reported_at"]

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["maintenance_orders.write"]
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()

class CleaningTaskViewSet(viewsets.ModelViewSet):
    queryset = CleaningTask.objects.select_related("room").all().order_by("-created_at")
    serializer_class = CleaningTaskSerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["cleaning_tasks.read"]

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["room_number", "notes", "task_type", "status"]
    ordering_fields = ["id", "task_type", "status", "scheduled_for", "created_at", "completed_at"]
    ordering = ["-created_at"]

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["cleaning_tasks.write"]
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()
