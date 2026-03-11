from rest_framework import serializers
from .models import HotelSettings, HotelFloor


class HotelFloorSerializer(serializers.ModelSerializer):
    # Rango visual calculado para el frontend
    range_display = serializers.SerializerMethodField()

    class Meta:
        model = HotelFloor
        fields = (
            "id",
            "hotel_settings",
            "floor_number",
            "name",
            "prefix",
            "room_count",
            "range_display",
        )

    def get_range_display(self, obj):
        """
        Construye un rango visual como:
        101 - 106
        201 - 206
        """
        if obj.room_count <= 0:
            return ""

        start = f"{obj.prefix}01"
        end = f"{obj.prefix}{str(obj.room_count).zfill(2)}"
        return f"{start} - {end}"

    def validate_room_count(self, value):
        """
        Validar que el piso tenga al menos una habitación.
        """
        if value < 1:
            raise serializers.ValidationError("Room count must be greater than 0.")
        return value

    def validate_floor_number(self, value):
        """
        Validar que el número de piso sea válido.
        """
        if value < 1:
            raise serializers.ValidationError("Floor number must be greater than 0.")
        return value


class HotelSettingsSerializer(serializers.ModelSerializer):
    # Lista anidada de pisos
    floors = HotelFloorSerializer(many=True, read_only=True)

    # Estadísticas calculadas para mostrar en tarjetas del frontend
    total_floors = serializers.SerializerMethodField()
    total_rooms = serializers.SerializerMethodField()
    average_rooms_per_floor = serializers.SerializerMethodField()

    class Meta:
        model = HotelSettings
        fields = (
            "id",
            "hotel_name",
            "legal_name",
            "slogan",
            "description",
            "logo",
            "stars",
            "facebook",
            "instagram",
            "twitter_x",
            "address",
            "city",
            "state",
            "country",
            "postal_code",
            "primary_phone",
            "secondary_phone",
            "general_email",
            "reservations_email",
            "website",
            "check_in_time",
            "check_out_time",
            "max_guests_per_room",
            "currency",
            "tax_rate",
            "system_language",
            "timezone",
            "created_at",
            "updated_at",
            "floors",
            "total_floors",
            "total_rooms",
            "average_rooms_per_floor",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "total_floors",
            "total_rooms",
            "average_rooms_per_floor",
        )

    def get_total_floors(self, obj):
        """
        Devuelve la cantidad total de pisos configurados.
        """
        return obj.floors.count()

    def get_total_rooms(self, obj):
        """
        Devuelve el total de habitaciones sumando todos los pisos.
        """
        return sum(floor.room_count for floor in obj.floors.all())

    def get_average_rooms_per_floor(self, obj):
        """
        Devuelve el promedio de habitaciones por piso.
        """
        floors_count = obj.floors.count()
        if floors_count == 0:
            return 0

        total_rooms = sum(floor.room_count for floor in obj.floors.all())
        return round(total_rooms / floors_count, 1)

    def validate_stars(self, value):
        """
        Validar que las estrellas estén entre 1 y 5.
        """
        if value < 1 or value > 5:
            raise serializers.ValidationError("Stars must be between 1 and 5.")
        return value

    def validate_tax_rate(self, value):
        """
        Validar que el impuesto esté entre 0 y 100.
        """
        if value < 0 or value > 100:
            raise serializers.ValidationError("Tax rate must be between 0 and 100.")
        return value

    def validate_max_guests_per_room(self, value):
        """
        Validar que el máximo de huéspedes sea al menos 1.
        """
        if value < 1:
            raise serializers.ValidationError("Max guests per room must be greater than 0.")
        return value

    def validate(self, attrs):
        """
        Validaciones cruzadas del modelo.
        """
        check_in_time = attrs.get("check_in_time")
        check_out_time = attrs.get("check_out_time")

        if check_in_time and check_out_time and check_in_time == check_out_time:
            raise serializers.ValidationError({
                "check_out_time": "Check-out time must be different from check-in time."
            })

        return attrs