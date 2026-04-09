import logging

from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.translation import gettext_lazy as _
from django.utils.encoding import force_str, smart_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.urls import reverse
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from rest_framework import serializers

from .models import Role, Resource

User = get_user_model()
logger = logging.getLogger(__name__)


# -----------------------------
# RBAC
# -----------------------------

class ResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resource
        fields = [
            "id",
            "key",
            "name",
            "description",
            "link",
            "link_backend",
            "icon",
            "order",
            "is_menu",
            "parent",
        ]


class RoleSerializer(serializers.ModelSerializer):
    resources = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = ["id", "name", "slug", "description", "resources"]

    def get_resources(self, obj):
        qs = (
            Resource.objects.filter(
                is_active=True,
                roleresource__role=obj,
                roleresource__is_active=True,
            )
            .distinct()
            .order_by("order", "name", "key")
        )
        return ResourceSerializer(qs, many=True).data


class UserMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email", "is_active", "avatar"]

# -----------------------------
# Usuarios
# -----------------------------

class UserSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    resource_keys = serializers.SerializerMethodField()
    menu = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "avatar",
            "first_name",
            "last_name",
            "username",
            "email",
            "is_active",
            "is_staff",
            "roles",
            "resource_keys",
            "menu",
        ]

    def get_resource_keys(self, obj):
        return sorted(list(obj.resource_keys()))

    def get_roles(self, obj):
        qs = (
            Role.objects.filter(
                is_active=True,
                userrole__user=obj,
                userrole__is_active=True,
            )
            .distinct()
            .order_by("name")
        )
        return RoleSerializer(qs, many=True).data

    def get_menu(self, obj):
        """
        Devuelve el menú dinámico basado en los Resources del usuario.
        Estructura:
        [
          {id, label, icon, route, children:[...]}
        ]
        """

        # 1) Recursos asignados al usuario (solo los que se muestran en menú)
        assigned_qs = (
            Resource.objects
            .filter(
                is_active=True,
                is_menu=True,
                roleresource__is_active=True,
                roleresource__role__is_active=True,
                roleresource__role__userrole__user=obj,
                roleresource__role__userrole__is_active=True,
            )
            .distinct()
            .select_related("parent")
        )

        assigned = list(assigned_qs)
        if not assigned:
            return []

        ids = set(r.id for r in assigned)

        # 2) Incluir padres para no perder grupos del menú
        parent_ids = set(r.parent_id for r in assigned if r.parent_id)

        # Traer padres faltantes recursivamente
        while True:
            missing = [pid for pid in parent_ids if pid and pid not in ids]
            if not missing:
                break
            parents = list(
                Resource.objects.filter(id__in=missing, is_menu=True, is_active=True)
                .select_related("parent")
            )
            if not parents:
                break
            for p in parents:
                ids.add(p.id)
                if p.parent_id:
                    parent_ids.add(p.parent_id)

        # 3) Traer todos los recursos del menú (asignados + padres)
        resources = list(
            Resource.objects
            .filter(id__in=ids, is_menu=True, is_active=True)
            .select_related("parent")
            .order_by("order", "name")
        )

        by_id = {r.id: r for r in resources}
        children_map = {}
        for r in resources:
            children_map.setdefault(r.parent_id, []).append(r)

        def node(r: Resource):
            children = children_map.get(r.id, [])
            return {
                "id": str(r.id),
                "label": r.name,
                "icon": r.icon or "",
                "route": r.link or "",
                "children": [node(ch) for ch in children],
            }

        # Top-level = parent null o parent fuera del set
        top = []
        for r in resources:
            if r.parent_id is None or r.parent_id not in by_id:
                top.append(r)

        return [node(r) for r in top]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(required=True, max_length=50)
    last_name = serializers.CharField(required=True, max_length=50)
    email = serializers.EmailField(required=True)
    is_active = serializers.BooleanField(default=True, required=False)
    status = serializers.CharField(required=False, write_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "avatar",
            "first_name",
            "last_name",
            "username",
            "email",
            "password",
            "is_active",
            "status",
        ]

    def validate_username(self, value):
        username = (value or "").strip()
        if not username:
            raise serializers.ValidationError("El nombre de usuario no puede estar vacío.")
        if User.objects.filter(username__iexact=username).exists():
            raise serializers.ValidationError("Ya existe un usuario con este nombre de usuario.")
        return username

    def validate_email(self, value):
        email = (value or "").strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("Ya existe un usuario con este correo.")
        return email

    def validate_password(self, value):
        password_validation.validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        status = validated_data.pop("status", "ACTIVE")

        is_active = validated_data.pop("is_active", True)
        if isinstance(status, str):
            is_active = status.upper() == "ACTIVE"

        validated_data["email"] = validated_data["email"].strip().lower()
        validated_data["username"] = validated_data["username"].strip()
        validated_data["first_name"] = validated_data.get("first_name", "").strip()
        validated_data["last_name"] = validated_data.get("last_name", "").strip()
        validated_data["is_active"] = is_active

        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        user = self.context["request"].user
        if not user.check_password(attrs["old_password"]):
            raise serializers.ValidationError({"old_password": _("Contraseña actual incorrecta")})
        password_validation.validate_password(attrs["new_password"], user)
        return attrs

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save()
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return (value or "").strip().lower()

    def save(self):
        request = self.context.get("request")
        email = self.validated_data["email"]

        qs = User.objects.filter(email__iexact=email, is_active=True)
        if not qs.exists():
            return {"found": False}

        user = qs.first()
        uid = urlsafe_base64_encode(smart_bytes(user.pk))
        token = PasswordResetTokenGenerator().make_token(user)

        base_url = self.context.get("base_url")
        if base_url:
            reset_url = f"{base_url}?uid={uid}&token={token}"
        else:
            path = reverse("password_reset_confirm")
            if request is not None:
                reset_url = request.build_absolute_uri(f"{path}?uid={uid}&token={token}")
            else:
                reset_url = f"http://localhost:8000{path}?uid={uid}&token={token}"

        brand = {
            "app_name": getattr(settings, "APP_DISPLAY_NAME", "Gestión Hotelera"),
            "support_email": getattr(settings, "SUPPORT_EMAIL", "soporte@hotel.local"),
            "primary_color": getattr(settings, "BRAND_PRIMARY_COLOR", "#0ea5e9"),
            "logo_url": getattr(settings, "BRAND_LOGO_URL", None),
        }

        subject = "Recuperación de contraseña"
        text_body = (
            f"Hola {user.username},\n\n"
            f"Recibimos una solicitud para restablecer tu contraseña en {brand['app_name']}.\n"
            f"Para continuar, abre el siguiente enlace:\n{reset_url}\n\n"
            "Si no fuiste tú, puedes ignorar este mensaje.\n"
            f"— Equipo {brand['app_name']}\n"
        )
        html_body = render_to_string(
            "email/password_reset.html",
            {"user": user, "reset_url": reset_url, **brand},
        )

        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@hotel.local")
        msg = EmailMultiAlternatives(subject, text_body, from_email, [email])
        msg.attach_alternative(html_body, "text/html")
        try:
            msg.send(fail_silently=False)
        except Exception:
            logger.exception(
                "Password reset email could not be sent for user_id=%s email=%s",
                user.pk,
                email,
            )
            # Avoid exposing internals and keep API response stable.
            return {"found": True, "sent": False}

        return {"found": True, "sent": True}


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=8, write_only=True)

    def validate(self, attrs):
        uid = attrs.get("uid")
        token = attrs.get("token")
        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id, is_active=True)
        except Exception:
            raise serializers.ValidationError({"uid": _("Token inválido o usuario no encontrado.")})

        if not PasswordResetTokenGenerator().check_token(user, token):
            raise serializers.ValidationError({"token": _("Token inválido o expirado.")})

        password_validation.validate_password(attrs["new_password"], user)
        attrs["user"] = user
        return attrs

    def save(self, **kwargs):
        user = self.validated_data["user"]
        user.set_password(self.validated_data["new_password"])
        user.save()
        return user
