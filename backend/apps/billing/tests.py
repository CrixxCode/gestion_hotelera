from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.billing.models import Charge, Invoice, Payment
from apps.billing.serializers import ChargeSerializer
from apps.billing.services import get_or_create_default_charge_type
from apps.clients.models import Client
from apps.hotel_settings.models import HotelFloor, HotelSettings
from apps.master_data.models import MasterData
from apps.packages.models import Package
from apps.reservations.models import Reservation, ReservationRoom
from apps.reservations.services import get_reservation_financials
from apps.rooms.models import Room
from apps.services.models import Service


class BillingAutomationTestCase(TestCase):
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

        self.room_type = self._md(MasterData.Group.ROOM_TYPE, "STD", "Standard", 1)
        self.room_status = self._md(MasterData.Group.ROOM_STATUS, "DISPONIBLE", "Disponible", 1)

        self.reservation_status = self._md(
            MasterData.Group.RESERVATION_STATUS,
            "CONFIRMADA",
            "Confirmada",
            1,
        )
        self.reservation_origin = self._md(
            MasterData.Group.RESERVATION_ORIGIN,
            "WEB",
            "Web",
            1,
        )
        self.service_type = self._md(MasterData.Group.SERVICE_TYPE, "ROOMSERVICE", "Room Service", 1)
        self.payment_method = self._md(MasterData.Group.PAYMENT_METHOD, "EFECTIVO", "Efectivo", 1)

        self.hotel_settings = HotelSettings.objects.create(hotel_name="Hotel Test")
        self.floor = HotelFloor.objects.create(
            hotel_settings=self.hotel_settings,
            floor_number=1,
            name="Piso 1",
            prefix="1",
            room_count=1,
        )
        self.room = Room.objects.create(
            number="101",
            room_type=self.room_type,
            floor=self.floor,
            status=self.room_status,
        )
        self.client = Client.objects.create(
            document_type=self.document_type,
            document_number="1234567890",
            first_name="Ana",
            last_name="Lopez",
            email="ana.billing@example.com",
            phone="3001234567",
            country="CO",
            client_type=self.client_type,
            status=self.client_status,
        )
        self.package = Package.objects.create(
            hotel_settings=self.hotel_settings,
            room_type=self.room_type,
            name="Paquete Standard",
            base_price=Decimal("25000.00"),
            is_active=True,
        )
        self.service = Service.objects.create(
            hotel_settings=self.hotel_settings,
            service_type=self.service_type,
            name="Minibar",
            base_price=Decimal("15000.00"),
            is_active=True,
        )

        today = timezone.now().date()
        self.reservation = Reservation.objects.create(
            client=self.client,
            status=self.reservation_status,
            origin=self.reservation_origin,
            package=self.package,
            package_name=self.package.name,
            package_price=self.package.base_price,
            expected_check_in=today + timedelta(days=1),
            expected_check_out=today + timedelta(days=3),
        )

    def _get_reservation_invoice(self):
        return (
            Invoice.objects.filter(reservation=self.reservation, is_active=True)
            .order_by("id")
            .first()
        )

    def _create_payment(self, invoice, amount: str):
        return Payment.objects.create(
            invoice=invoice,
            payment_method=self.payment_method,
            amount=Decimal(amount),
            is_active=True,
        )

    def test_creates_default_invoice_when_reservation_is_created(self):
        invoice = self._get_reservation_invoice()

        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.status.code, "BORRADOR")
        self.assertTrue(invoice.invoice_number.startswith("FAC-"))
        self.assertEqual(invoice.subtotal, Decimal("25000.00"))
        self.assertEqual(invoice.total_amount, Decimal("25000.00"))

    def test_does_not_duplicate_invoice_on_reservation_update(self):
        self.reservation.notes = "Actualizada"
        self.reservation.save(update_fields=["notes"])

        self.assertEqual(
            Invoice.objects.filter(reservation=self.reservation, is_active=True).count(),
            1,
        )

    def test_updates_invoice_subtotal_on_room_and_manual_charge_changes(self):
        invoice = self._get_reservation_invoice()
        self.assertIsNotNone(invoice)

        ReservationRoom.objects.create(
            reservation=self.reservation,
            room=self.room,
            night_rate=Decimal("100000.00"),
            adults=2,
            children=0,
        )

        invoice.refresh_from_db()
        self.assertEqual(invoice.subtotal, Decimal("225000.00"))
        self.assertEqual(invoice.total_amount, Decimal("225000.00"))

        extra_type = get_or_create_default_charge_type("OTRO")
        manual_charge = Charge.objects.create(
            reservation=self.reservation,
            charge_type=extra_type,
            description="Consumo snack bar",
            quantity=2,
            unit_price=Decimal("15000.00"),
            is_active=True,
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.subtotal, Decimal("255000.00"))

        manual_charge.is_active = False
        manual_charge.save(update_fields=["is_active"])
        invoice.refresh_from_db()
        self.assertEqual(invoice.subtotal, Decimal("225000.00"))

    def test_updates_invoice_status_to_emitida_and_pagada_on_payments(self):
        invoice = self._get_reservation_invoice()
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.status.code, "BORRADOR")

        self._create_payment(invoice, "5000.00")
        invoice.refresh_from_db()
        self.assertEqual(invoice.status.code, "EMITIDA")

        self._create_payment(invoice, "20000.00")
        invoice.refresh_from_db()
        self.assertEqual(invoice.status.code, "PAGADA")

    def test_reverts_invoice_status_when_pending_balance_returns(self):
        invoice = self._get_reservation_invoice()
        self.assertIsNotNone(invoice)

        self._create_payment(invoice, "25000.00")
        invoice.refresh_from_db()
        self.assertEqual(invoice.status.code, "PAGADA")

        extra_type = get_or_create_default_charge_type("OTRO")
        Charge.objects.create(
            reservation=self.reservation,
            charge_type=extra_type,
            description="Cargo adicional",
            quantity=1,
            unit_price=Decimal("10000.00"),
            is_active=True,
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.status.code, "EMITIDA")

        payment = Payment.objects.filter(invoice=invoice, is_active=True).first()
        self.assertIsNotNone(payment)
        payment.is_active = False
        payment.save(update_fields=["is_active"])
        invoice.refresh_from_db()
        self.assertEqual(invoice.status.code, "BORRADOR")

    def test_creates_and_updates_automatic_room_and_package_charges(self):
        reservation_room = ReservationRoom.objects.create(
            reservation=self.reservation,
            room=self.room,
            night_rate=Decimal("100000.00"),
            adults=2,
            children=0,
        )

        room_key = f"ROOM:{reservation_room.id}"
        room_charge = Charge.objects.get(
            reservation=self.reservation,
            is_automatic=True,
            automation_key=room_key,
        )
        package_charge = Charge.objects.get(
            reservation=self.reservation,
            is_automatic=True,
            automation_key="PACKAGE",
        )

        self.assertEqual(room_charge.charge_type.code, "HABITACION")
        self.assertTrue(room_charge.is_active)
        self.assertEqual(room_charge.quantity, 1)
        self.assertEqual(room_charge.total_amount, Decimal("200000.00"))

        self.assertEqual(package_charge.charge_type.code, "PAQUETE")
        self.assertTrue(package_charge.is_active)
        self.assertEqual(package_charge.total_amount, Decimal("25000.00"))

    def test_deactivates_automatic_room_charge_when_room_line_is_deleted(self):
        reservation_room = ReservationRoom.objects.create(
            reservation=self.reservation,
            room=self.room,
            night_rate=Decimal("120000.00"),
            adults=2,
            children=0,
        )
        room_key = f"ROOM:{reservation_room.id}"
        reservation_room.delete()

        room_charge = Charge.objects.get(
            reservation=self.reservation,
            is_automatic=True,
            automation_key=room_key,
        )
        self.assertFalse(room_charge.is_active)

    def test_financials_include_manual_extra_charges_without_double_counting_automatic(self):
        ReservationRoom.objects.create(
            reservation=self.reservation,
            room=self.room,
            night_rate=Decimal("100000.00"),
            adults=2,
            children=0,
        )
        self.reservation.total_discount = Decimal("10000.00")
        self.reservation.save(update_fields=["total_discount"])

        extra_type = get_or_create_default_charge_type("OTRO")
        Charge.objects.create(
            reservation=self.reservation,
            charge_type=extra_type,
            description="Consumo de minibar",
            quantity=2,
            unit_price=Decimal("15000.00"),
            is_active=True,
        )

        financials = get_reservation_financials(self.reservation)

        self.assertEqual(financials["rooms_subtotal"], Decimal("200000.00"))
        self.assertEqual(financials["package_subtotal"], Decimal("25000.00"))
        self.assertEqual(financials["additional_charges_total"], Decimal("30000.00"))
        self.assertEqual(financials["total_amount"], Decimal("245000.00"))

    def test_charge_serializer_autofills_service_charge_defaults(self):
        serializer = ChargeSerializer(
            data={
                "reservation": self.reservation.id,
                "service": self.service.id,
                "quantity": 2,
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

        charge = serializer.save()

        self.assertEqual(charge.charge_type.code, "SERVICIO")
        self.assertEqual(charge.description, "Servicio: Minibar")
        self.assertEqual(charge.unit_price, Decimal("15000.00"))
        self.assertEqual(charge.total_amount, Decimal("30000.00"))
