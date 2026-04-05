from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.billing.models import Charge, Invoice
from apps.master_data.models import MasterData
from apps.reservations.models import Reservation
from apps.reservations.services import get_reservation_financials


AUTO_ROOM_KEY_PREFIX = "ROOM"
AUTO_PACKAGE_KEY = "PACKAGE"
MONEY_ZERO = Decimal("0.00")

DEFAULT_CHARGE_TYPES: dict[str, tuple[str, int]] = {
    "HABITACION": ("Habitacion", 1),
    "PAQUETE": ("Paquete", 2),
    "SERVICIO": ("Servicio", 3),
    "OTRO": ("Otro", 4),
}

DEFAULT_INVOICE_STATUSES: dict[str, tuple[str, int]] = {
    "BORRADOR": ("Borrador", 1),
    "EMITIDA": ("Emitida", 2),
    "PAGADA": ("Pagada", 3),
    "ANULADA": ("Anulada", 4),
}


def get_or_create_default_charge_type(code: str):
    normalized_code = str(code or "").strip().upper()
    if not normalized_code:
        return None

    name, sort_order = DEFAULT_CHARGE_TYPES.get(
        normalized_code,
        (normalized_code.replace("_", " ").title(), 99),
    )
    charge_type, _ = MasterData.objects.get_or_create(
        group=MasterData.Group.CHARGE_TYPE,
        code=normalized_code,
        defaults={
            "name": name,
            "sort_order": sort_order,
            "is_active": True,
        },
    )

    if not charge_type.is_active:
        charge_type.is_active = True
        charge_type.save(update_fields=["is_active"])

    return charge_type


def get_or_create_default_invoice_status(code: str):
    normalized_code = str(code or "").strip().upper()
    if not normalized_code:
        return None

    name, sort_order = DEFAULT_INVOICE_STATUSES.get(
        normalized_code,
        (normalized_code.replace("_", " ").title(), 99),
    )
    invoice_status, _ = MasterData.objects.get_or_create(
        group=MasterData.Group.INVOICE_STATUS,
        code=normalized_code,
        defaults={
            "name": name,
            "sort_order": sort_order,
            "is_active": True,
        },
    )

    if not invoice_status.is_active:
        invoice_status.is_active = True
        invoice_status.save(update_fields=["is_active"])

    return invoice_status


def _to_decimal(value) -> Decimal:
    if value is None:
        return MONEY_ZERO
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return MONEY_ZERO


def _build_room_charge_description(reservation_room, nights: int) -> str:
    room_label = getattr(getattr(reservation_room, "room", None), "number", None) or str(
        reservation_room.room_id
    )
    return f"Hospedaje habitacion {room_label} ({nights} noche(s))"


def _build_package_charge_description(reservation) -> str:
    package_name = (
        str(getattr(reservation, "package_display_name", "") or "")
        or str(getattr(reservation, "package_name", "") or "")
        or str(getattr(getattr(reservation, "package", None), "name", "") or "")
    ).strip()
    if package_name:
        return f"Paquete: {package_name}"
    return "Paquete"


def _sync_automatic_room_charges(reservation, *, room_charge_type) -> set[str]:
    active_keys: set[str] = set()
    nights = max(int(getattr(reservation, "total_nights", 0) or 0), 0)

    for reservation_room in reservation.rooms_detail.select_related("room").all():
        automation_key = f"{AUTO_ROOM_KEY_PREFIX}:{reservation_room.id}"
        active_keys.add(automation_key)

        line_total = _to_decimal(getattr(reservation_room, "subtotal", MONEY_ZERO))
        if line_total < MONEY_ZERO:
            line_total = MONEY_ZERO

        Charge.objects.update_or_create(
            reservation=reservation,
            is_automatic=True,
            automation_key=automation_key,
            defaults={
                "charge_type": room_charge_type,
                "service": None,
                "package": None,
                "description": _build_room_charge_description(reservation_room, nights),
                "quantity": 1,
                "unit_price": line_total,
                "is_active": True,
            },
        )

    return active_keys


def _sync_automatic_package_charge(reservation, *, package_charge_type) -> set[str]:
    package_total = _to_decimal(getattr(reservation, "package_price", MONEY_ZERO))
    if not getattr(reservation, "package_id", None) or package_total <= MONEY_ZERO:
        return set()

    Charge.objects.update_or_create(
        reservation=reservation,
        is_automatic=True,
        automation_key=AUTO_PACKAGE_KEY,
        defaults={
            "charge_type": package_charge_type,
            "service": None,
            "package": reservation.package,
            "description": _build_package_charge_description(reservation),
            "quantity": 1,
            "unit_price": package_total,
            "is_active": True,
        },
    )
    return {AUTO_PACKAGE_KEY}


def sync_automatic_charges_for_reservation(reservation_id: int | None):
    if not reservation_id:
        return

    reservation = (
        Reservation.objects.select_related("package")
        .prefetch_related("rooms_detail__room")
        .filter(pk=reservation_id)
        .first()
    )
    if not reservation:
        return

    room_charge_type = get_or_create_default_charge_type("HABITACION")
    package_charge_type = get_or_create_default_charge_type("PAQUETE")

    active_keys: set[str] = set()
    if room_charge_type:
        active_keys.update(_sync_automatic_room_charges(reservation, room_charge_type=room_charge_type))
    if package_charge_type:
        active_keys.update(
            _sync_automatic_package_charge(reservation, package_charge_type=package_charge_type)
        )

    stale_qs = Charge.objects.filter(
        reservation=reservation,
        is_automatic=True,
        is_active=True,
    )
    if active_keys:
        stale_qs = stale_qs.exclude(automation_key__in=active_keys)
    stale_qs.update(is_active=False)


def _generate_invoice_number(reservation_id: int) -> str:
    base = f"FAC-{int(reservation_id):08d}"
    if not Invoice.objects.filter(invoice_number=base).exists():
        return base

    suffix = 2
    while Invoice.objects.filter(invoice_number=f"{base}-{suffix}").exists():
        suffix += 1
        if suffix > 9999:
            timestamp = timezone.now().strftime("%Y%m%d%H%M%S%f")
            return f"{base}-{timestamp}"

    return f"{base}-{suffix}"


def _get_existing_default_invoice(reservation_id: int):
    return (
        Invoice.objects.filter(reservation_id=reservation_id, is_active=True)
        .select_related("reservation")
        .order_by("id")
        .first()
    )


def ensure_default_invoice_for_reservation(reservation_id: int | None):
    if not reservation_id:
        return None

    existing_invoice = _get_existing_default_invoice(reservation_id)
    if existing_invoice:
        return existing_invoice

    reservation = Reservation.objects.filter(pk=reservation_id).first()
    if not reservation:
        return None

    status = get_or_create_default_invoice_status("BORRADOR")
    if not status:
        return None

    for _ in range(3):
        invoice_number = _generate_invoice_number(reservation_id)
        try:
            with transaction.atomic():
                return Invoice.objects.create(
                    reservation=reservation,
                    status=status,
                    invoice_number=invoice_number,
                    subtotal=MONEY_ZERO,
                    tax_amount=MONEY_ZERO,
                    is_active=True,
                )
        except IntegrityError:
            continue

    return _get_existing_default_invoice(reservation_id)


def _get_invoice_total_paid(invoice: Invoice) -> Decimal:
    return _to_decimal(
        sum(
            payment.amount
            for payment in invoice.payments.filter(is_active=True).only("amount")
        )
    )


def _resolve_invoice_status_code(invoice: Invoice) -> str | None:
    current_status_code = str(getattr(getattr(invoice, "status", None), "code", "") or "").strip().upper()
    if current_status_code == "ANULADA":
        return None

    total_paid = _get_invoice_total_paid(invoice)
    total_amount = _to_decimal(invoice.total_amount)

    if total_amount > MONEY_ZERO and total_paid >= total_amount:
        return "PAGADA"
    if total_paid > MONEY_ZERO:
        return "EMITIDA"
    return "BORRADOR"


def sync_invoice_status(invoice: Invoice | None):
    if not invoice or not invoice.is_active:
        return invoice

    target_code = _resolve_invoice_status_code(invoice)
    if not target_code:
        return invoice

    target_status = get_or_create_default_invoice_status(target_code)
    if target_status and invoice.status_id != target_status.id:
        invoice.status = target_status
        invoice.save(update_fields=["status"])

    return invoice


def sync_default_invoice_for_reservation(reservation_id: int | None):
    invoice = ensure_default_invoice_for_reservation(reservation_id)
    if not invoice:
        return None

    financials = get_reservation_financials(invoice.reservation)
    subtotal = _to_decimal(financials.get("total_amount"))
    if subtotal < MONEY_ZERO:
        subtotal = MONEY_ZERO
    tax_amount = MONEY_ZERO

    if invoice.subtotal != subtotal or invoice.tax_amount != tax_amount:
        invoice.subtotal = subtotal
        invoice.tax_amount = tax_amount
        invoice.save(update_fields=["subtotal", "tax_amount", "total_amount"])

    sync_invoice_status(invoice)
    return invoice
