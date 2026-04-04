from rest_framework import serializers

from apps.services.models import Service


class ServiceSerializer(serializers.ModelSerializer):
    hotel_name = serializers.CharField(source="hotel_settings.hotel_name", read_only=True)
    service_type_name = serializers.CharField(source="service_type.name", read_only=True)
    service_type_code = serializers.CharField(source="service_type.code", read_only=True)

    class Meta:
        model = Service
        fields = [
            "id",
            "hotel_settings",
            "hotel_name",
            "service_type",
            "service_type_name",
            "service_type_code",
            "name",
            "description",
            "base_price",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_base_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Base price cannot be negative.")
        return value