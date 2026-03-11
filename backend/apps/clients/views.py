from rest_framework import status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Client
from .serializers import (
    ClientSerializer,
    ClientCreateUpdateSerializer,
    normalize_client_type,
    normalize_status,
)

from accounts.permissions import HasResourcePermission


class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all().order_by("-id")
    serializer_class = ClientSerializer
    permission_classes = [HasResourcePermission]

    # Scopes por defecto (lectura)
    required_scopes = ["clients.read"]

    # Serializers por acción (igual que tu UserViewSet)
    serializer_action_classes = {
        "create": ClientCreateUpdateSerializer,
        "update": ClientCreateUpdateSerializer,
        "partial_update": ClientCreateUpdateSerializer,

        # Si quieres permitir registro público de clientes para reservas online (opcional)
        "register": ClientCreateUpdateSerializer,
    }

    # Búsqueda y orden (útil para p-table en Angular)
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "document_type",
        "document_number",
        "first_name",
        "last_name",
        "email",
        "phone",
        "country",
        "client_type",
        "status",
    ]
    ordering_fields = ["id", "created_at", "first_name", "last_name", "email"]
    ordering = ["-id"]

    def get_serializer_class(self):
        return self.serializer_action_classes.get(self.action, self.serializer_class)

    def get_required_scopes(self):
        # Escritura para POST/PUT/PATCH/DELETE, lectura para el resto
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["clients.write"]
        return self.required_scopes

    def get_permissions(self):
        # Registro público (si decides activarlo). Si no lo quieres, bórralo.
        if self.action in ("register",):
            return [AllowAny()]

        # Engancha scopes dinámicos antes de evaluar permisos (igual que tu patrón)
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        """
        Override de create para usar ClientCreateUpdateSerializer (input)
        y devolver ClientSerializer (output) para consistencia.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        client = serializer.save()

        response_data = ClientSerializer(client, context=self.get_serializer_context()).data
        return Response(response_data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="register")
    def register(self, request):
        """
        Endpoint opcional para registrar clientes sin login.
        Útil si más adelante tendrás reservas desde web pública.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        client = serializer.save()

        data = ClientSerializer(client, context=self.get_serializer_context()).data
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch"], url_path="set-status")
    def set_status(self, request, pk=None):
        """
        Cambiar estado del cliente desde la API (ACTIVE/INACTIVE/CURRENT_GUEST).
        Esto NO depende de reservas por ahora.
        """
        client = self.get_object()
        try:
            new_status = normalize_status(request.data.get("status"))
        except ValidationError as exc:
            return Response({"status": exc.detail}, status=status.HTTP_400_BAD_REQUEST)

        client.status = new_status
        client.save(update_fields=["status"])

        return Response(ClientSerializer(client, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["patch"], url_path="set-client-type")
    def set_client_type(self, request, pk=None):
        """
        Cambiar tipo de cliente (VIP/FREQUENT/REGULAR).
        Útil si quieres gestionarlo manualmente por ahora.
        """
        client = self.get_object()
        try:
            new_type = normalize_client_type(request.data.get("client_type"))
        except ValidationError as exc:
            return Response({"client_type": exc.detail}, status=status.HTTP_400_BAD_REQUEST)

        client.client_type = new_type
        client.save(update_fields=["client_type"])

        return Response(ClientSerializer(client, context=self.get_serializer_context()).data)
