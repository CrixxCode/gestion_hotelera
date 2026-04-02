from __future__ import annotations

from datetime import datetime, time
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


def _normalize_code(value) -> str:
    return str(value or "").strip().upper()


def get_master_data_code(group: str, code: str):
    normalized_code = _normalize_code(code)
    if not normalized_code:
        return None

    return MasterData.objects.filter(group=group, code=normalized_code, is_active=True).first()


def get_reservation_status_by_code(code: str):
    return get_master_data_code(MasterData.Group.RESERVATION_STATUS, code)


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
