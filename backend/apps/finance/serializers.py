from rest_framework import serializers

from apps.finance.models import (
    Expense,
    FinancialControlConfig,
    OperationalAlert,
    FinancialStatementSnapshot,
)
from apps.master_data.models import MasterData


class ExpenseSerializer(serializers.ModelSerializer):
    hotel_name = serializers.CharField(source="hotel_settings.hotel_name", read_only=True)

    expense_category_name = serializers.CharField(source="expense_category.name", read_only=True)
    expense_category_code = serializers.CharField(source="expense_category.code", read_only=True)
    expense_type_label = serializers.CharField(source="get_expense_type_display", read_only=True)
    cost_behavior_label = serializers.CharField(source="get_cost_behavior_display", read_only=True)

    payment_method_name = serializers.CharField(source="payment_method.name", read_only=True)
    payment_method_code = serializers.CharField(source="payment_method.code", read_only=True)

    class Meta:
        model = Expense
        fields = [
            "id",
            "hotel_settings",
            "hotel_name",
            "expense_category",
            "expense_category_name",
            "expense_category_code",
            "payment_method",
            "payment_method_name",
            "payment_method_code",
            "concept",
            "description",
            "amount",
            "expense_date",
            "expense_type",
            "expense_type_label",
            "cost_behavior",
            "cost_behavior_label",
            "reference",
            "supplier_name",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Expense amount must be greater than 0.")
        return value

    def validate_expense_category(self, value):
        if value and value.group != MasterData.Group.EXPENSE_CATEGORY:
            raise serializers.ValidationError(
                "The selected category must belong to EXPENSE_CATEGORY."
            )
        return value


class FinancialControlConfigSerializer(serializers.ModelSerializer):
    hotel_name = serializers.CharField(source="hotel_settings.hotel_name", read_only=True)

    class Meta:
        model = FinancialControlConfig
        fields = [
            "id",
            "hotel_settings",
            "hotel_name",
            "district_name",
            "tourism_law_enabled",
            "tourism_law_preferential_rate",
            "standard_income_tax_rate",
            "has_iva_exemption",
            "iva_rate",
            "ica_rate_per_thousand",
            "fontur_rate_per_thousand",
            "break_even_warning_pct",
            "break_even_optimal_pct",
            "operational_high_occupancy_threshold_pct",
            "operational_low_availability_threshold_rooms",
            "operational_revenue_drop_threshold_pct",
            "operational_high_refunds_threshold_count",
            "operational_revenue_window_days",
            "operational_refund_window_days",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("id", "created_at", "updated_at")


class OperationalAlertSerializer(serializers.ModelSerializer):
    hotel_name = serializers.CharField(source="hotel_settings.hotel_name", read_only=True)

    class Meta:
        model = OperationalAlert
        fields = [
            "id",
            "hotel_settings",
            "hotel_name",
            "alert_type",
            "severity",
            "status",
            "title",
            "message",
            "metric_value",
            "threshold_value",
            "metadata",
            "is_active",
            "triggered_at",
            "resolved_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = (
            "id",
            "hotel_name",
            "triggered_at",
            "created_at",
            "updated_at",
        )


class FinancialStatementSnapshotSerializer(serializers.ModelSerializer):
    hotel_name = serializers.CharField(source="hotel_settings.hotel_name", read_only=True)
    total_assets = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    total_liabilities = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    total_equity = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    current_ratio = serializers.DecimalField(
        max_digits=14,
        decimal_places=4,
        read_only=True,
        allow_null=True,
    )
    indebtedness_ratio = serializers.DecimalField(
        max_digits=14,
        decimal_places=4,
        read_only=True,
        allow_null=True,
    )
    receivables_turnover = serializers.DecimalField(
        max_digits=14,
        decimal_places=4,
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = FinancialStatementSnapshot
        fields = [
            "id",
            "hotel_settings",
            "hotel_name",
            "period_year",
            "period_month",
            "cash_and_equivalents",
            "trade_receivables",
            "current_financial_assets",
            "inventories",
            "current_assets",
            "property_plant_equipment",
            "non_current_financial_assets",
            "intangibles_other",
            "non_current_assets",
            "accounts_payable",
            "financial_obligations_current",
            "trade_creditors",
            "provision_income_tax",
            "provision_ica",
            "provision_fontur",
            "other_tax_provisions",
            "taxes_payable",
            "current_liabilities",
            "financial_obligations_non_current",
            "non_current_liabilities",
            "equity_capital",
            "equity_reserves",
            "equity_surplus",
            "retained_earnings",
            "depreciation_expense",
            "financial_income",
            "financial_expense",
            "income_tax_expense",
            "other_income_expense",
            "other_comprehensive_income",
            "average_accounts_receivable",
            "net_credit_sales",
            "notes",
            "is_active",
            "total_assets",
            "total_liabilities",
            "total_equity",
            "current_ratio",
            "indebtedness_ratio",
            "receivables_turnover",
            "created_at",
            "updated_at",
        ]
        read_only_fields = (
            "id",
            "current_assets",
            "non_current_assets",
            "taxes_payable",
            "current_liabilities",
            "non_current_liabilities",
            "created_at",
            "updated_at",
        )
