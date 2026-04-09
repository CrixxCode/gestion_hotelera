import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { RoomInventoryI } from '../room-inventory-model';

@Component({
  selector: 'app-detail-room-inventory',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './detail-room-inventory.html',
  styleUrls: ['./detail-room-inventory.css']
})
export class DetailRoomInventory {
  @Input() roomInventoryData: RoomInventoryI | null = null;

  @Output() closed = new EventEmitter<void>();
  @Output() statusRequested = new EventEmitter<RoomInventoryI>();
  @Output() deleteRequested = new EventEmitter<RoomInventoryI>();

  closeDrawer(): void {
    this.closed.emit();
  }

  requestStatusToggle(): void {
    if (!this.roomInventoryData) return;
    this.statusRequested.emit(this.roomInventoryData);
  }

  requestDelete(): void {
    if (!this.roomInventoryData) return;
    this.deleteRequested.emit(this.roomInventoryData);
  }

  getStatusLabel(): string {
    if (!this.roomInventoryData) return 'Sin estado';
    return this.roomInventoryData.is_active ? 'Activo' : 'Inactivo';
  }

  getItemLabel(): string {
    if (!this.roomInventoryData) return 'Item no definido';
    return this.roomInventoryData.item_name || 'Item no definido';
  }

  getRoomLabel(): string {
    if (!this.roomInventoryData) return 'Habitacion no definida';
    if (this.roomInventoryData.room_number) return `Habitacion ${this.roomInventoryData.room_number}`;
    if (typeof this.roomInventoryData.room === 'number' && this.roomInventoryData.room > 0) {
      return `Habitacion #${this.roomInventoryData.room}`;
    }
    return 'Habitacion no definida';
  }

  getCoverageLabel(): string {
    const quantity = this.toNonNegativeInt(this.roomInventoryData?.quantity);
    const minimum = this.toNonNegativeInt(this.roomInventoryData?.minimum_quantity);
    if (quantity <= 0) return 'Sin stock';
    if (quantity <= minimum) return 'Bajo minimo';
    return 'Cobertura normal';
  }

  getCoverageTone(): { bg: string; color: string } {
    const quantity = this.toNonNegativeInt(this.roomInventoryData?.quantity);
    const minimum = this.toNonNegativeInt(this.roomInventoryData?.minimum_quantity);
    if (quantity <= 0) return { bg: '#fef2f2', color: '#b42318' };
    if (quantity <= minimum) return { bg: '#fff7ed', color: '#c2410c' };
    return { bg: '#dcfce7', color: '#15803d' };
  }

  formatDate(value: string | undefined): string {
    if (!value) return 'Sin registro';
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value;

    return parsed.toLocaleDateString('es-CO', {
      day: '2-digit',
      month: 'short',
      year: 'numeric'
    });
  }

  private toNonNegativeInt(value: unknown): number {
    const parsed = Number(value);
    if (!Number.isFinite(parsed) || parsed < 0) return 0;
    return Math.floor(parsed);
  }
}
