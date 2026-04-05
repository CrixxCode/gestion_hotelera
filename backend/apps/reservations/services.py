from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal, InvalidOperation
from typing import Iterable

from django.utils import timezone

from apps.clients.models import Client
from apps.master_data.models import MasterData
from apps.rooms.models import Room
from apps.reservations.models import ReservationRoom


INACTIVE_RESERVATION_STATUS_CODES = {
    "CANCELADA",
    "CANCELADO",
    "ANULADA",
    "ANULADO",
    "FINALIZADA",
    "FINALIZADO",
    "COMPLETADA",
    "COMPLETADO",
    "CHECKED_OUT",
    "NO_SHOW",
}

IN_HOUSE_RESERVATION_STATUS_CODES = {
    "EN_CURSO",
    "CHECKED_IN",
    "HOSPEDADO",
    "OCUPADA",
}

ROOM_STATUS_AVAILABLE = "DISPONIBLE"
ROOM_STATUS_RESERVED = "RESERVADA"
ROOM_STATUS_OCCUPIED = "OCUPADA"

RESERVATION_STATUS_PENDING = "PENDIENTE"
RESERVATION_STATUS_CONFIRMED = "CONFIRMADA"
RESERVATION_STATUS_IN_PROGRESS = "EN_CURSO"
RESERVATION_STATUS_FINISHED = "FINALIZADA"
RESERVATION_STATUS_CANCELLED = "CANCELADA"

CLIENT_STATUS_ACTIVE = "ACTIVO"
CLIENT_STATUS_CURRENT_GUEST = "HUESPED_ACTUAL"

PAYMENT_STATUS_NO_CHARGES = "SIN_CARGOS"
PAYMENT_STATUS_PENDING = "PENDIENTE"
PAYMENT_STATUS_PARTIAL = "PARCIAL"
PAYMENT_STATUS_PAID = "PAGADO"

PAYMENT_STATUS_LABELS = {
    PAYMENT_STATUS_NO_CHARGES: "Sin cargos",
    PAYMENT_STATUS_PENDING: "Pendiente",
    PAYMENT_STATUS_PARTIAL: "Parcial",
    PAYMENT_STATUS_PAID: "Pagado",
}

MONEY_ZERO = Decimal("0.00")


def _normalize_code(value) -> str:
    return str(value or "").strip().upper()


def get_master_data_code(group: str, code: str):
    normalized_code = _normalize_code(code)
    if not normalized_code:
        return None

    return MasterData.objects.filter(group=group, code=normalized_code, is_active=True).first()


def get_reservation_status_by_code(code: str):
    return get_master_data_code(MasterData.Group.RESERVATION_STATUS, code)


def _to_decimal(value) -> Decimal:
    if value is None:
        return MONEY_ZERO
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return MONEY_ZERO


def _iter_reservation_rooms(reservation):
    prefetched = getattr(reservation, "_prefetched_objects_cache", {}).get("rooms_detail")
    if prefetched is not None:
        return prefetched
    return reservation.rooms_detail.all()


def _iter_reservation_deposits(reservation):
    prefetched = getattr(reservation, "_prefetched_objects_cache", {}).get("deposits")
    if prefetched is not None:
        return prefetched
    return reservation.deposits.all()


def _iter_reservation_charges(reservation):
    prefetched = getattr(reservation, "_prefetched_objects_cache", {}).get("charges")
    if prefetched is not None:
        return prefetched
    return reservation.charges.all()


def get_reservation_financials(reservation, *, exclude_deposit_id: int | None = None) -> dict[str, Decimal]:
    nights = max(int(getattr(reservation, "total_nights", 0) or 0), 0)

    rooms_subtotal = MONEY_ZERO
    for room in _iter_reservation_rooms(reservation):
        subtotal = getattr(room, "subtotal", None)
        if subtotal is None:
            subtotal = _to_decimal(getattr(room, "night_rate", 0)) * Decimal(nights)
        rooms_subtotal += _to_decimal(subtotal)

    package_subtotal = _to_decimal(getattr(reservation, "package_price", 0))
    if package_subtotal < MONEY_ZERO:
        package_subtotal = MONEY_ZERO

    total_discount = _to_decimal(getattr(reservation, "total_discount", 0))
    if total_discount < MONEY_ZERO:
        total_discount = MONEY_ZERO

    additional_charges_total = MONEY_ZERO
    for charge in _iter_reservation_charges(reservation):
        if not getattr(charge, "is_active", True):
            continue
        if getattr(charge, "is_automatic", False):
            continue
        additional_charges_total += _to_decimal(getattr(charge, "total_amount", 0))

    total_amount = rooms_subtotal + package_subtotal + additional_charges_total - total_discount
    if total_amount < MONEY_ZERO:
        total_amount = MONEY_ZERO

    total_deposits = MONEY_ZERO
    for deposit in _iter_reservation_deposits(reservation):
        if exclude_deposit_id and getattr(deposit, "id", None) == exclude_deposit_id:
            continue
        total_deposits += _to_decimal(getattr(deposit, "amount", 0))

    pending_amount = total_amount - total_deposits
    if pending_amount < MONEY_ZERO:
        pending_amount = MONEY_ZERO

    return {
        "rooms_subtotal": rooms_subtotal,
        "package_subtotal": package_subtotal,
        "additional_charges_total": additional_charges_total,
        "total_discount": total_discount,
        "total_amount": total_amount,
        "total_deposits": total_deposits,
        "pending_amount": pending_amount,
    }


def get_reservation_payment_status(
    reservation,
    *,
    financials: dict[str, Decimal] | None = None,
) -> dict[str, str]:
    values = financials or get_reservation_financials(reservation)
    total_amount = values["total_amount"]
    total_deposits = values["total_deposits"]
    pending_amount = values["pending_amount"]

    if total_amount <= MONEY_ZERO and total_deposits <= MONEY_ZERO:
        code = PAYMENT_STATUS_NO_CHARGES
    elif pending_amount <= MONEY_ZERO and total_amount > MONEY_ZERO:
        code = PAYMENT_STATUS_PAID
    elif total_deposits > MONEY_ZERO and pending_amount > MONEY_ZERO:
        code = PAYMENT_STATUS_PARTIAL
    else:
        code = PAYMENT_STATUS_PENDING

    return {
        "code": code,
        "label": PAYMENT_STATUS_LABELS[code],
    }


def get_reservation_flow_permissions(reservation) -> dict[str, bool]:
    status_code = _normalize_code(getattr(reservation, "status_code", None))
    has_check_in = getattr(reservation, "real_check_in", None) is not None
    has_check_out = getattr(reservation, "real_check_out", None) is not None

    can_confirm = (
        status_code == RESERVATION_STATUS_PENDING
        and not has_check_in
        and not has_check_out
    )
    can_check_in = (
        status_code == RESERVATION_STATUS_CONFIRMED
        and not has_check_in
        and not has_check_out
    )
    can_check_out = (
        (status_code == RESERVATION_STATUS_IN_PROGRESS or has_check_in)
        and not has_check_out
    )
    can_cancel = (
        status_code in {RESERVATION_STATUS_PENDING, RESERVATION_STATUS_CONFIRMED}
        and not has_check_in
        and not has_check_out
    )

    return {
        "can_confirm": can_confirm,
        "can_check_in": can_check_in,
        "can_check_out": can_check_out,
        "can_cancel": can_cancel,
    }


def can_add_payment_to_reservation(
    reservation,
    *,
    financials: dict[str, Decimal] | None = None,
) -> bool:
    status_code = _normalize_code(getattr(reservation, "status_code", None))
    if status_code == RESERVATION_STATUS_CANCELLED:
        return False

    values = financials or get_reservation_financials(reservation)
    if values["total_amount"] <= MONEY_ZERO:
        return False

    return values["pending_amount"] > MONEY_ZERO


def validate_reservation_deposit_rules(
    reservation,
    amount,
    *,
    exclude_deposit_id: int | None = None,
) -> dict[str, str]:
    errors: dict[str, str] = {}

    if reservation is None:
        errors["reservation"] = "Reservation is required."
        return errors

    status_code = _normalize_code(getattr(reservation, "status_code", None))
    if status_code == RESERVATION_STATUS_CANCELLED:
        errors["reservation"] = "No puedes registrar pagos en una reserva cancelada."
        return errors

    amount_decimal = _to_decimal(amount)
    if amount_decimal <= MONEY_ZERO:
        errors["amount"] = "Deposit amount must be greater than zero."
        return errors

    financials = get_reservation_financials(
        reservation,
        exclude_deposit_id=exclude_deposit_id,
    )

    if financials["total_amount"] <= MONEY_ZERO:
        errors["amount"] = "La reserva no tiene cargos para registrar pagos."
        return errors

    if financials["pending_amount"] <= MONEY_ZERO:
        errors["amount"] = "La reserva ya esta completamente pagada."
        return errors

    if amount_decimal > financials["pending_amount"]:
        errors["amount"] = (
            f"El monto no puede superar el saldo pendiente ({financials['pending_amount']})."
        )
        return errors

    return errors


def is_reservation_inactive(reservation) -> bool:
    if reservation.real_check_out is not None:
        return True
    return _normalize_code(getattr(reservation, "status_code", None)) in INACTIVE_RESERVATION_STATUS_CODES


def is_reservation_in_house(reservation) -> bool:
    if reservation.real_check_out is not None:
        return False
    if reservation.real_check_in is not None:
        return True
    return _normalize_code(getattr(reservation, "status_code", None)) in IN_HOUSE_RESERVATION_STATUS_CODES


def _reservation_check_in_started(reservation, room: Room) -> bool:
    if reservation.real_check_out is not None:
        return False

    if reservation.real_check_in is not None:
        return True

    check_in_date = reservation.expected_check_in
    if not check_in_date:
        return False

    hotel_settings = getattr(getattr(room, "floor", None), "hotel_settings", None)
    check_in_time = getattr(hotel_settings, "check_in_time", None) or time(0, 0)

    check_in_datetime = datetime.combine(check_in_date, check_in_time)
    if timezone.is_naive(check_in_datetime):
        check_in_datetime = timezone.make_aware(check_in_datetime, timezone.get_current_timezone())

    return timezone.now() >= check_in_datetime


def find_overlapping_reservation_room(
    *,
    room_id: int,
    expected_check_in,
    expected_check_out,
    exclude_reservation_id: int | None = None,
    exclude_reservation_room_id: int | None = None,
):
    if not room_id or not expected_check_in or not expected_check_out:
        return None

    queryset = ReservationRoom.objects.select_related("reservation", "reservation__status").filter(
        room_id=room_id,
        reservation__expected_check_in__lt=expected_check_out,
        reservation__expected_check_out__gt=expected_check_in,
        reservation__real_check_out__isnull=True,
    ).exclude(
        reservation__status__code__in=INACTIVE_RESERVATION_STATUS_CODES
    )

    if exclude_reservation_id:
        queryset = queryset.exclude(reservation_id=exclude_reservation_id)
    if exclude_reservation_room_id:
        queryset = queryset.exclude(id=exclude_reservation_room_id)

    return queryset.order_by("reservation__expected_check_in", "id").first()


def _get_room_status(code: str):
    return MasterData.objects.filter(
        group=MasterData.Group.ROOM_STATUS,
        code=_normalize_code(code),
    ).first()


def _set_room_status(room: Room, status_code: str) -> bool:
    status = _get_room_status(status_code)
    if not status:
        return False
    if room.status_id == status.id:
        return False
    Room.objects.filter(id=room.id).update(status=status)
    room.status = status
    return True


def _get_desired_room_status_code(room: Room) -> str | None:
    reservation_details = list(
        room.reservation_details.select_related("reservation", "reservation__status")
        .filter(reservation__real_check_out__isnull=True)
        .exclude(reservation__status__code__in=INACTIVE_RESERVATION_STATUS_CODES)
    )
    if not reservation_details:
        return None

    if any(is_reservation_in_house(detail.reservation) for detail in reservation_details):
        return ROOM_STATUS_OCCUPIED

    if any(_reservation_check_in_started(detail.reservation, room) for detail in reservation_details):
        return ROOM_STATUS_RESERVED

    return None


def sync_room_status_from_reservations(room: Room) -> bool:
    desired_status_code = _get_desired_room_status_code(room)
    current_status_code = _normalize_code(getattr(room.status, "code", None))

    if desired_status_code:
        if desired_status_code == ROOM_STATUS_RESERVED and not _get_room_status(ROOM_STATUS_RESERVED):
            desired_status_code = ROOM_STATUS_OCCUPIED
        return _set_room_status(room, desired_status_code)

    if current_status_code in {ROOM_STATUS_RESERVED, ROOM_STATUS_OCCUPIED}:
        return _set_room_status(room, ROOM_STATUS_AVAILABLE)

    return False


def sync_room_status_by_id(room_id: int | None) -> bool:
    if not room_id:
        return False

    room = Room.objects.select_related("status", "floor__hotel_settings").filter(id=room_id).first()
    if not room:
        return False

    return sync_room_status_from_reservations(room)


def sync_room_status_for_room_ids(room_ids: Iterable[int]) -> int:
    unique_ids = sorted({room_id for room_id in room_ids if room_id})
    changed = 0
    for room_id in unique_ids:
        if sync_room_status_by_id(room_id):
            changed += 1
    return changed


def sync_room_status_for_reservation(reservation) -> None:
    if not getattr(reservation, "id", None):
        return

    room_ids = reservation.rooms_detail.values_list("room_id", flat=True).distinct()
    sync_room_status_for_room_ids(room_ids)


def sync_client_status_by_id(client_id: int | None) -> bool:
    if not client_id:
        return False

    client = Client.objects.select_related("status").filter(id=client_id).first()
    if not client:
        return False

    has_in_house_reservation = ReservationRoom.objects.select_related("reservation", "reservation__status").filter(
        reservation__client_id=client_id,
        reservation__real_check_out__isnull=True,
    ).exclude(
        reservation__status__code__in=INACTIVE_RESERVATION_STATUS_CODES
    ).filter(
        reservation__real_check_in__isnull=False
    ).exists()

    current_status_code = _normalize_code(getattr(client.status, "code", None))

    if has_in_house_reservation:
        target_status = get_master_data_code(MasterData.Group.CLIENT_STATUS, CLIENT_STATUS_CURRENT_GUEST)
        if not target_status or client.status_id == target_status.id:
            return False
        Client.objects.filter(id=client_id).update(status=target_status)
        client.status = target_status
        return True

    if current_status_code != CLIENT_STATUS_CURRENT_GUEST:
        return False

    fallback_status = get_master_data_code(MasterData.Group.CLIENT_STATUS, CLIENT_STATUS_ACTIVE)
    if not fallback_status or client.status_id == fallback_status.id:
        return False

    Client.objects.filter(id=client_id).update(status=fallback_status)
    client.status = fallback_status
    return True


def sync_client_status_for_reservation(reservation) -> bool:
    return sync_client_status_by_id(getattr(reservation, "client_id", None))


def sync_all_room_statuses() -> tuple[int, int]:
    queryset = Room.objects.select_related("status", "floor__hotel_settings").order_by("id")
    processed = 0
    changed = 0
    for room in queryset:
        processed += 1
        if sync_room_status_from_reservations(room):
            changed += 1
    return processed, changed
