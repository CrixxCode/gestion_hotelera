import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RoomI } from '../../rooms/room-model';
import { ItemI } from '../../items/item-model';
import { RoomInventoryService } from '../../../services/room-inventory';
import { RoomInventoryFormPayload } from '../room-inventory-model';

@Component({
  selector: 'app-create-room-inventory',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './create-room-inventory.html',
  styleUrls: ['./create-room-inventory.css']
})
export class CreateRoomInventory {
  @Input() rooms: RoomI[] = [];
  @Input() items: ItemI[] = [];

  @Output() closed = new EventEmitter<void>();
  @Output() created = new EventEmitter<void>();

  saving = false;
  errorMessage = '';

  roomInventoryForm: ReturnType<FormBuilder['group']>;

  constructor(
    private fb: FormBuilder,
    private roomInventoryService: RoomInventoryService
  ) {
    this.roomInventoryForm = this.fb.group({
      room: [null as number | null, [Validators.required]],
      item: [null as number | null, [Validators.required]],
      quantity: [0, [Validators.required, Validators.min(0)]],
      minimum_quantity: [0, [Validators.required, Validators.min(0)]],
      notes: ['', [Validators.maxLength(2000)]],
      is_active: [true]
    });
  }

  get room() {
    return this.roomInventoryForm.get('room');
  }

  get item() {
    return this.roomInventoryForm.get('item');
  }

  get quantity() {
    return this.roomInventoryForm.get('quantity');
  }

  get minimum_quantity() {
    return this.roomInventoryForm.get('minimum_quantity');
  }

  get availableRooms(): RoomI[] {
    return this.rooms
      .filter((room) => !!room.number)
      .sort((a, b) => (a.number || '').localeCompare(b.number || '', 'es', { numeric: true }));
  }

  get availableItems(): ItemI[] {
    return this.items
      .filter((item) => item.is_active)
      .sort((a, b) => (a.name || '').localeCompare(b.name || '', 'es', { sensitivity: 'base' }));
  }

  get selectedItemLabel(): string {
    const selectedId = Number(this.item?.value);
    if (!Number.isInteger(selectedId) || selectedId <= 0) return 'Selecciona un item para ver stock disponible.';

    const selectedItem = this.items.find((item) => item.id === selectedId);
    if (!selectedItem) return 'Item no encontrado.';

    return `Stock general del item: ${this.toNonNegativeInt(selectedItem.stock)} unidades.`;
  }

  submit(): void {
    this.errorMessage = '';

    if (!this.availableRooms.length) {
      this.errorMessage = 'No hay habitaciones disponibles para asignar inventario.';
      return;
    }

    if (!this.availableItems.length) {
      this.errorMessage = 'No hay items activos para asignar en habitaciones.';
      return;
    }

    if (this.roomInventoryForm.invalid) {
      this.roomInventoryForm.markAllAsTouched();
      return;
    }

    const raw = this.roomInventoryForm.getRawValue();
    const payload: RoomInventoryFormPayload = {
      room: Number(raw.room),
      item: Number(raw.item),
      quantity: this.toNonNegativeInt(raw.quantity),
      minimum_quantity: this.toNonNegativeInt(raw.minimum_quantity),
      notes: raw.notes?.trim() || '',
      is_active: !!raw.is_active
    };

    this.saving = true;
    this.roomInventoryService.createRoomInventory(payload).subscribe({
      next: () => {
        this.saving = false;
        this.created.emit();
        this.closeDrawer();
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

  trackById(_: number, item: { id: number }): number {
    return item.id;
  }

  getRoomLabel(room: RoomI): string {
    const floor = room.floor_name ? ` - ${room.floor_name}` : '';
    return `Habitacion ${room.number}${floor}`;
  }

  getItemLabel(item: ItemI): string {
    const sku = item.sku?.trim();
    if (sku) return `${item.name} (${sku})`;
    return item.name;
  }

  private toNonNegativeInt(value: unknown): number {
    const parsed = Number(value);
    if (!Number.isFinite(parsed) || parsed < 0) return 0;
    return Math.floor(parsed);
  }

  private extractErrorMessage(error: unknown): string {
    const fallback = 'No se pudo crear el inventario de habitacion. Revisa los datos e intenta nuevamente.';

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
