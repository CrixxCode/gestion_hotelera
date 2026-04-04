from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from accounts.permissions import HasResourcePermission
from apps.reservations.models import (
    Reservation,
    ReservationRoom,
    ReservationGuest,
    ReservationDeposit,
)
from apps.reservations.serializers import (
    ReservationListSerializer,
    ReservationDetailSerializer,
    ReservationWriteSerializer,
    ReservationRoomSerializer,
    ReservationGuestSerializer,
    ReservationDepositSerializer,
)
from apps.reservations.services import (
    RESERVATION_STATUS_CANCELLED,
    RESERVATION_STATUS_CONFIRMED,
    RESERVATION_STATUS_FINISHED,
    RESERVATION_STATUS_IN_PROGRESS,
    RESERVATION_STATUS_PENDING,
    get_reservation_status_by_code,
)


class ReservationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class ReservationViewSet(viewsets.ModelViewSet):
    queryset = Reservation.objects.all()
    serializer_class = ReservationWriteSerializer
    pagination_class = ReservationPagination
    permission_classes = [HasResourcePermission]
    required_scopes = ["reservations.read"]

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "id",
        "client__first_name",
        "client__last_name",
        "client__document_number",
        "client__email",
        "promo_code",
        "notes",
    ]
    ordering_fields = [
        "id",
        "expected_check_in",
        "expected_check_out",
        "real_check_in",
        "real_check_out",
        "created_at",
        "total_discount",
    ]
    ordering = ["-id"]

    @staticmethod
    def _parse_bool(value) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).strip().lower() in {"1", "true", "yes", "si", "on"}

    @staticmethod
    def _get_finished_retention_days() -> int:
        raw_value = getattr(settings, "RESERVATIONS_FINISHED_RETENTION_DAYS", 30)
        try:
            days = int(raw_value)
        except (TypeError, ValueError):
            return 30
        return max(days, 0)

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related(
                "client",
                "status",
                "origin",
                "created_by",
            )
            .order_by("-id")
        )

        if self.action == "list":
            queryset = queryset.prefetch_related(
                "policies",
                "rooms_detail",
                "deposits",
            )
        elif self.action in {"retrieve", "confirm", "check_in", "check_out", "cancel"}:
            queryset = queryset.prefetch_related(
                "policies",
                "rooms_detail__room",
                "rooms_detail__meal_plan",
                "guests__document_type",
                "deposits__payment_method",
                "deposits__status",
            )

        if self.action != "list":
            return queryset

        include_finished = self._parse_bool(
            self.request.query_params.get("include_finished")
        )
        if include_finished:
            return queryset

        retention_days = self._get_finished_retention_days()
        cutoff = timezone.now() - timedelta(days=retention_days)

        return queryset.exclude(
            status__code=RESERVATION_STATUS_FINISHED,
            real_check_out__lt=cutoff,
        )

    def get_serializer_class(self):
        if self.action == "list":
            return ReservationListSerializer
        if self.action == "retrieve":
            return ReservationDetailSerializer
        return ReservationWriteSerializer

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["reservations.write"]
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @staticmethod
    def _normalize_code(value) -> str:
        return str(value or "").strip().upper()

    def _get_status_obj(self, code: str):
        status_obj = get_reservation_status_by_code(code)
        if not status_obj:
            raise ValueError(f"No existe un estado activo '{code}' para reservas.")
        return status_obj

    def _set_status(
        self,
        reservation: Reservation,
        *,
        status_code: str,
        set_real_check_in: bool | None = None,
        set_real_check_out: bool | None = None,
    ) -> Reservation:
        status_obj = self._get_status_obj(status_code)
        update_fields = ["status"]

        reservation.status = status_obj

        if set_real_check_in is True and not reservation.real_check_in:
            reservation.real_check_in = timezone.now()
            update_fields.append("real_check_in")

        if set_real_check_out is True and not reservation.real_check_out:
            reservation.real_check_out = timezone.now()
            update_fields.append("real_check_out")

        if set_real_check_in is False and reservation.real_check_in is not None:
            reservation.real_check_in = None
            update_fields.append("real_check_in")

        if set_real_check_out is False and reservation.real_check_out is not None:
            reservation.real_check_out = None
            update_fields.append("real_check_out")

        reservation.save(update_fields=update_fields)
        reservation.refresh_from_db()
        return reservation

    def _error(self, message: str) -> Response:
        return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)

    def _get_locked_reservation(self, reservation_id: int | str):
        return self.get_queryset().select_for_update().get(pk=reservation_id)

    @action(detail=True, methods=["post"], url_path="confirm")
    def confirm(self, request, pk=None):
        with transaction.atomic():
            reservation = self._get_locked_reservation(pk)
            code = self._normalize_code(reservation.status_code)

            if reservation.real_check_out:
                return self._error("La reserva ya fue finalizada.")

            if reservation.real_check_in:
                return self._error("La reserva ya tiene check-in registrado.")

            if code == RESERVATION_STATUS_CANCELLED:
                return self._error("No puedes confirmar una reserva cancelada.")

            if code == RESERVATION_STATUS_FINISHED:
                return self._error("No puedes confirmar una reserva finalizada.")

            if code == RESERVATION_STATUS_CONFIRMED:
                serializer = ReservationDetailSerializer(reservation, context=self.get_serializer_context())
                return Response(serializer.data, status=status.HTTP_200_OK)

            if code != RESERVATION_STATUS_PENDING:
                return self._error("Solo se pueden confirmar reservas en estado pendiente.")

            try:
                reservation = self._set_status(reservation, status_code=RESERVATION_STATUS_CONFIRMED)
            except ValueError as exc:
                return self._error(str(exc))

        serializer = ReservationDetailSerializer(reservation, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="check-in")
    def check_in(self, request, pk=None):
        with transaction.atomic():
            reservation = self._get_locked_reservation(pk)
            code = self._normalize_code(reservation.status_code)

            if reservation.real_check_out:
                return self._error("La reserva ya fue finalizada.")

            if reservation.real_check_in:
                return self._error("La reserva ya tiene check-in registrado.")

            if code == RESERVATION_STATUS_CANCELLED:
                return self._error("No puedes hacer check-in en una reserva cancelada.")

            if code != RESERVATION_STATUS_CONFIRMED:
                return self._error("Debes confirmar la reserva antes de hacer check-in.")

            try:
                reservation = self._set_status(
                    reservation,
                    status_code=RESERVATION_STATUS_IN_PROGRESS,
                    set_real_check_in=True,
                )
            except ValueError as exc:
                return self._error(str(exc))

        serializer = ReservationDetailSerializer(reservation, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="check-out")
    def check_out(self, request, pk=None):
        with transaction.atomic():
            reservation = self._get_locked_reservation(pk)
            code = self._normalize_code(reservation.status_code)

            if reservation.real_check_out:
                serializer = ReservationDetailSerializer(reservation, context=self.get_serializer_context())
                return Response(serializer.data, status=status.HTTP_200_OK)

            if reservation.real_check_in is None:
                return self._error("No puedes hacer check-out sin haber registrado check-in.")

            if code == RESERVATION_STATUS_CANCELLED:
                return self._error("No puedes hacer check-out en una reserva cancelada.")

            try:
                reservation = self._set_status(
                    reservation,
                    status_code=RESERVATION_STATUS_FINISHED,
                    set_real_check_out=True,
                )
            except ValueError as exc:
                return self._error(str(exc))

        serializer = ReservationDetailSerializer(reservation, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        with transaction.atomic():
            reservation = self._get_locked_reservation(pk)
            code = self._normalize_code(reservation.status_code)

            if reservation.real_check_in:
                return self._error("No puedes cancelar una reserva que ya tiene check-in.")

            if reservation.real_check_out:
                return self._error("No puedes cancelar una reserva finalizada.")

            if code == RESERVATION_STATUS_CANCELLED:
                serializer = ReservationDetailSerializer(reservation, context=self.get_serializer_context())
                return Response(serializer.data, status=status.HTTP_200_OK)

            if code == RESERVATION_STATUS_FINISHED:
                return self._error("No puedes cancelar una reserva finalizada.")

            try:
                reservation = self._set_status(reservation, status_code=RESERVATION_STATUS_CANCELLED)
            except ValueError as exc:
                return self._error(str(exc))

        serializer = ReservationDetailSerializer(reservation, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_200_OK)


class ReservationRoomViewSet(viewsets.ModelViewSet):
    queryset = (
        ReservationRoom.objects.select_related(
            "reservation",
            "room",
            "meal_plan",
        )
        .order_by("-id")
    )
    serializer_class = ReservationRoomSerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["reservation_rooms.read"]

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "reservation__id",
        "room__number",
    ]
    ordering_fields = [
        "id",
        "night_rate",
        "adults",
        "children",
        "created_at",
    ]
    ordering = ["-id"]

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["reservation_rooms.write"]
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()


class ReservationGuestViewSet(viewsets.ModelViewSet):
    queryset = (
        ReservationGuest.objects.select_related(
            "reservation",
            "document_type",
        )
        .order_by("-id")
    )
    serializer_class = ReservationGuestSerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["reservation_guests.read"]

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "reservation__id",
        "document_number",
        "first_name",
        "last_name",
        "nationality",
    ]
    ordering_fields = [
        "id",
        "first_name",
        "last_name",
        "birth_date",
        "created_at",
    ]
    ordering = ["-id"]

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["reservation_guests.write"]
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()


class ReservationDepositViewSet(viewsets.ModelViewSet):
    queryset = (
        ReservationDeposit.objects.select_related(
            "reservation",
            "payment_method",
            "status",
        )
        .order_by("-id")
    )
    serializer_class = ReservationDepositSerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["reservation_deposits.read"]

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "reservation__id",
        "reference",
        "notes",
    ]
    ordering_fields = [
        "id",
        "deposit_date",
        "amount",
        "created_at",
    ]
    ordering = ["-id"]

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["reservation_deposits.write"]
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()
