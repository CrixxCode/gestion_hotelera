from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework import status

from .models import HotelSettings, HotelFloor
from .serializers import HotelSettingsSerializer, HotelFloorSerializer

from accounts.permissions import HasResourcePermission


class HotelSettingsViewSet(viewsets.ModelViewSet):
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
        # Engancha scopes dinámicos antes de evaluar permisos
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        """
        Permitir una sola configuración principal del hotel.
        """
        if HotelSettings.objects.exists():
            return Response(
                {"detail": "Hotel settings already exists. Please update the existing record."},
                status=status.HTTP_400_BAD_REQUEST
            )

        return super().create(request, *args, **kwargs)

    @action(detail=False, methods=["get"], url_path="current")
    def current(self, request):
        """
        Devuelve la configuración actual del hotel.
        Ideal para cargar el frontend en una sola llamada.
        """
        settings_obj = HotelSettings.objects.first()

        if not settings_obj:
            return Response(None, status=status.HTTP_200_OK)

        serializer = self.get_serializer(settings_obj)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="clear")
    def clear(self, request):
        """
        Elimina toda la configuración actual del hotel.
        También borra los pisos relacionados por cascada.
        """
        settings_obj = HotelSettings.objects.first()

        if not settings_obj:
            return Response(
                {"detail": "No hotel settings found."},
                status=status.HTTP_404_NOT_FOUND
            )

        settings_obj.delete()

        return Response(
            {"detail": "Hotel settings deleted successfully."},
            status=status.HTTP_200_OK
        )


class HotelFloorViewSet(viewsets.ModelViewSet):
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
        # Engancha scopes dinámicos antes de evaluar permisos
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        """
        Validar que exista la configuración del hotel antes de crear pisos.
        """
        hotel_settings_id = request.data.get("hotel_settings")

        if not hotel_settings_id:
            return Response(
                {"hotel_settings": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not HotelSettings.objects.filter(id=hotel_settings_id).exists():
            return Response(
                {"hotel_settings": "Hotel settings not found."},
                status=status.HTTP_400_BAD_REQUEST
            )

        return super().create(request, *args, **kwargs)

    @action(detail=False, methods=["get"], url_path="by-settings/(?P<settings_id>[^/.]+)")
    def by_settings(self, request, settings_id=None):
        """
        Devuelve los pisos de una configuración específica.
        """
        floors = self.queryset.filter(hotel_settings_id=settings_id)
        serializer = self.get_serializer(floors, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)