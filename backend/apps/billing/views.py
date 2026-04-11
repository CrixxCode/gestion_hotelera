import re

from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.billing.models import Charge, Invoice, InvoiceCharge, Payment, PaymentRefund, CreditNote
from apps.billing.pdf_generator import build_invoice_pdf
from apps.billing.serializers import (
    ChargeSerializer,
    InvoiceSerializer,
    InvoiceChargeSerializer,
    PaymentSerializer,
    PaymentRefundSerializer,
    CreditNoteSerializer,
)
from apps.billing.services import get_or_create_default_payment_refund_status
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
        if self.action == "create":
            return [IsAuthenticated()]
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()

    @staticmethod
    def _is_checked_out_reservation(reservation) -> bool:
        if reservation is None:
            return False
        if getattr(reservation, "real_check_out", None) is not None:
            return True

        status_code = str(getattr(reservation, "status_code", "") or "").strip().upper()
        return status_code in {
            "FINALIZADA",
            "FINALIZADO",
            "CHECKED_OUT",
            "FINISHED",
            "COMPLETADA",
            "COMPLETADO",
        }

    def _ensure_charge_mutation_allowed(self, reservation):
        if self._is_checked_out_reservation(reservation):
            raise ValidationError(
                {
                    "reservation": "No puedes agregar o modificar cargos en una reserva finalizada. Solo se permiten pagos."
                }
            )

    def perform_create(self, serializer):
        reservation = serializer.validated_data.get("reservation")
        self._ensure_charge_mutation_allowed(reservation)
        serializer.save()

    def perform_update(self, serializer):
        reservation = serializer.validated_data.get(
            "reservation",
            getattr(serializer.instance, "reservation", None),
        )
        self._ensure_charge_mutation_allowed(reservation)
        serializer.save()

    def perform_destroy(self, instance):
        self._ensure_charge_mutation_allowed(getattr(instance, "reservation", None))
        super().perform_destroy(instance)

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

    def perform_update(self, serializer):
        requested_is_active = serializer.validated_data.get("is_active", None)
        current_is_active = bool(getattr(serializer.instance, "is_active", False))

        if (
            requested_is_active is False
            and current_is_active
            and not self._is_admin_user(self.request.user)
        ):
            raise PermissionDenied("Solo un administrador puede inactivar pagos.")

        serializer.save()

    @staticmethod
    def _is_admin_user(user) -> bool:
        if not user or not user.is_authenticated:
            return False
        if getattr(user, "is_superuser", False):
            return True
        return user.roles.filter(
            slug__iexact="admin",
            is_active=True,
            userrole__is_active=True,
        ).exists()


class PaymentRefundViewSet(LogicalDeleteViewSetMixin, viewsets.ModelViewSet):
    queryset = (
        PaymentRefund.objects.select_related(
            "payment",
            "payment__invoice",
            "payment__payment_method",
            "status",
        ).order_by("-id")
    )
    serializer_class = PaymentRefundSerializer
    pagination_class = None
    permission_classes = [HasResourcePermission]
    required_scopes = ["payments.read"]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["payment", "status", "is_active"]
    search_fields = [
        "payment__invoice__invoice_number",
        "payment__reference",
        "reason",
        "reference",
        "notes",
        "status__name",
        "status__code",
    ]
    ordering_fields = [
        "id",
        "amount",
        "refund_date",
        "created_at",
        "updated_at",
    ]
    ordering = ["-id"]

    allowed_transitions = {
        "PENDIENTE": {"APROBADO", "RECHAZADO", "ANULADO"},
        "APROBADO": {"PROCESADO", "ANULADO"},
        "PROCESADO": set(),
        "RECHAZADO": set(),
        "ANULADO": set(),
    }

    def get_required_scopes(self):
        if self.action == "create":
            return ["payments.read"]
        if self.request.method in ("PUT", "PATCH", "DELETE"):
            return ["payments.write"]
        if self.action in {"approve", "process", "reject", "cancel"}:
            return ["payments.write"]
        return self.required_scopes

    def get_permissions(self):
        self.required_scopes = self.get_required_scopes()
        return super().get_permissions()

    def get_queryset(self):
        queryset = super().get_queryset()
        invoice_id = self.request.query_params.get("invoice")
        if invoice_id is not None:
            try:
                invoice_id_value = int(invoice_id)
            except (TypeError, ValueError):
                return queryset.none()
            queryset = queryset.filter(payment__invoice_id=invoice_id_value)
        return queryset

    def perform_create(self, serializer):
        pending_status = get_or_create_default_payment_refund_status("PENDIENTE")
        if not pending_status:
            raise ValidationError({"status": "Unable to resolve default pending status."})
        serializer.save(status=pending_status)

    def perform_update(self, serializer):
        requested_status = serializer.validated_data.get("status")
        if requested_status and not self._is_admin_user(self.request.user):
            raise PermissionDenied("Solo un administrador puede cambiar el estado del reembolso.")
        serializer.save()

    @staticmethod
    def _is_admin_user(user) -> bool:
        if not user or not user.is_authenticated:
            return False
        if getattr(user, "is_superuser", False):
            return True
        return user.roles.filter(
            slug__iexact="admin",
            is_active=True,
            userrole__is_active=True,
        ).exists()

    def _ensure_admin_approval(self):
        if not self._is_admin_user(self.request.user):
            raise PermissionDenied("Solo un administrador puede aprobar o rechazar reembolsos.")

    def _update_status(self, refund: PaymentRefund, target_status_code: str):
        current_code = str(getattr(getattr(refund, "status", None), "code", "") or "").strip().upper()
        next_code = str(target_status_code or "").strip().upper()

        if not next_code:
            raise ValidationError({"status": "Refund target status is required."})
        if current_code == next_code:
            return refund

        allowed = self.allowed_transitions.get(current_code, set())
        if next_code not in allowed:
            raise ValidationError(
                {"status": f"Transition from {current_code or 'SIN_ESTADO'} to {next_code} is not allowed."}
            )

        target_status = get_or_create_default_payment_refund_status(next_code)
        if not target_status:
            raise ValidationError({"status": f"Unable to resolve status {next_code}."})

        refund.status = target_status
        refund.save(update_fields=["status"])
        return refund

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        self._ensure_admin_approval()
        refund = self.get_object()
        updated = self._update_status(refund, "APROBADO")
        serializer = self.get_serializer(updated)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="process")
    def process(self, request, pk=None):
        self._ensure_admin_approval()
        refund = self.get_object()
        updated = self._update_status(refund, "PROCESADO")
        serializer = self.get_serializer(updated)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        self._ensure_admin_approval()
        refund = self.get_object()
        updated = self._update_status(refund, "RECHAZADO")
        serializer = self.get_serializer(updated)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        self._ensure_admin_approval()
        refund = self.get_object()
        updated = self._update_status(refund, "ANULADO")
        serializer = self.get_serializer(updated)
        return Response(serializer.data)


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
