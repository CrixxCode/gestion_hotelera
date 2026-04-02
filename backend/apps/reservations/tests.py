from datetime import time, timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.clients.models import Client
from apps.hotel_settings.models import HotelFloor, HotelSettings
from apps.master_data.models import MasterData
from apps.reservations.models import Reservation, ReservationRoom
from apps.reservations.serializers import ReservationRoomSerializer, ReservationWriteSerializer
from apps.rooms.models import Room


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

        self.reservation_status_confirmed = self._md(
            MasterData.Group.RESERVATION_STATUS, "CONFIRMADA", "Confirmada", 1
        )
        self.reservation_status_cancelled = self._md(
            MasterData.Group.RESERVATION_STATUS, "CANCELADA", "Cancelada", 2
        )
        self.reservation_origin = self._md(MasterData.Group.RESERVATION_ORIGIN, "WEB", "Web", 1)

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
