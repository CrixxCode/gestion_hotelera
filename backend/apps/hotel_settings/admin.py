from django.contrib import admin
from .models import HotelSettings, HotelFloor


class HotelFloorInline(admin.TabularInline):
    model = HotelFloor
    extra = 1


@admin.register(HotelSettings)
class HotelSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "hotel_name",
        "stars",
        "city",
        "country",
        "primary_phone",
        "general_email",
        "currency",
        "tax_rate",
        "updated_at",
    )
    inlines = [HotelFloorInline]


@admin.register(HotelFloor)
class HotelFloorAdmin(admin.ModelAdmin):
    list_display = (
        "hotel_settings",
        "floor_number",
        "name",
        "prefix",
        "room_count",
    )
    list_filter = ("hotel_settings",)
    search_fields = ("name", "prefix")