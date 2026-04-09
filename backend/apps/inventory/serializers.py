from rest_framework import serializers

from apps.inventory.models import Item, InventoryMovement, RoomInventory


class ItemSerializer(serializers.ModelSerializer):
    hotel_name = serializers.CharField(source="hotel_settings.hotel_name", read_only=True)
    item_type_name = serializers.CharField(source="item_type.name", read_only=True)
    item_type_code = serializers.CharField(source="item_type.code", read_only=True)
    unit_measure_name = serializers.CharField(source="unit_measure.name", read_only=True)
    unit_measure_code = serializers.CharField(source="unit_measure.code", read_only=True)

    class Meta:
        model = Item
        fields = [
            "id",
            "hotel_settings",
            "hotel_name",
            "item_type",
            "item_type_name",
            "item_type_code",
            "unit_measure",
            "unit_measure_name",
            "unit_measure_code",
            "name",
            "sku",
            "description",
            "stock",
            "minimum_stock",
            "cost_price",
            "sale_price",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_stock(self, value):
        if value < 0:
            raise serializers.ValidationError("Stock cannot be negative.")
        return value

    def validate_minimum_stock(self, value):
        if value < 0:
            raise serializers.ValidationError("Minimum stock cannot be negative.")
        return value

    def validate_cost_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Cost price cannot be negative.")
        return value

    def validate_sale_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Sale price cannot be negative.")
        return value
    
class InventoryMovementSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.name", read_only=True)
    movement_type_name = serializers.CharField(source="movement_type.name", read_only=True)
    movement_type_code = serializers.CharField(source="movement_type.code", read_only=True)

    class Meta:
        model = InventoryMovement
        fields = [
            "id",
            "item",
            "item_name",
            "movement_type",
            "movement_type_name",
            "movement_type_code",
            "quantity",
            "previous_stock",
            "new_stock",
            "reference",
            "notes",
            "movement_date",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = (
            "id",
            "previous_stock",
            "new_stock",
            "movement_date",
            "created_at",
            "updated_at",
        )

    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError("Quantity must be at least 1.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)

        item = attrs.get("item", getattr(self.instance, "item", None))
        movement_type = attrs.get("movement_type", getattr(self.instance, "movement_type", None))
        quantity = attrs.get("quantity", getattr(self.instance, "quantity", None))

        if item and movement_type and quantity:
            movement_code = str(movement_type.code or "").strip().upper()

            if movement_code in ["OUT", "LOSS"] and quantity > item.stock:
                raise serializers.ValidationError(
                    {"quantity": "Quantity cannot be greater than current stock."}
                )

        return attrs
    
class RoomInventorySerializer(serializers.ModelSerializer):
    room_number = serializers.CharField(source="room.number", read_only=True)
    item_name = serializers.CharField(source="item.name", read_only=True)
    item_sku = serializers.CharField(source="item.sku", read_only=True)

    class Meta:
        model = RoomInventory
        fields = [
            "id",
            "room",
            "room_number",
            "item",
            "item_name",
            "item_sku",
            "quantity",
            "minimum_quantity",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
        )

    def validate_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError("Quantity cannot be negative.")
        return value

    def validate_minimum_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError("Minimum quantity cannot be negative.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)

        room = attrs.get("room", getattr(self.instance, "room", None))
        item = attrs.get("item", getattr(self.instance, "item", None))

        if room and item:
            room_hotel_settings_id = getattr(room, "hotel_settings_id", None)
            item_hotel_settings_id = getattr(item, "hotel_settings_id", None)

            if room_hotel_settings_id and item_hotel_settings_id:
                if room_hotel_settings_id != item_hotel_settings_id:
                    raise serializers.ValidationError(
                        {"item": "The item must belong to the same hotel as the room."}
                    )

        return attrs