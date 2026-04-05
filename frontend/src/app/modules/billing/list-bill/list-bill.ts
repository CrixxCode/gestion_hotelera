import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { catchError, forkJoin, of } from 'rxjs';
import { MasterDataI } from '../../../components/pages/master-data/master-data-model';
import { BillingService } from '../../../services/billing';
import { MasterDataService } from '../../../services/master-data.service';
import { ReservationService } from '../../../services/reservation';
import { ReservationI } from '../../reservations/reservation-model';
import { InvoiceI } from '../billing-model';
import { DetailBill } from '../detail-bill/detail-bill';

type InvoiceStatusFilter = 'ALL' | 'BORRADOR' | 'EMITIDA' | 'PAGADA' | 'ANULADA';
type InvoiceActivityFilter = 'ALL' | 'ACTIVE' | 'INACTIVE';

@Component({
  selector: 'app-list-bill',
  standalone: true,
  imports: [CommonModule, FormsModule, DetailBill],
  templateUrl: './list-bill.html',
  styleUrls: ['./list-bill.css']
})
export class ListBill implements OnInit {
  loading = false;
  errorMessage = '';
  infoMessage = '';

  invoices: InvoiceI[] = [];
  filteredInvoices: InvoiceI[] = [];
  invoiceStatuses: MasterDataI[] = [];
  reservationsMap = new Map<number, ReservationI>();

  search = '';
  statusFilter: InvoiceStatusFilter = 'ALL';
  activityFilter: InvoiceActivityFilter = 'ACTIVE';

  selectedInvoice: InvoiceI | null = null;

  readonly activityOptions: Array<{ value: InvoiceActivityFilter; label: string }> = [
    { value: 'ACTIVE', label: 'Activas' },
    { value: 'INACTIVE', label: 'Inactivas' },
    { value: 'ALL', label: 'Todas' }
  ];

  readonly statusOptions: Array<{ value: InvoiceStatusFilter; label: string }> = [
    { value: 'ALL', label: 'Todos los estados' },
    { value: 'BORRADOR', label: 'Borrador' },
    { value: 'EMITIDA', label: 'Emitida' },
    { value: 'PAGADA', label: 'Pagada' },
    { value: 'ANULADA', label: 'Anulada' }
  ];

  constructor(
    private billingService: BillingService,
    private reservationService: ReservationService,
    private masterDataService: MasterDataService
  ) {}

  ngOnInit(): void {
    this.loadBillingData();
  }

  get totalInvoices(): number {
    return this.invoices.length;
  }

  get draftCount(): number {
    return this.invoices.filter((invoice) => this.normalizeCode(invoice.status_code) === 'BORRADOR').length;
  }

  get issuedCount(): number {
    return this.invoices.filter((invoice) => {
      const code = this.normalizeCode(invoice.status_code);
      return code === 'EMITIDA' || code === 'PAGADA';
    }).length;
  }

  get totalBilledLabel(): string {
    const total = this.invoices.reduce((sum, invoice) => sum + this.toNumber(invoice.total_amount), 0);
    return this.formatCurrency(total);
  }

  get pendingCollectionLabel(): string {
    const total = this.invoices
      .filter((invoice) => {
        const code = this.normalizeCode(invoice.status_code);
        return code !== 'PAGADA' && code !== 'ANULADA';
      })
      .reduce((sum, invoice) => sum + this.toNumber(invoice.total_amount), 0);

    return this.formatCurrency(total);
  }

  loadBillingData(): void {
    this.loading = true;
    this.errorMessage = '';
    this.infoMessage = '';

    forkJoin({
      invoices: this.billingService
        .listInvoices({ ordering: '-id' })
        .pipe(catchError(() => of([] as InvoiceI[]))),
      reservationsPage: this.reservationService
        .listReservationsPage({ include_finished: true, ordering: '-id', page: 1, page_size: 100 })
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
      invoiceStatuses: this.masterDataService
        .listMasterData({ group: 'INVOICE_STATUS', is_active: 'true', ordering: 'sort_order,name' })
        .pipe(catchError(() => of([] as MasterDataI[])))
    }).subscribe({
      next: ({ invoices, reservationsPage, invoiceStatuses }) => {
        this.loading = false;
        this.invoices = [...invoices].sort((a, b) => b.id - a.id);
        this.invoiceStatuses = invoiceStatuses;
        this.reservationsMap = new Map(
          (reservationsPage.results || []).map((reservation) => [reservation.id, reservation])
        );

        this.applyFilters();

        if (!this.invoices.length) {
          this.infoMessage = 'No hay facturas registradas todavia.';
        }
      },
      error: () => {
        this.loading = false;
        this.errorMessage = 'No fue posible cargar el modulo de facturacion.';
      }
    });
  }

  refreshBillingData(): void {
    this.loadBillingData();
  }

  applyFilters(): void {
    const query = String(this.search || '').trim().toLowerCase();

    this.filteredInvoices = this.invoices.filter((invoice) => {
      const statusCode = this.normalizeCode(invoice.status_code);
      const activityMatch =
        this.activityFilter === 'ALL' ||
        (this.activityFilter === 'ACTIVE' && invoice.is_active) ||
        (this.activityFilter === 'INACTIVE' && !invoice.is_active);

      const statusMatch =
        this.statusFilter === 'ALL' ||
        (statusCode && statusCode === this.statusFilter);

      const reservation = this.reservationsMap.get(invoice.reservation) || null;
      const searchPool = [
        invoice.invoice_number,
        invoice.status_name || '',
        statusCode,
        this.getReservationCode(invoice, reservation),
        reservation?.client_full_name || '',
        reservation?.client_document_number || ''
      ]
        .join(' ')
        .toLowerCase();

      const searchMatch = !query || searchPool.includes(query);
      return activityMatch && statusMatch && searchMatch;
    });
  }

  openDetail(invoice: InvoiceI): void {
    this.selectedInvoice = invoice;
  }

  closeDetail(): void {
    this.selectedInvoice = null;
  }

  onInvoiceUpdated(updatedInvoice: InvoiceI): void {
    const index = this.invoices.findIndex((invoice) => invoice.id === updatedInvoice.id);
    if (index >= 0) {
      this.invoices[index] = updatedInvoice;
    } else {
      this.invoices.unshift(updatedInvoice);
    }

    this.invoices = [...this.invoices].sort((a, b) => b.id - a.id);
    this.applyFilters();

    this.selectedInvoice = this.invoices.find((invoice) => invoice.id === updatedInvoice.id) || null;
  }

  getStatusLabel(invoice: InvoiceI): string {
    if (invoice.status_name?.trim()) return invoice.status_name.trim();

    const statusCode = this.normalizeCode(invoice.status_code);
    if (!statusCode) return 'Sin estado';

    const status = this.invoiceStatuses.find((item) => this.normalizeCode(item.code) === statusCode);
    if (status?.name?.trim()) return status.name.trim();

    return statusCode;
  }

  getStatusTone(invoice: InvoiceI): { bg: string; color: string; dot: string } {
    const statusCode = this.normalizeCode(invoice.status_code);

    if (statusCode === 'BORRADOR') {
      return { bg: '#e2e8f0', color: '#334155', dot: '#64748b' };
    }
    if (statusCode === 'EMITIDA') {
      return { bg: '#fef3c7', color: '#b45309', dot: '#f59e0b' };
    }
    if (statusCode === 'PAGADA') {
      return { bg: '#dcfce7', color: '#15803d', dot: '#22c55e' };
    }
    if (statusCode === 'ANULADA') {
      return { bg: '#fee2e2', color: '#b42318', dot: '#ef4444' };
    }

    return { bg: '#e2e8f0', color: '#334155', dot: '#94a3b8' };
  }

  getReservationCode(invoice: InvoiceI, reservation?: ReservationI | null): string {
    if (reservation?.id) {
      const createdDate = reservation.created_at ? new Date(reservation.created_at) : null;
      const year =
        createdDate && !Number.isNaN(createdDate.getTime()) ? createdDate.getFullYear() : new Date().getFullYear();
      return `RES-${year}-${String(reservation.id).padStart(4, '0')}`;
    }

    return `RES-${String(invoice.reservation).padStart(4, '0')}`;
  }

  getGuestLabel(invoice: InvoiceI): string {
    const reservation = this.reservationsMap.get(invoice.reservation) || null;
    if (reservation?.client_full_name?.trim()) return reservation.client_full_name.trim();
    return `Reserva #${invoice.reservation}`;
  }

  getGuestDocument(invoice: InvoiceI): string {
    const reservation = this.reservationsMap.get(invoice.reservation) || null;
    return reservation?.client_document_number || 'Sin documento';
  }

  getStayLabel(invoice: InvoiceI): string {
    const reservation = this.reservationsMap.get(invoice.reservation) || null;
    if (!reservation) return 'Sin datos de estancia';
    return `${this.formatDate(reservation.expected_check_in)} - ${this.formatDate(reservation.expected_check_out)}`;
  }

  getIssueDateLabel(invoice: InvoiceI): string {
    return this.formatDateTime(invoice.issue_date);
  }

  getAmountLabel(invoice: InvoiceI): string {
    return this.formatCurrency(this.toNumber(invoice.total_amount));
  }

  trackByInvoice(_: number, invoice: InvoiceI): number {
    return invoice.id;
  }

  private toNumber(value: unknown): number {
    const parsed = Number(value || 0);
    return Number.isNaN(parsed) ? 0 : parsed;
  }

  private formatDate(value: string | null | undefined): string {
    if (!value) return 'Sin fecha';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);

    return date.toLocaleDateString('es-CO', {
      day: '2-digit',
      month: 'short',
      year: 'numeric'
    });
  }

  private formatDateTime(value: string | null | undefined): string {
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
}
