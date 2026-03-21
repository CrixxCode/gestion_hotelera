import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, OnChanges, Output, SimpleChanges } from '@angular/core';
import { AmenityI, RoomI, RoomPanelI, RoomStatus } from '../room-model';
import { RoomService } from '../../../services/room';

type StatusTone = {
  bg: string;
  color: string;
  dot: string;
};

@Component({
  selector: 'app-room-detail',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './room-detail.html',
  styleUrls: ['./room-detail.css']
})
export class RoomDetail implements OnChanges {
  @Input() room: RoomI | null = null;

  @Output() closed = new EventEmitter<void>();
  @Output() editRequested = new EventEmitter<RoomI>();
  @Output() refreshed = new EventEmitter<void>();

  panel: RoomPanelI | null = null;
  loading = false;
  errorMessage = '';
  actionLoading = false;

  constructor(private roomService: RoomService) {}

  ngOnChanges(changes: SimpleChanges): void {
    if (!changes['room'] || !this.room?.id) return;
    this.loadPanel(this.room.id);
  }

  get roomNumber(): string {
    return this.panel?.number || this.room?.number || '---';
  }

  get roomTypeLabel(): string {
    return this.panel?.room_type?.name || this.room?.room_type_name || 'Sin tipo';
  }

  get floorLabel(): string {
    const floorName = this.panel?.floor_name || this.room?.floor_name;
    const floorNumber = this.panel?.floor_number || this.room?.florr_number;
    if (floorName && floorNumber) return `${floorName} · Piso ${floorNumber}`;
    if (floorName) return floorName;
    if (floorNumber) return `Piso ${floorNumber}`;
    return 'Piso no asignado';
  }

  get statusLabel(): string {
    if (this.panel?.status_label) return this.panel.status_label;
    return this.getStatusLabel((this.panel?.status || this.room?.status || 'DISPONIBLE') as RoomStatus);
  }

  get statusTone(): StatusTone {
    return this.getStatusTone((this.panel?.status || this.room?.status || 'DISPONIBLE') as RoomStatus);
  }

  get priceLabel(): string {
    const rateValue = this.panel?.rate?.price;
    if (rateValue === null || rateValue === undefined || rateValue === '') return 'Tarifa pendiente';
    const asNumber = Number(rateValue);
    if (Number.isNaN(asNumber)) return `${rateValue}`;

    return new Intl.NumberFormat('es-CO', {
      style: 'currency',
      currency: 'COP',
      maximumFractionDigits: 0
    }).format(asNumber);
  }

  get bedLabel(): string {
    const roomType = this.panel?.room_type;
    if (!roomType) return 'Sin configuración de camas';
    const bedCount = roomType.bed_count ? `${roomType.bed_count}` : '?';
    const bedType = roomType.bed_type || 'cama';
    return `${bedCount} ${bedType}`;
  }

  get amenities(): Array<Pick<AmenityI, 'name' | 'icon'>> {
    if (this.panel?.amenities?.length) {
      return this.panel.amenities.map((amenity) => ({
        name: amenity.name,
        icon: amenity.icon
      }));
    }

    if (this.room?.amenities?.length) {
      return this.room.amenities.map((amenity) => ({
        name: amenity.name,
        icon: amenity.icon
      }));
    }

    return [];
  }

  get hasMaintenance(): boolean {
    return !!this.panel?.active_maintenance;
  }

  get canMarkAsAvailable(): boolean {
    const status = (this.panel?.status || this.room?.status) as RoomStatus | undefined;
    return status === 'MANTENIMIENTO' || status === 'FUERA_DE_SERVICIO' || status === 'LIMPIEZA';
  }

  closeDrawer(): void {
    if (this.actionLoading) return;
    this.closed.emit();
  }

  requestEdit(): void {
    if (!this.room) return;
    this.editRequested.emit(this.room);
  }

  markAsAvailable(): void {
    if (!this.room || this.actionLoading || !this.canMarkAsAvailable) return;

    this.actionLoading = true;
    const amenityIds = this.room.amenities?.map((amenity) => amenity.id) || [];

    this.roomService
      .updateRoom(this.room.id, {
        number: this.room.number,
        floor: this.room.floor,
        room_type: this.room.room_type,
        status: 'DISPONIBLE',
        notes: this.room.notes || '',
        amenity_ids: amenityIds
      })
      .subscribe({
        next: () => {
          this.actionLoading = false;
          this.loadPanel(this.room!.id);
          this.refreshed.emit();
        },
        error: () => {
          this.actionLoading = false;
          this.errorMessage = 'No fue posible cambiar el estado de la habitación.';
        }
      });
  }

  private loadPanel(roomId: number): void {
    this.loading = true;
    this.errorMessage = '';
    this.panel = null;

    this.roomService.getRoomPanel(roomId).subscribe({
      next: (data) => {
        this.loading = false;
        this.panel = data;
      },
      error: () => {
        this.loading = false;
        this.errorMessage = 'No se pudo cargar el detalle de la habitación.';
      }
    });
  }

  private getStatusLabel(status: RoomStatus): string {
    switch (status) {
      case 'DISPONIBLE':
        return 'Disponible';
      case 'OCUPADA':
        return 'Ocupada';
      case 'MANTENIMIENTO':
        return 'Mantenimiento';
      case 'LIMPIEZA':
        return 'Limpieza';
      case 'FUERA_DE_SERVICIO':
        return 'Fuera de servicio';
      default:
        return 'Sin estado';
    }
  }

  private getStatusTone(status: RoomStatus): StatusTone {
    switch (status) {
      case 'DISPONIBLE':
        return { bg: '#e9f9ef', color: '#0f9f56', dot: '#21c06a' };
      case 'OCUPADA':
        return { bg: '#eaf1ff', color: '#2f69e2', dot: '#3979ff' };
      case 'MANTENIMIENTO':
        return { bg: '#ffeceb', color: '#c8372e', dot: '#ef4444' };
      case 'LIMPIEZA':
        return { bg: '#ecfeff', color: '#0e7490', dot: '#06b6d4' };
      case 'FUERA_DE_SERVICIO':
        return { bg: '#f2f4f8', color: '#4b5563', dot: '#9ca3af' };
      default:
        return { bg: '#f2f4f8', color: '#4b5563', dot: '#9ca3af' };
    }
  }
}
