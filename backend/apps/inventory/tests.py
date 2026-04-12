from django.test import TestCase
from rest_framework import serializers as drf_serializers

from apps.hotel_settings.models import HotelFloor, HotelSettings
from apps.inventory.models import InventoryMovement, InventoryRestockAlert, Item, RoomInventory
from apps.inventory.serializers import RoomInventorySerializer
from apps.master_data.models import MasterData
from apps.rooms.models import Room, RoomType


class RoomInventoryAutomaticMovementTestCase(TestCase):
    def _md(self, group, code, name=None, sort_order=1):
        return MasterData.objects.update_or_create(
            group=group,
            code=code,
            defaults={
                "name": name or code.title(),
                "is_active": True,
                "sort_order": sort_order,
            },
        )[0]

    def setUp(self):
        self.room_status = self._md(MasterData.Group.ROOM_STATUS, "DISPONIBLE", "Disponible", 1)
        self.item_type = self._md(MasterData.Group.ITEM_TYPE, "AMENITY", "Amenidad", 1)
        self.unit_measure = self._md(MasterData.Group.UNIT_MEASURE, "UND", "Unidad", 1)

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


class InventoryLowStockAutomationTestCase(TestCase):
    def _md(self, group, code, name=None, sort_order=1):
        return MasterData.objects.update_or_create(
            group=group,
            code=code,
            defaults={
                "name": name or code.title(),
                "is_active": True,
                "sort_order": sort_order,
            },
        )[0]

    def setUp(self):
        self.item_type = self._md(MasterData.Group.ITEM_TYPE, "AMENITY", "Amenidad", 1)
        self.unit_measure = self._md(MasterData.Group.UNIT_MEASURE, "UND", "Unidad", 1)
        self.out_movement_type = self._md(
            MasterData.Group.INVENTORY_MOVEMENT_TYPE,
            "OUT",
            "Salida de inventario",
            1,
        )
        self.in_movement_type = self._md(
            MasterData.Group.INVENTORY_MOVEMENT_TYPE,
            "IN",
            "Entrada de inventario",
            2,
        )

        self.hotel = HotelSettings.objects.create(hotel_name="Hotel Stock")
        self.item = Item.objects.create(
            hotel_settings=self.hotel,
            item_type=self.item_type,
            unit_measure=self.unit_measure,
            name="Shampoo",
            stock=10,
            minimum_stock=5,
            maximum_stock=100,
            cost_price=5000,
            sale_price=7000,
            is_active=True,
        )

    def test_creates_restock_alert_when_stock_goes_below_minimum(self):
        InventoryMovement.objects.create(
            item=self.item,
            movement_type=self.out_movement_type,
            quantity=6,
            reference="TEST:LOW_STOCK",
            notes="Consumo de prueba",
            is_active=True,
        )

        self.item.refresh_from_db()
        self.assertEqual(self.item.stock, 4)

        alert = InventoryRestockAlert.objects.filter(
            item=self.item,
            status=InventoryRestockAlert.Status.DRAFT,
            is_active=True,
        ).first()
        self.assertIsNotNone(alert)
        self.assertEqual(alert.reference, f"LOW_STOCK:{self.item.id}")
        self.assertEqual(alert.current_stock, 4)
        self.assertEqual(alert.minimum_stock, 5)
        self.assertEqual(alert.suggested_quantity, 1)

    def test_updates_existing_draft_alert_without_creating_duplicates(self):
        InventoryMovement.objects.create(
            item=self.item,
            movement_type=self.out_movement_type,
            quantity=6,
            reference="TEST:LOW_STOCK:1",
            notes="Consumo inicial",
            is_active=True,
        )
        first_alert = InventoryRestockAlert.objects.get(item=self.item, status=InventoryRestockAlert.Status.DRAFT)

        InventoryMovement.objects.create(
            item=self.item,
            movement_type=self.out_movement_type,
            quantity=1,
            reference="TEST:LOW_STOCK:2",
            notes="Consumo adicional",
            is_active=True,
        )

        draft_alerts = InventoryRestockAlert.objects.filter(
            item=self.item,
            status=InventoryRestockAlert.Status.DRAFT,
            is_active=True,
        )
        self.assertEqual(draft_alerts.count(), 1)

        draft_alert = draft_alerts.first()
        self.assertEqual(draft_alert.id, first_alert.id)
        self.assertEqual(draft_alert.current_stock, 3)
        self.assertEqual(draft_alert.minimum_stock, 5)
        self.assertEqual(draft_alert.suggested_quantity, 2)

    def test_resolves_draft_alert_when_stock_recovers(self):
        InventoryMovement.objects.create(
            item=self.item,
            movement_type=self.out_movement_type,
            quantity=6,
            reference="TEST:LOW_STOCK:3",
            notes="Consumo inicial",
            is_active=True,
        )
        self.assertEqual(
            InventoryRestockAlert.objects.filter(
                item=self.item,
                status=InventoryRestockAlert.Status.DRAFT,
                is_active=True,
            ).count(),
            1,
        )

        InventoryMovement.objects.create(
            item=self.item,
            movement_type=self.in_movement_type,
            quantity=3,
            reference="TEST:RECOVER_STOCK",
            notes="Reposicion",
            is_active=True,
        )

        self.assertFalse(
            InventoryRestockAlert.objects.filter(
                item=self.item,
                status=InventoryRestockAlert.Status.DRAFT,
                is_active=True,
            ).exists()
        )

        resolved_alert = InventoryRestockAlert.objects.filter(
            item=self.item,
            status=InventoryRestockAlert.Status.RESOLVED,
        ).first()
        self.assertIsNotNone(resolved_alert)
        self.assertEqual(resolved_alert.current_stock, 7)
        self.assertEqual(resolved_alert.minimum_stock, 5)
        self.assertEqual(resolved_alert.suggested_quantity, 0)
        self.assertIsNotNone(resolved_alert.resolved_at)
