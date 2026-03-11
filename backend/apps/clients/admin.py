from django.contrib import admin
from .models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = (
        "document_number",
        "first_name",
        "last_name",
        "email",
        "phone",
        "country",
        "client_type",
        "total_stay_nights",
        "last_stay",
        "status",
        "created_at",
    )
    list_filter = (
        "client_type",
        "status",
        "country",
        "created_at",
    )
    search_fields = (
        "document_number",
        "first_name",
        "last_name",
        "email",
        "phone",
        "country",
    )
    ordering = ("-id",)
