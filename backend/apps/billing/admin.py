from django.contrib import admin

from apps.billing.models import Charge, Invoice, InvoiceCharge, Payment


@admin.register(Charge)
class ChargeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "reservation",
        "charge_type",
        "description",
        "quantity",
        "unit_price",
        "total_amount",
        "is_active",
        "is_automatic",
        "automation_key",
        "charge_date",
    )
    search_fields = ("description", "reservation__id")
    list_filter = ("charge_type", "is_active", "is_automatic", "charge_date")


class InvoiceChargeInline(admin.TabularInline):
    model = InvoiceCharge
    extra = 1


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "invoice_number",
        "reservation",
        "status",
        "subtotal",
        "tax_amount",
        "total_amount",
        "issue_date",
        "is_active",
    )
    search_fields = ("invoice_number", "reservation__id")
    list_filter = ("status", "is_active", "issue_date")
    inlines = [InvoiceChargeInline]


@admin.register(InvoiceCharge)
class InvoiceChargeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "invoice",
        "charge",
        "created_at",
    )
    search_fields = ("invoice__invoice_number", "charge__description")
    
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "invoice",
        "payment_method",
        "amount",
        "payment_date",
        "is_active",
    )
    search_fields = ("invoice__invoice_number", "reference", "notes")
    list_filter = ("payment_method", "is_active", "payment_date")