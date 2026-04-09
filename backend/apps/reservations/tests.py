from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from apps.clients.models import Client
from apps.billing.models import Charge
from apps.hotel_settings.models import HotelFloor, HotelSettings, ReservationPolicy
from apps.inventory.models import Item, RoomInventory
from apps.master_data.models import MasterData
from apps.packages.models import Package
from apps.reservations.models import (
    Reservation,
    ReservationDeposit,
    ReservationInventoryCheck,
    ReservationInventoryCheckLine,
    ReservationRoom,
)
from apps.reservations.serializers import (
    ReservationDetailSerializer,
    ReservationDepositSerializer,
    ReservationListSerializer,
    ReservationRoomSerializer,
    ReservationWriteSerializer,
)
from apps.rooms.models import CleaningTask, Rate, Room, RoomType

User = get_user_model()


class ReservationFlowTestCase(TestCase):
    def _same_day_future_past_times(self):
        now_local = timezone.localtime()
        now_date = now_local.date()

        future_candidate = now_local + timedelta(hours=2)
        if future_candidate.date() != now_date:
            future_time = time(23, 59)
        else:
            future_time = future_candidate.time()

        past_candidate = now_local - timedelta(hours=2)
        if past_candidate.date() != now_date:
            past_time = time(0, 0)
        else:
            past_time = past_candidate.time()

        return now_date, future_time, past_time

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
        self.document_type = self._md(MasterData.Group.DOCUMENT_TYPE, "CC", "Cedula", 1)
        self.client_type = self._md(MasterData.Group.CLIENT_TYPE, "REGULAR", "Regular", 1)
        self.client_status = self._md(MasterData.Group.CLIENT_STATUS, "ACTIVO", "Activo", 1)

        self.room_status_available = self._md(MasterData.Group.ROOM_STATUS, "DISPONIBLE", "Disponible", 1)
        self.room_status_reserved = self._md(MasterData.Group.ROOM_STATUS, "RESERVADA", "Reservada", 2)
        self.room_status_occupied = self._md(MasterData.Group.ROOM_STATUS, "OCUPADA", "Ocupada", 3)
        self.room_status_maintenance = self._md(MasterData.Group.ROOM_STATUS, "MANTENIMIENTO", "Mantenimiento", 4)
        self.room_status_cleaning = self._md(MasterData.Group.ROOM_STATUS, "LIMPIEZA", "Limpieza", 5)
        self.room_type_standard = RoomType.objects.update_or_create(
            code="STD",
            defaults={
                "name": "Standard",
                "description": "",
                "capacity": 2,
                "bed_count": 1,
                "bed_type": "Queen",
                "is_active": True,
                "sort_order": 1,
            },
        )[0]
        self.room_type_suite = RoomType.objects.update_or_create(
            code="SUI",
            defaults={
                "name": "Suite",
                "description": "",
                "capacity": 4,
                "bed_count": 2,
                "bed_type": "King",
                "is_active": True,
                "sort_order": 2,
            },
        )[0]

        self.reservation_status_confirmed = self._md(
            MasterData.Group.RESERVATION_STATUS, "CONFIRMADA", "Confirmada", 1
        )
        self.reservation_status_pending = self._md(
            MasterData.Group.RESERVATION_STATUS, "PENDIENTE", "Pendiente", 0
        )
        self.reservation_status_cancelled = self._md(
            MasterData.Group.RESERVATION_STATUS, "CANCELADA", "Cancelada", 2
        )
        self.reservation_status_finished = self._md(
            MasterData.Group.RESERVATION_STATUS, "FINALIZADA", "Finalizada", 3
        )
        self.reservation_origin = self._md(MasterData.Group.RESERVATION_ORIGIN, "WEB", "Web", 1)
        self.payment_method_cash = self._md(
            MasterData.Group.PAYMENT_METHOD, "EFECTIVO", "Efectivo", 1
        )
        self.deposit_status_validated = self._md(
            MasterData.Group.RESERVATION_DEPOSIT_STATUS, "VALIDADO", "Validado", 1
        )
        self.item_type_amenity = self._md(
            MasterData.Group.ITEM_TYPE, "AMENITY", "Amenidad", 1
        )
        self.unit_measure_unit = self._md(
            MasterData.Group.UNIT_MEASURE, "UNIDAD", "Unidad", 1
        )
        self.policy_type = self._md(
            MasterData.Group.RESERVATION_POLICY_TYPE, "CANCELLATION", "Cancellation", 1
        )
        self.penalty_type = self._md(
            MasterData.Group.RESERVATION_PENALTY_TYPE, "PERCENTAGE", "Percentage", 1
        )

        now_local = timezone.localtime()
        self.hotel_settings = HotelSettings.objects.create(
            hotel_name="Hotel Test",
            check_in_time=(now_local + timedelta(hours=1)).time(),
        )
        self.floor = HotelFloor.objects.create(
            hotel_settings=self.hotel_settings,
            floor_number=1,
            name="Piso 1",
            prefix="1",
            room_count=1,
        )

        self.room = Room.objects.create(
            number="101",
            room_type=self.room_type_standard,
            floor=self.floor,
            status=self.room_status_available,
        )

        self.client = Client.objects.create(
            document_type=self.document_type,
            document_number="123456789",
            first_name="Ana",
            last_name="Lopez",
            email="ana@example.com",
            phone="3001234567",
            country="CO",
            client_type=self.client_type,
            status=self.client_status,
        )

        self.policy_flexible = ReservationPolicy.objects.create(
            hotel_settings=self.hotel_settings,
            policy_type=self.policy_type,
            penalty_type=self.penalty_type,
            name="Flexible",
            penalty_value=10,
            hours_before_checkin=24,
            is_active=True,
        )
        self.policy_strict = ReservationPolicy.objects.create(
            hotel_settings=self.hotel_settings,
            policy_type=self.policy_type,
            penalty_type=self.penalty_type,
            name="Strict",
            penalty_value=50,
            hours_before_checkin=48,
            is_active=True,
        )
        self.package_standard = Package.objects.create(
            hotel_settings=self.hotel_settings,
            room_type=self.room_type_standard,
            name="Paquete Standard",
            base_price=25000,
            is_active=True,
        )

    def _create_reservation(self, *, check_in, check_out, status=None):
        return Reservation.objects.create(
            client=self.client,
            status=status or self.reservation_status_confirmed,
            origin=self.reservation_origin,
            expected_check_in=check_in,
            expected_check_out=check_out,
        )

    def test_room_status_changes_across_reservation_lifecycle(self):
        today = timezone.now().date()
        reservation = self._create_reservation(
            check_in=today + timedelta(days=1),
            check_out=today + timedelta(days=3),
        )

        ReservationRoom.objects.create(
            reservation=reservation,
            room=self.room,
            night_rate=150000,
            adults=2,
            children=0,
        )
        self.room.refresh_from_db()
        self.assertEqual(self.room.status.code, "DISPONIBLE")

        reservation.real_check_in = timezone.now()
        reservation.save(update_fields=["real_check_in"])
        self.room.refresh_from_db()
        self.assertEqual(self.room.status.code, "OCUPADA")

        reservation.real_check_out = timezone.now()
        reservation.save(update_fields=["real_check_out"])
        self.room.refresh_from_db()
        self.assertEqual(self.room.status.code, "DISPONIBLE")

    def test_cannot_create_overlapping_reservation_room(self):
        today = timezone.now().date()
        reservation_a = self._create_reservation(
            check_in=today + timedelta(days=10),
            check_out=today + timedelta(days=15),
        )
        ReservationRoom.objects.create(
            reservation=reservation_a,
            room=self.room,
            night_rate=150000,
            adults=2,
            children=0,
        )

        reservation_b = self._create_reservation(
            check_in=today + timedelta(days=12),
            check_out=today + timedelta(days=14),
        )

        serializer = ReservationRoomSerializer(
            data={
                "reservation": reservation_b.id,
                "room": self.room.id,
                "night_rate": "140000.00",
                "adults": 1,
                "children": 0,
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("room", serializer.errors)

    def test_room_serializer_rejects_room_in_maintenance_or_cleaning(self):
        today = timezone.now().date()

        for blocked_status in (self.room_status_maintenance, self.room_status_cleaning):
            with self.subTest(status=blocked_status.code):
                self.room.status = blocked_status
                self.room.save(update_fields=["status"])

                reservation = self._create_reservation(
                    check_in=today + timedelta(days=20),
                    check_out=today + timedelta(days=22),
                )

                serializer = ReservationRoomSerializer(
                    data={
                        "reservation": reservation.id,
                        "room": self.room.id,
                        "night_rate": "100000.00",
                        "adults": 2,
                        "children": 0,
                    }
                )

                self.assertFalse(serializer.is_valid())
                self.assertIn("room", serializer.errors)

    def test_reservation_serializer_snapshots_package_and_updates_total(self):
        today = timezone.now().date()
        serializer = ReservationWriteSerializer(
            data={
                "client": self.client.id,
                "origin": self.reservation_origin.id,
                "package": self.package_standard.id,
                "expected_check_in": today + timedelta(days=1),
                "expected_check_out": today + timedelta(days=3),
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        reservation = serializer.save()

        self.assertEqual(reservation.package_id, self.package_standard.id)
        self.assertEqual(reservation.package_name, self.package_standard.name)
        self.assertEqual(str(reservation.package_price), "25000.00")

        ReservationRoom.objects.create(
            reservation=reservation,
            room=self.room,
            night_rate=100000,
            adults=2,
            children=0,
        )

        data = ReservationListSerializer(instance=reservation).data
        self.assertEqual(str(data["rooms_subtotal"]), "200000.00")
        self.assertEqual(str(data["package_subtotal"]), "25000.00")
        self.assertEqual(str(data["total_amount"]), "225000.00")

    def test_reservation_serializer_rejects_package_outside_booking_dates(self):
        today = timezone.now().date()
        limited_package = Package.objects.create(
            hotel_settings=self.hotel_settings,
            room_type=self.room_type_standard,
            name="Paquete por temporada",
            base_price=15000,
            is_active=True,
            start_date=today + timedelta(days=10),
            end_date=today + timedelta(days=20),
        )

        serializer = ReservationWriteSerializer(
            data={
                "client": self.client.id,
                "origin": self.reservation_origin.id,
                "package": limited_package.id,
                "expected_check_in": today + timedelta(days=1),
                "expected_check_out": today + timedelta(days=3),
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("package", serializer.errors)

    def test_room_serializer_rejects_room_type_when_reservation_has_package(self):
        today = timezone.now().date()
        suite_package = Package.objects.create(
            hotel_settings=self.hotel_settings,
            room_type=self.room_type_suite,
            name="Paquete Suite",
            base_price=50000,
            is_active=True,
        )
        reservation_serializer = ReservationWriteSerializer(
            data={
                "client": self.client.id,
                "origin": self.reservation_origin.id,
                "package": suite_package.id,
                "expected_check_in": today + timedelta(days=1),
                "expected_check_out": today + timedelta(days=3),
            }
        )
        self.assertTrue(reservation_serializer.is_valid(), reservation_serializer.errors)
        reservation = reservation_serializer.save()

        serializer = ReservationRoomSerializer(
            data={
                "reservation": reservation.id,
                "room": self.room.id,
                "night_rate": "90000.00",
                "adults": 2,
                "children": 0,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("room", serializer.errors)

    def test_room_serializer_rejects_room_hotel_when_reservation_has_package(self):
        today = timezone.now().date()
        reservation_serializer = ReservationWriteSerializer(
            data={
                "client": self.client.id,
                "origin": self.reservation_origin.id,
                "package": self.package_standard.id,
                "expected_check_in": today + timedelta(days=1),
                "expected_check_out": today + timedelta(days=3),
            }
        )
        self.assertTrue(reservation_serializer.is_valid(), reservation_serializer.errors)
        reservation = reservation_serializer.save()

        other_hotel = HotelSettings.objects.create(hotel_name="Hotel Other")
        other_floor = HotelFloor.objects.create(
            hotel_settings=other_hotel,
            floor_number=1,
            name="Piso Other",
            prefix="2",
            room_count=1,
        )
        other_room = Room.objects.create(
            number="201",
            room_type=self.room_type_standard,
            floor=other_floor,
            status=self.room_status_available,
        )

        serializer = ReservationRoomSerializer(
            data={
                "reservation": reservation.id,
                "room": other_room.id,
                "night_rate": "90000.00",
                "adults": 2,
                "children": 0,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("room", serializer.errors)

    def test_room_serializer_rejects_night_rate_mismatch_with_active_rate(self):
        today = timezone.now().date()
        reservation = self._create_reservation(
            check_in=today + timedelta(days=1),
            check_out=today + timedelta(days=3),
        )
        Rate.objects.create(
            room_type=self.room_type_standard,
            name="Tarifa estandar vigente",
            price=150000,
            start_date=today,
            end_date=today + timedelta(days=10),
            is_active=True,
        )

        serializer = ReservationRoomSerializer(
            data={
                "reservation": reservation.id,
                "room": self.room.id,
                "night_rate": "120000.00",
                "adults": 2,
                "children": 0,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("night_rate", serializer.errors)

    def test_room_serializer_accepts_night_rate_matching_active_rate(self):
        today = timezone.now().date()
        reservation = self._create_reservation(
            check_in=today + timedelta(days=1),
            check_out=today + timedelta(days=3),
        )
        Rate.objects.create(
            room_type=self.room_type_standard,
            name="Tarifa estandar vigente",
            price=150000,
            start_date=today,
            end_date=today + timedelta(days=10),
            is_active=True,
        )

        serializer = ReservationRoomSerializer(
            data={
                "reservation": reservation.id,
                "room": self.room.id,
                "night_rate": "150000.00",
                "adults": 2,
                "children": 0,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_updating_reservation_dates_validates_existing_room_conflicts(self):
        today = timezone.now().date()
        reservation_a = self._create_reservation(
            check_in=today + timedelta(days=1),
            check_out=today + timedelta(days=3),
        )
        ReservationRoom.objects.create(
            reservation=reservation_a,
            room=self.room,
            night_rate=150000,
            adults=2,
            children=0,
        )

        reservation_b = self._create_reservation(
            check_in=today + timedelta(days=5),
            check_out=today + timedelta(days=8),
        )
        ReservationRoom.objects.create(
            reservation=reservation_b,
            room=self.room,
            night_rate=140000,
            adults=1,
            children=0,
        )

        serializer = ReservationWriteSerializer(
            instance=reservation_b,
            data={
                "expected_check_in": today + timedelta(days=2),
                "expected_check_out": today + timedelta(days=6),
            },
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("rooms_detail", serializer.errors)

    def test_room_becomes_reserved_only_after_check_in_window_starts(self):
        now_local = timezone.localtime()
        future_check_in = now_local + timedelta(hours=2)
        past_check_in = now_local - timedelta(hours=2)

        self.hotel_settings.check_in_time = future_check_in.time()
        self.hotel_settings.save(update_fields=["check_in_time"])

        reservation = self._create_reservation(
            check_in=future_check_in.date(),
            check_out=future_check_in.date() + timedelta(days=2),
        )
        ReservationRoom.objects.create(
            reservation=reservation,
            room=self.room,
            night_rate=150000,
            adults=2,
            children=0,
        )
        self.room.refresh_from_db()
        self.assertEqual(self.room.status.code, "DISPONIBLE")

        self.hotel_settings.check_in_time = past_check_in.time()
        self.hotel_settings.save(update_fields=["check_in_time"])

        reservation.expected_check_in = past_check_in.date()
        reservation.notes = "sync trigger"
        reservation.save(update_fields=["expected_check_in", "notes"])
        self.room.refresh_from_db()
        self.assertEqual(self.room.status.code, "RESERVADA")

    def test_sync_command_updates_status_when_only_time_changes(self):
        check_in_date, future_time, past_time = self._same_day_future_past_times()

        self.hotel_settings.check_in_time = future_time
        self.hotel_settings.save(update_fields=["check_in_time"])

        reservation = self._create_reservation(
            check_in=check_in_date,
            check_out=check_in_date + timedelta(days=1),
        )
        ReservationRoom.objects.create(
            reservation=reservation,
            room=self.room,
            night_rate=120000,
            adults=2,
            children=0,
        )
        self.room.refresh_from_db()
        self.assertEqual(self.room.status.code, "DISPONIBLE")

        self.hotel_settings.check_in_time = past_time
        self.hotel_settings.save(update_fields=["check_in_time"])

        call_command("sync_reservation_room_statuses")
        self.room.refresh_from_db()
        self.assertEqual(self.room.status.code, "RESERVADA")

    def test_create_reservation_assigns_policies(self):
        today = timezone.now().date()
        serializer = ReservationWriteSerializer(
            data={
                "client": self.client.id,
                "origin": self.reservation_origin.id,
                "policies": [self.policy_flexible.id],
                "expected_check_in": today + timedelta(days=1),
                "expected_check_out": today + timedelta(days=2),
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        reservation = serializer.save()

        self.assertEqual(reservation.status_id, self.reservation_status_pending.id)
        self.assertEqual(
            list(reservation.policies.values_list("id", flat=True)),
            [self.policy_flexible.id],
        )

    def test_update_reservation_policies_replaces_and_clears(self):
        today = timezone.now().date()
        reservation = self._create_reservation(
            check_in=today + timedelta(days=4),
            check_out=today + timedelta(days=6),
        )
        reservation.policies.add(self.policy_flexible)

        replace_serializer = ReservationWriteSerializer(
            instance=reservation,
            data={"policies": [self.policy_strict.id]},
            partial=True,
        )
        self.assertTrue(replace_serializer.is_valid(), replace_serializer.errors)
        reservation = replace_serializer.save()
        self.assertEqual(
            list(reservation.policies.values_list("id", flat=True)),
            [self.policy_strict.id],
        )

        clear_serializer = ReservationWriteSerializer(
            instance=reservation,
            data={"policies": []},
            partial=True,
        )
        self.assertTrue(clear_serializer.is_valid(), clear_serializer.errors)
        reservation = clear_serializer.save()
        self.assertEqual(reservation.policies.count(), 0)

    def test_detail_serializer_includes_policies(self):
        today = timezone.now().date()
        reservation = self._create_reservation(
            check_in=today + timedelta(days=7),
            check_out=today + timedelta(days=8),
        )
        reservation.policies.add(self.policy_flexible, self.policy_strict)

        data = ReservationDetailSerializer(instance=reservation).data
        policy_ids = sorted(item["id"] for item in data["policies"])

        self.assertIn("policies", data)
        self.assertEqual(policy_ids, sorted([self.policy_flexible.id, self.policy_strict.id]))

    def test_list_serializer_exposes_centralized_business_rules(self):
        today = timezone.now().date()
        reservation = self._create_reservation(
            check_in=today + timedelta(days=1),
            check_out=today + timedelta(days=3),
            status=self.reservation_status_confirmed,
        )
        reservation.total_discount = 10000
        reservation.save(update_fields=["total_discount"])

        ReservationRoom.objects.create(
            reservation=reservation,
            room=self.room,
            night_rate=100000,
            adults=2,
            children=0,
        )
        ReservationDeposit.objects.create(
            reservation=reservation,
            deposit_date=today,
            amount=50000,
            payment_method=self.payment_method_cash,
            status=self.deposit_status_validated,
        )

        data = ReservationListSerializer(instance=reservation).data

        self.assertEqual(str(data["rooms_subtotal"]), "200000.00")
        self.assertEqual(str(data["total_amount"]), "190000.00")
        self.assertEqual(str(data["total_deposits"]), "50000.00")
        self.assertEqual(str(data["pending_amount"]), "140000.00")
        self.assertEqual(data["payment_status_code"], "PARCIAL")
        self.assertEqual(data["payment_status_label"], "Parcial")
        self.assertTrue(data["can_add_payment"])
        self.assertFalse(data["can_confirm"])
        self.assertTrue(data["can_check_in"])
        self.assertFalse(data["can_check_out"])
        self.assertTrue(data["can_cancel"])

    def test_deposit_serializer_rejects_amount_greater_than_pending(self):
        today = timezone.now().date()
        reservation = self._create_reservation(
            check_in=today + timedelta(days=10),
            check_out=today + timedelta(days=12),
        )
        ReservationRoom.objects.create(
            reservation=reservation,
            room=self.room,
            night_rate=100000,
            adults=2,
            children=0,
        )
        ReservationDeposit.objects.create(
            reservation=reservation,
            deposit_date=today,
            amount=150000,
            payment_method=self.payment_method_cash,
            status=self.deposit_status_validated,
        )

        serializer = ReservationDepositSerializer(
            data={
                "reservation": reservation.id,
                "deposit_date": today,
                "amount": "60000.00",
                "payment_method": self.payment_method_cash.id,
                "status": self.deposit_status_validated.id,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("amount", serializer.errors)

    def test_deposit_serializer_rejects_cancelled_reservation(self):
        today = timezone.now().date()
        reservation = self._create_reservation(
            check_in=today + timedelta(days=15),
            check_out=today + timedelta(days=16),
            status=self.reservation_status_cancelled,
        )
        ReservationRoom.objects.create(
            reservation=reservation,
            room=self.room,
            night_rate=100000,
            adults=2,
            children=0,
        )

        serializer = ReservationDepositSerializer(
            data={
                "reservation": reservation.id,
                "deposit_date": today,
                "amount": "20000.00",
                "payment_method": self.payment_method_cash.id,
                "status": self.deposit_status_validated.id,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("reservation", serializer.errors)


class ReservationApiFlowTestCase(APITestCase):
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
        self.document_type = self._md(MasterData.Group.DOCUMENT_TYPE, "CC", "Cedula", 1)
        self.client_type = self._md(MasterData.Group.CLIENT_TYPE, "REGULAR", "Regular", 1)
        self.client_status = self._md(MasterData.Group.CLIENT_STATUS, "ACTIVO", "Activo", 1)

        self.room_status_available = self._md(MasterData.Group.ROOM_STATUS, "DISPONIBLE", "Disponible", 1)
        self._md(MasterData.Group.ROOM_STATUS, "RESERVADA", "Reservada", 2)
        self._md(MasterData.Group.ROOM_STATUS, "OCUPADA", "Ocupada", 3)

        self.reservation_status_pending = self._md(
            MasterData.Group.RESERVATION_STATUS, "PENDIENTE", "Pendiente", 0
        )
        self.reservation_status_confirmed = self._md(
            MasterData.Group.RESERVATION_STATUS, "CONFIRMADA", "Confirmada", 1
        )
        self.reservation_status_in_progress = self._md(
            MasterData.Group.RESERVATION_STATUS, "EN_CURSO", "En curso", 2
        )
        self.reservation_status_finished = self._md(
            MasterData.Group.RESERVATION_STATUS, "FINALIZADA", "Finalizada", 3
        )
        self.reservation_status_cancelled = self._md(
            MasterData.Group.RESERVATION_STATUS, "CANCELADA", "Cancelada", 4
        )
        self.cleaning_task_type_checkout = self._md(
            MasterData.Group.CLEANING_TASK_TYPE, "SALIDA", "Salida", 1
        )
        self.cleaning_status_pending = self._md(
            MasterData.Group.CLEANING_STATUS, "PENDIENTE", "Pendiente", 1
        )
        self.reservation_origin = self._md(MasterData.Group.RESERVATION_ORIGIN, "WEB", "Web", 1)
        self.payment_method_cash = self._md(MasterData.Group.PAYMENT_METHOD, "EFECTIVO", "Efectivo", 1)
        self.deposit_status_validated = self._md(
            MasterData.Group.RESERVATION_DEPOSIT_STATUS, "VALIDADO", "Validado", 1
        )
        self.item_type_amenity = self._md(
            MasterData.Group.ITEM_TYPE, "AMENITY", "Amenidad", 1
        )
        self.unit_measure_unit = self._md(
            MasterData.Group.UNIT_MEASURE, "UNIDAD", "Unidad", 1
        )

        self.hotel_settings = HotelSettings.objects.create(
            hotel_name="Hotel API Test",
            check_in_time=(timezone.localtime() + timedelta(hours=1)).time(),
        )
        self.floor = HotelFloor.objects.create(
            hotel_settings=self.hotel_settings,
            floor_number=1,
            name="Piso 1",
            prefix="1",
            room_count=1,
        )
        self.room = Room.objects.create(
            number="101",
            floor=self.floor,
            status=self.room_status_available,
        )
        self.towel_item = Item.objects.create(
            hotel_settings=self.hotel_settings,
            item_type=self.item_type_amenity,
            unit_measure=self.unit_measure_unit,
            name="Toalla",
            sku="TOWEL-001",
            stock=100,
            minimum_stock=10,
            cost_price=10000,
            sale_price=12000,
            is_active=True,
        )
        self.room_towel_inventory = RoomInventory.objects.create(
            room=self.room,
            item=self.towel_item,
            quantity=3,
            minimum_quantity=2,
            is_active=True,
        )

        self.client_model = Client.objects.create(
            document_type=self.document_type,
            document_number="99887766",
            first_name="Cliente",
            last_name="API",
            email="cliente.api@example.com",
            phone="3009998877",
            country="CO",
            client_type=self.client_type,
            status=self.client_status,
        )

        self.user = User.objects.create_superuser(
            username="admin_res_api",
            email="admin.res.api@example.com",
            password="Pass12345!",
        )
        self.client = APIClient()
        self.client.force_login(self.user)

    def _create_reservation(self, *, check_in_offset=1, check_out_offset=2, status=None):
        today = timezone.now().date()
        return Reservation.objects.create(
            client=self.client_model,
            status=status or self.reservation_status_pending,
            origin=self.reservation_origin,
            expected_check_in=today + timedelta(days=check_in_offset),
            expected_check_out=today + timedelta(days=check_out_offset),
        )

    def _create_room_line(self, reservation: Reservation, night_rate=100000):
        return ReservationRoom.objects.create(
            reservation=reservation,
            room=self.room,
            night_rate=night_rate,
            adults=2,
            children=0,
        )

    def test_reservations_list_is_paginated(self):
        for index in range(25):
            self._create_reservation(check_in_offset=5 + index, check_out_offset=6 + index)

        response = self.client.get("/api/reservations/?ordering=-id")
        self.assertEqual(response.status_code, 200)
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)
        self.assertEqual(response.data["count"], 25)
        self.assertEqual(len(response.data["results"]), 20)
        self.assertIsNotNone(response.data["next"])

        response_page_size = self.client.get("/api/reservations/?ordering=-id&page_size=10")
        self.assertEqual(response_page_size.status_code, 200)
        self.assertEqual(len(response_page_size.data["results"]), 10)

    def test_reservation_flow_endpoints_confirm_checkin_checkout(self):
        reservation = self._create_reservation(status=self.reservation_status_pending)

        confirm = self.client.post(f"/api/reservations/{reservation.id}/confirm/", data={}, format="json")
        self.assertEqual(confirm.status_code, 200)
        self.assertEqual(confirm.data["status_code"], "CONFIRMADA")
        self.assertTrue(confirm.data["can_check_in"])

        check_in = self.client.post(f"/api/reservations/{reservation.id}/check-in/", data={}, format="json")
        self.assertEqual(check_in.status_code, 200)
        self.assertEqual(check_in.data["status_code"], "EN_CURSO")
        self.assertIsNotNone(check_in.data["real_check_in"])

        check_out = self.client.post(f"/api/reservations/{reservation.id}/check-out/", data={}, format="json")
        self.assertEqual(check_out.status_code, 200)
        self.assertEqual(check_out.data["status_code"], "FINALIZADA")
        self.assertIsNotNone(check_out.data["real_check_out"])

    def test_check_out_creates_post_checkout_cleaning_task(self):
        reservation = self._create_reservation(status=self.reservation_status_pending)
        self._create_room_line(reservation=reservation, night_rate=100000)

        confirm = self.client.post(f"/api/reservations/{reservation.id}/confirm/", data={}, format="json")
        self.assertEqual(confirm.status_code, 200)

        check_in = self.client.post(f"/api/reservations/{reservation.id}/check-in/", data={}, format="json")
        self.assertEqual(check_in.status_code, 200)

        check_out = self.client.post(f"/api/reservations/{reservation.id}/check-out/", data={}, format="json")
        self.assertEqual(check_out.status_code, 200)
        self.assertEqual(check_out.data["status_code"], "FINALIZADA")

        reservation.refresh_from_db()
        expected_scheduled_for = timezone.localtime(reservation.real_check_out).date()

        tasks = CleaningTask.objects.filter(room_id=self.room.id, task_type__code="SALIDA")
        self.assertEqual(tasks.count(), 1)

        task = tasks.first()
        self.assertIsNotNone(task)
        self.assertEqual(task.status.code, "PENDIENTE")
        self.assertEqual(task.scheduled_for, expected_scheduled_for)
        self.assertIn(f"#{reservation.id}", task.notes or "")

        checkout_inventory_check = ReservationInventoryCheck.objects.filter(
            reservation=reservation,
            check_type=ReservationInventoryCheck.CheckType.CHECK_OUT,
        ).first()
        self.assertIsNotNone(checkout_inventory_check)

        checkout_line = ReservationInventoryCheckLine.objects.filter(
            inventory_check=checkout_inventory_check,
            room=self.room,
            item=self.towel_item,
        ).first()
        self.assertIsNotNone(checkout_line)
        self.assertEqual(checkout_line.expected_quantity, 3)
        self.assertEqual(checkout_line.reviewed_quantity, 3)
        self.assertEqual(checkout_line.difference_quantity, 0)

        check_out_again = self.client.post(f"/api/reservations/{reservation.id}/check-out/", data={}, format="json")
        self.assertEqual(check_out_again.status_code, 200)
        self.assertEqual(
            CleaningTask.objects.filter(room_id=self.room.id, task_type__code="SALIDA").count(),
            1,
        )

    def test_check_in_creates_inventory_snapshot(self):
        reservation = self._create_reservation(status=self.reservation_status_pending)
        self._create_room_line(reservation=reservation, night_rate=100000)

        confirm = self.client.post(f"/api/reservations/{reservation.id}/confirm/", data={}, format="json")
        self.assertEqual(confirm.status_code, 200)

        check_in = self.client.post(f"/api/reservations/{reservation.id}/check-in/", data={}, format="json")
        self.assertEqual(check_in.status_code, 200)
        self.assertEqual(check_in.data["status_code"], "EN_CURSO")

        inventory_check = ReservationInventoryCheck.objects.filter(
            reservation=reservation,
            check_type=ReservationInventoryCheck.CheckType.CHECK_IN,
        ).first()
        self.assertIsNotNone(inventory_check)

        line = ReservationInventoryCheckLine.objects.filter(
            inventory_check=inventory_check,
            room=self.room,
            item=self.towel_item,
        ).first()
        self.assertIsNotNone(line)
        self.assertEqual(line.expected_quantity, 3)
        self.assertEqual(line.reviewed_quantity, 3)
        self.assertEqual(line.difference_quantity, 0)

    def test_check_out_inventory_review_compares_against_check_in_snapshot(self):
        reservation = self._create_reservation(status=self.reservation_status_pending)
        self._create_room_line(reservation=reservation, night_rate=100000)

        confirm = self.client.post(f"/api/reservations/{reservation.id}/confirm/", data={}, format="json")
        self.assertEqual(confirm.status_code, 200)

        check_in = self.client.post(f"/api/reservations/{reservation.id}/check-in/", data={}, format="json")
        self.assertEqual(check_in.status_code, 200)

        check_out = self.client.post(
            f"/api/reservations/{reservation.id}/check-out/",
            data={
                "inventory_review": [
                    {
                        "room": self.room.id,
                        "item": self.towel_item.id,
                        "quantity": 1,
                        "notes": "Faltan dos toallas",
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(check_out.status_code, 200)
        self.assertIn("inventory_comparison", check_out.data)
        self.assertEqual(check_out.data["inventory_comparison"]["differences_count"], 1)
        self.assertEqual(check_out.data["inventory_comparison"]["missing_items_count"], 1)
        self.assertEqual(check_out.data["inventory_comparison"]["extra_items_count"], 0)

        checkout_inventory_check = ReservationInventoryCheck.objects.filter(
            reservation=reservation,
            check_type=ReservationInventoryCheck.CheckType.CHECK_OUT,
        ).first()
        self.assertIsNotNone(checkout_inventory_check)

        checkout_line = ReservationInventoryCheckLine.objects.filter(
            inventory_check=checkout_inventory_check,
            room=self.room,
            item=self.towel_item,
        ).first()
        self.assertIsNotNone(checkout_line)
        self.assertEqual(checkout_line.expected_quantity, 3)
        self.assertEqual(checkout_line.reviewed_quantity, 1)
        self.assertEqual(checkout_line.difference_quantity, -2)

        shortage_charge = Charge.objects.filter(
            reservation=reservation,
            is_active=True,
            automation_key__startswith="INVENTORY_MISSING:",
        ).first()
        self.assertIsNotNone(shortage_charge)
        self.assertEqual(shortage_charge.quantity, 2)
        self.assertEqual(shortage_charge.unit_price, self.towel_item.sale_price)
        self.assertEqual(shortage_charge.charge_type.code, "INVENTARIO_FALTANTE")
        self.assertFalse(shortage_charge.is_automatic)

    def test_cancel_endpoint_blocks_confirm_after_cancellation(self):
        reservation = self._create_reservation(status=self.reservation_status_confirmed)

        cancel = self.client.post(f"/api/reservations/{reservation.id}/cancel/", data={}, format="json")
        self.assertEqual(cancel.status_code, 200)
        self.assertEqual(cancel.data["status_code"], "CANCELADA")

        confirm_after_cancel = self.client.post(
            f"/api/reservations/{reservation.id}/confirm/",
            data={},
            format="json",
        )
        self.assertEqual(confirm_after_cancel.status_code, 400)
        self.assertIn("detail", confirm_after_cancel.data)

    def test_reservation_deposit_endpoint_validates_pending_amount(self):
        reservation = self._create_reservation(status=self.reservation_status_confirmed)
        self._create_room_line(reservation=reservation, night_rate=100000)

        ReservationDeposit.objects.create(
            reservation=reservation,
            deposit_date=timezone.now().date(),
            amount=150000,
            payment_method=self.payment_method_cash,
            status=self.deposit_status_validated,
        )

        response = self.client.post(
            "/api/reservation-deposits/",
            data={
                "reservation": reservation.id,
                "deposit_date": timezone.now().date(),
                "amount": "60000.00",
                "payment_method": self.payment_method_cash.id,
                "status": self.deposit_status_validated.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("errors", response.data)
        self.assertIn("amount", response.data["errors"])
