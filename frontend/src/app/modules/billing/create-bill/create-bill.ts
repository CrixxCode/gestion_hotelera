import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, OnChanges, Output, SimpleChanges } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MasterDataI } from '../../../components/pages/master-data/master-data-model';
import { BillingService } from '../../../services/billing';
import { ServiceI } from '../../services/service-model';
import { ChargeCreatePayloadI, ChargeI } from '../billing-model';

@Component({
  selector: 'app-create-bill',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './create-bill.html',
  styleUrls: ['./create-bill.css']
})
export class CreateBill implements OnChanges {
  @Input() reservationId: number | null = null;
  @Input() chargeTypes: MasterDataI[] = [];
  @Input() services: ServiceI[] = [];

  @Output() created = new EventEmitter<ChargeI>();
  @Output() cancelled = new EventEmitter<void>();

  saving = false;
  errorMessage = '';

  chargeForm: ReturnType<FormBuilder['group']>;

  constructor(
    private fb: FormBuilder,
    private billingService: BillingService
  ) {
    this.chargeForm = this.fb.group({
      charge_type: [null as number | null, [Validators.required]],
      service: [null as number | null],
      quantity: [1, [Validators.required, Validators.min(1)]],
      description: [''],
      unit_price: [0, [Validators.min(0)]],
    });
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['chargeTypes']) {
      this.ensureDefaultChargeType();
    }
  }

  get charge_type() {
    return this.chargeForm.get('charge_type');
  }

  get quantity() {
    return this.chargeForm.get('quantity');
  }

  get description() {
    return this.chargeForm.get('description');
  }

  get unit_price() {
    return this.chargeForm.get('unit_price');
  }

  get hasServicesCatalog(): boolean {
    return this.services.length > 0;
  }

  get manualMode(): boolean {
    const serviceId = Number(this.chargeForm.getRawValue().service || 0);
    return !(Number.isFinite(serviceId) && serviceId > 0);
  }

  submit(): void {
    this.errorMessage = '';

    if (!this.reservationId) {
      this.errorMessage = 'No se encontro una reserva asociada para registrar el cargo.';
      return;
    }

    if (this.chargeForm.invalid) {
      this.chargeForm.markAllAsTouched();
      return;
    }

    const raw = this.chargeForm.getRawValue();
    const quantity = this.normalizeQuantity(raw.quantity);
    if (quantity < 1) {
      this.errorMessage = 'La cantidad debe ser mayor o igual a 1.';
      return;
    }

    const payload: ChargeCreatePayloadI = {
      reservation: Number(this.reservationId),
      charge_type: Number(raw.charge_type || 0) || null,
      quantity,
      is_active: true,
    };

    const selectedService = Number(raw.service || 0);
    if (Number.isFinite(selectedService) && selectedService > 0) {
      payload.service = selectedService;
    } else {
      const description = String(raw.description || '').trim();
      if (!description) {
        this.errorMessage = 'Debes indicar una descripcion para el cargo manual.';
        return;
      }

      const unitPrice = this.normalizePrice(raw.unit_price);
      if (unitPrice < 0) {
        this.errorMessage = 'El valor unitario no puede ser negativo.';
        return;
      }

      payload.description = description;
      payload.unit_price = unitPrice;
    }

    this.saving = true;
    this.billingService.createCharge(payload).subscribe({
      next: (charge) => {
        this.saving = false;
        this.created.emit(charge);
        this.resetFormForNextEntry();
      },
      error: (error) => {
        this.saving = false;
        this.errorMessage = this.extractErrorMessage(error);
      }
    });
  }

  close(): void {
    if (this.saving) return;
    this.cancelled.emit();
  }

  trackById(_: number, item: { id: number }): number {
    return item.id;
  }

  private ensureDefaultChargeType(): void {
    const selected = Number(this.chargeForm.getRawValue().charge_type || 0);
    if (selected > 0) return;
    if (!this.chargeTypes.length) return;

    this.chargeForm.patchValue({
      charge_type: this.chargeTypes[0].id
    });
  }

  private resetFormForNextEntry(): void {
    this.chargeForm.patchValue({
      service: null,
      quantity: 1,
      description: '',
      unit_price: 0
    });
    this.chargeForm.markAsPristine();
    this.chargeForm.markAsUntouched();
    this.errorMessage = '';
  }

  private normalizeQuantity(value: unknown): number {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return 1;
    return Math.max(1, Math.round(parsed));
  }

  private normalizePrice(value: unknown): number {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return 0;
    return parsed;
  }

  private extractErrorMessage(error: unknown): string {
    const fallback = 'No fue posible registrar el cargo manual.';

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

