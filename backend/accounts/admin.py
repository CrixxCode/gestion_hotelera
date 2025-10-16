from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Role, Resource, UserRole, RoleResource

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    pass

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
