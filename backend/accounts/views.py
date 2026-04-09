# accounts/views.py

from django.contrib.auth import authenticate, login, logout, get_user_model
from django.conf import settings
from django.views.decorators.csrf import ensure_csrf_cookie
import logging
logger = logging.getLogger(__name__)
from django.utils.decorators import method_decorator

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle
from accounts.permissions import HasResourcePermission
from accounts.soft_delete import LogicalDeleteViewSetMixin

from .models import Role, Resource, UserRole, RoleResource
from .serializers import (
    RegisterSerializer, UserSerializer, RoleSerializer, ResourceSerializer,
    UserMiniSerializer, PasswordChangeSerializer, PasswordResetRequestSerializer, PasswordResetConfirmSerializer
)
from django.db import models

User = get_user_model()


# -----------------------------
# Salud / CSRF
# -----------------------------

class HealthCheckView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok"}, status=status.HTTP_200_OK)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfInitView(APIView):
    """
    GET -> setea cookie 'csrftoken' para que el front pueda enviar X-CSRFToken.
    Útil cuando el frontend es SPA en otro origen.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"detail": "CSRF cookie set"}, status=status.HTTP_200_OK)


# -----------------------------
# Sesión por cookies (login/logout/me)
# -----------------------------

class SessionLoginView(APIView):
    """
    POST {username, password, remember_me?}
    Crea sesión (cookie 'sessionid'). Requiere X-CSRFToken.
    - remember_me=true => sesión ~14 días
    - remember_me=false => expira al cerrar el navegador
    """
    permission_classes = [AllowAny]
    throttle_scope = "auth_login"
    throttle_classes = [ScopedRateThrottle]

    def post(self, request):
        username = (request.data.get("username") or "").strip()
        password = request.data.get("password") or ""
        remember = bool(request.data.get("remember_me"))

        if not username or not password:
            return Response({"detail": "Faltan credenciales."}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(request, username=username, password=password)
        if not user:
            return Response({"detail": "Credenciales inválidas."}, status=status.HTTP_401_UNAUTHORIZED)
        if not user.is_active:
            return Response({"detail": "Usuario inactivo."}, status=status.HTTP_403_FORBIDDEN)

        # Django rota la sesión en login (mitiga session fixation)
        login(request, user)

        # Caducidad
        request.session.set_expiry(60 * 60 * 24 * 14 if remember else 0)

        return Response({
            "detail": "Sesión iniciada",
            "remember_me": remember,
            "user": UserSerializer(user).data
        }, status=status.HTTP_200_OK)


class SessionLogoutView(APIView):
    """
    POST sin cuerpo -> cierra sesión (elimina cookie 'sessionid').
    Requiere X-CSRFToken porque modifica estado.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response({"detail": "Sesión cerrada"}, status=status.HTTP_200_OK)


class MeSessionView(APIView):
    """
    GET -> devuelve el usuario autenticado por sesión.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data, status=status.HTTP_200_OK)


class PasswordChangeView(APIView):
    """
    POST {old_password, new_password}
    Cambia la contraseña del usuario autenticado (por sesión).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = PasswordChangeSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response({"detail": "Contraseña cambiada"}, status=status.HTTP_200_OK)


# -----------------------------
# Recuperación de contraseña
# -----------------------------

class PasswordResetRequestView(APIView):
    """
    POST {email[, base_url]}
    Envía enlace de recuperación. Devuelve sent=True/False.
    (Throttle específico para evitar abuso.)
    """
    permission_classes = [AllowAny]
    throttle_scope = "password_reset"
    throttle_classes = [ScopedRateThrottle]

    def post(self, request):
        ser = PasswordResetRequestSerializer(
            data=request.data,
            context={"request": request, "base_url": request.data.get("base_url")}
        )
        ser.is_valid(raise_exception=True)
        result = ser.save()
        return Response(
            {
                "detail": (
                    "Si existe una cuenta asociada al correo, se enviara el enlace de recuperacion."
                ),
                "sent": bool((result or {}).get("sent", True)),
            },
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(APIView):
    """
    POST {uid, token, new_password}
    Confirma el restablecimiento y establece la nueva contraseña.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        ser = PasswordResetConfirmSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response({"detail": "Contraseña restablecida correctamente."}, status=status.HTTP_200_OK)


# -----------------------------
# RBAC + CRUD: Users / Roles / Resources
# -----------------------------

class UserViewSet(LogicalDeleteViewSetMixin, viewsets.ModelViewSet):
    queryset = User.objects.all().order_by("date_joined")
    serializer_class = UserSerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["users.read"]  # lectura por defecto
    serializer_action_classes = {
        "create": RegisterSerializer,
        "register": RegisterSerializer,
    }
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["roles__slug", "is_active", "is_staff"]
    search_fields = ["username", "email", "first_name", "last_name"]
    ordering_fields = ["date_joined", "username", "email", "first_name", "last_name"]
    ordering = ["-date_joined"]

    def get_serializer_class(self):
        return self.serializer_action_classes.get(self.action, self.serializer_class)

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["users.write"]
        return self.required_scopes

    def get_permissions(self):
        allow_public_register = getattr(settings, "ALLOW_PUBLIC_USER_REGISTRATION", False)
        if self.action in ("create", "register") and allow_public_register:
            return [AllowAny()]
        # engancha scopes dinámicos antes de evaluar permisos
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        """Override de create para usar RegisterSerializer y devolver UserSerializer"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        # Devolver usando UserSerializer para consistencia
        response_data = UserSerializer(user, context=self.get_serializer_context()).data
        return Response(response_data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="register")
    def register(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        data = UserSerializer(user, context=self.get_serializer_context()).data
        return Response(data, status=status.HTTP_201_CREATED)


class RoleViewSet(LogicalDeleteViewSetMixin, viewsets.ModelViewSet):
    queryset = Role.objects.all().order_by("name")
    serializer_class = RoleSerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["roles.read"]

    def get_required_scopes(self):
        # CRUD y acciones de asignación requieren roles.write
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["roles.write"]
        if getattr(self, "action", "") in ("assign_users", "remove_users", "assign_resources"):
            return ["roles.write"]
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()

    # -------------------------
    # Usuarios por rol
    # -------------------------

    @action(detail=True, methods=["get"], url_path="users")
    def users(self, request, pk=None):
        """
        GET /api/roles/<id>/users/
        Devuelve los usuarios asignados a ese rol.
        """
        role = self.get_object()
        qs = (
            User.objects.filter(
                userrole__role=role,
                userrole__is_active=True,
                is_active=True,
            )
            .distinct()
            .order_by("username")
        )
        return Response(UserMiniSerializer(qs, many=True).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="assign-users")
    def assign_users(self, request, pk=None):
        """
        POST /api/roles/<id>/assign-users/
        Body: { "user_ids": ["uuid1","uuid2", ...] }
        Asigna el rol a usuarios.
        """
        role = self.get_object()
        ids = request.data.get("user_ids", [])
        if not isinstance(ids, list):
            return Response({"detail": "user_ids debe ser una lista."}, status=status.HTTP_400_BAD_REQUEST)

        users = User.objects.filter(id__in=ids, is_active=True)
        for user in users:
            rel, created = UserRole.objects.get_or_create(
                user=user,
                role=role,
                defaults={"is_active": True},
            )
            if not created and not rel.is_active:
                rel.is_active = True
                rel.save(update_fields=["is_active"])

        return Response(
            {"assigned": [str(u.id) for u in users]},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["post"], url_path="remove-users")
    def remove_users(self, request, pk=None):
        """
        POST /api/roles/<id>/remove-users/
        Body: { "user_ids": ["uuid1","uuid2", ...] }
        Remueve el rol de usuarios.
        """
        role = self.get_object()
        ids = request.data.get("user_ids", [])
        if not isinstance(ids, list):
            return Response({"detail": "user_ids debe ser una lista."}, status=status.HTTP_400_BAD_REQUEST)

        users = User.objects.filter(id__in=ids, is_active=True)
        UserRole.objects.filter(role=role, user__in=users, is_active=True).update(is_active=False)

        return Response(
            {"removed": [str(u.id) for u in users]},
            status=status.HTTP_200_OK
        )

    # -------------------------
    # Catálogo de usuarios (para seleccionar en UI)
    # -------------------------

    @action(detail=False, methods=["get"], url_path="users-catalog")
    def users_catalog(self, request):
        """
        GET /api/roles/users-catalog/?q=
        Devuelve usuarios para el selector de asignación.
        """
        q = (request.query_params.get("q") or "").strip()

        qs = User.objects.filter(is_active=True).order_by("username")
        if q:
            qs = qs.filter(
                models.Q(username__icontains=q)
                | models.Q(email__icontains=q)
                | models.Q(first_name__icontains=q)
                | models.Q(last_name__icontains=q)
            )

        # límite simple para UI
        qs = qs[:200]
        return Response(UserMiniSerializer(qs, many=True).data, status=status.HTTP_200_OK)
    
    # -------------------------
    # Recursos
    # -------------------------
    
    @action(detail=True, methods=["get"], url_path="resources")
    def resources(self, request, pk=None):
        """
        GET /api/roles/<id>/resources/
        Devuelve los recursos asignados a este rol.
        """
        role = self.get_object()
        qs = (
            Resource.objects.filter(
                roleresource__role=role,
                roleresource__is_active=True,
                is_active=True,
            )
            .distinct()
            .order_by("order", "name", "key")
        )
        return Response(ResourceSerializer(qs, many=True).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="assign-resources")
    def assign_resources(self, request, pk=None):
        """
        POST /api/roles/<id>/assign-resources/
        Body: { "resource_ids": ["uuid1", ...] }
        """
        role = self.get_object()
        ids = request.data.get("resource_ids", [])
        if not isinstance(ids, list):
            return Response({"detail": "resource_ids debe ser una lista."}, status=status.HTTP_400_BAD_REQUEST)

        resources = Resource.objects.filter(id__in=ids, is_active=True)
        for resource in resources:
            rel, created = RoleResource.objects.get_or_create(
                role=role,
                resource=resource,
                defaults={"is_active": True},
            )
            if not created and not rel.is_active:
                rel.is_active = True
                rel.save(update_fields=["is_active"])

        return Response({"assigned": [str(r.id) for r in resources]}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="remove-resources")
    def remove_resources(self, request, pk=None):
        """
        POST /api/roles/<id>/remove-resources/
        Body: { "resource_ids": ["uuid1", ...] }
        """
        role = self.get_object()
        ids = request.data.get("resource_ids", [])
        if not isinstance(ids, list):
            return Response({"detail": "resource_ids debe ser una lista."}, status=status.HTTP_400_BAD_REQUEST)

        resources = Resource.objects.filter(id__in=ids, is_active=True)
        RoleResource.objects.filter(role=role, resource__in=resources, is_active=True).update(is_active=False)

        return Response({"removed": [str(r.id) for r in resources]}, status=status.HTTP_200_OK)
    

class ResourceViewSet(LogicalDeleteViewSetMixin, viewsets.ModelViewSet):
    queryset = Resource.objects.all()
    serializer_class = ResourceSerializer
    permission_classes = [HasResourcePermission]
    required_scopes = ["resources.read"]
    pagination_class = None

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["resources.write"]
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset().order_by("order", "name", "key")
        q = (self.request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                models.Q(key__icontains=q) |
                models.Q(name__icontains=q) |
                models.Q(description__icontains=q)
            )
        return qs

class ProfileUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Devuelve el perfil actual"""
        return Response(UserSerializer(request.user).data)

    def put(self, request):
        """Actualiza el perfil"""
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    

