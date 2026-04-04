from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.clients.models import Client
from apps.master_data.models import MasterData
from apps.rooms.models import Room
from apps.hotel_settings.models import ReservationPolicy


class Reservation(models.Model):
    client = models.ForeignKey(
        Client,
        on_delete=models.PROTECT,
        related_name="reservations",
    )
    status = models.ForeignKey(
        MasterData,
        on_delete=models.PROTECT,
        related_name="reservations_by_status",
        limit_choices_to={"group": MasterData.Group.RESERVATION_STATUS},
    )
    origin = models.ForeignKey(
        MasterData,
        on_delete=models.PROTECT,
        related_name="reservations_by_origin",
        limit_choices_to={"group": MasterData.Group.RESERVATION_ORIGIN},
    )
    policies = models.ManyToManyField(
        ReservationPolicy,
        related_name="reservations",
        blank=True,
    )

    expected_check_in = models.DateField()
    expected_check_out = models.DateField()
    real_check_in = models.DateTimeField(blank=True, null=True)
    real_check_out = models.DateTimeField(blank=True, null=True)

    promo_code = models.CharField(max_length=50, blank=True, null=True)
    total_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    notes = models.TextField(blank=True, null=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_reservations",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reservation"
        ordering = ["-id"]

    @property
    def status_code(self):
        return self.status.code if self.status else None

    @property
    def origin_code(self):
        return self.origin.code if self.origin else None

    @property
    def total_guests(self):
        return sum(item.adults + item.children for item in self.rooms_detail.all())

    @property
    def total_rooms(self):
        return self.rooms_detail.count()

    @property
    def total_nights(self):
        if self.expected_check_in and self.expected_check_out:
            return (self.expected_check_out - self.expected_check_in).days
        return 0

    def clean(self):
        errors = {}

        if self.expected_check_in and self.expected_check_out:
            if self.expected_check_out <= self.expected_check_in:
                errors["expected_check_out"] = "Expected check-out must be later than expected check-in."

        if self.real_check_out and not self.real_check_in:
            errors["real_check_out"] = "Real check-out cannot be registered without a real check-in."

        if self.real_check_in and self.real_check_out:
            if self.real_check_out < self.real_check_in:
                errors["real_check_out"] = "Real check-out cannot be earlier than real check-in."

        if self.total_discount is not None and self.total_discount < 0:
            errors["total_discount"] = "Total discount cannot be negative."

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"Reservation #{self.id} - {self.client.full_name}"


class ReservationRoom(models.Model):
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="rooms_detail",
    )
    room = models.ForeignKey(
        Room,
        on_delete=models.PROTECT,
        related_name="reservation_details",
    )
    night_rate = models.DecimalField(max_digits=10, decimal_places=2)
    adults = models.PositiveIntegerField(default=1)
    children = models.PositiveIntegerField(default=0)
    meal_plan = models.ForeignKey(
        MasterData,
        on_delete=models.PROTECT,
        related_name="reservation_rooms_by_meal_plan",
        limit_choices_to={"group": MasterData.Group.MEAL_PLAN},
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reservation_room"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["reservation", "room"],
                name="uq_reservation_room_unique",
            )
        ]

    @property
    def meal_plan_code(self):
        return self.meal_plan.code if self.meal_plan else None

    @property
    def subtotal(self):
        nights = self.reservation.total_nights
        return self.night_rate * nights

    def clean(self):
        errors = {}

        if self.night_rate is not None and self.night_rate < 0:
            errors["night_rate"] = "Night rate cannot be negative."

        if self.adults < 1:
            errors["adults"] = "There must be at least one adult assigned to the room."

        if self.children < 0:
            errors["children"] = "Children cannot be negative."

        if self.room_id and self.reservation_id:
            from apps.reservations.services import find_overlapping_reservation_room

            conflict = find_overlapping_reservation_room(
                room_id=self.room_id,
                expected_check_in=self.reservation.expected_check_in,
                expected_check_out=self.reservation.expected_check_out,
                exclude_reservation_room_id=self.id,
            )
            if conflict:
                conflict_reservation = conflict.reservation
                errors["room"] = (
                    f"Room {self.room.number} already has an active reservation "
                    f"(#{conflict_reservation.id}) from "
                    f"{conflict_reservation.expected_check_in} to "
                    f"{conflict_reservation.expected_check_out}."
                )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"Reservation #{self.reservation.id} - Room {self.room.number}"


class ReservationGuest(models.Model):
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="guests",
    )
    document_type = models.ForeignKey(
        MasterData,
        on_delete=models.PROTECT,
        related_name="reservation_guests_document_type",
        limit_choices_to={"group": MasterData.Group.DOCUMENT_TYPE},
    )
    document_number = models.CharField(max_length=40)
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    birth_date = models.DateField(blank=True, null=True)
    nationality = models.CharField(max_length=80, blank=True, null=True)
    blood_type = models.CharField(max_length=10, blank=True, null=True)
    emergency_contact_name = models.CharField(max_length=120, blank=True, null=True)
    emergency_contact_phone = models.CharField(max_length=40, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reservation_guest"
        ordering = ["-id"]
        unique_together = ("reservation", "document_type", "document_number")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def document_type_code(self):
        return self.document_type.code if self.document_type else None

    def __str__(self):
        return f"{self.full_name} - Reservation #{self.reservation.id}"


class ReservationDeposit(models.Model):
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="deposits",
    )
    deposit_date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.ForeignKey(
        MasterData,
        on_delete=models.PROTECT,
        related_name="reservation_deposits_by_payment_method",
        limit_choices_to={"group": MasterData.Group.PAYMENT_METHOD},
    )
    reference = models.CharField(max_length=100, blank=True, null=True)
    status = models.ForeignKey(
        MasterData,
        on_delete=models.PROTECT,
        related_name="reservation_deposits_by_status",
        limit_choices_to={"group": MasterData.Group.RESERVATION_DEPOSIT_STATUS},
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reservation_deposit"
        ordering = ["-id"]

    @property
    def payment_method_code(self):
        return self.payment_method.code if self.payment_method else None

    @property
    def status_code(self):
        return self.status.code if self.status else None

    def clean(self):
        errors = {}

        if self.amount is not None and self.amount <= 0:
            errors["amount"] = "Deposit amount must be greater than zero."

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"Deposit #{self.id} - Reservation #{self.reservation.id}"
