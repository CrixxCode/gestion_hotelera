from rest_framework import filters, viewsets

from apps.billing.models import Charge, Invoice, InvoiceCharge, Payment
from apps.billing.serializers import ChargeSerializer, InvoiceSerializer, InvoiceChargeSerializer, PaymentSerializer
from accounts.permissions import HasResourcePermission

class ChargeViewSet(viewsets.ModelViewSet):
    queryset = (
        Charge.objects.select_related(
            "reservation",
            "charge_type",
            "service",
            "package",
        ).order_by("-id")
    )
    serializer_class = ChargeSerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["charges.read"]

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "description",
        "reservation__id",
        "charge_type__name",
        "charge_type__code",
        "service__name",
        "package__name",
        "automation_key",
    ]
    ordering_fields = [
        "id",
        "quantity",
        "unit_price",
        "total_amount",
        "charge_date",
        "is_automatic",
    ]
    ordering = ["-id"]

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["charges.write"]
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()

class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = (
        Invoice.objects.select_related(
            "reservation",
            "status",
        )
        .prefetch_related(
            "invoice_charges__charge",
        )
        .order_by("-id")
    )
    serializer_class = InvoiceSerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["invoices.read"]

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "invoice_number",
        "notes",
        "reservation__id",
        "status__name",
        "status__code",
    ]
    ordering_fields = [
        "id",
        "invoice_number",
        "issue_date",
        "subtotal",
        "tax_amount",
        "total_amount",
        "created_at",
        "updated_at",
    ]
    ordering = ["-id"]

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["invoices.write"]
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()


class InvoiceChargeViewSet(viewsets.ModelViewSet):
    queryset = (
        InvoiceCharge.objects.select_related(
            "invoice",
            "charge",
        ).order_by("id")
    )
    serializer_class = InvoiceChargeSerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["invoices.read"]

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "invoice__invoice_number",
        "charge__description",
        "invoice__reservation__id",
    ]
    ordering_fields = [
        "id",
        "created_at",
    ]
    ordering = ["id"]

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["invoices.write"]
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()
    
class PaymentViewSet(viewsets.ModelViewSet):
    queryset = (
        Payment.objects.select_related(
            "invoice",
            "payment_method",
        ).order_by("-id")
    )
    serializer_class = PaymentSerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["payments.read"]

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "invoice__invoice_number",
        "payment_method__name",
        "payment_method__code",
        "reference",
        "notes",
    ]
    ordering_fields = [
        "id",
        "amount",
        "payment_date",
        "created_at",
        "updated_at",
    ]
    ordering = ["-id"]

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["payments.write"]
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()
