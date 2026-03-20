import unicodedata

from rest_framework import serializers

from apps.master_data.models import MasterData
from apps.master_data.serializers import MasterDataCodeField
from .models import Client


def _normalize_token(value):
    if value is None:
        return ""
    normalized = str(value).strip().lower()
    normalized = unicodedata.normalize("NFD", normalized)
    normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return normalized


CLIENT_TYPE_INPUT_MAP = {
    "vip": "VIP",
    "frequent": "FRECUENTE",
    "frecuente": "FRECUENTE",
    "regular": "REGULAR",
}

STATUS_INPUT_MAP = {
    "active": "ACTIVO",
    "activo": "ACTIVO",
    "inactive": "INACTIVO",
    "inactivo": "INACTIVO",
    "current_guest": "HUESPED_ACTUAL",
    "current guest": "HUESPED_ACTUAL",
    "huesped_actual": "HUESPED_ACTUAL",
    "huesped actual": "HUESPED_ACTUAL",
    "huespedactual": "HUESPED_ACTUAL",
}

DOCUMENT_TYPE_INPUT_MAP = {
    "cc": "CC",
    "cedula": "CC",
    "ce": "CE",
    "dni": "DNI",
    "passport": "PASAPORTE",
    "pasaporte": "PASAPORTE",
}


def normalize_client_type(value):
    if value is None:
        return value
    if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
        return value

    normalized = _normalize_token(value)
    if normalized in CLIENT_TYPE_INPUT_MAP:
        return CLIENT_TYPE_INPUT_MAP[normalized]

    raise serializers.ValidationError(
        "Tipo de cliente invalido. Usa: VIP, FRECUENTE o REGULAR."
    )


def normalize_status(value):
    if value is None:
        return value
    if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
        return value

    normalized = _normalize_token(value)
    if normalized in STATUS_INPUT_MAP:
        return STATUS_INPUT_MAP[normalized]

    raise serializers.ValidationError(
        "Estado invalido. Usa: ACTIVO, INACTIVO o HUESPED_ACTUAL."
    )


def normalize_document_type(value):
    if value is None:
        return value
    if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
        return value

    normalized = _normalize_token(value)
    if normalized in DOCUMENT_TYPE_INPUT_MAP:
        return DOCUMENT_TYPE_INPUT_MAP[normalized]

    return str(value).strip().upper()


def get_master_data(group, code):
    return MasterData.objects.filter(group=group, code=code).first()


class ClientSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    stay_level = serializers.SerializerMethodField()

    document_type = serializers.SerializerMethodField()
    document_type_label = serializers.CharField(source="document_type.name", read_only=True)

    client_type = serializers.SerializerMethodField()
    client_type_label = serializers.CharField(source="client_type.name", read_only=True)

    status = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="status.name", read_only=True)

    class Meta:
        model = Client
        fields = (
            "id",
            "document_type",
            "document_type_label",
            "document_number",
            "first_name",
            "last_name",
            "email",
            "phone",
            "country",
            "client_type",
            "client_type_label",
            "total_stay_nights",
            "last_stay",
            "status",
            "status_label",
            "created_at",
            "full_name",
            "stay_level",
        )
        read_only_fields = (
            "id",
            "total_stay_nights",
            "last_stay",
            "created_at",
            "full_name",
            "stay_level",
        )

    def get_full_name(self, obj):
        return obj.full_name

    def get_stay_level(self, obj):
        return obj.resolve_client_type_code_by_stay_nights()

    def get_document_type(self, obj):
        return obj.document_type_code

    def get_client_type(self, obj):
        return obj.client_type_code

    def get_status(self, obj):
        return obj.status_code


class ClientCreateUpdateSerializer(serializers.ModelSerializer):
    document_type = MasterDataCodeField(group=MasterData.Group.DOCUMENT_TYPE)
    client_type = MasterDataCodeField(
        group=MasterData.Group.CLIENT_TYPE,
        required=False,
        allow_null=True,
    )
    status = MasterDataCodeField(
        group=MasterData.Group.CLIENT_STATUS,
        required=False,
        allow_null=True,
    )

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

    def to_internal_value(self, data):
        mutable_data = data.copy() if hasattr(data, "copy") else dict(data)

        if "document_type" in mutable_data:
            mutable_data["document_type"] = normalize_document_type(mutable_data.get("document_type"))
        if "client_type" in mutable_data:
            mutable_data["client_type"] = normalize_client_type(mutable_data.get("client_type"))
        if "status" in mutable_data:
            mutable_data["status"] = normalize_status(mutable_data.get("status"))

        return super().to_internal_value(mutable_data)

    def validate_document_number(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Document number cannot be empty.")
        return value

    def validate_email(self, value):
        return value.lower().strip()

    def create(self, validated_data):
        if not validated_data.get("client_type"):
            validated_data["client_type"] = get_master_data(MasterData.Group.CLIENT_TYPE, "REGULAR")

        if not validated_data.get("status"):
            validated_data["status"] = get_master_data(MasterData.Group.CLIENT_STATUS, "ACTIVO")

        if not validated_data.get("client_type") or not validated_data.get("status"):
            raise serializers.ValidationError(
                "No existen los catalogos base de cliente (CLIENT_TYPE o CLIENT_STATUS)."
            )

        return super().create(validated_data)
