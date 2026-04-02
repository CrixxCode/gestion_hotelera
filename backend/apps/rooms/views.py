from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import HasResourcePermission
from apps.master_data.models import MasterData
from .models import Rate, Amenity, Room, MaintenanceOrder, CleaningTask
from .serializers import (
    RoomTypeSerializer,
    RateSerializer,
    AmenitySerializer,
    RoomSerializer,
    MaintenanceOrderSerializer,
    CleaningTaskSerializer,
    RoomPanelSerializer,
)


class RoomTypeViewSet(viewsets.ModelViewSet):
    queryset = MasterData.objects.filter(group=MasterData.Group.ROOM_TYPE).order_by("name")
    serializer_class = RoomTypeSerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["room_type.read"]

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["code", "name", "description"]
    ordering_fields = ["id", "code", "name", "sort_order", "created_at"]
    ordering = ["sort_order", "name"]

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["room_type.write"]
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()

    def get_queryset(self):
        return super().get_queryset().filter(group=MasterData.Group.ROOM_TYPE)

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        serializer.save()


class RateViewSet(viewsets.ModelViewSet):
    queryset = Rate.objects.select_related("room_type").all().order_by("-created_at")
    serializer_class = RateSerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["rates.read"]

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "room_type__name", "room_type__code"]
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

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()


class RoomViewSet(viewsets.ModelViewSet):
    queryset = (
        Room.objects.select_related("room_type", "floor", "status")
        .prefetch_related(
            "amenities",
            "maintenance_orders",
            "reservation_details__reservation__status",
            "reservation_details__reservation__client",
        )
        .all()
        .order_by("number")
    )
    serializer_class = RoomSerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["rooms.read"]

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "number",
        "room_type__name",
        "room_type__code",
        "floor__name",
        "notes",
        "status__code",
        "status__name",
    ]
    ordering_fields = ["id", "number", "created_at"]
    ordering = ["number"]

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["rooms.write"]
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()

    def get_queryset(self):
        queryset = super().get_queryset()
        status_code = (self.request.query_params.get("status") or "").strip().upper()
        floor = (self.request.query_params.get("floor") or "").strip()
        room_type = (self.request.query_params.get("room_type") or "").strip()

        if status_code:
            queryset = queryset.filter(status__code=status_code)
        if floor.isdigit():
            queryset = queryset.filter(floor_id=int(floor))
        if room_type:
            if room_type.isdigit():
                queryset = queryset.filter(room_type_id=int(room_type))
            else:
                queryset = queryset.filter(room_type__code=room_type.upper())

        return queryset

    @action(detail=True, methods=["GET"], name="panel")
    def panel(self, request, pk=None):
        room = self.get_object()
        serializer = RoomPanelSerializer(room, context=self.get_serializer_context())
        return Response(serializer.data)


class MaintenanceOrderViewSet(viewsets.ModelViewSet):
    queryset = MaintenanceOrder.objects.select_related("room", "priority", "status").all().order_by("-reported_at")
    serializer_class = MaintenanceOrderSerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["maintenance_orders.read"]

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "title",
        "description",
        "room__number",
        "priority__code",
        "priority__name",
        "status__code",
        "status__name",
    ]
    ordering_fields = ["id", "reported_at", "completed_at"]
    ordering = ["-reported_at"]

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["maintenance_orders.write"]
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()


class CleaningTaskViewSet(viewsets.ModelViewSet):
    queryset = CleaningTask.objects.select_related("room", "task_type", "status").all().order_by("-created_at")
    serializer_class = CleaningTaskSerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["cleaning_tasks.read"]

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "room__number",
        "notes",
        "task_type__code",
        "task_type__name",
        "status__code",
        "status__name",
    ]
    ordering_fields = ["id", "scheduled_for", "created_at", "completed_at"]
    ordering = ["-created_at"]

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["cleaning_tasks.write"]
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()
