from django.test import TestCase
from rest_framework import serializers as drf_serializers

from apps.hotel_settings.models import HotelFloor, HotelSettings
from apps.inventory.models import InventoryMovement, Item, RoomInventory
from apps.inventory.serializers import RoomInventorySerializer
from apps.master_data.models import MasterData
from apps.rooms.models import Room, RoomType


class RoomInventoryAutomaticMovementTestCase(TestCase):
    def setUp(self):
        self.room_status = MasterData.objects.create(
            group=MasterData.Group.ROOM_STATUS,
            code="DISPONIBLE",
            name="Disponible",
            is_active=True,
            sort_order=1,
        )
        self.item_type = MasterData.objects.create(
            group=MasterData.Group.ITEM_TYPE,
            code="AMENITY",
            name="Amenidad",
            is_active=True,
            sort_order=1,
        )
        self.unit_measure = MasterData.objects.create(
            group=MasterData.Group.UNIT_MEASURE,
            code="UND",
            name="Unidad",
            is_active=True,
            sort_order=1,
        )

        self.hotel = HotelSettings.objects.create(hotel_name="Hotel Test")
        self.floor = HotelFloor.objects.create(
            hotel_settings=self.hotel,
            floor_number=1,
            name="Primer piso",
            prefix="1",
            room_count=1,
        )
        self.room_type = RoomType.objects.create(code="STD", name="Standard")
        self.room = Room.objects.create(
            number="101",
            room_type=self.room_type,
            floor=self.floor,
            status=self.room_status,
        )

        self.item = Item.objects.create(
            hotel_settings=self.hotel,
            item_type=self.item_type,
            unit_measure=self.unit_measure,
            name="Toalla",
            stock=20,
            minimum_stock=2,
            maximum_stock=100,
            cost_price=10000,
            sale_price=12000,
            is_active=True,
        )

    def _create_room_inventory(self, quantity=4):
        serializer = RoomInventorySerializer(
            data={
                "room": self.room.id,
                "item": self.item.id,
                "quantity": quantity,
                "minimum_quantity": 1,
                "notes": "Asignacion inicial",
                "is_active": True,
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        return serializer.save()

    def test_create_room_inventory_decrements_item_stock_and_creates_out_movement(self):
        assignment = self._create_room_inventory(quantity=5)

        self.item.refresh_from_db()
        self.assertEqual(self.item.stock, 15)

        movement = InventoryMovement.objects.filter(
            item=self.item,
            reference=f"ROOM_INV_CREATE:{assignment.id}",
        ).order_by("-id").first()

        self.assertIsNotNone(movement)
        self.assertEqual(movement.movement_type.code, "OUT")
        self.assertEqual(movement.quantity, 5)
        self.assertEqual(movement.previous_stock, 20)
        self.assertEqual(movement.new_stock, 15)

    def test_create_room_inventory_rejects_if_quantity_exceeds_central_stock(self):
        serializer = RoomInventorySerializer(
            data={
                "room": self.room.id,
                "item": self.item.id,
                "quantity": 25,
                "minimum_quantity": 1,
                "notes": "",
                "is_active": True,
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

        with self.assertRaises(drf_serializers.ValidationError) as context:
            serializer.save()

        self.assertIn("quantity", context.exception.detail)
        self.item.refresh_from_db()
        self.assertEqual(self.item.stock, 20)
        self.assertEqual(RoomInventory.objects.count(), 0)

    def test_update_room_inventory_quantity_adjusts_stock_with_movements(self):
        assignment = self._create_room_inventory(quantity=4)

        serializer_increase = RoomInventorySerializer(
            instance=assignment,
            data={"quantity": 7},
            partial=True,
        )
        self.assertTrue(serializer_increase.is_valid(), serializer_increase.errors)
        serializer_increase.save()

        self.item.refresh_from_db()
        self.assertEqual(self.item.stock, 13)

        out_update_movement = InventoryMovement.objects.filter(
            item=self.item,
            reference=f"ROOM_INV_UPDATE:{assignment.id}",
            movement_type__code="OUT",
            quantity=3,
        ).first()
        self.assertIsNotNone(out_update_movement)

        serializer_decrease = RoomInventorySerializer(
            instance=assignment,
            data={"quantity": 2},
            partial=True,
        )
        self.assertTrue(serializer_decrease.is_valid(), serializer_decrease.errors)
        serializer_decrease.save()

        self.item.refresh_from_db()
        self.assertEqual(self.item.stock, 18)

        in_update_movement = InventoryMovement.objects.filter(
            item=self.item,
            reference=f"ROOM_INV_UPDATE:{assignment.id}",
            movement_type__code="IN",
            quantity=5,
        ).first()
        self.assertIsNotNone(in_update_movement)
