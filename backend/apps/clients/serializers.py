from rest_framework import serializers

from .models import Client


CLIENT_TYPE_INPUT_MAP = {
    "vip": Client.ClientType.VIP,
    "frequent": Client.ClientType.FREQUENT,
    "frecuente": Client.ClientType.FREQUENT,
    "regular": Client.ClientType.REGULAR,
}

STATUS_INPUT_MAP = {
    "active": Client.ClientStatus.ACTIVE,
    "activo": Client.ClientStatus.ACTIVE,
    "inactive": Client.ClientStatus.INACTIVE,
    "inactivo": Client.ClientStatus.INACTIVE,
    "current_guest": Client.ClientStatus.CURRENT_GUEST,
    "current guest": Client.ClientStatus.CURRENT_GUEST,
    "huesped_actual": Client.ClientStatus.CURRENT_GUEST,
    "huesped actual": Client.ClientStatus.CURRENT_GUEST,
    "huésped_actual": Client.ClientStatus.CURRENT_GUEST,
    "huésped actual": Client.ClientStatus.CURRENT_GUEST,
}


def normalize_client_type(value):
    if value is None:
        return value
    normalized = str(value).strip().lower()
    if normalized in CLIENT_TYPE_INPUT_MAP:
        return CLIENT_TYPE_INPUT_MAP[normalized]
    raise serializers.ValidationError(
        "Tipo de cliente invalido. Usa: VIP, FRECUENTE o REGULAR."
    )


def normalize_status(value):
    if value is None:
        return value
    normalized = str(value).strip().lower()
    if normalized in STATUS_INPUT_MAP:
        return STATUS_INPUT_MAP[normalized]
    raise serializers.ValidationError(
        "Estado invalido. Usa: ACTIVO, INACTIVO o HUESPED_ACTUAL."
    )


class ClientSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    stay_level = serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = "__all__"
        read_only_fields = (
            "id",
            "total_stay_nights",
            "last_stay",
            "created_at",
        )

    def get_full_name(self, obj):
        return obj.full_name

    def get_stay_level(self, obj):
        return obj.resolve_client_type_by_stay_nights()


class ClientCreateUpdateSerializer(serializers.ModelSerializer):
    # Override ChoiceField to accept text input and normalize manually.
    client_type = serializers.CharField(required=False)
    status = serializers.CharField(required=False)

    class Meta:
        model = Client
        fields = (
            "document_type",
            "document_number",
            "first_name",
            "last_name",
            "email",
            "phone",
            "country",
            "client_type",
            "status",
        )

    def validate_document_number(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Document number cannot be empty.")
        return value

    def validate_email(self, value):
        return value.lower().strip()

    def validate_client_type(self, value):
        return normalize_client_type(value)

    def validate_status(self, value):
        return normalize_status(value)
