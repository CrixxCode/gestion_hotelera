from django.core.exceptions import ImproperlyConfigured


class TenantScopeMixin:
    tenant_filter = "hotel_settings"
    allow_superuser_global = True

    def get_tenant_filter(self):
        if not getattr(self, "tenant_filter", None):
            raise ImproperlyConfigured(
                f"{self.__class__.__name__} debe definir tenant_filter."
            )
        return self.tenant_filter

    def get_tenant_id(self):
        user = getattr(self.request, "user", None)
        return getattr(user, "hotel_settings_id", None)

    def is_global_admin(self):
        user = getattr(self.request, "user", None)
        return bool(
            user
            and user.is_authenticated
            and self.allow_superuser_global
            and user.is_superuser
        )

    def get_base_queryset(self):
        queryset = getattr(self, "queryset", None)
        if queryset is None:
            raise ImproperlyConfigured(
                f"{self.__class__.__name__} debe definir queryset o sobrescribir get_base_queryset()."
            )
        return queryset.all()

    def get_queryset(self):
        qs = self.get_base_queryset()
        user = getattr(self.request, "user", None)

        if not user or not user.is_authenticated:
            return qs.none()

        if self.is_global_admin():
            return qs

        tenant_id = self.get_tenant_id()
        if tenant_id is None:
            return qs.none()

        return qs.filter(**{f"{self.get_tenant_filter()}_id": tenant_id})
    
from rest_framework import serializers


class TenantSerializerMixin:
    tenant_field_name = "hotel_settings"

    def get_actor(self):
        request = self.context.get("request")
        return getattr(request, "user", None)

    def is_global_admin(self):
        actor = self.get_actor()
        return bool(actor and actor.is_authenticated and actor.is_superuser)

    def get_actor_tenant(self):
        actor = self.get_actor()
        return getattr(actor, "hotel_settings", None)

    def resolve_target_tenant(self, attrs):
        incoming_tenant = None
        if self.tenant_field_name:
            incoming_tenant = attrs.get(
                self.tenant_field_name,
                getattr(self.instance, self.tenant_field_name, None) if self.instance else None,
            )

        actor = self.get_actor()

        if actor and actor.is_authenticated:
            if self.is_global_admin():
                return incoming_tenant

            actor_tenant = self.get_actor_tenant()
            if actor_tenant is None:
                raise serializers.ValidationError({
                    self.tenant_field_name: "El usuario autenticado no tiene un hotel asignado."
                })
            return actor_tenant

        return incoming_tenant

    def require_target_tenant(self, attrs):
        tenant = self.resolve_target_tenant(attrs)
        if tenant is None:
            raise serializers.ValidationError({
                self.tenant_field_name: "Este registro debe pertenecer a un hotel."
            })
        return tenant

    def assign_target_tenant(self, validated_data):
        tenant = self.require_target_tenant(validated_data)
        if self.tenant_field_name:
            validated_data[self.tenant_field_name] = tenant
        return tenant

    def extract_tenant_id_from_obj(self, obj, tenant_path):
        current = obj
        for part in tenant_path.split("__"):
            current = getattr(current, part)
            if current is None:
                return None

        return getattr(current, "id", current)

    def validate_same_tenant(self, obj, tenant_path, field_name, attrs):
        tenant = self.require_target_tenant(attrs)
        obj_tenant_id = self.extract_tenant_id_from_obj(obj, tenant_path)

        if obj_tenant_id != tenant.id:
            raise serializers.ValidationError({
                field_name: "El objeto relacionado no pertenece al mismo hotel."
            })