from rest_framework import serializers

from apps.packages.models import Package, PackageService
from apps.services.models import Service


class PackageServiceSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source="service.name", read_only=True)
    service_type_name = serializers.CharField(source="service.service_type.name", read_only=True)

    class Meta:
        model = PackageService
        fields = [
            "id",
            "package",
            "service",
            "service_name",
            "service_type_name",
            "quantity",
            "is_included",
            "created_at",
        ]
        read_only_fields = ("id", "created_at")

    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError("Quantity must be at least 1.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)

        package = attrs.get("package", getattr(self.instance, "package", None))
        service = attrs.get("service", getattr(self.instance, "service", None))

        if package and service and package.hotel_settings_id != service.hotel_settings_id:
            raise serializers.ValidationError(
                {"service": "The service must belong to the same hotel as the package."}
            )

        return attrs


class PackageSerializer(serializers.ModelSerializer):
    hotel_name = serializers.CharField(source="hotel_settings.hotel_name", read_only=True)
    room_type_name = serializers.CharField(source="room_type.name", read_only=True)
    room_type_code = serializers.CharField(source="room_type.code", read_only=True)
    package_services = PackageServiceSerializer(many=True, read_only=True)

    class Meta:
        model = Package
        fields = [
            "id",
            "hotel_settings",
            "hotel_name",
            "room_type",
            "room_type_name",
            "room_type_code",
            "name",
            "description",
            "base_price",
            "is_active",
            "start_date",
            "end_date",
            "package_services",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_base_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Base price cannot be negative.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)

        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))

        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError(
                {"end_date": "End date cannot be earlier than start date."}
            )

        return attrs