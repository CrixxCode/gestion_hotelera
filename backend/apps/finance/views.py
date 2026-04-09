from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import HasResourcePermission
from accounts.soft_delete import LogicalDeleteViewSetMixin
from apps.finance.models import (
    Expense,
    FinancialControlConfig,
    FinancialStatementSnapshot,
)
from apps.finance.serializers import (
    ExpenseSerializer,
    FinancialControlConfigSerializer,
    FinancialStatementSnapshotSerializer,
)
from apps.hotel_settings.models import HotelSettings
from apps.finance.services import (
    build_financial_dashboard,
    build_financial_statements,
    build_what_if_scenario,
    parse_decimal_param,
    resolve_period,
    resolve_year_month,
)


class ExpenseViewSet(LogicalDeleteViewSetMixin, viewsets.ModelViewSet):
    queryset = (
        Expense.objects.select_related(
            "hotel_settings",
            "expense_category",
            "payment_method",
        ).order_by("-id")
    )
    serializer_class = ExpenseSerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["expenses.read"]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["hotel_settings", "expense_category", "payment_method", "is_active"]
    search_fields = [
        "concept",
        "description",
        "reference",
        "supplier_name",
        "hotel_settings__hotel_name",
        "expense_category__name",
        "expense_category__code",
        "payment_method__name",
        "payment_method__code",
    ]
    ordering_fields = [
        "id",
        "concept",
        "amount",
        "expense_date",
        "created_at",
        "updated_at",
    ]
    ordering = ["-id"]

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["expenses.write"]
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()


class FinancialControlConfigViewSet(viewsets.ModelViewSet):
    queryset = FinancialControlConfig.objects.select_related("hotel_settings").order_by("hotel_settings__hotel_name")
    serializer_class = FinancialControlConfigSerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["financial_control.read"]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["hotel_settings"]
    search_fields = ["hotel_settings__hotel_name", "district_name"]
    ordering_fields = [
        "id",
        "hotel_settings__hotel_name",
        "district_name",
        "updated_at",
        "created_at",
    ]
    ordering = ["hotel_settings__hotel_name"]

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["financial_control.write"]
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()


class FinancialStatementSnapshotViewSet(LogicalDeleteViewSetMixin, viewsets.ModelViewSet):
    queryset = FinancialStatementSnapshot.objects.select_related("hotel_settings").order_by(
        "-period_year",
        "-period_month",
        "-id",
    )
    serializer_class = FinancialStatementSnapshotSerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["financial_control.read"]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["hotel_settings", "period_year", "period_month", "is_active"]
    search_fields = ["hotel_settings__hotel_name", "notes"]
    ordering_fields = [
        "id",
        "period_year",
        "period_month",
        "created_at",
        "updated_at",
    ]
    ordering = ["-period_year", "-period_month", "-id"]

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["financial_control.write"]
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()


class FinancialControlViewSet(viewsets.ViewSet):
    permission_classes = [HasResourcePermission]
    required_scopes = ["financial_control.read"]

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["financial_control.write"]
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()

    def list(self, request):
        return Response(
            {
                "endpoints": {
                    "dashboard": "/api/financial-control/dashboard/",
                    "what_if": "/api/financial-control/what-if/",
                    "statements": "/api/financial-control/statements/",
                }
            }
        )

    @action(detail=False, methods=["get"], url_path="dashboard")
    def dashboard(self, request):
        try:
            hotel_settings_id = self._parse_hotel_settings_id()
            start_date, end_date = resolve_period(
                start_date_raw=request.query_params.get("start_date"),
                end_date_raw=request.query_params.get("end_date"),
            )
            payload = build_financial_dashboard(
                hotel_settings_id=hotel_settings_id,
                start_date=start_date,
                end_date=end_date,
            )
            return Response(payload)
        except DjangoValidationError as exc:
            return self._validation_error_response(exc)

    @action(detail=False, methods=["get"], url_path="what-if")
    def what_if(self, request):
        try:
            hotel_settings_id = self._parse_hotel_settings_id()
            start_date, end_date = resolve_period(
                start_date_raw=request.query_params.get("start_date"),
                end_date_raw=request.query_params.get("end_date"),
            )
            rate_change_pct = parse_decimal_param(
                value=request.query_params.get("rate_change_pct"),
                field="rate_change_pct",
                default=Decimal("0"),
            )
            occupancy_change_pct = parse_decimal_param(
                value=request.query_params.get("occupancy_change_pct"),
                field="occupancy_change_pct",
                default=Decimal("0"),
            )
            target_occupancy_raw = request.query_params.get("target_occupancy_pct")
            target_occupancy_pct = (
                parse_decimal_param(
                    value=target_occupancy_raw,
                    field="target_occupancy_pct",
                )
                if target_occupancy_raw is not None and str(target_occupancy_raw).strip() != ""
                else None
            )
            operating_cost_change_pct = parse_decimal_param(
                value=request.query_params.get("operating_cost_change_pct"),
                field="operating_cost_change_pct",
                default=Decimal("0"),
            )
            payload = build_what_if_scenario(
                hotel_settings_id=hotel_settings_id,
                start_date=start_date,
                end_date=end_date,
                rate_change_pct=rate_change_pct,
                occupancy_change_pct=occupancy_change_pct,
                target_occupancy_pct=target_occupancy_pct,
                operating_cost_change_pct=operating_cost_change_pct,
            )
            return Response(payload)
        except DjangoValidationError as exc:
            return self._validation_error_response(exc)

    @action(detail=False, methods=["get"], url_path="statements")
    def statements(self, request):
        try:
            hotel_settings_id = self._parse_hotel_settings_id()
            year, month = resolve_year_month(
                year_raw=request.query_params.get("year"),
                month_raw=request.query_params.get("month"),
            )
            payload = build_financial_statements(
                hotel_settings_id=hotel_settings_id,
                year=year,
                month=month,
            )
            return Response(payload)
        except DjangoValidationError as exc:
            return self._validation_error_response(exc)

    def _parse_hotel_settings_id(self) -> int:
        raw_value = (self.request.query_params.get("hotel_settings") or "").strip()
        if not raw_value:
            raise DjangoValidationError(
                {"hotel_settings": "hotel_settings query parameter is required."}
            )
        if not raw_value.isdigit():
            raise DjangoValidationError({"hotel_settings": "hotel_settings must be a valid integer."})
        hotel_settings_id = int(raw_value)
        if not HotelSettings.objects.filter(id=hotel_settings_id).exists():
            raise DjangoValidationError({"hotel_settings": "The selected hotel_settings does not exist."})
        return hotel_settings_id

    def _validation_error_response(self, exc: DjangoValidationError):
        if hasattr(exc, "message_dict"):
            payload = exc.message_dict
        elif hasattr(exc, "messages"):
            payload = {"detail": exc.messages}
        else:
            payload = {"detail": str(exc)}
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)
