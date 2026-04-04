from django.utils.text import slugify
from rest_framework import serializers

from apps.master_data.models import MasterData
from apps.master_data.serializers import MasterDataCodeField
from apps.reservations.services import (
    INACTIVE_RESERVATION_STATUS_CODES,
    is_reservation_in_house,
)
from .models import Rate, Amenity, Room, MaintenanceOrder, CleaningTask

AMENITY_ICON_CATALOG = {
    "fa-solid fa-bed",
    "fa-solid fa-wifi",
    "fa-solid fa-tv",
    "fa-solid fa-bath",
    "fa-solid fa-snowflake",
    "fa-solid fa-mug-hot",
    "fa-solid fa-square-parking",
    "fa-solid fa-water-ladder",
    "fa-solid fa-bell-concierge",
    "fa-solid fa-dumbbell",
}


class AmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Amenity
        fields = "__all__"
        read_only_fields = ("id", "created_at")
        extra_kwargs = {
            "icon": {"required": True, "allow_blank": False, "allow_null": False},
        }

    def validate_name(self, value):
        normalized = (value or "").strip()
        if not normalized:
            raise serializers.ValidationError("El nombre de la amenidad es obligatorio.")
        return normalized

    def validate_icon(self, value):
        normalized = (value or "").strip()
        if normalized not in AMENITY_ICON_CATALOG:
            raise serializers.ValidationError("Icono no valido para amenidades.")
        return normalized


class RoomTypeSerializer(serializers.ModelSerializer):
    capacity = serializers.IntegerField(required=False, min_value=1, default=1)
    bed_count = serializers.IntegerField(required=False, min_value=1, default=1)
    bed_type = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = MasterData
        fields = (
            "id",
            "code",
            "name",
            "description",
            "capacity",
            "bed_count",
            "bed_type",
            "is_active",
            "created_at",
        )
        read_only_fields = ("id", "created_at")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        metadata = instance.metadata or {}
        data["capacity"] = int(metadata.get("capacity", 1))
        data["bed_count"] = int(metadata.get("bed_count", 1))
        data["bed_type"] = metadata.get("bed_type")
        return data

    def validate_code(self, value):
        return str(value).strip().upper()

    def create(self, validated_data):
        metadata = {
            "capacity": validated_data.pop("capacity", 1),
            "bed_count": validated_data.pop("bed_count", 1),
            "bed_type": validated_data.pop("bed_type", None),
        }

        code = validated_data.get("code")
        if not code:
            generated = slugify(validated_data.get("name", "")).replace("-", "_").upper()
            validated_data["code"] = generated or "ROOM_TYPE"

        return MasterData.objects.create(
            group=MasterData.Group.ROOM_TYPE,
            metadata=metadata,
            **validated_data,
        )

    def update(self, instance, validated_data):
        metadata = dict(instance.metadata or {})

        if "capacity" in validated_data:
            metadata["capacity"] = validated_data.pop("capacity")
        if "bed_count" in validated_data:
            metadata["bed_count"] = validated_data.pop("bed_count")
        if "bed_type" in validated_data:
            metadata["bed_type"] = validated_data.pop("bed_type")

        for field, value in validated_data.items():
            setattr(instance, field, value)

        instance.group = MasterData.Group.ROOM_TYPE
        instance.metadata = metadata
        instance.save()
        return instance


class RateSerializer(serializers.ModelSerializer):
    room_type = serializers.PrimaryKeyRelatedField(
        queryset=MasterData.objects.filter(group=MasterData.Group.ROOM_TYPE)
    )
    room_type_name = serializers.CharField(source="room_type.name", read_only=True)

    class Meta:
        model = Rate
        fields = "__all__"
        read_only_fields = ("id", "created_at")


class RoomSerializer(serializers.ModelSerializer):
    room_type = serializers.PrimaryKeyRelatedField(
        queryset=MasterData.objects.filter(group=MasterData.Group.ROOM_TYPE),
        allow_null=True,
        required=False,
    )
    room_type_name = serializers.CharField(source="room_type.name", read_only=True)
    floor_name = serializers.CharField(source="floor.name", read_only=True)
    floor_number = serializers.IntegerField(source="floor.floor_number", read_only=True)
    florr_number = serializers.IntegerField(source="floor.floor_number", read_only=True)

    status = MasterDataCodeField(group=MasterData.Group.ROOM_STATUS)
    status_label = serializers.CharField(source="status.name", read_only=True)
    active_reservation = serializers.SerializerMethodField()

    amenities = AmenitySerializer(many=True, read_only=True)
    amenity_ids = serializers.PrimaryKeyRelatedField(
        queryset=Amenity.objects.all(),
        source="amenities",
        many=True,
        write_only=True,
        required=False,
    )

    class Meta:
        model = Room
        fields = (
            "id",
            "number",
            "room_type",
            "room_type_name",
            "floor",
            "floor_name",
            "floor_number",
            "florr_number",
            "status",
            "status_label",
            "active_reservation",
            "notes",
            "amenities",
            "amenity_ids",
            "created_at",
        )
        read_only_fields = ("id", "created_at")

    def get_active_reservation(self, obj):
        reservation_details = list(
            obj.reservation_details.select_related(
                "reservation",
                "reservation__status",
                "reservation__client",
            )
            .filter(reservation__real_check_out__isnull=True)
            .exclude(reservation__status__code__in=INACTIVE_RESERVATION_STATUS_CODES)
            .order_by("reservation__expected_check_in", "reservation__id")
        )

        if not reservation_details:
            return None

        detail = next(
            (item for item in reservation_details if is_reservation_in_house(item.reservation)),
            reservation_details[0],
        )
        reservation = detail.reservation

        return {
            "id": reservation.id,
            "status": reservation.status_code,
            "status_label": reservation.status.name if reservation.status else None,
            "expected_check_in": reservation.expected_check_in,
            "expected_check_out": reservation.expected_check_out,
            "real_check_in": reservation.real_check_in,
            "real_check_out": reservation.real_check_out,
            "client_name": reservation.client.full_name if reservation.client_id else None,
        }


class MaintenanceOrderSerializer(serializers.ModelSerializer):
    room_number = serializers.CharField(source="room.number", read_only=True)
    priority = MasterDataCodeField(group=MasterData.Group.MAINTENANCE_PRIORITY)
    status = MasterDataCodeField(group=MasterData.Group.MAINTENANCE_STATUS)
    priority_label = serializers.CharField(source="priority.name", read_only=True)
    status_label = serializers.CharField(source="status.name", read_only=True)

    class Meta:
        model = MaintenanceOrder
        fields = (
            "id",
            "room",
            "room_number",
            "title",
            "description",
            "priority",
            "priority_label",
            "status",
            "status_label",
            "reported_at",
            "completed_at",
        )
        read_only_fields = ("id", "reported_at")


class CleaningTaskSerializer(serializers.ModelSerializer):
    room_number = serializers.CharField(source="room.number", read_only=True)
    task_type = MasterDataCodeField(group=MasterData.Group.CLEANING_TASK_TYPE)
    status = MasterDataCodeField(group=MasterData.Group.CLEANING_STATUS)
    task_type_label = serializers.CharField(source="task_type.name", read_only=True)
    status_label = serializers.CharField(source="status.name", read_only=True)

    class Meta:
        model = CleaningTask
        fields = (
            "id",
            "room",
            "room_number",
            "task_type",
            "task_type_label",
            "status",
            "status_label",
            "scheduled_for",
            "completed_at",
            "notes",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class RoomAmenityMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Amenity
        fields = ("id", "name", "icon")


class RoomTypeMiniSerializer(serializers.ModelSerializer):
    capacity = serializers.SerializerMethodField()
    bed_count = serializers.SerializerMethodField()
    bed_type = serializers.SerializerMethodField()

    class Meta:
        model = MasterData
        fields = ("id", "name", "capacity", "bed_count", "bed_type")

    def get_capacity(self, obj):
        return int((obj.metadata or {}).get("capacity", 1))

    def get_bed_count(self, obj):
        return int((obj.metadata or {}).get("bed_count", 1))

    def get_bed_type(self, obj):
        return (obj.metadata or {}).get("bed_type")


class RateMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rate
        fields = ("id", "name", "price")


class RoomPanelSerializer(serializers.ModelSerializer):
    room_type = RoomTypeMiniSerializer(read_only=True)
    amenities = RoomAmenityMiniSerializer(many=True, read_only=True)

    floor_name = serializers.CharField(source="floor.name", read_only=True)
    floor_number = serializers.IntegerField(source="floor.floor_number", read_only=True)

    status = serializers.CharField(source="status.code", read_only=True)
    status_label = serializers.CharField(source="status.name", read_only=True)

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
        if not obj.room_type:
            return None

        rate = obj.room_type.rates.filter(is_active=True).order_by("-created_at").first()
        if not rate:
            return None

        return RateMiniSerializer(rate).data

    def get_active_maintenance(self, obj):
        maintenance = obj.maintenance_orders.filter(
            status__code__in=["PENDIENTE", "EN_PROCESO"]
        ).order_by("-reported_at").first()

        if not maintenance:
            return None

        return {
            "id": maintenance.id,
            "title": maintenance.title,
            "description": maintenance.description,
            "priority": maintenance.priority_code,
            "priority_label": maintenance.get_priority_display(),
            "status": maintenance.status_code,
            "status_label": maintenance.get_status_display(),
            "reported_at": maintenance.reported_at,
            "completed_at": maintenance.completed_at,
        }

    def get_current_guest(self, obj):
        return None

    def get_active_reservation(self, obj):
        reservation_details = list(
            obj.reservation_details.select_related(
                "reservation",
                "reservation__status",
                "reservation__client",
            )
            .filter(reservation__real_check_out__isnull=True)
            .exclude(reservation__status__code__in=INACTIVE_RESERVATION_STATUS_CODES)
            .order_by("reservation__expected_check_in", "reservation__id")
        )

        if not reservation_details:
            return None

        detail = next(
            (item for item in reservation_details if is_reservation_in_house(item.reservation)),
            reservation_details[0],
        )
        reservation = detail.reservation

        return {
            "id": reservation.id,
            "reservation_room_id": detail.id,
            "status": reservation.status_code,
            "status_label": reservation.status.name if reservation.status else None,
            "expected_check_in": reservation.expected_check_in,
            "expected_check_out": reservation.expected_check_out,
            "real_check_in": reservation.real_check_in,
            "real_check_out": reservation.real_check_out,
            "client": {
                "id": reservation.client_id,
                "full_name": reservation.client.full_name if reservation.client_id else None,
                "document_number": (
                    reservation.client.document_number if reservation.client_id else None
                ),
            },
        }
