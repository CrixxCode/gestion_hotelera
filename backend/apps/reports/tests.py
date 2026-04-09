from datetime import date
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from apps.reports.serializers import ReportQuerySerializer
from apps.reports.services import resolve_report_period
from apps.reports.views import ReportsViewSet


class ReportQuerySerializerTests(SimpleTestCase):
    def test_valid_with_year(self):
        serializer = ReportQuerySerializer(
            data={
                "hotel_settings": 1,
                "year": 2026,
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_valid_with_date_range(self):
        serializer = ReportQuerySerializer(
            data={
                "hotel_settings": 1,
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_invalid_with_year_and_dates(self):
        serializer = ReportQuerySerializer(
            data={
                "hotel_settings": 1,
                "year": 2026,
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
            }
        )
        self.assertFalse(serializer.is_valid())

    def test_invalid_with_only_start_date(self):
        serializer = ReportQuerySerializer(
            data={
                "hotel_settings": 1,
                "start_date": "2026-01-01",
            }
        )
        self.assertFalse(serializer.is_valid())

    def test_valid_when_hotel_settings_missing(self):
        serializer = ReportQuerySerializer(data={"year": 2026})
        self.assertTrue(serializer.is_valid(), serializer.errors)


class ResolveReportPeriodTests(SimpleTestCase):
    def test_resolve_report_period_with_year(self):
        start_date, end_date, year = resolve_report_period(year_raw="2026")
        self.assertEqual(start_date, date(2026, 1, 1))
        self.assertEqual(end_date, date(2026, 12, 31))
        self.assertEqual(year, 2026)

    def test_resolve_report_period_with_range(self):
        start_date, end_date, year = resolve_report_period(
            start_date_raw="2026-04-01",
            end_date_raw="2026-04-30",
        )
        self.assertEqual(start_date, date(2026, 4, 1))
        self.assertEqual(end_date, date(2026, 4, 30))
        self.assertEqual(year, 2026)

    def test_resolve_report_period_invalid_year(self):
        with self.assertRaises(ValidationError):
            resolve_report_period(year_raw="abc")

    def test_resolve_report_period_invalid_range(self):
        with self.assertRaises(ValidationError):
            resolve_report_period(
                start_date_raw="2026-05-10",
                end_date_raw="2026-05-01",
            )


class ReportsViewSetTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @patch("apps.reports.views.parse_hotel_settings_id")
    @patch("apps.reports.views.resolve_report_period")
    @patch("apps.reports.views.build_executive_report")
    def test_executive_returns_200(
        self,
        mock_build_executive_report,
        mock_resolve_report_period,
        mock_parse_hotel_settings_id,
    ):
        mock_parse_hotel_settings_id.return_value = 1
        mock_resolve_report_period.return_value = (
            date(2026, 1, 1),
            date(2026, 12, 31),
            2026,
        )
        mock_build_executive_report.return_value = {
            "filters": {
                "hotel_settings": 1,
                "year": 2026,
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
                "generated_at": "2026-04-08T10:45:00Z",
            },
            "kpis": {
                "annual_income": {"value": 663900.0, "variation_pct": 12.4},
                "net_profit": {"value": 405000.0, "variation_pct": 8.1},
                "average_occupancy": {"value": 82.0, "variation_pct": 3.2},
                "revpar": {"value": 922.0, "variation_pct": 9.7},
            },
            "income_vs_profit_chart": [],
            "payment_methods": [],
            "weekly_occupancy": [],
            "top_guests": [],
        }

        view = ReportsViewSet.as_view({"get": "executive"})
        request = self.factory.get(
            "/api/reports/executive/",
            {"hotel_settings": 1, "year": 2026},
        )
        response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn("kpis", response.data)
        mock_parse_hotel_settings_id.assert_called_once_with(1)

    def test_executive_returns_400_when_missing_hotel_settings(self):
        view = ReportsViewSet.as_view({"get": "executive"})
        request = self.factory.get("/api/reports/executive/", {"year": 2026})
        response = view(request)

        self.assertEqual(response.status_code, 400)

    @patch("apps.reports.views.parse_hotel_settings_id")
    @patch("apps.reports.views.resolve_report_period")
    @patch("apps.reports.views.build_revenue_report")
    def test_revenue_returns_200(
        self,
        mock_build_revenue_report,
        mock_resolve_report_period,
        mock_parse_hotel_settings_id,
    ):
        mock_parse_hotel_settings_id.return_value = 1
        mock_resolve_report_period.return_value = (
            date(2026, 1, 1),
            date(2026, 12, 31),
            2026,
        )
        mock_build_revenue_report.return_value = {
            "filters": {
                "hotel_settings": 1,
                "year": 2026,
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
                "generated_at": "2026-04-08T10:45:00Z",
            },
            "kpis": {
                "gross_income": {"value": 663900.0, "variation_pct": 12.4},
                "total_expenses": {"value": 258900.0, "variation_pct": -6.2},
                "net_profit": {"value": 405000.0, "variation_pct": 18.3},
                "net_margin": {"value": 61.0, "variation_points": 2.8},
            },
            "monthly_income_vs_expenses": [],
            "monthly_net_profit": [],
            "payment_breakdown": [],
            "guest_origin": [],
        }

        view = ReportsViewSet.as_view({"get": "revenue"})
        request = self.factory.get(
            "/api/reports/revenue/",
            {"hotel_settings": 1, "year": 2026},
        )
        response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn("kpis", response.data)

    @patch("apps.reports.views.parse_hotel_settings_id")
    @patch("apps.reports.views.resolve_report_period")
    @patch("apps.reports.views.build_occupancy_report")
    def test_occupancy_returns_200(
        self,
        mock_build_occupancy_report,
        mock_resolve_report_period,
        mock_parse_hotel_settings_id,
    ):
        mock_parse_hotel_settings_id.return_value = 1
        mock_resolve_report_period.return_value = (
            date(2026, 1, 1),
            date(2026, 12, 31),
            2026,
        )
        mock_build_occupancy_report.return_value = {
            "filters": {
                "hotel_settings": 1,
                "year": 2026,
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
                "generated_at": "2026-04-08T10:45:00Z",
            },
            "kpis": {
                "average_occupancy": {"value": 82.0, "variation_pct": 3.2},
                "occupancy_peak": {"value": 95.0, "month": "Jul"},
                "average_stay": {"value": 3.8, "variation_nights": 0.4},
                "total_guests": {"value": 2840, "variation_pct": 14.2},
            },
            "monthly_occupancy_rate": [],
            "by_room_type": [],
            "occupied_rooms_by_month": [],
            "room_type_performance": [],
        }

        view = ReportsViewSet.as_view({"get": "occupancy"})
        request = self.factory.get(
            "/api/reports/occupancy/",
            {"hotel_settings": 1, "year": 2026},
        )
        response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn("kpis", response.data)

    @patch("apps.reports.views.parse_hotel_settings_id")
    @patch("apps.reports.views.resolve_report_period")
    @patch("apps.reports.views.build_services_report")
    def test_services_returns_200(
        self,
        mock_build_services_report,
        mock_resolve_report_period,
        mock_parse_hotel_settings_id,
    ):
        mock_parse_hotel_settings_id.return_value = 1
        mock_resolve_report_period.return_value = (
            date(2026, 1, 1),
            date(2026, 12, 31),
            2026,
        )
        mock_build_services_report.return_value = {
            "filters": {
                "hotel_settings": 1,
                "year": 2026,
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
                "generated_at": "2026-04-08T10:45:00Z",
            },
            "kpis": {
                "service_income": {"value": 87100.0, "variation_pct": 9.3},
                "transactions": {"value": 3947, "variation_pct": 11.2},
                "average_ticket": {"value": 22.1, "variation_value": 1.8},
                "top_category": {"name": "Restaurante", "amount": 28400.0},
            },
            "income_by_category": [],
            "transactions_by_category": [],
            "category_detail": [],
        }

        view = ReportsViewSet.as_view({"get": "services"})
        request = self.factory.get(
            "/api/reports/services/",
            {"hotel_settings": 1, "year": 2026},
        )
        response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn("kpis", response.data)

    def test_list_returns_available_endpoints(self):
        view = ReportsViewSet.as_view({"get": "list"})
        request = self.factory.get("/api/reports/")
        response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn("endpoints", response.data)
