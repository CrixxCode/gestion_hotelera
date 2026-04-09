from __future__ import annotations

import logging
from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from django.apps import apps as django_apps
from django.core.exceptions import (
    FieldDoesNotExist,
    FieldError,
    ImproperlyConfigured,
    ObjectDoesNotExist,
    ValidationError,
)
from django.db.models import Sum
from django.utils import timezone

from apps.billing.models import Charge, CreditNote, Invoice

from apps.finance.models import MONEY_ZERO
from apps.finance.models import Expense
from apps.finance.services import build_financial_dashboard
from apps.hotel_settings.models import HotelSettings
from apps.reservations.models import ReservationRoom
from apps.rooms.models import Room

logger = logging.getLogger(__name__)


CANCELLED_RESERVATION_STATUS_CODES = {
    "CANCELADA",
    "CANCELADO",
    "ANULADA",
    "ANULADO",
    "NO_SHOW",
}

ANULLED_INVOICE_STATUS_CODES = {
    "ANULADA",
    "ANULADO",
    "CANCELADA",
    "CANCELADO",
}

ROOM_CHARGE_CODES = {"HABITACION", "ROOM"}
PACKAGE_CHARGE_CODES = {"PAQUETE", "PACKAGE"}
SERVICE_EXCLUDED_CHARGE_CODES = ROOM_CHARGE_CODES | PACKAGE_CHARGE_CODES

MONTH_LABELS_ES = {
    1: "Ene",
    2: "Feb",
    3: "Mar",
    4: "Abr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dic",
}


# =========================================================
# PUBLIC API
# =========================================================
def parse_hotel_settings_id(raw_value: Any) -> int:
    value = str(raw_value or "").strip()
    if not value:
        raise ValidationError({"hotel_settings": "hotel_settings is required."})
    if not value.isdigit():
        raise ValidationError({"hotel_settings": "hotel_settings must be a valid integer."})

    hotel_settings_id = int(value)
    if not HotelSettings.objects.filter(id=hotel_settings_id).exists():
        raise ValidationError({"hotel_settings": "The selected hotel_settings does not exist."})

    return hotel_settings_id


def resolve_report_period(
    *,
    year_raw: str | None = None,
    start_date_raw: str | None = None,
    end_date_raw: str | None = None,
) -> tuple[date, date, int]:
    today = timezone.localdate()

    if year_raw is not None and str(year_raw).strip():
        try:
            year = int(str(year_raw).strip())
        except (TypeError, ValueError):
            raise ValidationError({"year": "year must be a valid integer."}) from None

        if year < 1900 or year > 2999:
            raise ValidationError({"year": "year must be between 1900 and 2999."})

        return date(year, 1, 1), date(year, 12, 31), year

    if (start_date_raw and not end_date_raw) or (end_date_raw and not start_date_raw):
        raise ValidationError(
            {"date_range": "start_date and end_date must be sent together."}
        )

    if start_date_raw and end_date_raw:
        start_date = _parse_iso_date(start_date_raw, field_name="start_date")
        end_date = _parse_iso_date(end_date_raw, field_name="end_date")

        if start_date > end_date:
            raise ValidationError(
                {"date_range": "start_date must be less than or equal to end_date."}
            )

        return start_date, end_date, start_date.year

    return date(today.year, 1, 1), date(today.year, 12, 31), today.year


def _normalize_report_builder_inputs(
    *,
    hotel_settings_id: Any,
    start_date: Any,
    end_date: Any,
) -> tuple[int, date, date]:
    if not isinstance(hotel_settings_id, int):
        raise ValidationError({"hotel_settings": "hotel_settings must be an integer."})
    if hotel_settings_id <= 0:
        raise ValidationError({"hotel_settings": "hotel_settings must be greater than zero."})

    normalized_start_date = _coerce_to_date(start_date)
    normalized_end_date = _coerce_to_date(end_date)

    if normalized_start_date is None or normalized_end_date is None:
        raise ValidationError({"date_range": "start_date and end_date must be valid dates."})

    if normalized_start_date > normalized_end_date:
        raise ValidationError(
            {"date_range": "start_date must be less than or equal to end_date."}
        )

    return hotel_settings_id, normalized_start_date, normalized_end_date


def build_executive_report(
    *,
    hotel_settings_id: int,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    hotel_settings_id, start_date, end_date = _normalize_report_builder_inputs(
        hotel_settings_id=hotel_settings_id,
        start_date=start_date,
        end_date=end_date,
    )

    previous_start = _shift_year_safe(start_date, years=-1)
    previous_end = _shift_year_safe(end_date, years=-1)

    current_dashboard = build_financial_dashboard(
        hotel_settings_id=hotel_settings_id,
        start_date=start_date,
        end_date=end_date,
    )
    previous_dashboard = build_financial_dashboard(
        hotel_settings_id=hotel_settings_id,
        start_date=previous_start,
        end_date=previous_end,
    )

    monthly_financial = _build_monthly_financial_series(
        hotel_settings_id=hotel_settings_id,
        start_date=start_date,
        end_date=end_date,
    )
    payment_breakdown = _build_payment_methods_breakdown(
        hotel_settings_id=hotel_settings_id,
        start_date=start_date,
        end_date=end_date,
    )
    weekly_occupancy = _build_weekly_occupancy_series(
        hotel_settings_id=hotel_settings_id,
        start_date=start_date,
        end_date=end_date,
        weeks=8,
    )
    top_guests = _build_top_guests(
        hotel_settings_id=hotel_settings_id,
        start_date=start_date,
        end_date=end_date,
        limit=5,
    )

    current_revenue = _to_decimal(current_dashboard["summary"]["revenue"])
    previous_revenue = _to_decimal(previous_dashboard["summary"]["revenue"])

    current_net_profit = _to_decimal(current_dashboard["summary"]["net_profit"])
    previous_net_profit = _to_decimal(previous_dashboard["summary"]["net_profit"])

    current_occupancy = _to_decimal(current_dashboard["summary"]["occupancy_rate_pct"])
    previous_occupancy = _to_decimal(previous_dashboard["summary"]["occupancy_rate_pct"])

    current_revpar = _to_decimal(
        current_dashboard["benchmarking"]["current_period"]["revpar"]
    )
    previous_revpar = _to_decimal(
        previous_dashboard["benchmarking"]["current_period"]["revpar"]
    )

    return {
        "filters": _build_filters_payload(
            hotel_settings_id=hotel_settings_id,
            start_date=start_date,
            end_date=end_date,
        ),
        "kpis": {
            "annual_income": {
                "value": _to_float(current_revenue),
                "variation_pct": _to_float(
                    _calculate_percentage_change(
                        current=current_revenue,
                        previous=previous_revenue,
                    ),
                    allow_null=True,
                ),
            },
            "net_profit": {
                "value": _to_float(current_net_profit),
                "variation_pct": _to_float(
                    _calculate_percentage_change(
                        current=current_net_profit,
                        previous=previous_net_profit,
                    ),
                    allow_null=True,
                ),
            },
            "average_occupancy": {
                "value": _to_float(current_occupancy),
                "variation_pct": _to_float(current_occupancy - previous_occupancy),
            },
            "revpar": {
                "value": _to_float(current_revpar),
                "variation_pct": _to_float(
                    _calculate_percentage_change(
                        current=current_revpar,
                        previous=previous_revpar,
                    ),
                    allow_null=True,
                ),
            },
        },
        "income_vs_profit_chart": [
            {
                "month": item["month"],
                "income": _to_float(item["income"]),
                "profit": _to_float(item["net_profit"]),
            }
            for item in monthly_financial
        ],
        "payment_methods": [
            {
                "method": item["method"],
                "amount": item["amount"],
                "pct": item["pct"],
            }
            for item in payment_breakdown
        ],
        "weekly_occupancy": weekly_occupancy,
        "top_guests": top_guests,
    }


def build_revenue_report(
    *,
    hotel_settings_id: int,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    hotel_settings_id, start_date, end_date = _normalize_report_builder_inputs(
        hotel_settings_id=hotel_settings_id,
        start_date=start_date,
        end_date=end_date,
    )

    previous_start = _shift_year_safe(start_date, years=-1)
    previous_end = _shift_year_safe(end_date, years=-1)

    current_dashboard = build_financial_dashboard(
        hotel_settings_id=hotel_settings_id,
        start_date=start_date,
        end_date=end_date,
    )
    previous_dashboard = build_financial_dashboard(
        hotel_settings_id=hotel_settings_id,
        start_date=previous_start,
        end_date=previous_end,
    )

    monthly_financial = _build_monthly_financial_series(
        hotel_settings_id=hotel_settings_id,
        start_date=start_date,
        end_date=end_date,
    )

    current_revenue = _to_decimal(current_dashboard["summary"]["revenue"])
    previous_revenue = _to_decimal(previous_dashboard["summary"]["revenue"])

    current_total_expenses = (
        _to_decimal(current_dashboard["summary"]["costs"])
        + _to_decimal(current_dashboard["summary"]["expenses"])
    )
    previous_total_expenses = (
        _to_decimal(previous_dashboard["summary"]["costs"])
        + _to_decimal(previous_dashboard["summary"]["expenses"])
    )

    current_net_profit = _to_decimal(current_dashboard["summary"]["net_profit"])
    previous_net_profit = _to_decimal(previous_dashboard["summary"]["net_profit"])

    current_net_margin = _to_decimal(
        current_dashboard["profitability_and_sales"]["net_margin_breakdown"]["net_margin_pct"]
    )
    previous_net_margin = _to_decimal(
        previous_dashboard["profitability_and_sales"]["net_margin_breakdown"]["net_margin_pct"]
    )

    payment_breakdown = _build_payment_methods_breakdown(
        hotel_settings_id=hotel_settings_id,
        start_date=start_date,
        end_date=end_date,
    )
    guest_origin = _build_guest_origin_breakdown(
        hotel_settings_id=hotel_settings_id,
        start_date=start_date,
        end_date=end_date,
        limit=5,
    )

    return {
        "filters": _build_filters_payload(
            hotel_settings_id=hotel_settings_id,
            start_date=start_date,
            end_date=end_date,
        ),
        "kpis": {
            "gross_income": {
                "value": _to_float(current_revenue),
                "variation_pct": _to_float(
                    _calculate_percentage_change(
                        current=current_revenue,
                        previous=previous_revenue,
                    ),
                    allow_null=True,
                ),
            },
            "total_expenses": {
                "value": _to_float(current_total_expenses),
                "variation_pct": _to_float(
                    _calculate_percentage_change(
                        current=current_total_expenses,
                        previous=previous_total_expenses,
                    ),
                    allow_null=True,
                ),
            },
            "net_profit": {
                "value": _to_float(current_net_profit),
                "variation_pct": _to_float(
                    _calculate_percentage_change(
                        current=current_net_profit,
                        previous=previous_net_profit,
                    ),
                    allow_null=True,
                ),
            },
            "net_margin": {
                "value": _to_float(current_net_margin),
                "variation_points": _to_float(current_net_margin - previous_net_margin),
            },
        },
        "monthly_income_vs_expenses": [
            {
                "month": item["month"],
                "income": _to_float(item["income"]),
                "expenses": _to_float(item["total_expenses"]),
            }
            for item in monthly_financial
        ],
        "monthly_net_profit": [
            {
                "month": item["month"],
                "value": _to_float(item["net_profit"]),
            }
            for item in monthly_financial
        ],
        "payment_breakdown": payment_breakdown,
        "guest_origin": guest_origin,
    }


def build_occupancy_report(
    *,
    hotel_settings_id: int,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    hotel_settings_id, start_date, end_date = _normalize_report_builder_inputs(
        hotel_settings_id=hotel_settings_id,
        start_date=start_date,
        end_date=end_date,
    )

    previous_start = _shift_year_safe(start_date, years=-1)
    previous_end = _shift_year_safe(end_date, years=-1)

    current_dashboard = build_financial_dashboard(
        hotel_settings_id=hotel_settings_id,
        start_date=start_date,
        end_date=end_date,
    )
    previous_dashboard = build_financial_dashboard(
        hotel_settings_id=hotel_settings_id,
        start_date=previous_start,
        end_date=previous_end,
    )

    monthly_financial = _build_monthly_financial_series(
        hotel_settings_id=hotel_settings_id,
        start_date=start_date,
        end_date=end_date,
    )
    room_type_stats = _build_room_type_statistics(
        hotel_settings_id=hotel_settings_id,
        start_date=start_date,
        end_date=end_date,
    )
    current_stay_metrics = _build_average_stay_and_guest_metrics(
        hotel_settings_id=hotel_settings_id,
        start_date=start_date,
        end_date=end_date,
    )
    previous_stay_metrics = _build_average_stay_and_guest_metrics(
        hotel_settings_id=hotel_settings_id,
        start_date=previous_start,
        end_date=previous_end,
    )

    current_occupancy = _to_decimal(current_dashboard["summary"]["occupancy_rate_pct"])
    previous_occupancy = _to_decimal(previous_dashboard["summary"]["occupancy_rate_pct"])

    peak_item = max(
        monthly_financial,
        key=lambda item: item["occupancy_rate_pct"],
        default={"month": "", "occupancy_rate_pct": MONEY_ZERO},
    )

    return {
        "filters": _build_filters_payload(
            hotel_settings_id=hotel_settings_id,
            start_date=start_date,
            end_date=end_date,
        ),
        "kpis": {
            "average_occupancy": {
                "value": _to_float(current_occupancy),
                "variation_pct": _to_float(current_occupancy - previous_occupancy),
            },
            "occupancy_peak": {
                "value": _to_float(_to_decimal(peak_item["occupancy_rate_pct"])),
                "month": peak_item["month"],
            },
            "average_stay": {
                "value": _to_float(current_stay_metrics["average_stay"], places=1),
                "variation_nights": _to_float(
                    current_stay_metrics["average_stay"] - previous_stay_metrics["average_stay"],
                    places=1,
                ),
            },
            "total_guests": {
                "value": int(current_stay_metrics["guest_count"]),
                "variation_pct": _to_float(
                    _calculate_percentage_change(
                        current=_to_decimal(current_stay_metrics["guest_count"]),
                        previous=_to_decimal(previous_stay_metrics["guest_count"]),
                    ),
                    allow_null=True,
                ),
            },
        },
        "monthly_occupancy_rate": [
            {
                "month": item["month"],
                "pct": _to_float(item["occupancy_rate_pct"]),
            }
            for item in monthly_financial
        ],
        "by_room_type": room_type_stats,
        "occupied_rooms_by_month": [
            {
                "month": item["month"],
                "rooms": int(_quantize(_safe_divide(
                    _to_decimal(item["occupied_room_nights"]),
                    _to_decimal(item["days"]),
                ), places=0)),
            }
            for item in monthly_financial
        ],
        "room_type_performance": room_type_stats,
    }


def build_services_report(
    *,
    hotel_settings_id: int,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    hotel_settings_id, start_date, end_date = _normalize_report_builder_inputs(
        hotel_settings_id=hotel_settings_id,
        start_date=start_date,
        end_date=end_date,
    )

    previous_start = _shift_year_safe(start_date, years=-1)
    previous_end = _shift_year_safe(end_date, years=-1)

    current_categories = _build_service_categories_metrics(
        hotel_settings_id=hotel_settings_id,
        start_date=start_date,
        end_date=end_date,
    )
    previous_categories = _build_service_categories_metrics(
        hotel_settings_id=hotel_settings_id,
        start_date=previous_start,
        end_date=previous_end,
    )

    current_total_income = sum(
        (_to_decimal(item["income"]) for item in current_categories.values()),
        MONEY_ZERO,
    )
    previous_total_income = sum(
        (_to_decimal(item["income"]) for item in previous_categories.values()),
        MONEY_ZERO,
    )

    current_total_transactions = sum(
        (int(item["transactions"]) for item in current_categories.values()),
        0,
    )
    previous_total_transactions = sum(
        (int(item["transactions"]) for item in previous_categories.values()),
        0,
    )

    current_average_ticket = _safe_divide(
        current_total_income,
        _to_decimal(current_total_transactions),
    )
    previous_average_ticket = _safe_divide(
        previous_total_income,
        _to_decimal(previous_total_transactions),
    )

    ordered_current = sorted(
        current_categories.items(),
        key=lambda pair: _to_decimal(pair[1]["income"]),
        reverse=True,
    )

    top_category_name = ordered_current[0][0] if ordered_current else "Sin categoría"
    top_category_amount = (
        _to_decimal(ordered_current[0][1]["income"]) if ordered_current else MONEY_ZERO
    )

    income_by_category = [
        {
            "category": category,
            "amount": _to_float(_to_decimal(data["income"])),
        }
        for category, data in ordered_current
    ]

    transactions_by_category = [
        {
            "category": category,
            "transactions": int(data["transactions"]),
        }
        for category, data in ordered_current
    ]

    category_detail = []
    for category, data in ordered_current:
        current_income = _to_decimal(data["income"])
        previous_income = _to_decimal(
            previous_categories.get(category, {}).get("income", MONEY_ZERO)
        )
        share_pct = _percentage(current_income, current_total_income)
        trend_pct = _calculate_percentage_change(
            current=current_income,
            previous=previous_income,
        )

        category_detail.append(
            {
                "category": category,
                "income": _to_float(current_income),
                "transactions": int(data["transactions"]),
                "average_ticket": _to_float(
                    _safe_divide(current_income, _to_decimal(data["transactions"])),
                    places=1,
                ),
                "share_pct": _to_float(share_pct),
                "trend_pct": _to_float(trend_pct, allow_null=True),
            }
        )

    return {
        "filters": _build_filters_payload(
            hotel_settings_id=hotel_settings_id,
            start_date=start_date,
            end_date=end_date,
        ),
        "kpis": {
            "service_income": {
                "value": _to_float(current_total_income),
                "variation_pct": _to_float(
                    _calculate_percentage_change(
                        current=current_total_income,
                        previous=previous_total_income,
                    ),
                    allow_null=True,
                ),
            },
            "transactions": {
                "value": int(current_total_transactions),
                "variation_pct": _to_float(
                    _calculate_percentage_change(
                        current=_to_decimal(current_total_transactions),
                        previous=_to_decimal(previous_total_transactions),
                    ),
                    allow_null=True,
                ),
            },
            "average_ticket": {
                "value": _to_float(current_average_ticket, places=1),
                "variation_value": _to_float(
                    current_average_ticket - previous_average_ticket,
                    places=1,
                ),
            },
            "top_category": {
                "name": top_category_name,
                "amount": _to_float(top_category_amount),
            },
        },
        "income_by_category": income_by_category,
        "transactions_by_category": transactions_by_category,
        "category_detail": category_detail,
    }


# =========================================================
# SHARED BUILDERS
# =========================================================
def _build_filters_payload(
    *,
    hotel_settings_id: int,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    return {
        "hotel_settings": hotel_settings_id,
        "year": start_date.year if start_date.year == end_date.year else None,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "generated_at": timezone.now().isoformat(),
    }


def _build_monthly_financial_series(
    *,
    hotel_settings_id: int,
    start_date: date,
    end_date: date,
) -> list[dict[str, Any]]:
    series: list[dict[str, Any]] = []

    for month_start, effective_start, effective_end in _iter_month_ranges(start_date, end_date):
        payload = build_financial_dashboard(
            hotel_settings_id=hotel_settings_id,
            start_date=effective_start,
            end_date=effective_end,
        )
        summary = payload["summary"]
        revenue = _to_decimal(summary["revenue"])
        costs = _to_decimal(summary["costs"])
        expenses = _to_decimal(summary["expenses"])

        series.append(
            {
                "month": MONTH_LABELS_ES[month_start.month],
                "month_key": f"{month_start.year}-{month_start.month:02d}",
                "days": (effective_end - effective_start).days + 1,
                "income": revenue,
                "costs": costs,
                "expenses": expenses,
                "total_expenses": costs + expenses,
                "net_profit": _to_decimal(summary["net_profit"]),
                "occupancy_rate_pct": _to_decimal(summary["occupancy_rate_pct"]),
                "occupied_room_nights": int(summary["occupied_room_nights"]),
                "available_room_nights": int(summary["available_room_nights"]),
                "revpar": _to_decimal(
                    payload["benchmarking"]["current_period"]["revpar"]
                ),
            }
        )

    return series


def _build_weekly_occupancy_series(
    *,
    hotel_settings_id: int,
    start_date: date,
    end_date: date,
    weeks: int = 8,
) -> list[dict[str, Any]]:
    week_ranges = _iter_last_week_ranges(end_date=end_date, weeks=weeks)
    items: list[dict[str, Any]] = []

    room_count = _room_count(hotel_settings_id=hotel_settings_id)
    overlapping_rows = _get_overlapping_reservation_rows(
        hotel_settings_id=hotel_settings_id,
        start_date=max(start_date, week_ranges[0][0]) if week_ranges else start_date,
        end_date=end_date,
    )

    for week_start, week_end in week_ranges:
        occupied_nights = 0
        for row, _ in overlapping_rows:
            occupied_nights += _calculate_row_overlap_nights(
                row=row,
                start_date=week_start,
                end_date=week_end,
            )

        days = (week_end - week_start).days + 1
        average_occupied_rooms = _safe_divide(
            _to_decimal(occupied_nights),
            _to_decimal(days),
        )

        available_room_nights = room_count * days
        occupancy_pct = (
            _percentage(_to_decimal(occupied_nights), _to_decimal(available_room_nights))
            if available_room_nights > 0
            else MONEY_ZERO
        )

        items.append(
            {
                "week": f"Sem {week_start.isocalendar().week}",
                "occupied_rooms": int(_quantize(average_occupied_rooms, places=0)),
                "occupancy_rate_pct": _to_float(occupancy_pct),
            }
        )

    return items


def _resolve_payment_model():
    try:
        return django_apps.get_model("billing", "Payment")
    except LookupError as exc:
        logger.exception("Payment model lookup failed while building reports.")
        raise ImproperlyConfigured(
            "apps.reports requires billing.Payment model to build payment breakdown."
        ) from exc


def _build_payment_methods_breakdown(
    *,
    hotel_settings_id: int,
    start_date: date,
    end_date: date,
) -> list[dict[str, Any]]:
    payment_model = _resolve_payment_model()

    queryset = payment_model.objects.all()
    queryset = _apply_optional_boolean_filter(queryset, "is_active", True)
    queryset = _apply_date_filter(
        queryset,
        candidates=[
            "payment_date__date",
            "payment_date",
            "paid_at__date",
            "paid_at",
            "created_at__date",
            "created_at",
        ],
        start_date=start_date,
        end_date=end_date,
    )

    reservation_ids = _reservation_ids_queryset(hotel_settings_id=hotel_settings_id)
    queryset = _filter_queryset_by_reservation_candidates(
        queryset,
        reservation_ids=reservation_ids,
        candidates=[
            "invoice__reservation_id__in",
            "reservation_id__in",
            "charge__reservation_id__in",
        ],
    )

    payment_rows = []
    for payment in queryset:
        amount = _to_decimal(
            _first_existing_attr_value(
                payment,
                [
                    "amount",
                    "paid_amount",
                    "total_amount",
                    "value",
                ],
            )
        )
        method_name = (
            _first_existing_attr_value(
                payment,
                [
                    "payment_method.name",
                    "payment_method.code",
                    "method.name",
                    "method.code",
                ],
            )
            or "Sin método"
        )
        payment_rows.append(
            {
                "method": str(method_name),
                "amount": amount,
                "transactions": 1,
            }
        )

    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"amount": MONEY_ZERO, "transactions": 0}
    )
    for row in payment_rows:
        grouped[row["method"]]["amount"] += _to_decimal(row["amount"])
        grouped[row["method"]]["transactions"] += 1

    total_amount = sum((item["amount"] for item in grouped.values()), MONEY_ZERO)
    total_transactions = sum((item["transactions"] for item in grouped.values()), 0)

    result = []
    for method, data in grouped.items():
        result.append(
            {
                "method": method,
                "transactions_pct": _to_float(
                    _percentage(
                        _to_decimal(data["transactions"]),
                        _to_decimal(total_transactions),
                    )
                ),
                "amount": _to_float(data["amount"]),
                "amount_pct": _to_float(_percentage(data["amount"], total_amount)),
                "pct": _to_float(_percentage(data["amount"], total_amount)),
            }
        )

    result.sort(key=lambda item: item["amount"], reverse=True)
    return result


def _build_top_guests(
    *,
    hotel_settings_id: int,
    start_date: date,
    end_date: date,
    limit: int = 5,
) -> list[dict[str, Any]]:
    rows = _get_overlapping_reservation_rows(
        hotel_settings_id=hotel_settings_id,
        start_date=start_date,
        end_date=end_date,
    )
    reservations = _unique_reservations_from_rows(rows)
    reservation_spend = _build_reservation_spend_map(
        hotel_settings_id=hotel_settings_id,
        start_date=start_date,
        end_date=end_date,
    )

    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "guest_name": "Sin nombre",
            "country": "Sin país",
            "stays": 0,
            "nights": 0,
            "total_spent": MONEY_ZERO,
            "segment": "GENERAL",
        }
    )

    for reservation in reservations:
        guest_name = _resolve_guest_name(reservation) or f"Reserva {getattr(reservation, 'id', 'N/A')}"
        country = _resolve_guest_country(reservation) or "Sin país"
        segment = _resolve_guest_segment(reservation) or "GENERAL"
        key = f"{guest_name}|{country}|{segment}"

        grouped[key]["guest_name"] = guest_name
        grouped[key]["country"] = country
        grouped[key]["segment"] = segment
        grouped[key]["stays"] += 1
        grouped[key]["nights"] += _calculate_reservation_overlap_nights(
            reservation=reservation,
            start_date=start_date,
            end_date=end_date,
        )
        grouped[key]["total_spent"] += reservation_spend.get(
            getattr(reservation, "id", None),
            MONEY_ZERO,
        )

    ordered = sorted(
        grouped.values(),
        key=lambda item: item["total_spent"],
        reverse=True,
    )[:limit]

    return [
        {
            "guest_name": item["guest_name"],
            "country": item["country"],
            "stays": int(item["stays"]),
            "nights": int(item["nights"]),
            "total_spent": _to_float(item["total_spent"]),
            "segment": item["segment"],
        }
        for item in ordered
    ]


def _build_guest_origin_breakdown(
    *,
    hotel_settings_id: int,
    start_date: date,
    end_date: date,
    limit: int = 5,
) -> list[dict[str, Any]]:
    rows = _get_overlapping_reservation_rows(
        hotel_settings_id=hotel_settings_id,
        start_date=start_date,
        end_date=end_date,
    )
    reservations = _unique_reservations_from_rows(rows)

    country_counts: dict[str, int] = defaultdict(int)
    for reservation in reservations:
        country = _resolve_guest_country(reservation) or "Otros"
        country_counts[country] += 1

    total = sum(country_counts.values())
    if total <= 0:
        return []

    ordered = sorted(country_counts.items(), key=lambda item: item[1], reverse=True)
    head = ordered[:limit]
    tail = ordered[limit:]

    result = [
        {
            "country": country,
            "pct": _to_float(
                _percentage(_to_decimal(count), _to_decimal(total))
            ),
        }
        for country, count in head
    ]

    if tail:
        other_count = sum(count for _, count in tail)
        result.append(
            {
                "country": "Otros",
                "pct": _to_float(
                    _percentage(_to_decimal(other_count), _to_decimal(total))
                ),
            }
        )

    return result


def _build_average_stay_and_guest_metrics(
    *,
    hotel_settings_id: int,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    rows = _get_overlapping_reservation_rows(
        hotel_settings_id=hotel_settings_id,
        start_date=start_date,
        end_date=end_date,
    )
    reservations = _unique_reservations_from_rows(rows)

    total_nights = 0
    total_guests = 0

    for reservation in reservations:
        total_nights += _calculate_reservation_overlap_nights(
            reservation=reservation,
            start_date=start_date,
            end_date=end_date,
        )
        total_guests += _resolve_guest_count(reservation)

    reservation_count = len(reservations)
    average_stay = _safe_divide(
        _to_decimal(total_nights),
        _to_decimal(reservation_count),
    )

    return {
        "reservation_count": reservation_count,
        "guest_count": total_guests,
        "average_stay": average_stay,
    }


def _build_room_type_statistics(
    *,
    hotel_settings_id: int,
    start_date: date,
    end_date: date,
) -> list[dict[str, Any]]:
    rooms_queryset = Room.objects.filter(floor__hotel_settings_id=hotel_settings_id)
    all_rooms = list(rooms_queryset)

    room_count_by_type: dict[str, int] = defaultdict(int)
    for room in all_rooms:
        room_type_name = _resolve_room_type_name(room)
        room_count_by_type[room_type_name] += 1

    rows = _get_overlapping_reservation_rows(
        hotel_settings_id=hotel_settings_id,
        start_date=start_date,
        end_date=end_date,
    )
    reservation_spend = _build_reservation_spend_map(
        hotel_settings_id=hotel_settings_id,
        start_date=start_date,
        end_date=end_date,
    )

    occupied_nights_by_type: dict[str, int] = defaultdict(int)
    reservation_count_by_type: dict[str, int] = defaultdict(int)
    revenue_by_type: dict[str, Decimal] = defaultdict(lambda: MONEY_ZERO)

    rows_by_reservation: dict[int, list[Any]] = defaultdict(list)
    for row, overlap_nights in rows:
        reservation_id = getattr(row.reservation, "id", None)
        if reservation_id is None:
            continue
        rows_by_reservation[reservation_id].append((row, overlap_nights))

    for reservation_id, reservation_rows in rows_by_reservation.items():
        reservation_total = reservation_spend.get(reservation_id, MONEY_ZERO)
        row_count = len(reservation_rows)

        per_row_revenue = _safe_divide(
            reservation_total,
            _to_decimal(row_count),
        )

        used_types_for_reservation: set[str] = set()
        for row, overlap_nights in reservation_rows:
            room_type_name = _resolve_room_type_name(getattr(row, "room", None))
            occupied_nights_by_type[room_type_name] += overlap_nights
            revenue_by_type[room_type_name] += per_row_revenue
            used_types_for_reservation.add(room_type_name)

        for room_type_name in used_types_for_reservation:
            reservation_count_by_type[room_type_name] += 1

    days = (end_date - start_date).days + 1
    result = []

    all_types = set(room_count_by_type.keys()) | set(occupied_nights_by_type.keys())
    for room_type_name in all_types:
        room_count = room_count_by_type.get(room_type_name, 0)
        occupied_nights = occupied_nights_by_type.get(room_type_name, 0)
        available_nights = room_count * max(days, 1)
        occupancy_pct = (
            _percentage(_to_decimal(occupied_nights), _to_decimal(available_nights))
            if available_nights > 0
            else MONEY_ZERO
        )
        avg_stay = _safe_divide(
            _to_decimal(occupied_nights),
            _to_decimal(reservation_count_by_type.get(room_type_name, 0)),
        )

        result.append(
            {
                "room_type": room_type_name,
                "occupancy_pct": _to_float(occupancy_pct),
                "avg_stay": _to_float(avg_stay, places=1),
                "income": _to_float(revenue_by_type.get(room_type_name, MONEY_ZERO)),
            }
        )

    result.sort(key=lambda item: item["income"], reverse=True)
    return result


def _build_service_categories_metrics(
    *,
    hotel_settings_id: int,
    start_date: date,
    end_date: date,
) -> dict[str, dict[str, Any]]:
    reservation_ids = _reservation_ids_queryset(hotel_settings_id=hotel_settings_id)

    queryset = Charge.objects.filter(
        is_active=True,
        charge_date__date__gte=start_date,
        charge_date__date__lte=end_date,
    )
    queryset = queryset.filter(reservation_id__in=reservation_ids)

    metrics: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "income": MONEY_ZERO,
            "transactions": 0,
        }
    )

    for charge in queryset.select_related("charge_type"):
        charge_type = getattr(charge, "charge_type", None)
        code = _normalize_code(getattr(charge_type, "code", ""))
        if code in SERVICE_EXCLUDED_CHARGE_CODES:
            continue

        category = (
            str(getattr(charge_type, "name", "") or getattr(charge_type, "code", "")).strip()
            or "Otros"
        )
        amount = _to_decimal(
            getattr(charge, "total_amount", None)
            or getattr(charge, "amount", None)
        )

        metrics[category]["income"] += amount
        metrics[category]["transactions"] += 1

    return metrics


# =========================================================
# RESERVATIONS / OCCUPANCY HELPERS
# =========================================================
def _reservation_ids_queryset(*, hotel_settings_id: int):
    return ReservationRoom.objects.filter(
        room__floor__hotel_settings_id=hotel_settings_id
    ).values_list("reservation_id", flat=True)


def _get_overlapping_reservation_rows(
    *,
    hotel_settings_id: int,
    start_date: date,
    end_date: date,
) -> list[tuple[Any, int]]:
    queryset = ReservationRoom.objects.select_related(
        "reservation",
        "reservation__status",
        "room",
        "room__floor",
    ).filter(room__floor__hotel_settings_id=hotel_settings_id)

    rows: list[tuple[Any, int]] = []
    for row in queryset:
        overlap_nights = _calculate_row_overlap_nights(
            row=row,
            start_date=start_date,
            end_date=end_date,
        )
        if overlap_nights > 0:
            rows.append((row, overlap_nights))
    return rows


def _unique_reservations_from_rows(rows: list[tuple[Any, int]]) -> list[Any]:
    unique: dict[Any, Any] = {}
    for row, _ in rows:
        reservation = getattr(row, "reservation", None)
        reservation_id = getattr(reservation, "id", None)
        if reservation is None or reservation_id is None:
            continue
        unique[reservation_id] = reservation
    return list(unique.values())


def _calculate_row_overlap_nights(
    *,
    row: Any,
    start_date: date,
    end_date: date,
) -> int:
    reservation = getattr(row, "reservation", None)
    if reservation is None:
        return 0

    status_code = _normalize_code(
        _first_existing_attr_value(reservation, ["status.code", "status"])
    )
    if status_code in CANCELLED_RESERVATION_STATUS_CODES:
        return 0

    check_in = _resolve_reservation_check_in_date(reservation)
    check_out = _resolve_reservation_check_out_date(reservation)

    if not check_in or not check_out:
        return 0
    if check_out <= check_in:
        return 0

    period_end_exclusive = end_date + timedelta(days=1)
    overlap_start = max(check_in, start_date)
    overlap_end = min(check_out, period_end_exclusive)
    overlap_nights = (overlap_end - overlap_start).days

    return max(overlap_nights, 0)


def _calculate_reservation_overlap_nights(
    *,
    reservation: Any,
    start_date: date,
    end_date: date,
) -> int:
    status_code = _normalize_code(
        _first_existing_attr_value(reservation, ["status.code", "status"])
    )
    if status_code in CANCELLED_RESERVATION_STATUS_CODES:
        return 0

    check_in = _resolve_reservation_check_in_date(reservation)
    check_out = _resolve_reservation_check_out_date(reservation)

    if not check_in or not check_out:
        return 0
    if check_out <= check_in:
        return 0

    period_end_exclusive = end_date + timedelta(days=1)
    overlap_start = max(check_in, start_date)
    overlap_end = min(check_out, period_end_exclusive)
    overlap_nights = (overlap_end - overlap_start).days

    return max(overlap_nights, 0)


def _resolve_reservation_check_in_date(reservation: Any) -> date | None:
    value = (
        _first_existing_attr_value(
            reservation,
            [
                "real_check_in",
                "actual_check_in",
                "expected_check_in",
                "check_in",
            ],
        )
    )
    return _coerce_to_date(value)


def _resolve_reservation_check_out_date(reservation: Any) -> date | None:
    value = (
        _first_existing_attr_value(
            reservation,
            [
                "real_check_out",
                "actual_check_out",
                "expected_check_out",
                "check_out",
            ],
        )
    )
    return _coerce_to_date(value)


def _resolve_room_type_name(room: Any) -> str:
    if room is None:
        return "Sin tipo"

    return str(
        _first_existing_attr_value(
            room,
            [
                "room_type.name",
                "room_type.type_name",
                "type_room.name",
                "type_room.type_name",
                "category.name",
            ],
        )
        or "Sin tipo"
    )


def _resolve_guest_name(reservation: Any) -> str:
    first_name = _first_existing_attr_value(
        reservation,
        [
            "client.first_name",
            "guest.first_name",
            "primary_guest.first_name",
            "main_guest.first_name",
        ],
    )
    last_name = _first_existing_attr_value(
        reservation,
        [
            "client.last_name",
            "guest.last_name",
            "primary_guest.last_name",
            "main_guest.last_name",
        ],
    )
    full_name = " ".join(
        part for part in [str(first_name or "").strip(), str(last_name or "").strip()] if part
    ).strip()
    if full_name:
        return full_name

    fallback = _first_existing_attr_value(
        reservation,
        [
            "client.full_name",
            "client.name",
            "guest.full_name",
            "guest.name",
            "primary_guest.full_name",
            "primary_guest.name",
            "main_guest.full_name",
            "main_guest.name",
        ],
    )
    return str(fallback or "").strip()


def _resolve_guest_country(reservation: Any) -> str:
    value = _first_existing_attr_value(
        reservation,
        [
            "client.country.name",
            "client.country",
            "client.nationality.name",
            "client.nationality",
            "guest.country.name",
            "guest.country",
            "primary_guest.country.name",
            "primary_guest.country",
            "main_guest.country.name",
            "main_guest.country",
        ],
    )
    return str(value or "").strip()


def _resolve_guest_segment(reservation: Any) -> str:
    value = _first_existing_attr_value(
        reservation,
        [
            "client.client_type.name",
            "client.client_type.code",
            "client.segment.name",
            "client.segment.code",
            "guest.segment.name",
            "guest.segment.code",
        ],
    )
    return str(value or "").strip()


def _resolve_guest_count(reservation: Any) -> int:
    direct_count = _first_existing_attr_value(
        reservation,
        [
            "guest_count",
            "total_guests",
            "number_of_guests",
            "passenger_count",
        ],
    )
    if direct_count is not None:
        try:
            parsed = int(direct_count)
            return max(parsed, 1)
        except (TypeError, ValueError):
            pass

    adults = _safe_int(_first_existing_attr_value(reservation, ["adults"]))
    children = _safe_int(_first_existing_attr_value(reservation, ["children"]))
    kids = _safe_int(_first_existing_attr_value(reservation, ["kids"]))
    infants = _safe_int(_first_existing_attr_value(reservation, ["infants"]))

    total = adults + children + kids + infants
    return total if total > 0 else 1


def _room_count(*, hotel_settings_id: int) -> int:
    return Room.objects.filter(floor__hotel_settings_id=hotel_settings_id).count()


# =========================================================
# FINANCIAL HELPERS
# =========================================================
def _build_reservation_spend_map(
    *,
    hotel_settings_id: int,
    start_date: date,
    end_date: date,
) -> dict[int, Decimal]:
    reservation_ids = _reservation_ids_queryset(hotel_settings_id=hotel_settings_id)

    invoice_queryset = Invoice.objects.filter(
        is_active=True,
        issue_date__date__gte=start_date,
        issue_date__date__lte=end_date,
        reservation_id__in=reservation_ids,
    ).exclude(status__code__in=ANULLED_INVOICE_STATUS_CODES)

    credit_note_queryset = CreditNote.objects.filter(
        is_active=True,
        issue_date__date__gte=start_date,
        issue_date__date__lte=end_date,
        invoice__is_active=True,
        invoice__reservation_id__in=reservation_ids,
    )

    invoice_totals: dict[int, Decimal] = defaultdict(lambda: MONEY_ZERO)
    for row in invoice_queryset.values("reservation_id").annotate(total=Sum("total_amount")):
        reservation_id = row["reservation_id"]
        invoice_totals[reservation_id] += _to_decimal(row["total"])

    credit_totals: dict[int, Decimal] = defaultdict(lambda: MONEY_ZERO)
    for row in credit_note_queryset.values("invoice__reservation_id").annotate(total=Sum("amount")):
        reservation_id = row["invoice__reservation_id"]
        credit_totals[reservation_id] += _to_decimal(row["total"])

    result: dict[int, Decimal] = {}
    reservation_keys = set(invoice_totals.keys()) | set(credit_totals.keys())
    for reservation_id in reservation_keys:
        value = invoice_totals.get(reservation_id, MONEY_ZERO) - credit_totals.get(
            reservation_id,
            MONEY_ZERO,
        )
        if value < MONEY_ZERO:
            value = MONEY_ZERO
        result[reservation_id] = value

    return result


# =========================================================
# GENERIC HELPERS
# =========================================================
def _iter_month_ranges(
    start_date: date,
    end_date: date,
):
    cursor = start_date.replace(day=1)
    last_month = end_date.replace(day=1)

    while cursor <= last_month:
        month_end = date(cursor.year, cursor.month, monthrange(cursor.year, cursor.month)[1])
        effective_start = max(cursor, start_date)
        effective_end = min(month_end, end_date)
        yield cursor, effective_start, effective_end
        cursor = _add_months(cursor, 1)


def _iter_last_week_ranges(*, end_date: date, weeks: int) -> list[tuple[date, date]]:
    if weeks <= 0:
        raise ValidationError({"weeks": "weeks must be greater than zero."})

    ranges = []
    current_monday = end_date - timedelta(days=end_date.weekday())

    for offset in range(weeks - 1, -1, -1):
        week_start = current_monday - timedelta(days=7 * offset)
        week_end = week_start + timedelta(days=6)
        if week_end > end_date:
            week_end = end_date
        ranges.append((week_start, week_end))

    return ranges


def _add_months(base_date: date, delta_months: int) -> date:
    month_index = (base_date.month - 1) + delta_months
    year = base_date.year + (month_index // 12)
    month = (month_index % 12) + 1
    return date(year, month, 1)


def _shift_year_safe(base_date: date, *, years: int) -> date:
    target_year = base_date.year + years
    try:
        return base_date.replace(year=target_year)
    except ValueError:
        return base_date.replace(year=target_year, day=28)


def _parse_iso_date(raw_value: str, *, field_name: str) -> date:
    value = str(raw_value).strip()
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(
            {field_name: f"Invalid date format: {value}. Use YYYY-MM-DD."}
        ) from exc


def _apply_date_filter(queryset, *, candidates: list[str], start_date: date, end_date: date):
    last_error = None
    for candidate in candidates:
        try:
            return queryset.filter(**{f"{candidate}__gte": start_date, f"{candidate}__lte": end_date})
        except FieldError as exc:
            last_error = exc
            continue

    if last_error:
        return queryset.none()
    return queryset


def _filter_queryset_by_reservation_candidates(queryset, *, reservation_ids, candidates: list[str]):
    last_error = None
    for candidate in candidates:
        try:
            return queryset.filter(**{candidate: reservation_ids})
        except FieldError as exc:
            last_error = exc
            continue

    if last_error:
        return queryset.none()
    return queryset


def _apply_optional_boolean_filter(queryset, field_name: str, value: bool):
    try:
        queryset.model._meta.get_field(field_name)
        return queryset.filter(**{field_name: value})
    except FieldDoesNotExist:
        return queryset


def _first_existing_attr_value(obj: Any, paths: list[str]) -> Any:
    for path in paths:
        current = obj
        failed = False
        for part in path.split("."):
            if current is None:
                failed = True
                break
            try:
                current = getattr(current, part)
            except (AttributeError, ObjectDoesNotExist):
                failed = True
                break
        if failed:
            continue
        if current is not None:
            return current
    return None


def _coerce_to_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return None


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _safe_divide(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator <= MONEY_ZERO:
        return MONEY_ZERO
    return numerator / denominator


def _percentage(part: Decimal, total: Decimal) -> Decimal:
    if total <= MONEY_ZERO:
        return MONEY_ZERO
    return (part / total) * Decimal("100.00")


def _calculate_percentage_change(*, current: Decimal, previous: Decimal) -> Decimal | None:
    if previous == MONEY_ZERO:
        if current == MONEY_ZERO:
            return MONEY_ZERO
        return None
    return ((current - previous) / previous) * Decimal("100.00")


def _normalize_code(value: Any) -> str:
    return str(value or "").strip().upper()


def _to_decimal(value: Any) -> Decimal:
    if value is None:
        return MONEY_ZERO
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return MONEY_ZERO


def _quantize(value: Decimal, *, places: int = 2) -> Decimal:
    quantizer = Decimal("1").scaleb(-places)
    return _to_decimal(value).quantize(quantizer, rounding=ROUND_HALF_UP)


def _to_float(
    value: Decimal | None,
    *,
    places: int = 2,
    allow_null: bool = False,
) -> float | None:
    if value is None:
        return None if allow_null else 0.0
    return float(_quantize(_to_decimal(value), places=places))
