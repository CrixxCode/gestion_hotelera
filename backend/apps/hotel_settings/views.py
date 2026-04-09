from django.db import transaction
from rest_framework import status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from accounts.permissions import HasResourcePermission
from accounts.soft_delete import LogicalDeleteViewSetMixin
from apps.master_data.models import MasterData
from apps.rooms.models import Room

from .models import HotelFloor, HotelSettings, ReservationPolicy
from .serializers import HotelFloorSerializer, HotelSettingsSerializer, ReservationPolicySerializer


class HotelSettingsViewSet(LogicalDeleteViewSetMixin, viewsets.ModelViewSet):
    queryset = HotelSettings.objects.all().order_by("-id")
    serializer_class = HotelSettingsSerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    required_scopes = ["hotel_settings.read"]

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["hotel_settings.write"]
        return self.required_scopes

    def get_permissions(self):
        # Engancha scopes dinamicos antes de evaluar permisos
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        """
        Permite una sola configuracion principal del hotel.
        """
        if HotelSettings.objects.exists():
            return Response(
                {"detail": "Hotel settings already exists. Please update the existing record."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return super().create(request, *args, **kwargs)

    @action(detail=False, methods=["get"], url_path="current")
    def current(self, request):
        """
        Devuelve la configuracion actual del hotel.
        """
        settings_obj = HotelSettings.objects.first()

        if not settings_obj:
            return Response(None, status=status.HTTP_200_OK)

        serializer = self.get_serializer(settings_obj)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="clear")
    def clear(self, request):
        """
        Elimina toda la configuracion actual del hotel.
        Tambien borra los pisos relacionados por cascada.
        """
        settings_obj = HotelSettings.objects.first()

        if not settings_obj:
            return Response(
                {"detail": "No hotel settings found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        with transaction.atomic():
            floors = list(HotelFloor.objects.filter(hotel_settings=settings_obj))
            floor_ids = [f.id for f in floors]
            if floor_ids:
                rooms = list(Room.objects.filter(floor_id__in=floor_ids))
                for room in rooms:
                    self.perform_destroy(room)
                for floor in floors:
                    self.perform_destroy(floor)
            self.perform_destroy(settings_obj)

        return Response(
            {"detail": "Hotel settings deleted successfully."},
            status=status.HTTP_200_OK,
        )


class HotelFloorViewSet(LogicalDeleteViewSetMixin, viewsets.ModelViewSet):
    queryset = HotelFloor.objects.select_related("hotel_settings").all().order_by("floor_number")
    serializer_class = HotelFloorSerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]

    required_scopes = ["hotel_settings.read"]

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["hotel_settings.write"]
        return self.required_scopes

    def get_permissions(self):
        # Engancha scopes dinamicos antes de evaluar permisos
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()

    @staticmethod
    def _parse_bool(value):
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).strip().lower() in {"1", "true", "yes", "si", "on"}

    @staticmethod
    def _build_room_number(prefix, room_index):
        return f"{prefix}{str(room_index).zfill(2)}"

    def _create_missing_rooms(self, floor):
        """
        Crea solo las habitaciones faltantes segun room_count/prefix.
        """
        target_numbers = [
            self._build_room_number(floor.prefix, room_index)
            for room_index in range(1, floor.room_count + 1)
        ]

        existing_by_number = {
            number: floor_id
            for number, floor_id in Room.objects.filter(number__in=target_numbers).values_list("number", "floor_id")
        }

        conflicting_numbers = sorted(
            number
            for number, floor_id in existing_by_number.items()
            if floor_id != floor.id
        )
        if conflicting_numbers:
            raise ValidationError(
                {
                    "room_count": (
                        "No se pudieron autogenerar habitaciones porque estos numeros "
                        f"ya existen en otro piso: {', '.join(conflicting_numbers)}"
                    )
                }
            )

        missing_numbers = [number for number in target_numbers if number not in existing_by_number]
        if missing_numbers:
            default_status = MasterData.objects.filter(
                group=MasterData.Group.ROOM_STATUS,
                code="DISPONIBLE",
            ).first()

            if not default_status:
                raise ValidationError(
                    {
                        "room_count": (
                            "No se pudo autogenerar habitaciones porque falta el catalogo "
                            "ROOM_STATUS:DISPONIBLE."
                        )
                    }
                )

            Room.objects.bulk_create(
                [Room(number=number, floor=floor, status=default_status) for number in missing_numbers]
            )

        return missing_numbers

    def _delete_extra_rooms(self, floor):
        """
        Elimina habitaciones del piso con secuencia > room_count.
        Solo se usa cuando el usuario lo solicita.
        """
        prefix_len = len(floor.prefix)
        room_ids_to_delete = []

        for room in Room.objects.filter(floor=floor):
            if not room.number.startswith(floor.prefix):
                continue

            suffix = room.number[prefix_len:]
            if not suffix.isdigit():
                continue

            if int(suffix) > floor.room_count:
                room_ids_to_delete.append(room.id)

        if room_ids_to_delete:
            rooms = Room.objects.filter(id__in=room_ids_to_delete)
            for room in rooms:
                self.perform_destroy(room)

        return room_ids_to_delete

    @transaction.atomic
    def perform_create(self, serializer):
        floor = serializer.save()
        self._create_missing_rooms(floor)

    @transaction.atomic
    def perform_update(self, serializer):
        """
        Siempre crea faltantes.
        Solo borra extras si viene ?delete_extra_rooms=true en la URL.
        """
        delete_extra_rooms = self._parse_bool(
            self.request.query_params.get("delete_extra_rooms")
        )

        floor = serializer.save()
        self._create_missing_rooms(floor)

        if delete_extra_rooms:
            self._delete_extra_rooms(floor)

    def create(self, request, *args, **kwargs):
        """
        Valida que exista la configuracion del hotel antes de crear pisos.
        """
        hotel_settings_id = request.data.get("hotel_settings")

        if not hotel_settings_id:
            return Response(
                {"hotel_settings": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not HotelSettings.objects.filter(id=hotel_settings_id).exists():
            return Response(
                {"hotel_settings": "Hotel settings not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return super().create(request, *args, **kwargs)

    @action(detail=False, methods=["get"], url_path="by-settings/(?P<settings_id>[^/.]+)")
    def by_settings(self, request, settings_id=None):
        """
        Devuelve los pisos de una configuracion especifica.
        """
        floors = self.queryset.filter(hotel_settings_id=settings_id)
        serializer = self.get_serializer(floors, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class ReservationPolicyViewSet(LogicalDeleteViewSetMixin, viewsets.ModelViewSet):
    queryset = (
        ReservationPolicy.objects.select_related(
            "hotel_settings",
            "policy_type",
            "penalty_type",
        ).order_by("-id")
    )
    serializer_class = ReservationPolicySerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["reservation-policies.read"]

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "name",
        "description",
        "policy_type__name",
        "policy_type__code",
        "penalty_type__name",
        "penalty_type__code",
        "hotel_settings__hotel_name",
    ]
    ordering_fields = [
        "id",
        "name",
        "penalty_value",
        "hours_before_checkin",
        "created_at",
        "updated_at",
    ]
    ordering = ["-id"]

    @staticmethod
    def _parse_bool(value):
        if isinstance(value, bool):
            return value
        if value is None:
            return None

        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "si", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        return None

    def get_queryset(self):
        queryset = super().get_queryset()

        hotel_settings_id = (self.request.query_params.get("hotel_settings") or "").strip()
        if hotel_settings_id.isdigit():
            queryset = queryset.filter(hotel_settings_id=int(hotel_settings_id))

        is_active = self._parse_bool(self.request.query_params.get("is_active"))
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)

        return queryset

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["reservation-policies.write"]
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()
