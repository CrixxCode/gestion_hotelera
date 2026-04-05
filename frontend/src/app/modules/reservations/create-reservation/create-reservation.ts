import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, OnChanges, Output, SimpleChanges } from '@angular/core';
import { ReactiveFormsModule, UntypedFormArray, UntypedFormBuilder, UntypedFormGroup, Validators } from '@angular/forms';
import { forkJoin, of } from 'rxjs';
import { MasterDataI } from '../../../components/pages/master-data/master-data-model';
import { ClientI } from '../../clients/client-model';
import { RoomI } from '../../rooms/room-model';
import { ReservationService } from '../../../services/reservation';
import { PackageI } from '../../packages/package-model';
import {
  ReservationGuestPayloadI,
  ReservationPolicyI,
  ReservationRoomPayloadI,
  ReservationWritePayloadI
} from '../reservation-model';

@Component({
  selector: 'app-create-reservation',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './create-reservation.html',
  styleUrls: ['./create-reservation.css']
})
export class CreateReservation implements OnChanges {
  @Input() clients: ClientI[] = [];
  @Input() origins: MasterDataI[] = [];
  @Input() documentTypes: MasterDataI[] = [];
  @Input() reservationPolicies: ReservationPolicyI[] = [];
  @Input() rooms: RoomI[] = [];
  @Input() packages: PackageI[] = [];
  @Input() initialRoomId: number | null = null;
  @Input() initialCheckInMode = false;

  @Output() closed = new EventEmitter<void>();
  @Output() created = new EventEmitter<void>();

  saving = false;
  errorMessage = '';

  reservationForm: UntypedFormGroup;

  constructor(
    private fb: UntypedFormBuilder,
    private reservationService: ReservationService
  ) {
    this.reservationForm = this.fb.group({
      client: [null, [Validators.required]],
      origin: [null, [Validators.required]],
      package: [null],
      expected_check_in: [this.formatDateForInput(new Date()), [Validators.required]],
      expected_check_out: [this.formatDateForInput(this.addDays(new Date(), 1)), [Validators.required]],
      promo_code: [''],
      total_discount: [0],
      notes: ['', [Validators.maxLength(1200)]],
      policy_lines: this.fb.array([]),
      room_lines: this.fb.array([]),
      guest_lines: this.fb.array([])
    });

    this.addPolicyLine();
    this.addRoomLine();
    this.addGuestLine();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['origins']) {
      const originValue = this.reservationForm.get('origin')?.value;
      if (!originValue && this.origins.length) {
        this.reservationForm.patchValue({ origin: this.getDefaultOriginId() });
      }
    }

    if (changes['documentTypes']) {
      this.setDefaultDocumentTypeForGuests();
    }

    if (changes['rooms'] || changes['initialRoomId'] || changes['initialCheckInMode']) {
      this.applyInitialRoomSelection();
    }
  }

  get roomLines(): UntypedFormArray {
    return this.reservationForm.get('room_lines') as UntypedFormArray;
  }

  get policyLines(): UntypedFormArray {
    return this.reservationForm.get('policy_lines') as UntypedFormArray;
  }

  get guestLines(): UntypedFormArray {
    return this.reservationForm.get('guest_lines') as UntypedFormArray;
  }

  get availableRooms(): RoomI[] {
    return [...this.rooms].sort((a, b) => String(a.number).localeCompare(String(b.number), 'es-CO'));
  }

  get availableDocumentTypes(): MasterDataI[] {
    return [...this.documentTypes].sort((a, b) => Number(a.sort_order || 0) - Number(b.sort_order || 0));
  }

  get availableReservationPolicies(): ReservationPolicyI[] {
    return [...this.reservationPolicies]
      .filter((policy) => policy.is_active !== false)
      .sort((a, b) => (a.name || '').localeCompare(b.name || '', 'es-CO'));
  }

  get availablePackages(): PackageI[] {
    return [...this.packages]
      .filter((item) => item.is_active !== false)
      .sort((a, b) => (a.name || '').localeCompare(b.name || '', 'es-CO'));
  }

  get selectedPoliciesCount(): number {
    return this.collectSelectedPolicyIds().length;
  }

  addPolicyLine(): void {
    this.policyLines.push(this.buildPolicyLine());
  }

  removePolicyLine(index: number): void {
    if (index < 0 || index >= this.policyLines.length) return;
    this.policyLines.removeAt(index);

    if (this.policyLines.length === 0) {
      this.addPolicyLine();
    }
  }

  addRoomLine(): void {
    this.roomLines.push(this.buildRoomLine());
  }

  removeRoomLine(index: number): void {
    if (index < 0 || index >= this.roomLines.length) return;
    this.roomLines.removeAt(index);

    if (this.roomLines.length === 0) {
      this.addRoomLine();
    }
  }

  addGuestLine(): void {
    this.guestLines.push(this.buildGuestLine());
  }

  removeGuestLine(index: number): void {
    if (index < 0 || index >= this.guestLines.length) return;
    this.guestLines.removeAt(index);

    if (this.guestLines.length === 0) {
      this.addGuestLine();
    }
  }

  submit(): void {
    this.errorMessage = '';

    if (this.reservationForm.invalid) {
      this.reservationForm.markAllAsTouched();
      this.policyLines.controls.forEach((control) => control.markAllAsTouched());
      this.roomLines.controls.forEach((control) => control.markAllAsTouched());
      this.guestLines.controls.forEach((control) => control.markAllAsTouched());
      return;
    }

    const dateError = this.validateDateRange();
    if (dateError) {
      this.errorMessage = dateError;
      return;
    }

    const packageError = this.validateSelectedPackage();
    if (packageError) {
      this.errorMessage = packageError;
      return;
    }

    const policyBuild = this.buildPolicySelection();
    if (policyBuild.error) {
      this.errorMessage = policyBuild.error;
      return;
    }

    const roomBuild = this.buildRoomPayloads();
    if (roomBuild.error) {
      this.errorMessage = roomBuild.error;
      return;
    }

    const guestBuild = this.buildGuestPayloads();
    if (guestBuild.error) {
      this.errorMessage = guestBuild.error;
      return;
    }

    this.saving = true;

    const payload = this.buildReservationPayload(policyBuild.policyIds);

    this.reservationService.createReservation(payload).subscribe({
      next: (createdReservation) => {
        const roomRequests = roomBuild.payloads.map((roomPayload) =>
          this.reservationService.createReservationRoom({
            ...roomPayload,
            reservation: createdReservation.id
          })
        );

        const guestRequests = guestBuild.payloads.map((guestPayload) =>
          this.reservationService.createReservationGuest({
            ...guestPayload,
            reservation: createdReservation.id
          })
        );

        const creationRequests = [...roomRequests, ...guestRequests];

        if (creationRequests.length === 0) {
          this.saving = false;
          this.created.emit();
          this.closeDrawer();
          return;
        }

        forkJoin(creationRequests).subscribe({
          next: () => {
            this.saving = false;
            this.created.emit();
            this.closeDrawer();
          },
          error: (error) => {
            this.rollbackReservationCreation(createdReservation.id, error);
          }
        });
      },
      error: (error) => {
        this.saving = false;
        this.errorMessage = this.extractErrorMessage(error);
      }
    });
  }

  closeDrawer(): void {
    if (this.saving) return;
    this.closed.emit();
  }

  trackByRoomLine(index: number): number {
    return index;
  }

  trackByPolicyLine(index: number): number {
    return index;
  }

  trackByGuestLine(index: number): number {
    return index;
  }

  trackById(index: number, item: { id?: number }): number {
    return item.id ?? index;
  }

  getAvailablePackagesForDates(): PackageI[] {
    const checkIn = this.parseDate(this.reservationForm.get('expected_check_in')?.value);
    const checkOut = this.parseDate(this.reservationForm.get('expected_check_out')?.value);

    return this.availablePackages.filter((item) => {
      if (!checkIn || !checkOut) {
        return true;
      }

      return this.isPackageWithinDateRange(item, checkIn, checkOut);
    });
  }

  getPackageOptionLabel(item: PackageI): string {
    const price = Number(item.base_price || 0);
    const formattedPrice = Number.isNaN(price)
      ? String(item.base_price || 0)
      : price.toLocaleString('es-CO');
    return `${item.name} - ${formattedPrice}`;
  }

  private buildRoomLine(): UntypedFormGroup {
    return this.fb.group({
      room: [null],
      night_rate: [null],
      adults: [1],
      children: [0]
    });
  }

  private buildPolicyLine(initialPolicyId: number | null = null): UntypedFormGroup {
    return this.fb.group({
      policy: [initialPolicyId]
    });
  }

  private buildGuestLine(): UntypedFormGroup {
    return this.fb.group({
      document_type: [this.getDefaultDocumentTypeId()],
      document_number: [''],
      first_name: [''],
      last_name: [''],
      birth_date: [''],
      nationality: [''],
      blood_type: [''],
      emergency_contact_name: [''],
      emergency_contact_phone: ['']
    });
  }

  private buildReservationPayload(policyIds: number[]): ReservationWritePayloadI {
    const raw = this.reservationForm.getRawValue();

    return {
      client: Number(raw.client),
      origin: Number(raw.origin),
      package: raw.package ? Number(raw.package) : null,
      expected_check_in: String(raw.expected_check_in || ''),
      expected_check_out: String(raw.expected_check_out || ''),
      promo_code: raw.promo_code ? String(raw.promo_code).trim() : null,
      total_discount: raw.total_discount ? Number(raw.total_discount) : 0,
      policies: policyIds,
      notes: raw.notes ? String(raw.notes).trim() : null
    };
  }

  private buildPolicySelection(): { policyIds: number[]; error?: string } {
    const selectedIds: number[] = [];
    const usedIds = new Set<number>();
    const availablePolicyIds = new Set(this.availableReservationPolicies.map((policy) => policy.id));

    for (const policyControl of this.policyLines.controls) {
      const raw = policyControl.getRawValue();
      const policyRaw = raw['policy'];
      const hasSelection = policyRaw !== null && policyRaw !== undefined && `${policyRaw}`.trim() !== '';

      if (!hasSelection) {
        continue;
      }

      const policyId = Number(policyRaw);
      if (!policyId || Number.isNaN(policyId)) {
        return { policyIds: [], error: 'Debes seleccionar una politica valida en cada fila cargada.' };
      }

      if (!availablePolicyIds.has(policyId)) {
        return { policyIds: [], error: 'Una de las politicas seleccionadas ya no esta disponible.' };
      }

      if (usedIds.has(policyId)) {
        return { policyIds: [], error: 'No puedes repetir la misma politica en la reserva.' };
      }

      usedIds.add(policyId);
      selectedIds.push(policyId);
    }

    return { policyIds: selectedIds };
  }

  private buildRoomPayloads(): { payloads: ReservationRoomPayloadI[]; error?: string } {
    const payloads: ReservationRoomPayloadI[] = [];
    const usedRooms = new Set<number>();

    for (const lineControl of this.roomLines.controls) {
      const raw = lineControl.getRawValue();
      const roomRaw = raw['room'];
      const nightRateRaw = raw['night_rate'];
      const adultsRaw = raw['adults'];
      const childrenRaw = raw['children'];

      const hasRoom = roomRaw !== null && roomRaw !== undefined && `${roomRaw}`.trim() !== '';
      const hasNightRate = nightRateRaw !== null && nightRateRaw !== undefined && `${nightRateRaw}`.trim() !== '';
      const hasData = hasRoom || hasNightRate;

      if (!hasData) {
        continue;
      }

      const room = Number(roomRaw);
      const nightRate = Number(nightRateRaw);
      const adults = Number(adultsRaw ?? 1);
      const children = Number(childrenRaw ?? 0);

      if (!room || Number.isNaN(room)) {
        return { payloads: [], error: 'Debes seleccionar una habitacion valida en cada fila cargada.' };
      }

      if (usedRooms.has(room)) {
        return { payloads: [], error: 'No puedes repetir la misma habitacion en una misma reserva.' };
      }
      usedRooms.add(room);

      if (Number.isNaN(nightRate) || nightRate <= 0) {
        return { payloads: [], error: 'La tarifa por noche debe ser mayor a cero.' };
      }

      if (Number.isNaN(adults) || adults < 1) {
        return { payloads: [], error: 'Cada habitacion debe tener minimo 1 adulto.' };
      }

      if (Number.isNaN(children) || children < 0) {
        return { payloads: [], error: 'La cantidad de ninos no puede ser negativa.' };
      }

      payloads.push({
        reservation: 0,
        room,
        night_rate: nightRate,
        adults,
        children
      });
    }

    return { payloads };
  }

  private buildGuestPayloads(): { payloads: ReservationGuestPayloadI[]; error?: string } {
    const payloads: ReservationGuestPayloadI[] = [];
    const usedDocuments = new Set<string>();

    for (const lineControl of this.guestLines.controls) {
      const raw = lineControl.getRawValue();

      const documentTypeRaw = raw['document_type'];
      const documentNumberRaw = String(raw['document_number'] || '').trim();
      const firstNameRaw = String(raw['first_name'] || '').trim();
      const lastNameRaw = String(raw['last_name'] || '').trim();

      const hasCoreData = !!(documentNumberRaw || firstNameRaw || lastNameRaw);
      const hasOptionalData = !!(
        raw['birth_date'] ||
        String(raw['nationality'] || '').trim() ||
        String(raw['blood_type'] || '').trim() ||
        String(raw['emergency_contact_name'] || '').trim() ||
        String(raw['emergency_contact_phone'] || '').trim()
      );

      if (!hasCoreData && !hasOptionalData) {
        continue;
      }

      const documentType = Number(documentTypeRaw || 0);

      if (!documentType || Number.isNaN(documentType)) {
        return { payloads: [], error: 'Cada huesped debe tener un tipo de documento valido.' };
      }

      if (!documentNumberRaw) {
        return { payloads: [], error: 'Cada huesped debe tener numero de documento.' };
      }

      if (!firstNameRaw || !lastNameRaw) {
        return { payloads: [], error: 'Cada huesped debe tener nombre y apellido.' };
      }

      const documentKey = `${documentType}:${documentNumberRaw.toUpperCase()}`;
      if (usedDocuments.has(documentKey)) {
        return { payloads: [], error: 'No puedes repetir el mismo documento en los huespedes de una reserva.' };
      }
      usedDocuments.add(documentKey);

      payloads.push({
        reservation: 0,
        document_type: documentType,
        document_number: documentNumberRaw,
        first_name: firstNameRaw,
        last_name: lastNameRaw,
        birth_date: raw['birth_date'] ? String(raw['birth_date']) : null,
        nationality: String(raw['nationality'] || '').trim() || null,
        blood_type: String(raw['blood_type'] || '').trim() || null,
        emergency_contact_name: String(raw['emergency_contact_name'] || '').trim() || null,
        emergency_contact_phone: String(raw['emergency_contact_phone'] || '').trim() || null
      });
    }

    return { payloads };
  }

  private rollbackReservationCreation(reservationId: number, sourceError: unknown): void {
    this.reservationService.deleteReservation(reservationId).subscribe({
      next: () => {
        this.saving = false;
        this.errorMessage = `${this.extractErrorMessage(sourceError)} Se revirtio la reserva incompleta automaticamente.`;
      },
      error: () => {
        this.saving = false;
        this.errorMessage = `${this.extractErrorMessage(sourceError)} La reserva parcial no se pudo revertir automaticamente.`;
      }
    });
  }

  private validateDateRange(): string {
    const checkInValue = this.reservationForm.get('expected_check_in')?.value;
    const checkOutValue = this.reservationForm.get('expected_check_out')?.value;

    const checkIn = this.parseDate(checkInValue);
    const checkOut = this.parseDate(checkOutValue);

    if (!checkIn || !checkOut) {
      return 'Las fechas de check-in y check-out son obligatorias.';
    }

    if (checkOut <= checkIn) {
      return 'La fecha de check-out debe ser posterior al check-in.';
    }

    return '';
  }

  private validateSelectedPackage(): string {
    const packageRaw = this.reservationForm.get('package')?.value;
    const hasPackage = packageRaw !== null && packageRaw !== undefined && `${packageRaw}`.trim() !== '';
    if (!hasPackage) return '';

    const packageId = Number(packageRaw);
    if (!packageId || Number.isNaN(packageId)) {
      return 'Debes seleccionar un paquete valido.';
    }

    const selectedPackage = this.findPackageById(packageId);
    if (!selectedPackage || selectedPackage.is_active === false) {
      return 'El paquete seleccionado ya no esta disponible.';
    }

    const checkIn = this.parseDate(this.reservationForm.get('expected_check_in')?.value);
    const checkOut = this.parseDate(this.reservationForm.get('expected_check_out')?.value);
    if (checkIn && checkOut && !this.isPackageWithinDateRange(selectedPackage, checkIn, checkOut)) {
      return 'El paquete seleccionado no esta vigente para las fechas de la reserva.';
    }

    return '';
  }

  private parseDate(value: string | null | undefined): Date | null {
    if (!value) return null;
    const parts = String(value).split('-').map((part) => Number(part));
    if (parts.length !== 3 || parts.some((part) => Number.isNaN(part))) return null;

    const date = new Date(parts[0], parts[1] - 1, parts[2]);
    date.setHours(0, 0, 0, 0);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  private addDays(date: Date, days: number): Date {
    const copy = new Date(date);
    copy.setDate(copy.getDate() + days);
    return copy;
  }

  private formatDateForInput(date: Date): string {
    const year = date.getFullYear();
    const month = `${date.getMonth() + 1}`.padStart(2, '0');
    const day = `${date.getDate()}`.padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  private getDefaultOriginId(): number | null {
    const preferredCodes = ['WEB', 'RECEPCION'];
    for (const code of preferredCodes) {
      const match = this.origins.find((origin) => this.normalizeCode(origin.code) === code);
      if (match) return match.id;
    }
    return this.origins[0]?.id ?? null;
  }

  private getDefaultDocumentTypeId(): number | null {
    const preferredCodes = ['CC', 'CE', 'DNI', 'PASAPORTE'];
    for (const code of preferredCodes) {
      const match = this.documentTypes.find((doc) => this.normalizeCode(doc.code) === code);
      if (match) return match.id;
    }
    return this.documentTypes[0]?.id ?? null;
  }

  private setDefaultDocumentTypeForGuests(): void {
    const defaultDocumentTypeId = this.getDefaultDocumentTypeId();
    if (!defaultDocumentTypeId) return;

    for (const guestControl of this.guestLines.controls) {
      const currentValue = guestControl.get('document_type')?.value;
      if (!currentValue) {
        guestControl.get('document_type')?.setValue(defaultDocumentTypeId);
      }
    }
  }

  private applyInitialRoomSelection(): void {
    const targetRoomId = Number(this.initialRoomId || 0);
    if (!targetRoomId || !this.rooms.some((room) => room.id === targetRoomId)) return;

    if (!this.roomLines.length) {
      this.addRoomLine();
    }

    const firstLine = this.roomLines.at(0) as UntypedFormGroup;
    if (firstLine?.get('room')) {
      firstLine.get('room')?.setValue(targetRoomId);
      firstLine.get('room')?.markAsDirty();
    }

    if (this.initialCheckInMode) {
      const today = new Date();
      this.reservationForm.patchValue({
        expected_check_in: this.formatDateForInput(today),
        expected_check_out: this.formatDateForInput(this.addDays(today, 1))
      });
    }
  }

  private normalizeCode(value: string | undefined): string {
    return String(value || '').trim().toUpperCase();
  }

  private findPackageById(packageId: unknown): PackageI | undefined {
    const id = Number(packageId || 0);
    if (!id || Number.isNaN(id)) return undefined;
    return this.availablePackages.find((item) => item.id === id);
  }

  private isPackageWithinDateRange(item: PackageI, checkIn: Date, checkOut: Date): boolean {
    const startDate = this.parseDate(item.start_date || null);
    const endDate = this.parseDate(item.end_date || null);

    if (startDate && checkIn < startDate) {
      return false;
    }

    if (endDate && checkOut > endDate) {
      return false;
    }

    return true;
  }

  private findPolicyById(policyId: unknown): ReservationPolicyI | undefined {
    const id = Number(policyId || 0);
    if (!id || Number.isNaN(id)) return undefined;
    return this.availableReservationPolicies.find((policy) => policy.id === id);
  }

  getPolicyTypeLabel(policyId: unknown): string {
    const policy = this.findPolicyById(policyId);
    if (!policy) return 'Sin tipo';
    return policy.policy_type_name || policy.policy_type_code || 'Sin tipo';
  }

  getPolicyPenaltyLabel(policyId: unknown): string {
    const policy = this.findPolicyById(policyId);
    if (!policy) return 'Sin penalidad';

    const penaltyType = policy.penalty_type_name || policy.penalty_type_code || 'Penalidad';
    const rawValue = policy.penalty_value;
    if (rawValue === null || rawValue === undefined || rawValue === '') {
      return penaltyType;
    }

    const value = Number(rawValue);
    if (Number.isNaN(value)) return penaltyType;

    const isPercentage = this.normalizeCode(policy.penalty_type_code) === 'PERCENTAGE';
    const formattedValue = isPercentage ? `${value}%` : value.toLocaleString('es-CO');
    return `${penaltyType}: ${formattedValue}`;
  }

  getPolicyHoursLabel(policyId: unknown): string {
    const policy = this.findPolicyById(policyId);
    const hours = Number(policy?.hours_before_checkin);
    if (Number.isNaN(hours) || hours < 0) return 'Sin limite';
    return `${hours} hora(s)`;
  }

  private collectSelectedPolicyIds(): number[] {
    const selectedIds: number[] = [];
    const usedIds = new Set<number>();

    for (const control of this.policyLines.controls) {
      const raw = control.getRawValue();
      const policyId = Number(raw['policy'] || 0);
      if (!policyId || Number.isNaN(policyId) || usedIds.has(policyId)) {
        continue;
      }
      usedIds.add(policyId);
      selectedIds.push(policyId);
    }

    return selectedIds;
  }

  private extractErrorMessage(error: unknown): string {
    const fallback = 'No se pudo crear la reserva. Verifica los datos e intenta nuevamente.';

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
