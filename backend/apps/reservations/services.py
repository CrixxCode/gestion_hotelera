from __future__ import annotations

from datetime import date as date_cls, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from apps.clients.models import Client
from apps.inventory.models import Item, RoomInventory
from apps.master_data.models import MasterData
from apps.rooms.models import CleaningTask, Room
from apps.reservations.models import (
    ReservationInventoryCheck,
    ReservationInventoryCheckLine,
    ReservationRoom,
)


INACTIVE_RESERVATION_STATUS_CODES = {
    "CANCELADA",
    "CANCELADO",
    "CANCELLED",
    "ANULADA",
    "ANULADO",
    "FINALIZADA",
    "FINALIZADO",
    "FINISHED",
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
ROOM_STATUS_CLEANING = "LIMPIEZA"
ROOM_STATUS_BOOKING_BLOCKED_CODES = {
    "MANTENIMIENTO",
    "LIMPIEZA",
}

CLEANING_TASK_TYPE_CHECK_OUT = "SALIDA"
CLEANING_STATUS_PENDING = "PENDIENTE"
CLEANING_STATUS_IN_PROGRESS = "EN_PROCESO"
CLEANING_ACTIVE_STATUS_CODES = {
    CLEANING_STATUS_PENDING,
    CLEANING_STATUS_IN_PROGRESS,
}

INVENTORY_CHECK_TYPE_CHECK_IN = ReservationInventoryCheck.CheckType.CHECK_IN
INVENTORY_CHECK_TYPE_CHECK_OUT = ReservationInventoryCheck.CheckType.CHECK_OUT

RESERVATION_STATUS_PENDING = "PENDIENTE"
RESERVATION_STATUS_CONFIRMED = "CONFIRMADA"
RESERVATION_STATUS_IN_PROGRESS = "EN_CURSO"
RESERVATION_STATUS_FINISHED = "FINALIZADA"
RESERVATION_STATUS_CANCELLED = "CANCELADA"

RESERVATION_STATUS_PENDING_CODES = (
    RESERVATION_STATUS_PENDING,
    "PENDING",
)
RESERVATION_STATUS_CONFIRMED_CODES = (
    RESERVATION_STATUS_CONFIRMED,
    "CONFIRMADO",
    "CONFIRMED",
)
RESERVATION_STATUS_IN_PROGRESS_CODES = (
    RESERVATION_STATUS_IN_PROGRESS,
    "CHECKED_IN",
    "IN_PROGRESS",
)
RESERVATION_STATUS_FINISHED_CODES = (
    RESERVATION_STATUS_FINISHED,
    "FINALIZADO",
    "CHECKED_OUT",
    "FINISHED",
    "COMPLETADA",
    "COMPLETADO",
)
RESERVATION_STATUS_CANCELLED_CODES = (
    RESERVATION_STATUS_CANCELLED,
    "CANCELADO",
    "ANULADA",
    "ANULADO",
    "CANCELLED",
)

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
ADULT_AGE_THRESHOLD = 18
REFUND_IMPACT_STATUS_CODES = {"APROBADO", "PROCESADO"}


def _normalize_code(value) -> str:
    return str(value or "").strip().upper()


def is_room_status_blocked_for_reservation(code) -> bool:
    return _normalize_code(code) in ROOM_STATUS_BOOKING_BLOCKED_CODES


def get_master_data_code(group: str, code: str):
    normalized_code = _normalize_code(code)
    if not normalized_code:
        return None

    return MasterData.objects.filter(group=group, code=normalized_code, is_active=True).first()


def get_master_data_code_any(group: str, codes: Iterable[str]):
    normalized_codes = [_normalize_code(code) for code in codes if _normalize_code(code)]
    if not normalized_codes:
        return None

    candidates = {
        item.code: item
        for item in MasterData.objects.filter(
            group=group,
            code__in=normalized_codes,
            is_active=True,
        )
    }

    for code in normalized_codes:
        if code in candidates:
            return candidates[code]

    return None


def get_reservation_status_by_code(code: str):
    return get_master_data_code(MasterData.Group.RESERVATION_STATUS, code)


def get_reservation_status_by_codes(codes: Iterable[str]):
    return get_master_data_code_any(MasterData.Group.RESERVATION_STATUS, codes)


def _code_in_aliases(value, aliases: Iterable[str]) -> bool:
    normalized_value = _normalize_code(value)
    if not normalized_value:
        return False
    return normalized_value in {_normalize_code(alias) for alias in aliases}


def is_reservation_status_pending(code) -> bool:
    return _code_in_aliases(code, RESERVATION_STATUS_PENDING_CODES)


def is_reservation_status_confirmed(code) -> bool:
    return _code_in_aliases(code, RESERVATION_STATUS_CONFIRMED_CODES)


def is_reservation_status_in_progress(code) -> bool:
    return _code_in_aliases(code, RESERVATION_STATUS_IN_PROGRESS_CODES)


def is_reservation_status_finished(code) -> bool:
    return _code_in_aliases(code, RESERVATION_STATUS_FINISHED_CODES)


def is_reservation_status_cancelled(code) -> bool:
    return _code_in_aliases(code, RESERVATION_STATUS_CANCELLED_CODES)


def get_pending_reservation_status():
    return get_reservation_status_by_codes(RESERVATION_STATUS_PENDING_CODES)


def get_confirmed_reservation_status():
    return get_reservation_status_by_codes(RESERVATION_STATUS_CONFIRMED_CODES)


def get_in_progress_reservation_status():
    return get_reservation_status_by_codes(RESERVATION_STATUS_IN_PROGRESS_CODES)


def get_finished_reservation_status():
    return get_reservation_status_by_codes(RESERVATION_STATUS_FINISHED_CODES)


def get_cancelled_reservation_status():
    return get_reservation_status_by_codes(RESERVATION_STATUS_CANCELLED_CODES)


def has_active_rate_for_room_type(room_type_id: int | None) -> bool:
    if not room_type_id:
        return False

    from apps.rooms.models import Rate

    return Rate.objects.filter(room_type_id=room_type_id, is_active=True).exists()


def find_active_rate_for_room_type_dates(
    *,
    room_type_id: int | None,
    expected_check_in=None,
    expected_check_out=None,
):
    if not room_type_id:
        return None

    from apps.rooms.models import Rate

    queryset = Rate.objects.filter(
        room_type_id=room_type_id,
        is_active=True,
    )

    if expected_check_in:
        queryset = queryset.filter(
            Q(start_date__isnull=True) | Q(start_date__lte=expected_check_in)
        )

    if expected_check_out:
        queryset = queryset.filter(
            Q(end_date__isnull=True) | Q(end_date__gte=expected_check_out)
        )

    return queryset.order_by("-start_date", "-created_at", "-id").first()


def _calculate_age_in_years(*, birth_date: date_cls, reference_date: date_cls) -> int:
    age = reference_date.year - birth_date.year
    if (reference_date.month, reference_date.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age


def get_reservation_guest_age_breakdown(
    reservation,
    *,
    reference_date: date_cls | None = None,
) -> dict[str, int]:
    if not reservation:
        return {"adults": 0, "children": 0, "total": 0}

    as_of_date = reference_date or getattr(reservation, "expected_check_in", None) or timezone.localdate()
    if isinstance(as_of_date, datetime):
        as_of_date = as_of_date.date()

    guests = getattr(reservation, "_prefetched_objects_cache", {}).get("guests")
    if guests is None:
        guests = reservation.guests.all()

    adults = 0
    children = 0
    for guest in guests:
        birth_date = getattr(guest, "birth_date", None)
        if not birth_date:
            adults += 1
            continue

        age = _calculate_age_in_years(birth_date=birth_date, reference_date=as_of_date)
        if age < ADULT_AGE_THRESHOLD:
            children += 1
        else:
            adults += 1

    return {
        "adults": adults,
        "children": children,
        "total": adults + children,
    }


def _distribute_guests_across_rooms(
    *,
    room_capacities: list[int],
    room_count: int,
    adults: int,
    children: int,
) -> list[tuple[int, int]]:
    if room_count <= 0:
        return []

    if len(room_capacities) != room_count:
        raise ValidationError(
            {
                "rooms_detail": (
                    "No se pudo distribuir la ocupacion porque la capacidad de las habitaciones "
                    "no coincide con la asignacion actual."
                )
            }
        )

    if adults < room_count:
        raise ValidationError(
            {
                "adults": (
                    "Debe existir al menos un adulto por habitacion para distribuir "
                    "la ocupacion automaticamente."
                )
            }
        )

    total_capacity = sum(room_capacities)
    total_guests = adults + children
    if total_guests > total_capacity:
        raise ValidationError(
            {
                "rooms_detail": (
                    f"La ocupacion total ({total_guests} huespedes) supera la capacidad total "
                    f"({total_capacity}) de las habitaciones seleccionadas."
                )
            }
        )

    adults_by_room = [1 for _ in range(room_count)]
    remaining_slots = [max(capacity - 1, 0) for capacity in room_capacities]

    remaining_adults = adults - room_count
    index = 0
    while remaining_adults > 0:
        if sum(remaining_slots) <= 0:
            raise ValidationError(
                {
                    "rooms_detail": (
                        "La capacidad de las habitaciones no permite ubicar todos los adultos."
                    )
                }
            )

        room_index = index % room_count
        if remaining_slots[room_index] <= 0:
            index += 1
            continue

        adults_by_room[room_index] += 1
        remaining_slots[room_index] -= 1
        remaining_adults -= 1
        index += 1

    children_by_room = [0 for _ in range(room_count)]
    index = 0
    remaining_children = max(children, 0)
    while remaining_children > 0:
        if sum(remaining_slots) <= 0:
            raise ValidationError(
                {
                    "rooms_detail": (
                        "La capacidad de las habitaciones no permite ubicar todos los ninos."
                    )
                }
            )

        room_index = index % room_count
        if remaining_slots[room_index] <= 0:
            index += 1
            continue

        children_by_room[room_index] += 1
        remaining_slots[room_index] -= 1
        remaining_children -= 1
        index += 1

    return list(zip(adults_by_room, children_by_room))


def sync_reservation_room_pricing_and_occupancy(reservation) -> None:
    if not reservation or not getattr(reservation, "id", None):
        return

    reservation_rooms = list(
        reservation.rooms_detail.select_related("room", "room__room_type").order_by("id")
    )
    if not reservation_rooms:
        return

    guest_breakdown = get_reservation_guest_age_breakdown(reservation)
    adults = guest_breakdown["adults"]
    children = guest_breakdown["children"]

    # Si aun no hay huespedes, mantenemos un adulto base por habitacion.
    if guest_breakdown["total"] == 0:
        adults = len(reservation_rooms)
        children = 0

    room_capacities: list[int] = []
    for reservation_room in reservation_rooms:
        room = reservation_room.room
        capacity = getattr(getattr(room, "room_type", None), "capacity", None)
        if capacity is None or int(capacity) <= 0:
            raise ValidationError(
                {
                    "room": (
                        f"La habitacion {room.number} no tiene una capacidad valida en su tipo de habitacion."
                    )
                }
            )
        room_capacities.append(int(capacity))

    distributions = _distribute_guests_across_rooms(
        room_capacities=room_capacities,
        room_count=len(reservation_rooms),
        adults=adults,
        children=children,
    )

    for index, reservation_room in enumerate(reservation_rooms):
        room = reservation_room.room
        room_type_id = getattr(room, "room_type_id", None)
        if not room_type_id:
            raise ValidationError(
                {"room": f"La habitacion {room.number} no tiene tipo de habitacion configurado."}
            )

        expected_rate = find_active_rate_for_room_type_dates(
            room_type_id=room_type_id,
            expected_check_in=reservation.expected_check_in,
            expected_check_out=reservation.expected_check_out,
        )

        if not expected_rate:
            if has_active_rate_for_room_type(room_type_id):
                raise ValidationError(
                    {
                        "night_rate": (
                            f"No existe una tarifa activa para la habitacion {room.number} "
                            "en el rango de fechas de la reserva."
                        )
                    }
                )
            raise ValidationError(
                {
                    "night_rate": (
                        f"La habitacion {room.number} no tiene una tarifa activa configurada "
                        "para su tipo de habitacion."
                    )
                }
            )

        adults_by_room, children_by_room = distributions[index]
        occupancy = adults_by_room + children_by_room
        if occupancy > room_capacities[index]:
            raise ValidationError(
                {
                    "rooms_detail": (
                        f"La ocupacion asignada para la habitacion {room.number} ({occupancy}) "
                        f"supera su capacidad ({room_capacities[index]})."
                    )
                }
            )
        reservation_room.night_rate = expected_rate.price
        reservation_room.adults = adults_by_room
        reservation_room.children = children_by_room

    ReservationRoom.objects.bulk_update(
        reservation_rooms,
        ["night_rate", "adults", "children"],
    )


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


def _iter_reservation_invoices(reservation):
    prefetched = getattr(reservation, "_prefetched_objects_cache", {}).get("invoices")
    if prefetched is not None:
        return prefetched
    return reservation.invoices.all()


def _iter_invoice_payments(invoice):
    prefetched = getattr(invoice, "_prefetched_objects_cache", {}).get("payments")
    if prefetched is not None:
        return prefetched
    return invoice.payments.all()


def _iter_payment_refunds(payment):
    prefetched = getattr(payment, "_prefetched_objects_cache", {}).get("refunds")
    if prefetched is not None:
        return prefetched
    return payment.refunds.all()


def _iter_reservation_charges(reservation):
    prefetched = getattr(reservation, "_prefetched_objects_cache", {}).get("charges")
    if prefetched is not None:
        return prefetched
    return reservation.charges.all()


def _build_check_in_datetime(check_in_date, check_in_time) -> datetime:
    check_in_datetime = datetime.combine(check_in_date, check_in_time or time(0, 0))
    if timezone.is_naive(check_in_datetime):
        check_in_datetime = timezone.make_aware(check_in_datetime, timezone.get_current_timezone())
    return check_in_datetime


def _resolve_reservation_check_in_time(reservation) -> time:
    check_in_times: list[time] = []
    for reservation_room in _iter_reservation_rooms(reservation):
        room = getattr(reservation_room, "room", None)
        hotel_settings = getattr(getattr(room, "floor", None), "hotel_settings", None)
        room_check_in_time = getattr(hotel_settings, "check_in_time", None)
        if room_check_in_time is not None:
            check_in_times.append(room_check_in_time)

    if check_in_times:
        # In mixed-hotel edge cases, choose the strictest start time.
        return max(check_in_times)
    return time(0, 0)


def get_reservation_check_in_start_datetime(reservation) -> datetime | None:
    check_in_date = getattr(reservation, "expected_check_in", None)
    if not check_in_date:
        return None

    check_in_time = _resolve_reservation_check_in_time(reservation)
    return _build_check_in_datetime(check_in_date, check_in_time)


def has_reservation_check_in_window_started(reservation) -> bool:
    if getattr(reservation, "real_check_out", None) is not None:
        return False

    if getattr(reservation, "real_check_in", None) is not None:
        return True

    check_in_start_datetime = get_reservation_check_in_start_datetime(reservation)
    if check_in_start_datetime is None:
        return False

    return timezone.now() >= check_in_start_datetime


def get_reservation_financials(
    reservation,
    *,
    exclude_deposit_id: int | None = None,
    exclude_payment_id: int | None = None,
) -> dict[str, Decimal]:
    if exclude_payment_id is None and exclude_deposit_id is not None:
        # Compatibilidad hacia atras con llamadas que aun usan exclude_deposit_id.
        exclude_payment_id = exclude_deposit_id

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
    for invoice in _iter_reservation_invoices(reservation):
        if not getattr(invoice, "is_active", True):
            continue

        for payment in _iter_invoice_payments(invoice):
            if not getattr(payment, "is_active", True):
                continue
            if exclude_payment_id and getattr(payment, "id", None) == exclude_payment_id:
                continue

            total_deposits += _to_decimal(getattr(payment, "amount", 0))

            for refund in _iter_payment_refunds(payment):
                if not getattr(refund, "is_active", True):
                    continue
                refund_status_code = _normalize_code(
                    getattr(refund, "status_code", None)
                    or getattr(getattr(refund, "status", None), "code", None)
                )
                if refund_status_code not in REFUND_IMPACT_STATUS_CODES:
                    continue
                total_deposits -= _to_decimal(getattr(refund, "amount", 0))

    if total_deposits < MONEY_ZERO:
        total_deposits = MONEY_ZERO

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
    check_in_window_started = has_reservation_check_in_window_started(reservation)
    rooms_available_for_check_in = _reservation_rooms_available_for_check_in(reservation)

    can_confirm = (
        is_reservation_status_pending(status_code)
        and not has_check_in
        and not has_check_out
    )
    can_check_in = (
        is_reservation_status_confirmed(status_code)
        and check_in_window_started
        and rooms_available_for_check_in
        and not has_check_in
        and not has_check_out
    )
    can_check_out = (
        (is_reservation_status_in_progress(status_code) or has_check_in)
        and not has_check_out
    )
    can_cancel = (
        (
            is_reservation_status_pending(status_code)
            or is_reservation_status_confirmed(status_code)
        )
        and not has_check_in
        and not has_check_out
    )

    return {
        "can_confirm": can_confirm,
        "can_check_in": can_check_in,
        "can_check_out": can_check_out,
        "can_cancel": can_cancel,
    }


def _reservation_rooms_available_for_check_in(reservation) -> bool:
    room_details = getattr(reservation, "rooms_detail", None)
    if room_details is None or not hasattr(room_details, "select_related"):
        return True

    for room_detail in room_details.select_related("room__status").all():
        room = getattr(room_detail, "room", None)
        room_status_code = _normalize_code(
            getattr(getattr(room, "status", None), "code", None)
        )
        if room_status_code != ROOM_STATUS_AVAILABLE:
            return False

    return True


def can_add_payment_to_reservation(
    reservation,
    *,
    financials: dict[str, Decimal] | None = None,
) -> bool:
    status_code = _normalize_code(getattr(reservation, "status_code", None))
    if is_reservation_status_cancelled(status_code):
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
    exclude_payment_id: int | None = None,
) -> dict[str, str]:
    errors: dict[str, str] = {}

    if reservation is None:
        errors["reservation"] = "Reservation is required."
        return errors

    status_code = _normalize_code(getattr(reservation, "status_code", None))
    if is_reservation_status_cancelled(status_code):
        errors["reservation"] = "No puedes registrar pagos en una reserva cancelada."
        return errors

    amount_decimal = _to_decimal(amount)
    if amount_decimal <= MONEY_ZERO:
        errors["amount"] = "Deposit amount must be greater than zero."
        return errors

    financials = get_reservation_financials(
        reservation,
        exclude_deposit_id=exclude_deposit_id,
        exclude_payment_id=exclude_payment_id,
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
    check_in_datetime = _build_check_in_datetime(check_in_date, check_in_time)

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


def _room_has_active_cleaning_tasks(room: Room) -> bool:
    return room.cleaning_tasks.filter(
        status__code__in=CLEANING_ACTIVE_STATUS_CODES
    ).exists()


def _get_desired_room_status_code_with_operations(room: Room) -> str | None:
    desired_status_code = _get_desired_room_status_code(room)
    if desired_status_code:
        return desired_status_code

    if _room_has_active_cleaning_tasks(room):
        return ROOM_STATUS_CLEANING

    return None


def sync_room_status_from_reservations(room: Room) -> bool:
    desired_status_code = _get_desired_room_status_code_with_operations(room)
    current_status_code = _normalize_code(getattr(room.status, "code", None))

    if desired_status_code:
        if desired_status_code == ROOM_STATUS_RESERVED and not _get_room_status(ROOM_STATUS_RESERVED):
            desired_status_code = ROOM_STATUS_OCCUPIED
        return _set_room_status(room, desired_status_code)

    if current_status_code in {ROOM_STATUS_RESERVED, ROOM_STATUS_OCCUPIED, ROOM_STATUS_CLEANING}:
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


def _get_post_checkout_cleaning_task_type():
    task_type = get_master_data_code(
        MasterData.Group.CLEANING_TASK_TYPE,
        CLEANING_TASK_TYPE_CHECK_OUT,
    )
    if task_type:
        return task_type

    return (
        MasterData.objects.filter(
            group=MasterData.Group.CLEANING_TASK_TYPE,
            is_active=True,
        )
        .order_by("sort_order", "id")
        .first()
    )


def _get_post_checkout_cleaning_status():
    status = get_master_data_code(
        MasterData.Group.CLEANING_STATUS,
        CLEANING_STATUS_PENDING,
    )
    if status:
        return status

    return (
        MasterData.objects.filter(
            group=MasterData.Group.CLEANING_STATUS,
            is_active=True,
        )
        .order_by("sort_order", "id")
        .first()
    )


def create_post_checkout_cleaning_tasks(reservation) -> int:
    if not reservation or not getattr(reservation, "id", None):
        return 0

    task_type = _get_post_checkout_cleaning_task_type()
    task_status = _get_post_checkout_cleaning_status()
    if not task_type or not task_status:
        return 0

    room_ids = list(
        reservation.rooms_detail.values_list("room_id", flat=True).distinct()
    )
    if not room_ids:
        return 0

    check_out_at = reservation.real_check_out or timezone.now()
    if timezone.is_naive(check_out_at):
        check_out_at = timezone.make_aware(
            check_out_at,
            timezone.get_current_timezone(),
        )
    scheduled_for = timezone.localtime(check_out_at).date()
    notes = f"Limpieza post check-out de reserva #{reservation.id}."

    existing_room_ids = set(
        CleaningTask.objects.filter(
            room_id__in=room_ids,
            task_type_id=task_type.id,
            scheduled_for=scheduled_for,
            notes=notes,
        ).values_list("room_id", flat=True)
    )

    room_ids_to_create = [room_id for room_id in room_ids if room_id not in existing_room_ids]
    if not room_ids_to_create:
        return 0

    tasks_to_create = [
        CleaningTask(
            room_id=room_id,
            task_type=task_type,
            status=task_status,
            scheduled_for=scheduled_for,
            notes=notes,
        )
        for room_id in room_ids_to_create
    ]

    CleaningTask.objects.bulk_create(tasks_to_create)
    sync_room_status_for_room_ids(room_ids_to_create)
    return len(tasks_to_create)


def _get_audit_user(user):
    if user is not None and getattr(user, "is_authenticated", False):
        return user
    return None


def _coerce_int(
    value: Any,
    *,
    field_name: str,
    min_value: int = 0,
    line_number: int | None = None,
) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        line_prefix = f"Linea {line_number}: " if line_number is not None else ""
        raise ValidationError(
            {
                "inventory_review": (
                    f"{line_prefix}el campo '{field_name}' debe ser un numero entero."
                )
            }
        )

    if parsed < min_value:
        line_prefix = f"Linea {line_number}: " if line_number is not None else ""
        if min_value == 0:
            message = f"{line_prefix}el campo '{field_name}' no puede ser negativo."
        else:
            message = (
                f"{line_prefix}el campo '{field_name}' debe ser mayor o igual a {min_value}."
            )
        raise ValidationError({"inventory_review": message})

    return parsed


def validate_checkout_inventory_review_payload(
    reservation,
    payload: Any,
) -> list[dict[str, Any]]:
    if payload in (None, "", []):
        return []

    if not isinstance(payload, list):
        raise ValidationError(
            {
                "inventory_review": (
                    "El inventario revisado debe enviarse como una lista de lineas."
                )
            }
        )

    reservation_room_ids = set(
        reservation.rooms_detail.values_list("room_id", flat=True).distinct()
    )
    if not reservation_room_ids and payload:
        raise ValidationError(
            {
                "inventory_review": (
                    "La reserva no tiene habitaciones asociadas para registrar inventario."
                )
            }
        )

    normalized_lines: list[dict[str, Any]] = []
    requested_item_ids: set[int] = set()

    for index, raw_line in enumerate(payload, start=1):
        if not isinstance(raw_line, dict):
            raise ValidationError(
                {
                    "inventory_review": (
                        f"Linea {index}: cada elemento debe ser un objeto con room, item y quantity."
                    )
                }
            )

        room_raw = raw_line.get("room_id", raw_line.get("room"))
        item_raw = raw_line.get("item_id", raw_line.get("item"))
        quantity_raw = raw_line.get("quantity")

        room_id = _coerce_int(
            room_raw,
            field_name="room",
            min_value=1,
            line_number=index,
        )
        item_id = _coerce_int(
            item_raw,
            field_name="item",
            min_value=1,
            line_number=index,
        )
        quantity = _coerce_int(
            quantity_raw,
            field_name="quantity",
            min_value=0,
            line_number=index,
        )

        if room_id not in reservation_room_ids:
            raise ValidationError(
                {
                    "inventory_review": (
                        f"Linea {index}: la habitacion {room_id} no pertenece a la reserva."
                    )
                }
            )

        notes = raw_line.get("notes")
        if notes is not None:
            notes = str(notes).strip()

        normalized_lines.append(
            {
                "room_id": room_id,
                "item_id": item_id,
                "quantity": quantity,
                "notes": notes or "",
            }
        )
        requested_item_ids.add(item_id)

    if requested_item_ids:
        existing_item_ids = set(
            Item.objects.filter(id__in=requested_item_ids).values_list("id", flat=True)
        )
        missing_item_ids = sorted(requested_item_ids - existing_item_ids)
        if missing_item_ids:
            raise ValidationError(
                {
                    "inventory_review": (
                        "Los siguientes items no existen: "
                        + ", ".join(str(item_id) for item_id in missing_item_ids)
                        + "."
                    )
                }
            )

    return normalized_lines


def create_check_in_inventory_snapshot(
    reservation,
    *,
    created_by=None,
):
    if not reservation or not getattr(reservation, "id", None):
        return None

    check, created = ReservationInventoryCheck.objects.get_or_create(
        reservation=reservation,
        check_type=INVENTORY_CHECK_TYPE_CHECK_IN,
        defaults={
            "created_by": _get_audit_user(created_by),
            "notes": f"Snapshot inicial de inventario para reserva #{reservation.id}.",
        },
    )
    if not created:
        return check

    reservation_rooms = list(
        reservation.rooms_detail.values("id", "room_id")
    )
    room_ids = [line["room_id"] for line in reservation_rooms if line.get("room_id")]
    if not room_ids:
        return check

    reservation_room_by_room_id = {
        line["room_id"]: line["id"] for line in reservation_rooms
    }

    room_inventory_rows = RoomInventory.objects.filter(
        room_id__in=room_ids,
        is_active=True,
    ).values("room_id", "item_id", "quantity")

    lines_to_create = []
    for row in room_inventory_rows:
        quantity = max(int(row.get("quantity") or 0), 0)
        lines_to_create.append(
            ReservationInventoryCheckLine(
                inventory_check=check,
                reservation_room_id=reservation_room_by_room_id.get(row["room_id"]),
                room_id=row["room_id"],
                item_id=row["item_id"],
                expected_quantity=quantity,
                reviewed_quantity=quantity,
                difference_quantity=0,
            )
        )

    if lines_to_create:
        ReservationInventoryCheckLine.objects.bulk_create(lines_to_create)

    return check


def create_checkout_inventory_comparison(
    reservation,
    *,
    inventory_review_lines: list[dict[str, Any]] | None = None,
    created_by=None,
) -> dict[str, Any]:
    if not reservation or not getattr(reservation, "id", None):
        return {
            "check_id": None,
            "total_lines": 0,
            "differences_count": 0,
            "missing_items_count": 0,
            "extra_items_count": 0,
            "lines": [],
        }

    inventory_review_lines = inventory_review_lines or []

    reservation_rooms = list(
        reservation.rooms_detail.select_related("room").values("id", "room_id", "room__number")
    )
    reservation_room_by_room_id = {row["room_id"]: row["id"] for row in reservation_rooms}
    room_number_by_id = {
        row["room_id"]: str(row.get("room__number") or row["room_id"])
        for row in reservation_rooms
    }

    check_in_check = (
        ReservationInventoryCheck.objects.filter(
            reservation=reservation,
            check_type=INVENTORY_CHECK_TYPE_CHECK_IN,
        )
        .prefetch_related("lines")
        .first()
    )

    expected_by_key: dict[tuple[int, int], int] = {}
    if check_in_check:
        for line in check_in_check.lines.all():
            key = (line.room_id, line.item_id)
            expected_by_key[key] = int(line.reviewed_quantity or 0)

    if not expected_by_key:
        room_ids = list(reservation_room_by_room_id.keys())
        room_inventory_rows = RoomInventory.objects.filter(
            room_id__in=room_ids,
            is_active=True,
        ).values("room_id", "item_id", "quantity")
        for row in room_inventory_rows:
            key = (row["room_id"], row["item_id"])
            expected_by_key[key] = int(row.get("quantity") or 0)

    reviewed_by_key: dict[tuple[int, int], int] = {}
    notes_by_key: dict[tuple[int, int], str] = {}
    for line in inventory_review_lines:
        key = (line["room_id"], line["item_id"])
        reviewed_by_key[key] = int(line["quantity"])
        notes_by_key[key] = str(line.get("notes") or "").strip()

    comparison_keys = set(expected_by_key.keys())
    if reviewed_by_key:
        comparison_keys.update(reviewed_by_key.keys())
    else:
        reviewed_by_key = dict(expected_by_key)

    item_ids = sorted({item_id for _, item_id in comparison_keys})
    item_name_by_id = {
        item_id: name
        for item_id, name in Item.objects.filter(id__in=item_ids).values_list("id", "name")
    }

    default_notes = f"Revision de inventario post check-out de reserva #{reservation.id}."
    check, created = ReservationInventoryCheck.objects.get_or_create(
        reservation=reservation,
        check_type=INVENTORY_CHECK_TYPE_CHECK_OUT,
        defaults={
            "created_by": _get_audit_user(created_by),
            "notes": default_notes,
        },
    )
    if not created:
        fields_to_update: list[str] = []
        audit_user = _get_audit_user(created_by)
        if audit_user and not check.created_by_id:
            check.created_by = audit_user
            fields_to_update.append("created_by")
        if not check.notes:
            check.notes = default_notes
            fields_to_update.append("notes")
        if fields_to_update:
            check.save(update_fields=fields_to_update)
        check.lines.all().delete()

    sorted_keys = sorted(
        comparison_keys,
        key=lambda key: (
            room_number_by_id.get(key[0], str(key[0])),
            item_name_by_id.get(key[1], str(key[1])),
            key[0],
            key[1],
        ),
    )

    lines_to_create = []
    response_lines = []
    differences_count = 0
    missing_items_count = 0
    extra_items_count = 0

    for room_id, item_id in sorted_keys:
        expected_quantity = int(expected_by_key.get((room_id, item_id), 0))
        reviewed_quantity = int(
            reviewed_by_key.get((room_id, item_id), expected_quantity)
        )
        difference_quantity = reviewed_quantity - expected_quantity
        line_notes = notes_by_key.get((room_id, item_id), "")

        if difference_quantity != 0:
            differences_count += 1
            if difference_quantity < 0:
                missing_items_count += 1
            else:
                extra_items_count += 1

        lines_to_create.append(
            ReservationInventoryCheckLine(
                inventory_check=check,
                reservation_room_id=reservation_room_by_room_id.get(room_id),
                room_id=room_id,
                item_id=item_id,
                expected_quantity=expected_quantity,
                reviewed_quantity=reviewed_quantity,
                difference_quantity=difference_quantity,
                notes=line_notes,
            )
        )

        response_lines.append(
            {
                "room_id": room_id,
                "room_number": room_number_by_id.get(room_id),
                "item_id": item_id,
                "item_name": item_name_by_id.get(item_id),
                "expected_quantity": expected_quantity,
                "reviewed_quantity": reviewed_quantity,
                "difference_quantity": difference_quantity,
                "notes": line_notes,
            }
        )

    if lines_to_create:
        ReservationInventoryCheckLine.objects.bulk_create(lines_to_create)

    return {
        "check_id": check.id,
        "total_lines": len(response_lines),
        "differences_count": differences_count,
        "missing_items_count": missing_items_count,
        "extra_items_count": extra_items_count,
        "lines": response_lines,
    }


def _resolve_reservation_stay_nights(*, expected_check_in, expected_check_out) -> int:
    if not expected_check_in or not expected_check_out:
        return 0

    try:
        nights = (expected_check_out - expected_check_in).days
    except TypeError:
        return 0

    return max(int(nights), 0)


def _to_local_date(value) -> date_cls | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        date_value = value
        if timezone.is_naive(date_value):
            date_value = timezone.make_aware(date_value, timezone.get_current_timezone())
        return timezone.localtime(date_value).date()

    if isinstance(value, date_cls):
        return value

    return None


def sync_client_stay_metrics_by_id(client_id: int | None) -> bool:
    if not client_id:
        return False

    client = Client.objects.select_related("client_type").filter(id=client_id).first()
    if not client:
        return False

    total_stay_nights = 0
    last_stay: date_cls | None = None

    completed_stays = client.reservations.filter(
        real_check_in__isnull=False,
        real_check_out__isnull=False,
    ).values_list("expected_check_in", "expected_check_out", "real_check_out")

    for expected_check_in, expected_check_out, real_check_out in completed_stays:
        total_stay_nights += _resolve_reservation_stay_nights(
            expected_check_in=expected_check_in,
            expected_check_out=expected_check_out,
        )

        stay_date = _to_local_date(real_check_out)
        if stay_date and (last_stay is None or stay_date > last_stay):
            last_stay = stay_date

    target_client_type_code = (
        "VIP"
        if total_stay_nights >= 30
        else "FRECUENTE"
        if total_stay_nights >= 10
        else "REGULAR"
    )
    current_client_type_code = _normalize_code(getattr(client.client_type, "code", None))

    has_metric_changes = (
        int(client.total_stay_nights or 0) != total_stay_nights
        or client.last_stay != last_stay
    )
    has_type_mismatch = current_client_type_code != target_client_type_code

    if not has_metric_changes and not has_type_mismatch:
        return False

    client.total_stay_nights = total_stay_nights
    client.last_stay = last_stay
    client.save(update_fields=["total_stay_nights", "last_stay", "client_type"])
    return True


def sync_client_stay_metrics_for_reservation(reservation) -> bool:
    return sync_client_stay_metrics_by_id(getattr(reservation, "client_id", None))


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
