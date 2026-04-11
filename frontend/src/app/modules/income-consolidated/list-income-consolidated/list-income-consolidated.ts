import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { catchError, forkJoin, of } from 'rxjs';
import { MasterDataI } from '../../../components/pages/master-data/master-data-model';
import { BillingService } from '../../../services/billing';
import { MasterDataService } from '../../../services/master-data.service';
import { ReservationService } from '../../../services/reservation';
import { InvoiceI, PaymentI } from '../../billing/billing-model';
import { ReservationI } from '../../reservations/reservation-model';

type IncomeActivityFilter = 'ALL' | 'ACTIVE' | 'INACTIVE';
type IncomePeriodFilter = 'ALL' | 'TODAY' | 'LAST_7_DAYS' | 'THIS_MONTH' | 'THIS_YEAR';
type IncomeViewMode = 'daily' | 'methods';

type DailyIncomeRow = {
  dateKey: string;
  dateLabel: string;
  transactions: number;
  activeTransactions: number;
  inactiveTransactions: number;
  totalAmount: number;
  averageTicket: number;
  topMethod: string;
  topGuest: string;
};

type MethodIncomeRow = {
  methodKey: string;
  methodLabel: string;
  transactions: number;
  activeTransactions: number;
  inactiveTransactions: number;
  totalAmount: number;
  averageTicket: number;
  sharePercent: number;
};

type DailyAccumulator = {
  dateKey: string;
  dateLabel: string;
  transactions: number;
  activeTransactions: number;
  inactiveTransactions: number;
  totalAmount: number;
  methodTotals: Map<string, number>;
  guestTotals: Map<string, number>;
};

type MethodAccumulator = {
  methodKey: string;
  methodLabel: string;
  transactions: number;
  activeTransactions: number;
  inactiveTransactions: number;
  totalAmount: number;
};

@Component({
  selector: 'app-list-income-consolidated',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './list-income-consolidated.html',
  styleUrls: ['./list-income-consolidated.css']
})
export class ListIncomeConsolidated implements OnInit {
  loading = false;
  errorMessage = '';
  infoMessage = '';

  payments: PaymentI[] = [];
  filteredPayments: PaymentI[] = [];
  dailyRows: DailyIncomeRow[] = [];
  methodRows: MethodIncomeRow[] = [];

  invoicesMap = new Map<number, InvoiceI>();
  reservationsMap = new Map<number, ReservationI>();
  paymentMethods: MasterDataI[] = [];

  search = '';
  periodFilter: IncomePeriodFilter = 'THIS_MONTH';
  activityFilter: IncomeActivityFilter = 'ACTIVE';
  methodFilter = 'ALL';
  viewMode: IncomeViewMode = 'daily';

  readonly activityOptions: Array<{ value: IncomeActivityFilter; label: string }> = [
    { value: 'ACTIVE', label: 'Activos' },
    { value: 'INACTIVE', label: 'Inactivos' },
    { value: 'ALL', label: 'Todos' }
  ];

  readonly periodOptions: Array<{ value: IncomePeriodFilter; label: string }> = [
    { value: 'TODAY', label: 'Hoy' },
    { value: 'LAST_7_DAYS', label: 'Ultimos 7 dias' },
    { value: 'THIS_MONTH', label: 'Mes actual' },
    { value: 'THIS_YEAR', label: 'Ano actual' },
    { value: 'ALL', label: 'Todo el historico' }
  ];

  constructor(
    private billingService: BillingService,
    private reservationService: ReservationService,
    private masterDataService: MasterDataService
  ) {}

  ngOnInit(): void {
    this.loadIncomeData();
  }

  get totalTransactions(): number {
    return this.payments.length;
  }

  get activeTransactionsCount(): number {
    return this.payments.filter((payment) => !!payment.is_active).length;
  }

  get totalCollectedLabel(): string {
    const total = this.payments
      .filter((payment) => !!payment.is_active)
      .reduce((sum, payment) => sum + this.toNumber(payment.amount), 0);
    return this.formatCurrency(total);
  }

  get todayCollectedLabel(): string {
    const todayKey = this.formatDateKey(new Date());
    const total = this.payments
      .filter((payment) => !!payment.is_active)
      .filter((payment) => {
        const paymentDate = this.getPaymentDate(payment);
        if (!paymentDate) return false;
        return this.formatDateKey(paymentDate) === todayKey;
      })
      .reduce((sum, payment) => sum + this.toNumber(payment.amount), 0);
    return this.formatCurrency(total);
  }

  get monthCollectedLabel(): string {
    const now = new Date();
    const year = now.getFullYear();
    const month = now.getMonth();

    const total = this.payments
      .filter((payment) => !!payment.is_active)
      .filter((payment) => {
        const paymentDate = this.getPaymentDate(payment);
        if (!paymentDate) return false;
        return paymentDate.getFullYear() === year && paymentDate.getMonth() === month;
      })
      .reduce((sum, payment) => sum + this.toNumber(payment.amount), 0);

    return this.formatCurrency(total);
  }

  get averageTicketLabel(): string {
    if (!this.activeTransactionsCount) return this.formatCurrency(0);

    const total = this.payments
      .filter((payment) => !!payment.is_active)
      .reduce((sum, payment) => sum + this.toNumber(payment.amount), 0);

    return this.formatCurrency(total / this.activeTransactionsCount);
  }

  get methodOptions(): Array<{ value: string; label: string }> {
    const base = [{ value: 'ALL', label: 'Todos los metodos' }];
    const options = this.paymentMethods
      .map((method) => ({
        value: this.normalizeCode(method.code || method.name || String(method.id)),
        label: method.name || method.code || `Metodo #${method.id}`
      }))
      .filter((option) => !!option.value);

    const unique = new Map<string, string>();
    for (const option of options) {
      if (!unique.has(option.value)) {
        unique.set(option.value, option.label);
      }
    }

    return [
      ...base,
      ...Array.from(unique.entries()).map(([value, label]) => ({
        value,
        label
      }))
    ];
  }

  loadIncomeData(): void {
    this.loading = true;
    this.errorMessage = '';
    this.infoMessage = '';

    forkJoin({
      payments: this.billingService
        .listPayments({ ordering: '-payment_date,-id' })
        .pipe(catchError(() => of([] as PaymentI[]))),
      invoices: this.billingService
        .listInvoices({ ordering: '-id' })
        .pipe(catchError(() => of([] as InvoiceI[]))),
      reservationsPage: this.reservationService
        .listReservationsPage({ include_finished: true, ordering: '-id', page: 1, page_size: 300 })
        .pipe(
          catchError(() =>
            of({
              count: 0,
              next: null,
              previous: null,
              results: [] as ReservationI[]
            })
          )
        ),
      paymentMethods: this.masterDataService
        .listMasterData({ group: 'PAYMENT_METHOD', is_active: 'true', ordering: 'sort_order,name' })
        .pipe(catchError(() => of([] as MasterDataI[])))
    }).subscribe({
      next: ({ payments, invoices, reservationsPage, paymentMethods }) => {
        this.loading = false;
        this.payments = [...payments].sort((a, b) => b.id - a.id);
        this.invoicesMap = new Map(invoices.map((invoice) => [invoice.id, invoice]));
        this.reservationsMap = new Map((reservationsPage.results || []).map((reservation) => [reservation.id, reservation]));
        this.paymentMethods = paymentMethods;

        this.applyFilters();

        if (!this.payments.length) {
          this.infoMessage = 'No hay ingresos registrados todavia.';
        }
      },
      error: () => {
        this.loading = false;
        this.errorMessage = 'No fue posible cargar el consolidado de ingresos.';
      }
    });
  }

  refreshIncomeData(): void {
    this.loadIncomeData();
  }

  applyFilters(): void {
    const query = String(this.search || '').trim().toLowerCase();

    this.filteredPayments = this.payments.filter((payment) => {
      const activityMatch =
        this.activityFilter === 'ALL' ||
        (this.activityFilter === 'ACTIVE' && payment.is_active) ||
        (this.activityFilter === 'INACTIVE' && !payment.is_active);

      const methodCode = this.resolvePaymentMethodCode(payment);
      const methodMatch = this.methodFilter === 'ALL' || methodCode === this.methodFilter;

      const paymentDate = this.getPaymentDate(payment);
      const periodMatch = this.matchesPeriod(paymentDate);

      const invoice = this.invoicesMap.get(payment.invoice) || null;
      const reservation = invoice ? this.reservationsMap.get(invoice.reservation) || null : null;

      const searchPool = [
        this.getInvoiceNumber(payment),
        this.getGuestLabel(payment),
        reservation?.client_document_number || '',
        this.getMethodLabel(payment),
        payment.reference || '',
        payment.notes || ''
      ]
        .join(' ')
        .toLowerCase();

      const searchMatch = !query || searchPool.includes(query);
      return activityMatch && methodMatch && periodMatch && searchMatch;
    });

    this.dailyRows = this.buildDailyRows(this.filteredPayments);
    this.methodRows = this.buildMethodRows(this.filteredPayments);
  }

  setViewMode(mode: IncomeViewMode): void {
    this.viewMode = mode;
  }

  exportCsv(): void {
    if (this.viewMode === 'daily') {
      this.exportDailyCsv();
      return;
    }
    this.exportMethodsCsv();
  }

  trackByDailyRow(_: number, row: DailyIncomeRow): string {
    return row.dateKey;
  }

  trackByMethodRow(_: number, row: MethodIncomeRow): string {
    return row.methodKey;
  }

  getMethodCardTone(index: number): { bg: string; accent: string } {
    const palette = [
      { bg: 'var(--gh-status-info-bg)', accent: 'var(--gh-status-info-text)' },
      { bg: 'var(--gh-status-success-bg)', accent: 'var(--gh-status-success-text)' },
      { bg: 'var(--gh-status-orange-bg)', accent: 'var(--gh-status-orange-text)' },
      { bg: 'var(--gh-status-violet-bg)', accent: 'var(--gh-status-violet-text)' },
      { bg: 'var(--gh-status-danger-bg)', accent: 'var(--gh-status-danger-text)' },
      { bg: 'var(--gh-status-neutral-bg)', accent: 'var(--gh-status-neutral-text)' }
    ];
    return palette[index % palette.length];
  }

  formatShare(value: number): string {
    const safe = Number.isFinite(value) ? value : 0;
    return `${safe.toFixed(1)}%`;
  }

  formatTransactions(value: number): string {
    return new Intl.NumberFormat('es-CO').format(value || 0);
  }

  private buildDailyRows(payments: PaymentI[]): DailyIncomeRow[] {
    const rowsMap = new Map<string, DailyAccumulator>();

    for (const payment of payments) {
      const paymentDate = this.getPaymentDate(payment);
      const dateKey = paymentDate ? this.formatDateKey(paymentDate) : 'SIN_FECHA';
      const dateLabel = paymentDate ? this.formatDateLabel(paymentDate) : 'Sin fecha';
      const amount = this.toNumber(payment.amount);
      const methodLabel = this.getMethodLabel(payment);
      const guestLabel = this.getGuestLabel(payment);

      if (!rowsMap.has(dateKey)) {
        rowsMap.set(dateKey, {
          dateKey,
          dateLabel,
          transactions: 0,
          activeTransactions: 0,
          inactiveTransactions: 0,
          totalAmount: 0,
          methodTotals: new Map<string, number>(),
          guestTotals: new Map<string, number>()
        });
      }

      const bucket = rowsMap.get(dateKey);
      if (!bucket) continue;

      bucket.transactions += 1;
      if (payment.is_active) {
        bucket.activeTransactions += 1;
      } else {
        bucket.inactiveTransactions += 1;
      }
      bucket.totalAmount += amount;
      bucket.methodTotals.set(methodLabel, (bucket.methodTotals.get(methodLabel) || 0) + amount);
      bucket.guestTotals.set(guestLabel, (bucket.guestTotals.get(guestLabel) || 0) + amount);
    }

    const rows = Array.from(rowsMap.values()).map((bucket) => {
      const topMethod = this.getTopEntryLabel(bucket.methodTotals, 'Sin metodo');
      const topGuest = this.getTopEntryLabel(bucket.guestTotals, 'Sin huesped');
      const averageTicket = bucket.transactions ? bucket.totalAmount / bucket.transactions : 0;

      return {
        dateKey: bucket.dateKey,
        dateLabel: bucket.dateLabel,
        transactions: bucket.transactions,
        activeTransactions: bucket.activeTransactions,
        inactiveTransactions: bucket.inactiveTransactions,
        totalAmount: bucket.totalAmount,
        averageTicket,
        topMethod,
        topGuest
      };
    });

    rows.sort((a, b) => {
      if (a.dateKey === 'SIN_FECHA') return 1;
      if (b.dateKey === 'SIN_FECHA') return -1;
      return a.dateKey < b.dateKey ? 1 : -1;
    });

    return rows;
  }

  private buildMethodRows(payments: PaymentI[]): MethodIncomeRow[] {
    const rowsMap = new Map<string, MethodAccumulator>();

    for (const payment of payments) {
      const methodKey = this.resolvePaymentMethodCode(payment);
      const methodLabel = this.getMethodLabel(payment);
      const amount = this.toNumber(payment.amount);

      if (!rowsMap.has(methodKey)) {
        rowsMap.set(methodKey, {
          methodKey,
          methodLabel,
          transactions: 0,
          activeTransactions: 0,
          inactiveTransactions: 0,
          totalAmount: 0
        });
      }

      const bucket = rowsMap.get(methodKey);
      if (!bucket) continue;

      bucket.transactions += 1;
      if (payment.is_active) {
        bucket.activeTransactions += 1;
      } else {
        bucket.inactiveTransactions += 1;
      }
      bucket.totalAmount += amount;
    }

    const grandTotal = Array.from(rowsMap.values()).reduce((sum, row) => sum + row.totalAmount, 0);

    const rows = Array.from(rowsMap.values()).map((bucket) => {
      const averageTicket = bucket.transactions ? bucket.totalAmount / bucket.transactions : 0;
      const sharePercent = grandTotal > 0 ? (bucket.totalAmount / grandTotal) * 100 : 0;

      return {
        methodKey: bucket.methodKey,
        methodLabel: bucket.methodLabel,
        transactions: bucket.transactions,
        activeTransactions: bucket.activeTransactions,
        inactiveTransactions: bucket.inactiveTransactions,
        totalAmount: bucket.totalAmount,
        averageTicket,
        sharePercent
      };
    });

    rows.sort((a, b) => b.totalAmount - a.totalAmount);
    return rows;
  }

  private matchesPeriod(paymentDate: Date | null): boolean {
    if (this.periodFilter === 'ALL') return true;
    if (!paymentDate) return false;

    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const paymentDay = new Date(paymentDate.getFullYear(), paymentDate.getMonth(), paymentDate.getDate());

    if (this.periodFilter === 'TODAY') {
      return paymentDay.getTime() === todayStart.getTime();
    }

    if (this.periodFilter === 'LAST_7_DAYS') {
      const sevenDaysAgo = new Date(todayStart);
      sevenDaysAgo.setDate(todayStart.getDate() - 6);
      return paymentDay.getTime() >= sevenDaysAgo.getTime() && paymentDay.getTime() <= todayStart.getTime();
    }

    if (this.periodFilter === 'THIS_MONTH') {
      return paymentDate.getFullYear() === now.getFullYear() && paymentDate.getMonth() === now.getMonth();
    }

    if (this.periodFilter === 'THIS_YEAR') {
      return paymentDate.getFullYear() === now.getFullYear();
    }

    return true;
  }

  private getInvoiceNumber(payment: PaymentI): string {
    if (payment.invoice_number?.trim()) return payment.invoice_number.trim();

    const invoice = this.invoicesMap.get(payment.invoice) || null;
    if (invoice?.invoice_number?.trim()) return invoice.invoice_number.trim();

    return `FAC-${payment.invoice}`;
  }

  private getGuestLabel(payment: PaymentI): string {
    const invoice = this.invoicesMap.get(payment.invoice) || null;
    const reservation = invoice ? this.reservationsMap.get(invoice.reservation) || null : null;
    if (reservation?.client_full_name?.trim()) return reservation.client_full_name.trim();
    if (invoice?.reservation) return `Reserva #${invoice.reservation}`;
    return 'Huesped sin nombre';
  }

  private getMethodLabel(payment: PaymentI): string {
    if (payment.payment_method_name?.trim()) return payment.payment_method_name.trim();

    const methodCode = this.resolvePaymentMethodCode(payment);
    if (methodCode && methodCode !== 'SINMETODO') {
      const method = this.paymentMethods.find((item) => this.normalizeCode(item.code) === methodCode);
      if (method?.name?.trim()) return method.name.trim();
    }

    if (payment.payment_method_code?.trim()) return payment.payment_method_code.trim();
    return 'Sin metodo';
  }

  private resolvePaymentMethodCode(payment: PaymentI): string {
    const methodCode = this.normalizeCode(payment.payment_method_code);
    if (methodCode) return methodCode;

    const methodName = this.normalizeCode(payment.payment_method_name);
    if (methodName) return methodName;

    return 'SINMETODO';
  }

  private getPaymentDate(payment: PaymentI): Date | null {
    const rawValue = payment.payment_date || payment.created_at || null;
    if (!rawValue) return null;
    const parsed = new Date(rawValue);
    if (Number.isNaN(parsed.getTime())) return null;
    return parsed;
  }

  private formatDateKey(date: Date): string {
    const year = date.getFullYear();
    const month = `${date.getMonth() + 1}`.padStart(2, '0');
    const day = `${date.getDate()}`.padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  private formatDateLabel(date: Date): string {
    return date.toLocaleDateString('es-CO', {
      day: '2-digit',
      month: 'short',
      year: 'numeric'
    });
  }

  private getTopEntryLabel(totals: Map<string, number>, fallback: string): string {
    let bestLabel = fallback;
    let bestTotal = -1;

    totals.forEach((value, key) => {
      if (value > bestTotal) {
        bestTotal = value;
        bestLabel = key;
      }
    });

    return bestLabel;
  }

  private exportDailyCsv(): void {
    if (!this.dailyRows.length) return;

    const headers = [
      'fecha',
      'transacciones',
      'activas',
      'inactivas',
      'total_ingresos',
      'ticket_promedio',
      'metodo_principal',
      'huesped_principal'
    ];

    const rows = this.dailyRows.map((row) =>
      [
        row.dateLabel,
        row.transactions,
        row.activeTransactions,
        row.inactiveTransactions,
        row.totalAmount.toFixed(2),
        row.averageTicket.toFixed(2),
        row.topMethod,
        row.topGuest
      ]
        .map((cell) => this.escapeCsvCell(cell))
        .join(',')
    );

    const csv = [headers.join(','), ...rows].join('\n');
    this.downloadCsv(csv, `consolidado-ingresos-diario-${this.formatFileDate(new Date())}.csv`);
  }

  private exportMethodsCsv(): void {
    if (!this.methodRows.length) return;

    const headers = [
      'metodo',
      'transacciones',
      'activas',
      'inactivas',
      'total_ingresos',
      'ticket_promedio',
      'participacion'
    ];

    const rows = this.methodRows.map((row) =>
      [
        row.methodLabel,
        row.transactions,
        row.activeTransactions,
        row.inactiveTransactions,
        row.totalAmount.toFixed(2),
        row.averageTicket.toFixed(2),
        this.formatShare(row.sharePercent)
      ]
        .map((cell) => this.escapeCsvCell(cell))
        .join(',')
    );

    const csv = [headers.join(','), ...rows].join('\n');
    this.downloadCsv(csv, `consolidado-ingresos-metodos-${this.formatFileDate(new Date())}.csv`);
  }

  private downloadCsv(csvContent: string, filename: string): void {
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  }

  private toNumber(value: unknown): number {
    const parsed = Number(value || 0);
    return Number.isNaN(parsed) ? 0 : parsed;
  }

  private formatCurrency(value: number): string {
    return new Intl.NumberFormat('es-CO', {
      style: 'currency',
      currency: 'COP',
      maximumFractionDigits: 0
    }).format(value || 0);
  }

  private normalizeCode(value: unknown): string {
    return String(value || '')
      .trim()
      .toUpperCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[^A-Z0-9]/g, '');
  }

  private formatFileDate(date: Date): string {
    const year = date.getFullYear();
    const month = `${date.getMonth() + 1}`.padStart(2, '0');
    const day = `${date.getDate()}`.padStart(2, '0');
    return `${year}${month}${day}`;
  }

  private escapeCsvCell(value: unknown): string {
    const normalized = String(value ?? '');
    const escaped = normalized.replace(/"/g, '""');
    return `"${escaped}"`;
  }
}
