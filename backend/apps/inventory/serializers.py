from django.db import transaction
from rest_framework import serializers

from apps.inventory.models import Item, InventoryMovement, RoomInventory
from apps.master_data.models import MasterData


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
            "maximum_stock",
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

    def validate_maximum_stock(self, value):
        if value < 0:
            raise serializers.ValidationError("Maximum stock cannot be negative.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)

        stock = attrs.get("stock", getattr(self.instance, "stock", 0))
        minimum_stock = attrs.get("minimum_stock", getattr(self.instance, "minimum_stock", 0))
        maximum_stock = attrs.get("maximum_stock", getattr(self.instance, "maximum_stock", 0))

        if maximum_stock and minimum_stock > maximum_stock:
            raise serializers.ValidationError(
                {"minimum_stock": "Minimum stock cannot be greater than maximum stock."}
            )

        if maximum_stock and stock > maximum_stock:
            raise serializers.ValidationError(
                {"stock": "Stock cannot be greater than maximum stock."}
            )

        return attrs

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

    @staticmethod
    def _get_or_create_movement_type(code: str, name: str, sort_order: int = 0):
        movement_type, _ = MasterData.objects.get_or_create(
            group=MasterData.Group.INVENTORY_MOVEMENT_TYPE,
            code=code,
            defaults={
                "name": name,
                "is_active": True,
                "sort_order": sort_order,
            },
        )

        fields_to_update = []
        if not movement_type.is_active:
            movement_type.is_active = True
            fields_to_update.append("is_active")
        if not movement_type.name:
            movement_type.name = name
            fields_to_update.append("name")
        if fields_to_update:
            movement_type.save(update_fields=fields_to_update)

        return movement_type

    @staticmethod
    def _build_reference(action: str, room_inventory_id: int):
        return f"ROOM_INV_{action}:{room_inventory_id}"

    @staticmethod
    def _build_movement_note(action: str, room_inventory):
        room_number = getattr(getattr(room_inventory, "room", None), "number", None) or "N/A"
        item_name = getattr(getattr(room_inventory, "item", None), "name", None) or "Item"
        if action == "CREATE":
            return f"Asignacion inicial de {item_name} a habitacion {room_number}."
        if action == "UPDATE_IN":
            return f"Ajuste de devolucion de {item_name} desde habitacion {room_number}."
        if action == "UPDATE_OUT":
            return f"Ajuste adicional de {item_name} hacia habitacion {room_number}."
        return f"Movimiento automatico de inventario por habitacion {room_number}."

    def _create_inventory_movement(self, *, item, movement_code: str, quantity: int, reference: str, notes: str):
        if quantity <= 0:
            return None

        movement_type = self._get_or_create_movement_type(
            movement_code,
            "Salida de inventario" if movement_code == "OUT" else "Entrada de inventario",
            sort_order=1 if movement_code == "OUT" else 2,
        )

        return InventoryMovement.objects.create(
            item=item,
            movement_type=movement_type,
            quantity=quantity,
            reference=reference,
            notes=notes,
            is_active=True,
        )

    def create(self, validated_data):
        requested_item = validated_data["item"]
        quantity = int(validated_data.get("quantity") or 0)

        with transaction.atomic():
            locked_item = Item.objects.select_for_update().get(pk=requested_item.pk)

            if quantity > locked_item.stock:
                raise serializers.ValidationError(
                    {"quantity": "Quantity cannot be greater than current stock."}
                )

            validated_data["item"] = locked_item
            instance = super().create(validated_data)

            self._create_inventory_movement(
                item=locked_item,
                movement_code="OUT",
                quantity=quantity,
                reference=self._build_reference("CREATE", instance.id),
                notes=self._build_movement_note("CREATE", instance),
            )
            return instance

    def update(self, instance, validated_data):
        with transaction.atomic():
            locked_instance = RoomInventory.objects.select_for_update().get(pk=instance.pk)
            old_item = locked_instance.item
            old_quantity = int(locked_instance.quantity or 0)
            requested_item = validated_data.get("item", old_item)
            new_quantity = int(validated_data.get("quantity", old_quantity) or 0)

            locked_items = {
                item.pk: item
                for item in Item.objects.select_for_update().filter(
                    pk__in={old_item.pk, requested_item.pk}
                )
            }

            current_item = locked_items[old_item.pk]
            target_item = locked_items[requested_item.pk]
            validated_data["item"] = target_item

            # Cambio de item asignado: devuelve la cantidad anterior al item viejo
            # y descuenta la nueva cantidad del item nuevo.
            if target_item.pk != current_item.pk:
                if new_quantity > target_item.stock:
                    raise serializers.ValidationError(
                        {"quantity": "Quantity cannot be greater than current stock."}
                    )

                updated_instance = super().update(locked_instance, validated_data)

                self._create_inventory_movement(
                    item=current_item,
                    movement_code="IN",
                    quantity=old_quantity,
                    reference=self._build_reference("UPDATE", updated_instance.id),
                    notes=self._build_movement_note("UPDATE_IN", updated_instance),
                )
                self._create_inventory_movement(
                    item=target_item,
                    movement_code="OUT",
                    quantity=new_quantity,
                    reference=self._build_reference("UPDATE", updated_instance.id),
                    notes=self._build_movement_note("UPDATE_OUT", updated_instance),
                )
                return updated_instance

            delta = new_quantity - old_quantity
            if delta > 0 and delta > target_item.stock:
                raise serializers.ValidationError(
                    {"quantity": "Quantity cannot be greater than current stock."}
                )

            updated_instance = super().update(locked_instance, validated_data)

            if delta > 0:
                self._create_inventory_movement(
                    item=target_item,
                    movement_code="OUT",
                    quantity=delta,
                    reference=self._build_reference("UPDATE", updated_instance.id),
                    notes=self._build_movement_note("UPDATE_OUT", updated_instance),
                )
            elif delta < 0:
                self._create_inventory_movement(
                    item=target_item,
                    movement_code="IN",
                    quantity=abs(delta),
                    reference=self._build_reference("UPDATE", updated_instance.id),
                    notes=self._build_movement_note("UPDATE_IN", updated_instance),
                )

            return updated_instance
