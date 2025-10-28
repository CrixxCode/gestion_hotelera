from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import Role, Resource, RoleResource, User, UserRole

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        (_("Información adicional"), {"fields": ("avatar",)}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "password1",
                    "password2",
                    "avatar",
                ),
            },
        ),
    )

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")

@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ("key", "name")

@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "assigned_at")

@admin.register(RoleResource)
class RoleResourceAdmin(admin.ModelAdmin):
    list_display = ("role", "resource", "granted_at")
