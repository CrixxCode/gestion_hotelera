import re

from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.billing.models import Charge, Invoice, InvoiceCharge, Payment, CreditNote
from apps.billing.pdf_generator import build_invoice_pdf
from apps.billing.serializers import ChargeSerializer, InvoiceSerializer, InvoiceChargeSerializer, PaymentSerializer, CreditNoteSerializer
from accounts.permissions import HasResourcePermission
from accounts.soft_delete import LogicalDeleteViewSetMixin

class ChargeViewSet(LogicalDeleteViewSetMixin, viewsets.ModelViewSet):
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

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["reservation", "charge_type", "service", "package", "is_active", "is_automatic"]
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

class InvoiceViewSet(LogicalDeleteViewSetMixin, viewsets.ModelViewSet):
    queryset = (
        Invoice.objects.select_related(
            "reservation",
            "reservation__client",
            "reservation__origin",
            "status",
        )
        .prefetch_related(
            "invoice_charges__charge",
            "reservation__rooms_detail__room__floor__hotel_settings",
        )
        .order_by("-id")
    )
    serializer_class = InvoiceSerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["invoices.read"]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["reservation", "status", "is_active"]
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

    @action(detail=True, methods=["get"], url_path="pdf")
    def pdf(self, request, pk=None):
        invoice = self.get_object()
        charges = (
            Charge.objects.select_related("charge_type")
            .filter(reservation_id=invoice.reservation_id, is_active=True)
            .order_by("charge_date", "id")
        )
        payments = (
            Payment.objects.select_related("payment_method")
            .filter(invoice_id=invoice.id, is_active=True)
            .order_by("payment_date", "id")
        )
        credit_notes = (
            CreditNote.objects.select_related("status")
            .filter(invoice_id=invoice.id, is_active=True)
            .order_by("issue_date", "id")
        )

        try:
            pdf_content = build_invoice_pdf(
                invoice=invoice,
                charges=charges,
                payments=payments,
                credit_notes=credit_notes,
            )
        except RuntimeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        base_name = invoice.invoice_number or f"FAC-{invoice.id}"
        safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", base_name).strip("_") or f"FAC-{invoice.id}"
        response = HttpResponse(pdf_content, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{safe_name}.pdf"'
        return response


class InvoiceChargeViewSet(LogicalDeleteViewSetMixin, viewsets.ModelViewSet):
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

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["invoice", "charge"]
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
    
class PaymentViewSet(LogicalDeleteViewSetMixin, viewsets.ModelViewSet):
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

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["invoice", "payment_method", "is_active"]
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
    
class CreditNoteViewSet(LogicalDeleteViewSetMixin, viewsets.ModelViewSet):
    queryset = (
        CreditNote.objects.select_related(
            "invoice",
            "status",
        ).order_by("-id")
    )
    serializer_class = CreditNoteSerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["credit-notes.read"]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["invoice", "status", "is_active"]
    search_fields = [
        "credit_note_number",
        "reason",
        "notes",
        "invoice__invoice_number",
        "status__name",
        "status__code",
    ]
    ordering_fields = [
        "id",
        "credit_note_number",
        "amount",
        "issue_date",
        "created_at",
        "updated_at",
    ]
    ordering = ["-id"]

    def get_required_scopes(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return ["credit-notes.write"]
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()
