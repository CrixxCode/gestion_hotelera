from rest_framework import serializers
from .models import RoomType, Rate, Amenity, Room, MaintenanceOrder, CleaningTask

class AmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Amenity
        fields = "__all__"
        read_only_fields = ("id", "created_at")

class RoomTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomType
        fields = "__all__"
        read_only_fields = ("id", "created_at")

class RateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rate
        fields = "__all__"
        read_only_fields = ("id", "created_at")

class RoomSerializer(serializers.ModelSerializer):
    room_type_name = serializers.CharField(source="room_type.name", read_only=True)
    floor_name = serializers.CharField(source="floor.name", read_only=True)
    florr_number = serializers.IntegerField(source="floor.floor_number", read_only=True)

    amenities = AmenitySerializer(many=True, read_only=True)

    amenity_ids = serializers.PrimaryKeyRelatedField(
        queryset=Amenity.objects.all(),
        source="amenities",
        many=True,
        write_only=True,
        required=False
    )

    class Meta:
        model = Room
        fields = "__all__"
        read_only_fields = ("id", "created_at")

class MaintenanceOrderSerializer(serializers.ModelSerializer):
    room_number = serializers.CharField(source="room.number", read_only=True)

    class Meta:
        model = MaintenanceOrder
        fields = "__all__"
        read_only_fields = ("id", "reported_at")

class CleaningTaskSerializer(serializers.ModelSerializer):
    room_number = serializers.CharField(source="room.number", read_only=True)

    class Meta:
        model = CleaningTask
        fields = "__all__"
        read_only_fields = ("id", "created_at")

class RoomAmenityMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Amenity
        fields = ("id", "name", "icon")


class RoomTypeMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomType
        fields = ("id", "name", "capacity", "bed_count", "bed_type")


class RateMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rate
        fields = ("id", "name", "price")

class RoomPanelSerializer(serializers.ModelSerializer):
    # Tipo de habitación resumido
    room_type = RoomTypeMiniSerializer(read_only=True)

    # Amenidades resumidas
    amenities = RoomAmenityMiniSerializer(many=True, read_only=True)

    # Información del piso
    floor_name = serializers.CharField(source="floor.name", read_only=True)
    floor_number = serializers.IntegerField(source="floor.floor_number", read_only=True)

    # Etiqueta visible del estado
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    # Campos calculados
    rate = serializers.SerializerMethodField()
    active_maintenance = serializers.SerializerMethodField()
    current_guest = serializers.SerializerMethodField()
    active_reservation = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = (
            "id",
            "number",
            "status",
            "status_label",
            "notes",
            "floor_name",
            "floor_number",
            "room_type",
            "rate",
            "amenities",
            "current_guest",
            "active_reservation",
            "active_maintenance",
        )

    def get_rate(self, obj):
        """
        Devuelve una tarifa activa asociada al tipo de habitación.
        Si hay varias, toma la más reciente.
        """
        if not obj.room_type:
            return None

        rate = obj.room_type.rates.filter(is_active=True).order_by("-created_at").first()
        if not rate:
            return None

        return RateMiniSerializer(rate).data

    def get_active_maintenance(self, obj):
        """
        Devuelve una orden de mantenimiento activa si existe.
        """
        maintenance = obj.maintenance_orders.filter(
            status__in=["PENDIENTE", "EN_PROCESO"]
        ).order_by("-reported_at").first()

        if not maintenance:
            return None

        return {
            "id": maintenance.id,
            "title": maintenance.title,
            "description": maintenance.description,
            "priority": maintenance.priority,
            "priority_label": maintenance.get_priority_display(),
            "status": maintenance.status,
            "status_label": maintenance.get_status_display(),
            "reported_at": maintenance.reported_at,
            "completed_at": maintenance.completed_at,
        }

    def get_current_guest(self, obj):
        """
        Este campo depende del módulo de reservas.
        Por ahora devuelve None hasta integrar reservation/client.
        """
        return None

    def get_active_reservation(self, obj):
        """
        Este campo depende del módulo de reservas.
        Por ahora devuelve None hasta integrar reservation.
        """
        return None
