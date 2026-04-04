import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { catchError, forkJoin, map, Observable, of, switchMap } from 'rxjs';
import { environment } from '../../../../enviorements/environment';
import { MasterDataI } from '../master-data/master-data-model';
import { AuthService } from '../../../services/auth/auth';
import { HotelSettingsService } from '../../../services/hotel-settings';
import { MasterDataService } from '../../../services/master-data.service';
import { ReservationService } from '../../../services/reservation';
import { ReservationPolicyI, ReservationPolicyPayloadI } from '../../../modules/reservations/reservation-model';
import { HotelFloor, HotelSettings as HotelSettingsModel } from './hotel-setting-model';

type SettingsTab = 'general' | 'contact' | 'structure' | 'operation' | 'policies';
type SettingsForm = {
  hotel_name: string;
  legal_name: string;
  slogan: string;
  description: string;
  stars: number;
  facebook: string;
  instagram: string;
  twitter_x: string;
  address: string;
  city: string;
  state: string;
  country: string;
  postal_code: string;
  primary_phone: string;
  secondary_phone: string;
  general_email: string;
  reservations_email: string;
  website: string;
  check_in_time: string;
  check_out_time: string;
  max_guests_per_room: number;
  currency: string;
  tax_rate: number;
  system_language: string;
  timezone: string;
};

type ReservationPolicyForm = {
  id: number | null;
  policy_type: number | null;
  penalty_type: number | null;
  name: string;
  description: string;
  penalty_value: number | null;
  hours_before_checkin: number | null;
  is_active: boolean;
};

@Component({
  selector: 'app-hotel-settings',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './hotel-settings.html',
  styleUrl: './hotel-settings.css',
})
export class HotelSettings implements OnInit {
  private readonly apiBase = (environment.API_URI || 'http://localhost:8000').replace(/\/$/, '');
  private readonly floorsUrl = `${this.apiBase}/api/hotel-floors/`;

  loading = true;
  saving = false;
  errorMessage = '';
  successMessage = '';
  canEdit = false;
  canReadPolicies = false;
  canEditPolicies = false;

  activeTab: SettingsTab = 'general';
  settingsId: number | null = null;
  updatedAt: string | null = null;

  form: SettingsForm = this.buildDefaultForm();
  floors: HotelFloor[] = [];
  deletedFloorIds: number[] = [];
  reservationPolicies: ReservationPolicyI[] = [];
  policyTypes: MasterDataI[] = [];
  penaltyTypes: MasterDataI[] = [];
  policyForm: ReservationPolicyForm = this.buildDefaultPolicyForm();
  policyLoading = false;
  policySaving = false;
  policyDeletingId: number | null = null;

  private initialSnapshot = '';

  readonly tabs: Array<{ key: SettingsTab; label: string; icon: string }> = [
    { key: 'general', label: 'Información General', icon: 'fa-solid fa-building' },
    { key: 'contact', label: 'Contacto & Ubicación', icon: 'fa-solid fa-location-dot' },
    { key: 'structure', label: 'Estructura', icon: 'fa-solid fa-layer-group' },
    { key: 'policies', label: 'Politicas de Reserva', icon: 'fa-solid fa-file-contract' },
    { key: 'operation', label: 'Operación', icon: 'fa-regular fa-clock' },
  ];

  readonly currencyOptions = [
    { code: 'COP', label: 'COP - Peso Colombiano' },
    { code: 'MXN', label: 'MXN - Peso Mexicano' },
    { code: 'USD', label: 'USD - Dólar Estadounidense' },
    { code: 'EUR', label: 'EUR - Euro' },
  ];

  readonly languageOptions = [
    { code: 'es', label: 'Español' },
    { code: 'en', label: 'Inglés' },
    { code: 'pt', label: 'Portugués' },
  ];

  readonly timezoneOptions = [
    'America/Bogota',
    'America/Mexico_City',
    'America/New_York',
    'Europe/Madrid',
  ];

  constructor(
    private settingsSvc: HotelSettingsService,
    private http: HttpClient,
    private auth: AuthService,
    private masterDataService: MasterDataService,
    private reservationService: ReservationService
  ) {}

  ngOnInit(): void {
    this.resolvePermissions();
    this.loadCurrentSettings();
  }

  selectTab(tab: SettingsTab): void {
    this.activeTab = tab;
  }

  get totalFloors(): number {
    return this.floors.length;
  }

  get totalRooms(): number {
    return this.floors.reduce((sum, floor) => sum + (Number(floor.room_count) || 0), 0);
  }

  get averageRoomsPerFloor(): number {
    if (!this.totalFloors) return 0;
    return Number((this.totalRooms / this.totalFloors).toFixed(1));
  }

  get starsArray(): number[] {
    const stars = Math.max(1, Math.min(5, Number(this.form.stars) || 1));
    return Array.from({ length: 5 }, (_, i) => (i < stars ? 1 : 0));
  }

  get taxRateDisplay(): string {
    return `${Number(this.form.tax_rate || 0).toFixed(0)}%`;
  }

  get lastUpdatedLabel(): string {
    if (!this.updatedAt) return 'Sin actualizaciones registradas';
    const parsed = new Date(this.updatedAt);
    if (Number.isNaN(parsed.getTime())) return 'Sin actualizaciones registradas';

    return new Intl.DateTimeFormat('es-CO', {
      dateStyle: 'long',
      timeStyle: 'short',
      hour12: true,
    }).format(parsed);
  }

  get hasChanges(): boolean {
    return this.initialSnapshot !== this.currentSnapshot();
  }

  get isActiveTabReadOnly(): boolean {
    if (this.activeTab === 'policies') return !this.canEditPolicies;
    return !this.canEdit;
  }

  get activePoliciesCount(): number {
    return this.reservationPolicies.filter((policy) => policy.is_active !== false).length;
  }

  get isPercentagePenaltySelected(): boolean {
    return this.getPenaltyTypeCode(this.policyForm.penalty_type) === 'PERCENTAGE';
  }

  setStars(value: number): void {
    if (!this.canEdit) return;
    this.form.stars = value;
  }

  onHotelLogoSelected(event: Event): void {
    if (!this.canEdit) return;
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0] ?? null;
    if (!file) return;
    this.successMessage = `Logo seleccionado: ${file.name}`;
  }

  addFloor(): void {
    if (!this.canEdit) return;
    const nextFloorNumber = Math.max(0, ...this.floors.map((f) => Number(f.floor_number) || 0)) + 1;
    this.floors = [
      ...this.floors,
      {
        floor_number: nextFloorNumber,
        name: `Piso ${nextFloorNumber}`,
        prefix: String(nextFloorNumber),
        room_count: 1,
      },
    ];
  }

  removeFloor(index: number): void {
    if (!this.canEdit) return;
    const floor = this.floors[index];
    if (!floor) return;
    if (floor.id) this.deletedFloorIds.push(floor.id);
    this.floors = this.floors.filter((_, i) => i !== index);
  }

  floorRange(floor: HotelFloor): string {
    const prefix = `${floor.prefix || ''}`.trim();
    const roomCount = Number(floor.room_count) || 0;
    if (!prefix || roomCount <= 0) return 'Sin rango';

    const start = `${prefix}01`;
    const end = `${prefix}${String(roomCount).padStart(2, '0')}`;
    return `${start} - ${end}`;
  }

  trackPolicy(_: number, policy: ReservationPolicyI): number {
    return policy.id;
  }

  newPolicy(): void {
    if (!this.canEditPolicies) return;
    this.policyForm = this.buildDefaultPolicyForm();
    this.applyPolicyCatalogDefaults();
    this.errorMessage = '';
    this.successMessage = '';
  }

  editPolicy(policy: ReservationPolicyI): void {
    if (!this.canEditPolicies) return;

    const penaltyValue =
      policy.penalty_value === undefined || policy.penalty_value === null || policy.penalty_value === ''
        ? null
        : Number(policy.penalty_value);

    this.policyForm = {
      id: policy.id,
      policy_type: Number(policy.policy_type) || null,
      penalty_type: Number(policy.penalty_type) || null,
      name: (policy.name || '').trim(),
      description: String(policy.description || ''),
      penalty_value: Number.isNaN(penaltyValue) ? null : penaltyValue,
      hours_before_checkin:
        policy.hours_before_checkin === undefined || policy.hours_before_checkin === null
          ? null
          : Number(policy.hours_before_checkin),
      is_active: policy.is_active !== false
    };

    this.errorMessage = '';
    this.successMessage = '';
  }

  cancelPolicyEdition(): void {
    this.policyForm = this.buildDefaultPolicyForm();
    this.applyPolicyCatalogDefaults();
    this.errorMessage = '';
    this.successMessage = '';
  }

  savePolicy(): void {
    if (!this.canEditPolicies) {
      this.errorMessage = 'No tienes permisos para modificar politicas de reserva.';
      return;
    }

    const validation = this.validatePolicyBeforeSave();
    if (validation) {
      this.errorMessage = validation;
      return;
    }

    const payload = this.buildPolicyPayload();
    if (!payload) {
      this.errorMessage = 'No se pudo construir la politica a guardar.';
      return;
    }

    this.policySaving = true;
    this.errorMessage = '';
    this.successMessage = '';

    const request$ = this.policyForm.id
      ? this.reservationService.updateReservationPolicy(this.policyForm.id, payload)
      : this.reservationService.createReservationPolicy(payload);

    request$.subscribe({
      next: () => {
        this.policySaving = false;
        const wasEditing = !!this.policyForm.id;
        this.policyForm = this.buildDefaultPolicyForm();
        this.applyPolicyCatalogDefaults();
        this.loadReservationPolicies();
        this.successMessage = wasEditing
          ? 'Politica de reserva actualizada correctamente.'
          : 'Politica de reserva creada correctamente.';
      },
      error: (error) => {
        this.policySaving = false;
        this.errorMessage = this.extractApiErrorMessage(
          error,
          'No se pudo guardar la politica de reserva.'
        );
      }
    });
  }

  deletePolicy(policy: ReservationPolicyI): void {
    if (!this.canEditPolicies) return;
    const policyName = (policy.name || '').trim() || `#${policy.id}`;
    const confirmed = window.confirm(`Deseas eliminar la politica "${policyName}"?`);
    if (!confirmed) return;

    this.policyDeletingId = policy.id;
    this.errorMessage = '';
    this.successMessage = '';

    this.reservationService.deleteReservationPolicy(policy.id).subscribe({
      next: () => {
        if (this.policyForm.id === policy.id) {
          this.policyForm = this.buildDefaultPolicyForm();
          this.applyPolicyCatalogDefaults();
        }

        this.loadReservationPolicies();
        this.policyDeletingId = null;
        this.successMessage = 'Politica de reserva eliminada correctamente.';
      },
      error: (error) => {
        this.policyDeletingId = null;
        this.errorMessage = this.extractApiErrorMessage(
          error,
          'No se pudo eliminar la politica de reserva.'
        );
      }
    });
  }

  policyPenaltyLabel(policy: ReservationPolicyI): string {
    const penaltyCode = this.normalizeCode(policy.penalty_type_code);
    const penaltyValue = Number(policy.penalty_value);

    if (Number.isNaN(penaltyValue)) {
      return policy.penalty_type_name || policy.penalty_type_code || 'Sin penalidad';
    }

    if (penaltyCode === 'PERCENTAGE') {
      return `${penaltyValue}%`;
    }

    return penaltyValue.toLocaleString('es-CO');
  }

  saveSettings(): void {
    if (!this.canEdit) {
      this.errorMessage = 'No tienes permisos para modificar la configuración del hotel.';
      return;
    }

    this.errorMessage = '';
    this.successMessage = '';

    const validation = this.validateBeforeSave();
    if (validation) {
      this.errorMessage = validation;
      return;
    }

    this.saving = true;
    const payload = this.buildPayload();
    const save$ = this.settingsId
      ? this.settingsSvc.updateSettings(this.settingsId, payload)
      : this.settingsSvc.createSettings(payload);

    save$
      .pipe(
        switchMap((saved) => {
          this.settingsId = saved.id ?? null;
          this.updatedAt = this.extractUpdatedAt(saved);
          if (!saved.id) return of(saved);

          return this.syncFloors(saved.id).pipe(map(() => saved));
        }),
        switchMap(() => this.settingsSvc.getCurrentSettings())
      )
      .subscribe({
        next: (fresh) => {
          this.saving = false;
          this.applySettings(fresh);
          this.initialSnapshot = this.currentSnapshot();
          this.successMessage = 'Configuración guardada correctamente.';
        },
        error: () => {
          this.saving = false;
          this.errorMessage = 'No se pudo guardar la configuración. Verifica los datos e inténtalo de nuevo.';
        },
      });
  }

  discardChanges(): void {
    if (!this.canEdit) return;
    this.errorMessage = '';
    this.successMessage = '';
    this.loadCurrentSettings();
  }

  clearAllSettings(): void {
    if (!this.canEdit || this.saving) return;

    if (!this.settingsId) {
      this.errorMessage = 'No hay configuracion activa para eliminar.';
      return;
    }

    const confirmed = window.confirm(
      'Esta accion eliminara toda la configuracion del hotel. Deseas continuar?'
    );
    if (!confirmed) return;

    this.saving = true;
    this.errorMessage = '';
    this.successMessage = '';

    this.settingsSvc
      .clearSettings()
      .pipe(switchMap(() => this.settingsSvc.getCurrentSettings()))
      .subscribe({
        next: (fresh) => {
          this.saving = false;
          this.applySettings(fresh);
          this.initialSnapshot = this.currentSnapshot();
          this.successMessage = 'Configuracion eliminada correctamente.';
        },
        error: (error) => {
          this.saving = false;
          if (error?.status === 404) {
            this.applySettings(null);
            this.initialSnapshot = this.currentSnapshot();
            this.successMessage = 'No habia configuracion activa.';
            return;
          }
          this.errorMessage = 'No se pudo eliminar la configuracion del hotel.';
        },
      });
  }

  resetOperationDefaults(): void {
    if (!this.canEdit) return;
    this.form.check_in_time = '14:00';
    this.form.check_out_time = '12:00';
    this.form.max_guests_per_room = 2;
    this.form.currency = 'COP';
    this.form.tax_rate = 19;
    this.form.system_language = 'es';
    this.form.timezone = 'America/Bogota';
  }

  trackFloor(_: number, floor: HotelFloor): number | string {
    return floor.id ?? `${floor.floor_number}-${floor.prefix}`;
  }

  private loadCurrentSettings(): void {
    this.loading = true;
    this.settingsSvc.getCurrentSettings().subscribe({
      next: (settings) => {
        this.loading = false;
        this.applySettings(settings);
        this.initialSnapshot = this.currentSnapshot();
      },
      error: () => {
        this.loading = false;
        this.applySettings(null);
        this.initialSnapshot = this.currentSnapshot();
        this.errorMessage = 'No se pudo cargar la configuración actual.';
      },
    });
  }

  private resolvePermissions(): void {
    this.auth.getUserInfo().subscribe({
      next: (user) => {
        const keys = Array.isArray(user.resource_keys) ? user.resource_keys : [];
        this.canEdit = this.hasSettingsWritePermission(keys);
        this.canReadPolicies = this.hasPoliciesReadPermission(keys);
        this.canEditPolicies = this.hasPoliciesWritePermission(keys);

        if (this.canReadPolicies) {
          this.loadPolicyCatalogs();
          if (this.settingsId) {
            this.loadReservationPolicies();
          }
        } else {
          this.resetPolicyState();
        }
      },
      error: () => {
        this.canEdit = false;
        this.canReadPolicies = false;
        this.canEditPolicies = false;
        this.resetPolicyState();
      }
    });
  }

  private hasSettingsWritePermission(resourceKeys: string[]): boolean {
    const normalized = new Set(resourceKeys.map((k) => (k || '').trim().toLowerCase()));
    return (
      normalized.has('*') ||
      normalized.has('hotel_settings.write') ||
      normalized.has('hotel-settings.write') ||
      normalized.has('hotel-config.write') ||
      normalized.has('hotel_settings.*') ||
      normalized.has('hotel-settings.*') ||
      normalized.has('hotel-config.*')
    );
  }

  private hasPoliciesReadPermission(resourceKeys: string[]): boolean {
    const normalized = new Set(resourceKeys.map((k) => (k || '').trim().toLowerCase()));
    return (
      normalized.has('*') ||
      normalized.has('reservation-policies.read') ||
      normalized.has('reservation_policies.read') ||
      normalized.has('reservation-policies.write') ||
      normalized.has('reservation_policies.write') ||
      normalized.has('reservation-policies.*') ||
      normalized.has('reservation_policies.*')
    );
  }

  private hasPoliciesWritePermission(resourceKeys: string[]): boolean {
    const normalized = new Set(resourceKeys.map((k) => (k || '').trim().toLowerCase()));
    return (
      normalized.has('*') ||
      normalized.has('reservation-policies.write') ||
      normalized.has('reservation_policies.write') ||
      normalized.has('reservation-policies.*') ||
      normalized.has('reservation_policies.*')
    );
  }

  private applySettings(settings: HotelSettingsModel | null): void {
    if (!settings) {
      this.settingsId = null;
      this.updatedAt = null;
      this.form = this.buildDefaultForm();
      this.floors = [];
      this.deletedFloorIds = [];
      this.clearPoliciesCollection();
      return;
    }

    this.settingsId = settings.id ?? null;
    this.updatedAt = this.extractUpdatedAt(settings);
    this.form = {
      ...this.buildDefaultForm(),
      ...settings,
      stars: settings.stars ?? 3,
      tax_rate: Number(settings.tax_rate ?? 0),
      max_guests_per_room: Number(settings.max_guests_per_room ?? 2),
      check_in_time: this.normalizeTime(settings.check_in_time, '14:00'),
      check_out_time: this.normalizeTime(settings.check_out_time, '12:00'),
    };

    this.floors = (settings.floors ?? []).map((floor) => ({
      ...floor,
      room_count: Number(floor.room_count) || 0,
    }));
    this.deletedFloorIds = [];

    if (this.canReadPolicies) {
      this.loadReservationPolicies();
    } else {
      this.clearPoliciesCollection();
    }
  }

  private loadPolicyCatalogs(): void {
    forkJoin({
      policyTypes: this.masterDataService
        .listMasterData({
          group: 'RESERVATION_POLICY_TYPE',
          is_active: 'true',
          ordering: 'sort_order,name'
        })
        .pipe(catchError(() => of([] as MasterDataI[]))),
      penaltyTypes: this.masterDataService
        .listMasterData({
          group: 'RESERVATION_PENALTY_TYPE',
          is_active: 'true',
          ordering: 'sort_order,name'
        })
        .pipe(catchError(() => of([] as MasterDataI[])))
    }).subscribe({
      next: ({ policyTypes, penaltyTypes }) => {
        this.policyTypes = [...policyTypes];
        this.penaltyTypes = [...penaltyTypes];
        this.applyPolicyCatalogDefaults();
      }
    });
  }

  private loadReservationPolicies(): void {
    const settingsId = this.settingsId;
    if (!this.canReadPolicies || !settingsId) {
      this.clearPoliciesCollection();
      return;
    }

    this.policyLoading = true;
    this.reservationService
      .listReservationPolicies({
        ordering: '-id',
        hotel_settings: settingsId,
        is_active: true
      })
      .subscribe({
      next: (policies) => {
        this.policyLoading = false;
        this.reservationPolicies = policies.sort((a, b) => b.id - a.id);
      },
      error: (error) => {
        this.policyLoading = false;
        this.reservationPolicies = [];

        if (error?.status === 403) {
          this.canReadPolicies = false;
          this.canEditPolicies = false;
          this.resetPolicyState();
          this.errorMessage = 'No tienes permisos para ver politicas de reserva.';
          return;
        }

        this.errorMessage = 'No se pudieron cargar las politicas de reserva.';
      }
    });
  }

  private clearPoliciesCollection(): void {
    this.reservationPolicies = [];
    this.policyForm = this.buildDefaultPolicyForm();
    this.policyLoading = false;
    this.policySaving = false;
    this.policyDeletingId = null;
    this.applyPolicyCatalogDefaults();
  }

  private resetPolicyState(): void {
    this.policyTypes = [];
    this.penaltyTypes = [];
    this.clearPoliciesCollection();
  }

  private applyPolicyCatalogDefaults(): void {
    if (this.policyForm.id) return;

    if (!this.policyForm.policy_type && this.policyTypes.length > 0) {
      this.policyForm.policy_type = this.policyTypes[0].id;
    }

    if (!this.policyForm.penalty_type && this.penaltyTypes.length > 0) {
      this.policyForm.penalty_type = this.penaltyTypes[0].id;
    }
  }

  private syncFloors(settingsId: number): Observable<void> {
    const options = this.auth.buildCsrfRequestOptions();
    const createReqs = this.floors
      .filter((floor) => !floor.id)
      .map((floor) =>
        this.http.post(this.floorsUrl, this.floorPayload(floor, settingsId), options)
      );

    const updateReqs = this.floors
      .filter((floor) => !!floor.id)
      .map((floor) =>
        this.http.patch(
          `${this.floorsUrl}${floor.id}/`,
          this.floorPayload(floor, settingsId),
          options
        )
      );

    const deleteReqs = this.deletedFloorIds.map((id) =>
      this.http.delete(`${this.floorsUrl}${id}/`, options)
    );

    const requests = [...createReqs, ...updateReqs, ...deleteReqs];
    if (!requests.length) return of(void 0);

    return forkJoin(requests).pipe(map(() => void 0));
  }

  private floorPayload(floor: HotelFloor, settingsId: number): Partial<HotelFloor> & { hotel_settings: number } {
    return {
      hotel_settings: settingsId,
      floor_number: Number(floor.floor_number) || 1,
      name: (floor.name || '').trim() || `Piso ${Number(floor.floor_number) || 1}`,
      prefix: (floor.prefix || '').trim() || String(Number(floor.floor_number) || 1),
      room_count: Math.max(1, Number(floor.room_count) || 1),
    };
  }

  private buildPayload(): Partial<HotelSettingsModel> {
    return {
      hotel_name: this.form.hotel_name.trim(),
      legal_name: this.emptyAsUndefined(this.form.legal_name),
      slogan: this.emptyAsUndefined(this.form.slogan),
      description: this.emptyAsUndefined(this.form.description),
      stars: Math.max(1, Math.min(5, Number(this.form.stars) || 3)),
      facebook: this.emptyAsUndefined(this.form.facebook),
      instagram: this.emptyAsUndefined(this.form.instagram),
      twitter_x: this.emptyAsUndefined(this.form.twitter_x),
      address: this.emptyAsUndefined(this.form.address),
      city: this.emptyAsUndefined(this.form.city),
      state: this.emptyAsUndefined(this.form.state),
      country: this.emptyAsUndefined(this.form.country),
      postal_code: this.emptyAsUndefined(this.form.postal_code),
      primary_phone: this.emptyAsUndefined(this.form.primary_phone),
      secondary_phone: this.emptyAsUndefined(this.form.secondary_phone),
      general_email: this.emptyAsUndefined(this.form.general_email),
      reservations_email: this.emptyAsUndefined(this.form.reservations_email),
      website: this.emptyAsUndefined(this.form.website),
      check_in_time: this.emptyAsUndefined(this.form.check_in_time),
      check_out_time: this.emptyAsUndefined(this.form.check_out_time),
      max_guests_per_room: Math.max(1, Number(this.form.max_guests_per_room) || 1),
      currency: this.form.currency || 'COP',
      tax_rate: Math.max(0, Math.min(100, Number(this.form.tax_rate) || 0)),
      system_language: this.form.system_language || 'es',
      timezone: this.form.timezone || 'America/Bogota',
    };
  }

  private validateBeforeSave(): string | null {
    if (!(this.form.hotel_name || '').trim()) {
      return 'El nombre comercial del hotel es obligatorio.';
    }

    const floorNumbers = new Set<number>();
    for (const floor of this.floors) {
      const floorNumber = Number(floor.floor_number);
      const roomCount = Number(floor.room_count);
      if (!floorNumber || floorNumber < 1) return 'Todos los pisos deben tener un número válido.';
      if (floorNumbers.has(floorNumber)) return 'No puede haber números de piso duplicados.';
      if (!roomCount || roomCount < 1) return 'Cada piso debe tener al menos una habitación.';
      floorNumbers.add(floorNumber);
    }

    if (this.form.check_in_time && this.form.check_out_time && this.form.check_in_time === this.form.check_out_time) {
      return 'Check-in y check-out no pueden tener la misma hora.';
    }

    return null;
  }

  private validatePolicyBeforeSave(): string | null {
    if (!this.settingsId) {
      return 'Debes guardar primero la configuracion principal del hotel.';
    }

    if (!(this.policyForm.name || '').trim()) {
      return 'El nombre de la politica es obligatorio.';
    }

    if (!this.policyForm.policy_type) {
      return 'Debes seleccionar el tipo de politica.';
    }

    if (!this.policyForm.penalty_type) {
      return 'Debes seleccionar el tipo de penalidad.';
    }

    if (this.policyForm.penalty_value !== null && Number(this.policyForm.penalty_value) < 0) {
      return 'El valor de penalidad no puede ser negativo.';
    }

    if (
      this.policyForm.hours_before_checkin !== null &&
      Number(this.policyForm.hours_before_checkin) < 0
    ) {
      return 'Las horas antes del check-in no pueden ser negativas.';
    }

    if (this.isPercentagePenaltySelected) {
      if (this.policyForm.penalty_value === null) {
        return 'El valor de penalidad es obligatorio para penalidad porcentual.';
      }

      if (Number(this.policyForm.penalty_value) > 100) {
        return 'La penalidad porcentual no puede ser mayor a 100.';
      }
    }

    return null;
  }

  private buildPolicyPayload(): ReservationPolicyPayloadI | null {
    if (!this.settingsId) return null;

    const penaltyValue =
      this.policyForm.penalty_value === null || this.policyForm.penalty_value === undefined
        ? null
        : Number(this.policyForm.penalty_value);
    const hoursBeforeCheckin =
      this.policyForm.hours_before_checkin === null || this.policyForm.hours_before_checkin === undefined
        ? null
        : Number(this.policyForm.hours_before_checkin);

    return {
      hotel_settings: this.settingsId,
      policy_type: Number(this.policyForm.policy_type || 0),
      penalty_type: Number(this.policyForm.penalty_type || 0),
      name: (this.policyForm.name || '').trim(),
      description: this.emptyAsNull(this.policyForm.description),
      penalty_value: penaltyValue,
      hours_before_checkin: hoursBeforeCheckin,
      is_active: this.policyForm.is_active
    };
  }

  private getPenaltyTypeCode(penaltyTypeId: number | null): string {
    if (!penaltyTypeId) return '';
    const selected = this.penaltyTypes.find((item) => item.id === penaltyTypeId);
    return this.normalizeCode(selected?.code);
  }

  private currentSnapshot(): string {
    const normalizedFloors = this.floors
      .map((floor) => ({
        id: floor.id ?? null,
        floor_number: Number(floor.floor_number) || 0,
        name: (floor.name || '').trim(),
        prefix: (floor.prefix || '').trim(),
        room_count: Number(floor.room_count) || 0,
      }))
      .sort((a, b) => a.floor_number - b.floor_number);

    return JSON.stringify({
      settingsId: this.settingsId,
      payload: this.buildPayload(),
      floors: normalizedFloors,
      deletedFloorIds: [...this.deletedFloorIds].sort((a, b) => a - b),
    });
  }

  private normalizeTime(value?: string | null, fallback = '00:00'): string {
    if (!value) return fallback;
    return value.slice(0, 5);
  }

  private emptyAsUndefined(value?: string | null): string | undefined {
    const normalized = (value || '').trim();
    return normalized ? normalized : undefined;
  }

  private emptyAsNull(value?: string | null): string | null {
    const normalized = (value || '').trim();
    return normalized ? normalized : null;
  }

  private normalizeCode(value: string | undefined): string {
    return String(value || '').trim().toUpperCase();
  }

  private extractApiErrorMessage(error: unknown, fallback: string): string {
    const payload =
      error && typeof error === 'object' ? (error as Record<string, unknown>)['error'] : null;

    if (typeof payload === 'string' && payload.trim()) {
      return payload.trim();
    }

    if (payload && typeof payload === 'object') {
      const detail = (payload as Record<string, unknown>)['detail'];
      if (typeof detail === 'string' && detail.trim()) {
        return detail.trim();
      }

      for (const value of Object.values(payload as Record<string, unknown>)) {
        if (typeof value === 'string' && value.trim()) {
          return value.trim();
        }
        if (Array.isArray(value) && value.length > 0 && typeof value[0] === 'string') {
          const first = value[0].trim();
          if (first) return first;
        }
      }
    }

    return fallback;
  }

  private buildDefaultForm(): SettingsForm {
    return {
      hotel_name: '',
      legal_name: '',
      slogan: '',
      description: '',
      stars: 3,
      facebook: '',
      instagram: '',
      twitter_x: '',
      address: '',
      city: '',
      state: '',
      country: '',
      postal_code: '',
      primary_phone: '',
      secondary_phone: '',
      general_email: '',
      reservations_email: '',
      website: '',
      check_in_time: '14:00',
      check_out_time: '12:00',
      max_guests_per_room: 2,
      currency: 'COP',
      tax_rate: 19,
      system_language: 'es',
      timezone: 'America/Bogota',
    };
  }

  private buildDefaultPolicyForm(): ReservationPolicyForm {
    return {
      id: null,
      policy_type: null,
      penalty_type: null,
      name: '',
      description: '',
      penalty_value: null,
      hours_before_checkin: null,
      is_active: true
    };
  }

  private extractUpdatedAt(settings: unknown): string | null {
    if (!settings || typeof settings !== 'object') return null;
    const value = (settings as Record<string, unknown>)['updated_at'];
    return typeof value === 'string' ? value : null;
  }
}

