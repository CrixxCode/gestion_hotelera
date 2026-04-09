from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import HasResourcePermission
from apps.hotel_settings.models import HotelSettings
from apps.reports.serializers import (
    ExecutiveReportSerializer,
    OccupancyReportSerializer,
    ReportQuerySerializer,
    RevenueReportSerializer,
    ServicesReportSerializer,
)
from apps.reports.services import (
    build_executive_report,
    build_occupancy_report,
    build_revenue_report,
    build_services_report,
    parse_hotel_settings_id,
    resolve_report_period,
)


class ReportsViewSet(viewsets.ViewSet):
    permission_classes = [HasResourcePermission]
    required_scopes = ["reports.read"]

    def get_required_scopes(self):
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()

    def list(self, request):
        return Response(
            {
                "endpoints": {
                    "executive": "/api/reports/executive/",
                    "revenue": "/api/reports/revenue/",
                    "occupancy": "/api/reports/occupancy/",
                    "services": "/api/reports/services/",
                }
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="executive")
    def executive(self, request):
        try:
            payload = self._build_payload(
                request=request,
                builder=build_executive_report,
                response_serializer_class=ExecutiveReportSerializer,
            )
            return Response(payload, status=status.HTTP_200_OK)
        except DjangoValidationError as exc:
            return self._validation_error_response(exc)

    @action(detail=False, methods=["get"], url_path="revenue")
    def revenue(self, request):
        try:
            payload = self._build_payload(
                request=request,
                builder=build_revenue_report,
                response_serializer_class=RevenueReportSerializer,
            )
            return Response(payload, status=status.HTTP_200_OK)
        except DjangoValidationError as exc:
            return self._validation_error_response(exc)

    @action(detail=False, methods=["get"], url_path="occupancy")
    def occupancy(self, request):
        try:
            payload = self._build_payload(
                request=request,
                builder=build_occupancy_report,
                response_serializer_class=OccupancyReportSerializer,
            )
            return Response(payload, status=status.HTTP_200_OK)
        except DjangoValidationError as exc:
            return self._validation_error_response(exc)

    @action(detail=False, methods=["get"], url_path="services")
    def services(self, request):
        try:
            payload = self._build_payload(
                request=request,
                builder=build_services_report,
                response_serializer_class=ServicesReportSerializer,
            )
            return Response(payload, status=status.HTTP_200_OK)
        except DjangoValidationError as exc:
            return self._validation_error_response(exc)

    def _build_payload(self, *, request, builder, response_serializer_class):
        query_serializer = ReportQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        validated = query_serializer.validated_data

        hotel_settings_id = self._resolve_hotel_settings_id(validated)

        if "year" in validated:
            start_date, end_date, _ = resolve_report_period(
                year_raw=str(validated["year"]),
            )
        elif "start_date" in validated and "end_date" in validated:
            start_date, end_date, _ = resolve_report_period(
                start_date_raw=validated["start_date"].isoformat(),
                end_date_raw=validated["end_date"].isoformat(),
            )
        else:
            start_date, end_date, _ = resolve_report_period()

        payload = builder(
            hotel_settings_id=hotel_settings_id,
            start_date=start_date,
            end_date=end_date,
        )

        serializer = response_serializer_class(payload)
        return serializer.data

    def _resolve_hotel_settings_id(self, validated):
        hotel_settings_raw = validated.get("hotel_settings")
        if hotel_settings_raw is not None:
            return parse_hotel_settings_id(hotel_settings_raw)

        hotel_settings_ids = list(
            HotelSettings.objects.order_by("id").values_list("id", flat=True)
        )
        if len(hotel_settings_ids) == 1:
            return hotel_settings_ids[0]

        if not hotel_settings_ids:
            raise DjangoValidationError(
                {
                    "hotel_settings": (
                        "No hotel settings found. Create one or send hotel_settings in query params."
                    )
                }
            )

        raise DjangoValidationError(
            {
                "hotel_settings": (
                    "hotel_settings is required when multiple hotels are configured."
                )
            }
        )

    def _validation_error_response(self, exc):
        if hasattr(exc, "message_dict"):
            payload = exc.message_dict
        elif hasattr(exc, "messages"):
            payload = {"detail": exc.messages}
        else:
            payload = {"detail": str(exc)}
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)
