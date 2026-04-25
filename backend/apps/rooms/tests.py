from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory

from apps.hotel_settings.models import HotelFloor, HotelSettings
from apps.inventory.models import InventoryMovement, Item, RoomInventory
from apps.master_data.models import MasterData
from apps.rooms.models import CleaningTask, MaintenanceOrder, Room, RoomType
from apps.rooms.serializers import AmenitySerializer


class RoomOperationInventoryAutomationTestCase(TestCase):
    def _md(self, group, code, name=None, sort_order=1):
        return MasterData.objects.update_or_create(
            group=group,
            code=code,
            defaults={
                "name": name or code.title(),
                "sort_order": sort_order,
                "is_active": True,
            },
        )[0]

    def setUp(self):
        self.room_status = self._md(MasterData.Group.ROOM_STATUS, "DISPONIBLE", "Disponible", 1)

        self.maintenance_priority = self._md(
            MasterData.Group.MAINTENANCE_PRIORITY,
            "MEDIA",
            "Media",
            1,
        )
        self.maintenance_status_pending = self._md(
            MasterData.Group.MAINTENANCE_STATUS,
            "PENDIENTE",
            "Pendiente",
            1,
        )
        self.maintenance_status_completed = self._md(
            MasterData.Group.MAINTENANCE_STATUS,
            "COMPLETADA",
            "Completada",
            2,
        )

        self.cleaning_task_type_checkout = self._md(
            MasterData.Group.CLEANING_TASK_TYPE,
            "SALIDA",
            "Salida",
            1,
        )
        self.cleaning_status_pending = self._md(
            MasterData.Group.CLEANING_STATUS,
            "PENDIENTE",
            "Pendiente",
            1,
        )
        self.cleaning_status_completed = self._md(
            MasterData.Group.CLEANING_STATUS,
            "COMPLETADA",
            "Completada",
            2,
        )

        self.item_type = self._md(MasterData.Group.ITEM_TYPE, "AMENITY", "Amenidad", 1)
        self.unit_measure = self._md(MasterData.Group.UNIT_MEASURE, "UND", "Unidad", 1)

        self.hotel = HotelSettings.objects.create(hotel_name="Hotel Operaciones")
        self.floor = HotelFloor.objects.create(
            hotel_settings=self.hotel,
            floor_number=1,
            name="Piso 1",
            prefix="1",
            room_count=1,
        )
        self.room_type = RoomType.objects.create(code="STD", name="Standard", capacity=2)
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
            name="Agua",
            sku="WATER-001",
            stock=10,
            minimum_stock=2,
            maximum_stock=100,
            cost_price=1000,
            sale_price=2000,
            is_active=True,
        )

        self.room_inventory = RoomInventory.objects.create(
            room=self.room,
            item=self.item,
            quantity=1,
            minimum_quantity=3,
            is_active=True,
        )

    def test_closing_cleaning_task_replenishes_room_inventory_and_creates_out_movement(self):
        task = CleaningTask.objects.create(
            room=self.room,
            task_type=self.cleaning_task_type_checkout,
            status=self.cleaning_status_pending,
            notes="Limpieza normal",
        )

        task.status = self.cleaning_status_completed
        task.save(update_fields=["status"])

        self.room_inventory.refresh_from_db()
        self.item.refresh_from_db()
        self.assertEqual(self.room_inventory.quantity, 3)
        self.assertEqual(self.item.stock, 8)

        movement = InventoryMovement.objects.filter(
            item=self.item,
            movement_type__code="OUT",
            reference=f"ROOM_REPLENISH:CLEANING:{task.id}:{self.room_inventory.id}",
        ).first()
        self.assertIsNotNone(movement)
        self.assertEqual(movement.quantity, 2)

        task.notes = "Cierre confirmado"
        task.save(update_fields=["notes"])

        self.assertEqual(
            InventoryMovement.objects.filter(
                reference=f"ROOM_REPLENISH:CLEANING:{task.id}:{self.room_inventory.id}",
            ).count(),
            1,
        )

    def test_closing_maintenance_order_replenishes_partially_when_stock_is_low(self):
        self.room_inventory.quantity = 0
        self.room_inventory.minimum_quantity = 3
        self.room_inventory.save(update_fields=["quantity", "minimum_quantity"])

        self.item.stock = 1
        self.item.save(update_fields=["stock"])

        order = MaintenanceOrder.objects.create(
            room=self.room,
            title="Ajuste lavabo",
            description="Cambio de repuesto",
            priority=self.maintenance_priority,
            status=self.maintenance_status_pending,
        )

        order.status = self.maintenance_status_completed
        order.save(update_fields=["status"])

        self.room_inventory.refresh_from_db()
        self.item.refresh_from_db()
        self.assertEqual(self.room_inventory.quantity, 1)
        self.assertEqual(self.item.stock, 0)

        movement = InventoryMovement.objects.filter(
            item=self.item,
            movement_type__code="OUT",
            reference=f"ROOM_REPLENISH:MAINTENANCE:{order.id}:{self.room_inventory.id}",
        ).first()
        self.assertIsNotNone(movement)
        self.assertEqual(movement.quantity, 1)


class AmenitySerializerTenantAutofillTests(TestCase):
    def test_create_without_hotel_settings_uses_user_hotel(self):
        user_model = get_user_model()
        hotel = HotelSettings.objects.create(hotel_name="Hotel Amenidades")
        user = user_model.objects.create_user(
            username="amenity_user",
            password="secret123",
            hotel_settings=hotel,
        )

        request = APIRequestFactory().post(
            "/api/amenities/",
            {
                "name": "WiFi Premium",
                "icon": "fa-solid fa-wifi",
                "is_active": True,
            },
            format="json",
        )
        request.user = user

        serializer = AmenitySerializer(
            data={
                "name": "WiFi Premium",
                "icon": "fa-solid fa-wifi",
                "is_active": True,
            },
            context={"request": request},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
