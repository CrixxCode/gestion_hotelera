import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, OnChanges, Output, SimpleChanges } from '@angular/core';
import { catchError, forkJoin, of } from 'rxjs';
import { ConfirmationService } from 'primeng/api';
import { BillingService } from '../../../services/billing';
import { errorActionAlert, successActionAlert } from '../../../services/action-alerts';
import { openActionConfirmation } from '../../../services/action-confirmations';
import { InvoiceI, PaymentI } from '../../billing/billing-model';

@Component({
  selector: 'app-detail-payment',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './detail-payment.html',
  styleUrls: ['./detail-payment.css']
})
export class DetailPayment implements OnChanges {
  @Input() payment: PaymentI | null = null;

  @Output() closed = new EventEmitter<void>();
  @Output() paymentUpdated = new EventEmitter<PaymentI>();

  loading = false;
  updating = false;
  errorMessage = '';
  infoMessage = '';

  activePayment: PaymentI | null = null;
  invoice: InvoiceI | null = null;
  invoicePayments: PaymentI[] = [];

  constructor(
    private billingService: BillingService,
    private confirmationService: ConfirmationService
  ) {}

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['payment']) {
      this.loadDetail();
    }
  }

  get invoiceTotalAmount(): number {
    return this.toNumber(this.invoice?.total_amount);
  }

  get totalPaidAmount(): number {
    return this.invoicePayments
      .filter((payment) => !!payment.is_active)
      .reduce((sum, payment) => sum + this.toNumber(payment.amount), 0);
  }

  get pendingBalanceAmount(): number {
    const pending = this.invoiceTotalAmount - this.totalPaidAmount;
    return pending > 0 ? pending : 0;
  }

  get paymentStatusLabel(): string {
    return this.activePayment?.is_active ? 'Activo' : 'Inactivo';
  }

  get paymentStatusTone(): { bg: string; color: string; dot: string } {
    if (this.activePayment?.is_active) {
      return { bg: '#dcfce7', color: '#166534', dot: '#22c55e' };
    }

    return { bg: '#e2e8f0', color: '#475569', dot: '#94a3b8' };
  }

  closeDrawer(): void {
    this.closed.emit();
  }

  refresh(): void {
    this.loadDetail();
  }

  deactivatePayment(): void {
    if (!this.activePayment || !this.activePayment.is_active || this.updating) return;

    openActionConfirmation(this.confirmationService, {
      action: 'deactivate',
      target: 'pago',
      onAccept: () => {
        this.updating = true;
        this.errorMessage = '';
        this.infoMessage = '';

        this.billingService.updatePayment(this.activePayment!.id, { is_active: false }).subscribe({
          next: (updatedPayment) => {
            this.updating = false;
            this.activePayment = updatedPayment;
            this.paymentUpdated.emit(updatedPayment);
            this.infoMessage = successActionAlert('deactivate', 'pago');
            this.refreshInvoicePayments();
          },
          error: (error) => {
            this.updating = false;
            this.errorMessage = this.extractErrorMessage(error, errorActionAlert('deactivate', 'pago'));
          }
        });
      }
    });
  }

  formatCurrency(value: number): string {
    return new Intl.NumberFormat('es-CO', {
      style: 'currency',
      currency: 'COP',
      maximumFractionDigits: 0
    }).format(value || 0);
  }

  formatDateTime(value: string | null | undefined): string {
    if (!value) return 'Sin registro';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);

    return date.toLocaleString('es-CO', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  private loadDetail(): void {
    if (!this.payment) {
      this.activePayment = null;
      this.invoice = null;
      this.invoicePayments = [];
      return;
    }

    this.loading = true;
    this.errorMessage = '';
    this.infoMessage = '';

    const paymentId = this.payment.id;
    const invoiceId = this.payment.invoice;

    forkJoin({
      payment: this.billingService.getPaymentById(paymentId).pipe(catchError(() => of(this.payment as PaymentI))),
      invoice: this.billingService.getInvoiceById(invoiceId).pipe(catchError(() => of(null))),
      invoicePayments: this.billingService
        .listPayments({ invoice: invoiceId, ordering: '-payment_date,-id' })
        .pipe(catchError(() => of([] as PaymentI[])))
    }).subscribe({
      next: ({ payment, invoice, invoicePayments }) => {
        this.loading = false;
        this.activePayment = payment;
        this.invoice = invoice;
        this.invoicePayments = invoicePayments
          .filter((row) => Number(row.invoice) === invoiceId)
          .sort((a, b) => b.id - a.id);
      },
      error: () => {
        this.loading = false;
        this.errorMessage = 'No fue posible cargar el detalle del pago.';
      }
    });
  }

  private refreshInvoicePayments(): void {
    if (!this.activePayment) return;
    const invoiceId = this.activePayment.invoice;

    this.billingService
      .listPayments({ invoice: invoiceId, ordering: '-payment_date,-id' })
      .pipe(catchError(() => of([] as PaymentI[])))
      .subscribe((payments) => {
        this.invoicePayments = payments
          .filter((row) => Number(row.invoice) === invoiceId)
          .sort((a, b) => b.id - a.id);
      });
  }

  private toNumber(value: unknown): number {
    const parsed = Number(value || 0);
    return Number.isNaN(parsed) ? 0 : parsed;
  }

  private extractErrorMessage(error: unknown, fallback: string): string {
    if (!error || typeof error !== 'object') return fallback;
    const payload = (error as { error?: unknown }).error;
    if (!payload || typeof payload !== 'object') return fallback;

    const detail = (payload as Record<string, unknown>)['detail'];
    if (typeof detail === 'string' && detail.trim()) return detail;

    for (const key of Object.keys(payload as Record<string, unknown>)) {
      const value = (payload as Record<string, unknown>)[key];
      if (typeof value === 'string' && value.trim()) return value;
      if (Array.isArray(value) && value.length && typeof value[0] === 'string') return value[0];
    }

    return fallback;
  }
}
