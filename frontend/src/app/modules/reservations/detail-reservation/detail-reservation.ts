import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, OnChanges, Output, SimpleChanges } from '@angular/core';
import { Observable } from 'rxjs';
import { ReservationService } from '../../../services/reservation';
import { ReservationDetailI, ReservationGuestI, ReservationStatusStyleI, ReservationVisualStatus } from '../reservation-model';

@Component({
  selector: 'app-detail-reservation',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './detail-reservation.html',
  styleUrls: ['./detail-reservation.css']
})
export class DetailReservation implements OnChanges {
  @Input() reservationId: number | null = null;
  @Input() preloaded: ReservationDetailI | null = null;

  @Output() closed = new EventEmitter<void>();
  @Output() editRequested = new EventEmitter<ReservationDetailI>();
  @Output() flowChanged = new EventEmitter<ReservationDetailI>();

  reservation: ReservationDetailI | null = null;
  loading = false;
  errorMessage = '';
  actionLoading = false;
  showGuestsModal = false;

  constructor(private reservationService: ReservationService) {}

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['preloaded'] && this.preloaded && this.preloaded.id === this.reservationId) {
      this.reservation = this.preloaded;
      this.errorMessage = '';
      this.showGuestsModal = false;
      return;
    }

    if (changes['reservationId']) {
      this.showGuestsModal = false;
      this.loadReservation();
    }
  }

  get visualStatus(): ReservationVisualStatus {
    return this.getVisualStatus(this.reservation);
  }

  get drawerStatusClass(): string {
    switch (this.visualStatus) {
      case 'CONFIRMADA':
        return 'status-confirmada';
      case 'PENDIENTE':
        return 'status-pendiente';
      case 'EN_CURSO':
        return 'status-en-curso';
      case 'POR_SALIR_HOY':
        return 'status-por-salir-hoy';
      case 'CANCELADA':
        return 'status-cancelada';
      case 'FINALIZADA':
        return 'status-finalizada';
      default:
        return 'status-otra';
    }
  }

  get statusStyle(): ReservationStatusStyleI {
    return this.resolveStatusStyle(this.visualStatus);
  }

  get reservationCodeLabel(): string {
    if (!this.reservation) return 'RES';

    const createdDate = this.reservation.created_at ? new Date(this.reservation.created_at) : null;
    const year =
      createdDate && !Number.isNaN(createdDate.getTime())
        ? createdDate.getFullYear()
        : new Date().getFullYear();
    return `RES-${year}-${String(this.reservation.id).padStart(3, '0')}`;
  }

  get guestInitials(): string {
    const fullName = String(this.reservation?.client_full_name || '').trim();
    if (!fullName) return 'HG';

    const parts = fullName.split(/\s+/).filter(Boolean);
    const first = parts[0]?.charAt(0) || '';
    const second = parts.length > 1 ? parts[parts.length - 1].charAt(0) : '';
    return `${first}${second}`.toUpperCase();
  }

  get guestSecondaryLabel(): string {
    const firstNationality = this.reservation?.guests?.find((guest) => !!guest.nationality)?.nationality;
    if (firstNationality && String(firstNationality).trim()) return String(firstNationality).trim();

    return this.reservation?.client_document_number || 'Sin documento';
  }

  get guestCountLabel(): string {
    if (!this.reservation) return '0 huespedes';

    const adults = (this.reservation.rooms_detail || []).reduce((sum, room) => sum + Number(room.adults || 0), 0);
    const children = (this.reservation.rooms_detail || []).reduce((sum, room) => sum + Number(room.children || 0), 0);

    if (adults <= 0 && children <= 0) {
      const totalGuests = Number(this.reservation.total_guests || 0);
      return `${totalGuests} huesped${totalGuests === 1 ? '' : 'es'}`;
    }

    if (children > 0) {
      return `${adults} adulto${adults === 1 ? '' : 's'} + ${children} nino${children === 1 ? '' : 's'}`;
    }

    return `${adults} adulto${adults === 1 ? '' : 's'}`;
  }

  get guests(): ReservationGuestI[] {
    return this.reservation?.guests || [];
  }

  get hasGuests(): boolean {
    return this.guests.length > 0;
  }

  get guestSummaryRows(): ReservationGuestI[] {
    return this.guests.slice(0, 3);
  }

  get hiddenGuestsCount(): number {
    return Math.max(0, this.guests.length - this.guestSummaryRows.length);
  }

  get stayCheckoutLabel(): string {
    if (!this.reservation?.expected_check_out) return 'Sin registro';
    if (this.visualStatus === 'POR_SALIR_HOY') return 'Hoy';
    return this.formatDate(this.reservation.expected_check_out);
  }

  get canRunPrimaryAction(): boolean {
    switch (this.visualStatus) {
      case 'PENDIENTE':
        return this.canConfirm;
      case 'CONFIRMADA':
        return this.canCheckIn;
      case 'EN_CURSO':
      case 'POR_SALIR_HOY':
        return this.canCheckOut;
      default:
        return false;
    }
  }

  get primaryActionLabel(): string {
    if (this.actionLoading) return 'Procesando...';

    switch (this.visualStatus) {
      case 'PENDIENTE':
        return 'Confirmar reserva';
      case 'CONFIRMADA':
        return 'Registrar check-in';
      case 'POR_SALIR_HOY':
        return 'Confirmar check-out';
      case 'EN_CURSO':
        return 'Registrar check-out';
      default:
        return 'Accion';
    }
  }

  get showCancelInfoMessage(): boolean {
    return this.visualStatus === 'CANCELADA';
  }

  get showEditAction(): boolean {
    return !['CANCELADA', 'FINALIZADA'].includes(this.visualStatus);
  }

  get showCancelAction(): boolean {
    if (this.visualStatus === 'PENDIENTE') return false;
    return this.canCancel;
  }

  get totalNights(): number {
    if (!this.reservation) return 0;
    if (typeof this.reservation.total_nights === 'number') return this.reservation.total_nights;

    const checkIn = this.parseDate(this.reservation.expected_check_in);
    const checkOut = this.parseDate(this.reservation.expected_check_out);
    if (!checkIn || !checkOut) return 0;

    const diff = Math.round((checkOut.getTime() - checkIn.getTime()) / (1000 * 60 * 60 * 24));
    return diff > 0 ? diff : 0;
  }

  get totalAmount(): number {
    return Math.max(0, this.roomsSubtotal - this.discountAmount);
  }

  get roomsSubtotal(): number {
    if (!this.reservation) return 0;

    return (this.reservation.rooms_detail || []).reduce((sum, room) => {
      const subtotal = Number(room.subtotal ?? room.night_rate ?? 0);
      return sum + (Number.isNaN(subtotal) ? 0 : subtotal);
    }, 0);
  }

  get discountAmount(): number {
    const discount = Number(this.reservation?.total_discount || 0);
    return Number.isNaN(discount) ? 0 : discount;
  }

  get roomChargeLabel(): string {
    const nights = this.totalNights;
    if (nights <= 0 || this.roomsSubtotal <= 0) return 'Habitacion';

    const nightRate = this.roomsSubtotal / nights;
    return `Habitacion (${nights}n x ${this.formatCurrency(nightRate)})`;
  }

  get totalDeposits(): number {
    if (!this.reservation) return 0;

    return (this.reservation.deposits || []).reduce((sum, deposit) => {
      const amount = Number(deposit.amount || 0);
      return sum + (Number.isNaN(amount) ? 0 : amount);
    }, 0);
  }

  get pendingAmount(): number {
    return Math.max(0, this.totalAmount - this.totalDeposits);
  }

  get paymentLabel(): string {
    if (!this.reservation) return 'Sin datos';

    if (this.totalAmount <= 0 && this.totalDeposits <= 0) {
      return 'Sin cargos';
    }

    if (this.pendingAmount <= 0 && this.totalAmount > 0) {
      return 'Pagado';
    }

    if (this.totalDeposits > 0 && this.pendingAmount > 0) {
      return 'Parcial';
    }

    return 'Pendiente';
  }

  get paymentTone(): { bg: string; color: string } {
    const label = this.paymentLabel;

    if (label === 'Pagado') {
      return { bg: '#dcfce7', color: '#15803d' };
    }

    if (label === 'Parcial') {
      return { bg: '#dbeafe', color: '#1d4ed8' };
    }

    if (label === 'Pendiente') {
      return { bg: '#fef3c7', color: '#b45309' };
    }

    return { bg: '#e2e8f0', color: '#475569' };
  }

  get firstRoomLabel(): string {
    if (!this.reservation?.rooms_detail?.length) return 'Sin habitacion';
    const roomNumber = this.reservation.rooms_detail[0].room_number || String(this.reservation.rooms_detail[0].room);
    const normalized = String(roomNumber || '').trim();
    if (!normalized) return 'Sin habitacion';
    return /^hab\./i.test(normalized) ? normalized : `Hab. ${normalized}`;
  }

  get firstRoomCategoryLabel(): string {
    const firstRoom = this.reservation?.rooms_detail?.[0] as Record<string, unknown> | undefined;
    const roomTypeName = firstRoom?.['room_type_name'];
    if (typeof roomTypeName === 'string' && roomTypeName.trim()) {
      return roomTypeName.trim();
    }

    return 'Habitacion';
  }

  get canConfirm(): boolean {
    if (!this.reservation) return false;
    const statusCode = this.normalizeCode(this.reservation.status_code);
    return statusCode === 'PENDIENTE' && !this.reservation.real_check_in && !this.reservation.real_check_out;
  }

  get canCheckIn(): boolean {
    if (!this.reservation) return false;
    const statusCode = this.normalizeCode(this.reservation.status_code);
    return statusCode === 'CONFIRMADA' && !this.reservation.real_check_in && !this.reservation.real_check_out;
  }

  get canCheckOut(): boolean {
    if (!this.reservation) return false;
    const statusCode = this.normalizeCode(this.reservation.status_code);
    return (
      (statusCode === 'EN_CURSO' || !!this.reservation.real_check_in) &&
      !this.reservation.real_check_out
    );
  }

  get canCancel(): boolean {
    if (!this.reservation) return false;
    const statusCode = this.normalizeCode(this.reservation.status_code);
    return ['PENDIENTE', 'CONFIRMADA'].includes(statusCode) && !this.reservation.real_check_in && !this.reservation.real_check_out;
  }

  closeDrawer(): void {
    this.showGuestsModal = false;
    this.closed.emit();
  }

  openGuestsModal(): void {
    if (!this.hasGuests) return;
    this.showGuestsModal = true;
  }

  closeGuestsModal(): void {
    this.showGuestsModal = false;
  }

  requestEdit(): void {
    if (!this.reservation) return;
    this.editRequested.emit(this.reservation);
  }

  confirmReservation(): void {
    if (!this.reservation || this.actionLoading || !this.canConfirm) return;
    this.runFlowAction(this.reservationService.confirmReservation(this.reservation.id));
  }

  performCheckIn(): void {
    if (!this.reservation || this.actionLoading || !this.canCheckIn) return;
    this.runFlowAction(this.reservationService.checkInReservation(this.reservation.id));
  }

  performCheckOut(): void {
    if (!this.reservation || this.actionLoading || !this.canCheckOut) return;
    this.runFlowAction(this.reservationService.checkOutReservation(this.reservation.id));
  }

  cancelReservation(): void {
    if (!this.reservation || this.actionLoading || !this.canCancel) return;
    this.runFlowAction(this.reservationService.cancelReservation(this.reservation.id));
  }

  runPrimaryAction(): void {
    if (this.actionLoading || !this.canRunPrimaryAction) return;

    switch (this.visualStatus) {
      case 'PENDIENTE':
        this.confirmReservation();
        break;
      case 'CONFIRMADA':
        this.performCheckIn();
        break;
      case 'EN_CURSO':
      case 'POR_SALIR_HOY':
        this.performCheckOut();
        break;
      default:
        break;
    }
  }

  formatCurrency(value: number): string {
    return new Intl.NumberFormat('es-CO', {
      style: 'currency',
      currency: 'COP',
      maximumFractionDigits: 0
    }).format(value || 0);
  }

  toNumber(value: unknown): number {
    const parsed = Number(value || 0);
    return Number.isNaN(parsed) ? 0 : parsed;
  }

  formatDate(value: string | null | undefined): string {
    if (!value) return 'Sin registro';

    const parsed = this.parseDate(value);
    if (!parsed) return value;

    return parsed.toLocaleDateString('es-CO', {
      day: '2-digit',
      month: 'short',
      year: 'numeric'
    });
  }

  formatDateTime(value: string | null | undefined): string {
    if (!value) return 'Sin registro';

    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value;

    return parsed.toLocaleString('es-CO', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  getGuestDocumentLabel(guest: ReservationGuestI): string {
    const documentType = guest.document_type_code || guest.document_type_name || 'Doc';
    const documentNumber = guest.document_number || 'Sin numero';
    return `${documentType}: ${documentNumber}`;
  }

  trackById(_: number, item: { id: number }): number {
    return item.id;
  }

  private loadReservation(): void {
    if (!this.reservationId) {
      this.reservation = null;
      return;
    }

    if (this.preloaded && this.preloaded.id === this.reservationId) {
      this.reservation = this.preloaded;
      this.errorMessage = '';
      return;
    }

    this.loading = true;
    this.errorMessage = '';

    this.reservationService.getReservationById(this.reservationId).subscribe({
      next: (detail) => {
        this.loading = false;
        this.reservation = detail;
      },
      error: () => {
        this.loading = false;
        this.errorMessage = 'No fue posible cargar el detalle de la reserva.';
      }
    });
  }

  private runFlowAction(action$: Observable<ReservationDetailI>): void {
    this.actionLoading = true;
    this.errorMessage = '';

    action$.subscribe({
      next: (detail: ReservationDetailI) => {
        this.actionLoading = false;
        this.reservation = detail;
        this.flowChanged.emit(detail);
      },
      error: (error: unknown) => {
        this.actionLoading = false;
        this.errorMessage = this.extractErrorMessage(error);
      }
    });
  }

  private parseDate(value: string): Date | null {
    if (!value) return null;

    if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
      const [year, month, day] = value.split('-').map((part) => Number(part));
      const date = new Date(year, month - 1, day);
      date.setHours(0, 0, 0, 0);
      return Number.isNaN(date.getTime()) ? null : date;
    }

    const asDateTime = new Date(value);
    if (Number.isNaN(asDateTime.getTime())) return null;
    return asDateTime;
  }

  private getVisualStatus(reservation: ReservationDetailI | null): ReservationVisualStatus {
    if (!reservation) return 'OTRA';

    const statusCode = this.normalizeCode(reservation.status_code);

    if (statusCode === 'CANCELADA') return 'CANCELADA';
    if (statusCode === 'FINALIZADA') return 'FINALIZADA';

    if (this.isCheckoutToday(reservation) && (statusCode === 'CONFIRMADA' || statusCode === 'EN_CURSO' || statusCode === 'PENDIENTE')) {
      return 'POR_SALIR_HOY';
    }

    if (statusCode === 'EN_CURSO') return 'EN_CURSO';
    if (statusCode === 'PENDIENTE') return 'PENDIENTE';
    if (statusCode === 'CONFIRMADA') return 'CONFIRMADA';

    return 'OTRA';
  }

  private isCheckoutToday(reservation: ReservationDetailI): boolean {
    const checkout = this.parseDate(reservation.expected_check_out);
    if (!checkout) return false;

    const today = new Date();
    today.setHours(0, 0, 0, 0);
    checkout.setHours(0, 0, 0, 0);

    return checkout.getTime() === today.getTime();
  }

  private normalizeCode(value: string | undefined): string {
    return String(value || '').trim().toUpperCase();
  }

  private resolveStatusStyle(status: ReservationVisualStatus): ReservationStatusStyleI {
    switch (status) {
      case 'CONFIRMADA':
        return {
          label: 'Confirmada',
          chipBg: '#dbeafe',
          chipColor: '#1d4ed8',
          dotColor: '#3b82f6',
          borderColor: '#3b82f6',
          actionBg: '#1d4ed8',
          actionColor: '#ffffff'
        };
      case 'PENDIENTE':
        return {
          label: 'Pendiente',
          chipBg: '#fef3c7',
          chipColor: '#b45309',
          dotColor: '#f59e0b',
          borderColor: '#f59e0b',
          actionBg: '#b45309',
          actionColor: '#ffffff'
        };
      case 'EN_CURSO':
        return {
          label: 'En curso',
          chipBg: '#dcfce7',
          chipColor: '#15803d',
          dotColor: '#22c55e',
          borderColor: '#22c55e',
          actionBg: '#166534',
          actionColor: '#ffffff'
        };
      case 'POR_SALIR_HOY':
        return {
          label: 'Por salir hoy',
          chipBg: '#ffedd5',
          chipColor: '#c2410c',
          dotColor: '#f97316',
          borderColor: '#f97316',
          actionBg: '#ea580c',
          actionColor: '#ffffff'
        };
      case 'CANCELADA':
        return {
          label: 'Cancelada',
          chipBg: '#e5e7eb',
          chipColor: '#4b5563',
          dotColor: '#9ca3af',
          borderColor: '#9ca3af',
          actionBg: '#64748b',
          actionColor: '#ffffff'
        };
      case 'FINALIZADA':
        return {
          label: 'Finalizada',
          chipBg: '#e2e8f0',
          chipColor: '#334155',
          dotColor: '#64748b',
          borderColor: '#64748b',
          actionBg: '#334155',
          actionColor: '#ffffff'
        };
      default:
        return {
          label: 'Sin estado',
          chipBg: '#e2e8f0',
          chipColor: '#334155',
          dotColor: '#94a3b8',
          borderColor: '#94a3b8',
          actionBg: '#334155',
          actionColor: '#ffffff'
        };
    }
  }

  private extractErrorMessage(error: unknown): string {
    const fallback = 'No se pudo completar la accion sobre la reserva.';

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
