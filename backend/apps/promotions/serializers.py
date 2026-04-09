from rest_framework import serializers

from apps.promotions.models import Promotion


class PromotionSerializer(serializers.ModelSerializer):
    hotel_name = serializers.CharField(source="hotel_settings.hotel_name", read_only=True)
    discount_type_name = serializers.CharField(source="discount_type.name", read_only=True)
    discount_type_code = serializers.CharField(source="discount_type.code", read_only=True)
    service_name = serializers.CharField(source="service.name", read_only=True)
    package_name = serializers.CharField(source="package.name", read_only=True)

    class Meta:
        model = Promotion
        fields = [
            "id",
            "hotel_settings",
            "hotel_name",
            "discount_type",
            "discount_type_name",
            "discount_type_code",
            "service",
            "service_name",
            "package",
            "package_name",
            "name",
            "code",
            "description",
            "discount_value",
            "start_date",
            "end_date",
            "is_active",
            "is_public",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_discount_value(self, value):
        if value <= 0:
            raise serializers.ValidationError("Discount value must be greater than 0.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)

        hotel_settings = attrs.get("hotel_settings", getattr(self.instance, "hotel_settings", None))
        discount_type = attrs.get("discount_type", getattr(self.instance, "discount_type", None))
        service = attrs.get("service", getattr(self.instance, "service", None))
        package = attrs.get("package", getattr(self.instance, "package", None))
        discount_value = attrs.get("discount_value", getattr(self.instance, "discount_value", None))
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))

        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError(
                {"end_date": "End date cannot be earlier than start date."}
            )

        if service and package:
            raise serializers.ValidationError(
                {"package": "A promotion should reference either a service or a package, not both."}
            )

        if discount_type:
            discount_code = str(discount_type.code or "").strip().upper()
            if discount_code == "PERCENTAGE" and discount_value is not None and discount_value > 100:
                raise serializers.ValidationError(
                    {"discount_value": "Percentage discount cannot be greater than 100."}
                )

        if hotel_settings and service and hotel_settings.id != service.hotel_settings_id:
            raise serializers.ValidationError(
                {"service": "The service must belong to the same hotel as the promotion."}
            )

        if hotel_settings and package and hotel_settings.id != package.hotel_settings_id:
            raise serializers.ValidationError(
                {"package": "The package must belong to the same hotel as the promotion."}
            )

        return attrs