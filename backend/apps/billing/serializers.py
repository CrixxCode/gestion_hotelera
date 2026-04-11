from rest_framework import serializers

from apps.billing.models import Invoice, InvoiceCharge, Charge, Payment, PaymentRefund, CreditNote
from apps.billing.services import (
    get_or_create_default_charge_type,
    get_or_create_default_payment_refund_status,
)

class ChargeSerializer(serializers.ModelSerializer):
    charge_type_name = serializers.CharField(source="charge_type.name", read_only=True)
    charge_type_code = serializers.CharField(source="charge_type.code", read_only=True)

    service_name = serializers.CharField(source="service.name", read_only=True)
    package_name = serializers.CharField(source="package.name", read_only=True)

    class Meta:
        model = Charge
        fields = [
            "id",
            "reservation",
            "charge_type",
            "charge_type_name",
            "charge_type_code",
            "service",
            "service_name",
            "package",
            "package_name",
            "description",
            "quantity",
            "unit_price",
            "total_amount",
            "charge_date",
            "is_active",
            "is_automatic",
            "automation_key",
        ]
        read_only_fields = ("id", "total_amount", "charge_date", "is_automatic", "automation_key")
        extra_kwargs = {
            "charge_type": {"required": False, "allow_null": True},
            "description": {"required": False, "allow_blank": True},
            "unit_price": {"required": False},
        }

    @staticmethod
    def _normalize_text(value) -> str:
        return str(value or "").strip()

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

    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError("Quantity must be at least 1.")
        return value

    def validate_unit_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Unit price cannot be negative.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        reservation = attrs.get("reservation", getattr(self.instance, "reservation", None))

        if self._is_checked_out_reservation(reservation):
            raise serializers.ValidationError(
                {
                    "reservation": "No puedes agregar o modificar cargos en una reserva finalizada. Solo se permiten pagos."
                }
            )

        service = attrs.get("service", getattr(self.instance, "service", None))
        package = attrs.get("package", getattr(self.instance, "package", None))
        charge_type = attrs.get("charge_type", getattr(self.instance, "charge_type", None))

        if service and package:
            raise serializers.ValidationError(
                {"package": "A charge should reference either a service or a package, not both."}
            )

        if service:
            resolved_unit_price = attrs.get("unit_price", getattr(self.instance, "unit_price", None))
            if resolved_unit_price is None:
                attrs["unit_price"] = service.base_price

            if not self._normalize_text(attrs.get("description", getattr(self.instance, "description", ""))):
                attrs["description"] = f"Servicio: {service.name}"

            if not charge_type:
                attrs["charge_type"] = get_or_create_default_charge_type("SERVICIO")

        elif package:
            resolved_unit_price = attrs.get("unit_price", getattr(self.instance, "unit_price", None))
            if resolved_unit_price is None:
                attrs["unit_price"] = package.base_price

            package_name = (getattr(package, "name", "") or "").strip()
            if not self._normalize_text(attrs.get("description", getattr(self.instance, "description", ""))):
                attrs["description"] = f"Paquete: {package_name}" if package_name else "Paquete"

            if not charge_type:
                attrs["charge_type"] = get_or_create_default_charge_type("PAQUETE")

        if not attrs.get("charge_type", getattr(self.instance, "charge_type", None)):
            attrs["charge_type"] = get_or_create_default_charge_type("OTRO")

        unit_price = attrs.get("unit_price", getattr(self.instance, "unit_price", None))
        if unit_price is None:
            raise serializers.ValidationError({"unit_price": "Unit price is required."})
        if unit_price < 0:
            raise serializers.ValidationError({"unit_price": "Unit price cannot be negative."})

        quantity = attrs.get("quantity", getattr(self.instance, "quantity", 1) or 1)
        if quantity < 1:
            raise serializers.ValidationError({"quantity": "Quantity must be at least 1."})

        description = self._normalize_text(attrs.get("description", getattr(self.instance, "description", "")))
        if not description:
            raise serializers.ValidationError({"description": "Description is required."})
        attrs["description"] = description

        return attrs

class InvoiceChargeSerializer(serializers.ModelSerializer):
    charge_description = serializers.CharField(source="charge.description", read_only=True)
    charge_total_amount = serializers.DecimalField(
        source="charge.total_amount",
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = InvoiceCharge
        fields = [
            "id",
            "invoice",
            "charge",
            "charge_description",
            "charge_total_amount",
            "created_at",
        ]
        read_only_fields = ("id", "created_at")

    def validate(self, attrs):
        attrs = super().validate(attrs)

        invoice = attrs.get("invoice", getattr(self.instance, "invoice", None))
        charge = attrs.get("charge", getattr(self.instance, "charge", None))

        if invoice and charge and invoice.reservation_id != charge.reservation_id:
            raise serializers.ValidationError(
                {"charge": "The charge must belong to the same reservation as the invoice."}
            )

        return attrs


class InvoiceSerializer(serializers.ModelSerializer):
    status_name = serializers.CharField(source="status.name", read_only=True)
    status_code = serializers.CharField(source="status.code", read_only=True)
    invoice_charges = InvoiceChargeSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "reservation",
            "status",
            "status_name",
            "status_code",
            "invoice_number",
            "issue_date",
            "subtotal",
            "tax_amount",
            "total_amount",
            "notes",
            "is_active",
            "invoice_charges",
            "created_at",
            "updated_at",
        ]
        read_only_fields = (
            "id",
            "issue_date",
            "total_amount",
            "created_at",
            "updated_at",
        )

    def validate_subtotal(self, value):
        if value < 0:
            raise serializers.ValidationError("Subtotal cannot be negative.")
        return value

    def validate_tax_amount(self, value):
        if value < 0:
            raise serializers.ValidationError("Tax amount cannot be negative.")
        return value
    
class PaymentSerializer(serializers.ModelSerializer):
    payment_method_name = serializers.CharField(source="payment_method.name", read_only=True)
    payment_method_code = serializers.CharField(source="payment_method.code", read_only=True)
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "invoice",
            "invoice_number",
            "payment_method",
            "payment_method_name",
            "payment_method_code",
            "amount",
            "payment_date",
            "reference",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = (
            "id",
            "payment_date",
            "created_at",
            "updated_at",
        )

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Payment amount must be greater than 0.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)

        invoice = attrs.get("invoice", getattr(self.instance, "invoice", None))
        amount = attrs.get("amount", getattr(self.instance, "amount", None))

        if invoice and amount:
            total_paid = sum(
                payment.amount
                for payment in invoice.payments.filter(is_active=True).exclude(
                    pk=getattr(self.instance, "pk", None)
                )
            )
            total_processed_refunds = sum(
                refund.amount
                for refund in PaymentRefund.objects.filter(
                    payment__invoice=invoice,
                    is_active=True,
                    status__code__in=["APROBADO", "PROCESADO"],
                ).only("amount")
            )
            net_paid = total_paid - total_processed_refunds
            if net_paid < 0:
                net_paid = 0

            pending_balance = invoice.total_amount - net_paid
            if pending_balance < 0:
                pending_balance = 0

            if amount > pending_balance:
                raise serializers.ValidationError(
                    {"amount": "Payment amount cannot be greater than the pending balance."}
                )

        return attrs


class PaymentRefundSerializer(serializers.ModelSerializer):
    invoice = serializers.IntegerField(source="payment.invoice_id", read_only=True)
    invoice_number = serializers.CharField(source="payment.invoice.invoice_number", read_only=True)
    payment_method = serializers.IntegerField(source="payment.payment_method_id", read_only=True)
    payment_method_name = serializers.CharField(source="payment.payment_method.name", read_only=True)
    payment_method_code = serializers.CharField(source="payment.payment_method.code", read_only=True)
    status_name = serializers.CharField(source="status.name", read_only=True)
    status_code = serializers.CharField(source="status.code", read_only=True)

    class Meta:
        model = PaymentRefund
        fields = [
            "id",
            "payment",
            "invoice",
            "invoice_number",
            "payment_method",
            "payment_method_name",
            "payment_method_code",
            "status",
            "status_name",
            "status_code",
            "amount",
            "reason",
            "refund_date",
            "reference",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = (
            "id",
            "invoice",
            "invoice_number",
            "payment_method",
            "payment_method_name",
            "payment_method_code",
            "refund_date",
            "created_at",
            "updated_at",
        )
        extra_kwargs = {
            "status": {"required": False, "allow_null": True},
        }

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Refund amount must be greater than 0.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)

        payment = attrs.get("payment", getattr(self.instance, "payment", None))
        amount = attrs.get("amount", getattr(self.instance, "amount", None))
        status = attrs.get("status", getattr(self.instance, "status", None))

        if payment and not payment.is_active:
            raise serializers.ValidationError(
                {"payment": "Cannot register a refund for an inactive payment."}
            )

        if payment and amount:
            reserved_refunds = sum(
                refund.amount
                for refund in PaymentRefund.objects.filter(
                    payment=payment,
                    is_active=True,
                )
                .exclude(pk=getattr(self.instance, "pk", None))
                .exclude(status__code__in=["RECHAZADO", "ANULADO"])
                .only("amount")
            )
            available_amount = payment.amount - reserved_refunds
            if available_amount < 0:
                available_amount = 0

            if amount > available_amount:
                raise serializers.ValidationError(
                    {"amount": "Refund amount cannot be greater than the refundable payment balance."}
                )

        status_code = str(getattr(status, "code", "") or "").strip().upper()
        if status_code == "PROCESADO" and payment and not payment.is_active:
            raise serializers.ValidationError(
                {"status": "Cannot process a refund for an inactive payment."}
            )

        return attrs

    def create(self, validated_data):
        if not validated_data.get("status"):
            default_status = get_or_create_default_payment_refund_status("PENDIENTE")
            if default_status:
                validated_data["status"] = default_status
        return super().create(validated_data)


class CreditNoteSerializer(serializers.ModelSerializer):
    status_name = serializers.CharField(source="status.name", read_only=True)
    status_code = serializers.CharField(source="status.code", read_only=True)
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)

    class Meta:
        model = CreditNote
        fields = [
            "id",
            "invoice",
            "invoice_number",
            "status",
            "status_name",
            "status_code",
            "credit_note_number",
            "amount",
            "reason",
            "issue_date",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = (
            "id",
            "issue_date",
            "created_at",
            "updated_at",
        )

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Credit note amount must be greater than 0.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)

        invoice = attrs.get("invoice", getattr(self.instance, "invoice", None))
        amount = attrs.get("amount", getattr(self.instance, "amount", None))

        if invoice and amount:
            total_active_credit_notes = sum(
                note.amount
                for note in invoice.credit_notes.filter(is_active=True).exclude(
                    pk=getattr(self.instance, "pk", None)
                )
            )
            max_credit_available = invoice.total_amount - total_active_credit_notes

            if amount > max_credit_available:
                raise serializers.ValidationError(
                    {"amount": "Credit note amount cannot be greater than the available invoice balance."}
                )

        return attrs
