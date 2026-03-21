import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { catchError, forkJoin, map, of } from 'rxjs';
import { RoomService } from '../../../services/room';
import { AmenityI, RoomI } from '../room-model';

type StatusFilter = 'ALL' | 'ACTIVE' | 'INACTIVE';
type DrawerMode = 'create' | 'edit';
type ToastKind = 'success' | 'danger' | 'info';

type AmenityIconOption = {
  value: string;
  label: string;
};

const AMENITY_ICON_CATALOG: AmenityIconOption[] = [
  { value: 'fa-solid fa-bed', label: 'Cama' },
  { value: 'fa-solid fa-wifi', label: 'WiFi' },
  { value: 'fa-solid fa-tv', label: 'TV' },
  { value: 'fa-solid fa-bath', label: 'Bano' },
  { value: 'fa-solid fa-snowflake', label: 'Aire' },
  { value: 'fa-solid fa-mug-hot', label: 'Cafe' },
  { value: 'fa-solid fa-square-parking', label: 'Parqueadero' },
  { value: 'fa-solid fa-water-ladder', label: 'Piscina' },
  { value: 'fa-solid fa-bell-concierge', label: 'Servicio' },
  { value: 'fa-solid fa-dumbbell', label: 'Gimnasio' }
];

@Component({
  selector: 'app-amenities',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './amenities.html',
  styleUrls: ['./amenities.css']
})
export class AmenitiesPage implements OnInit {
  loading = false;
  saving = false;
  loadWarning = '';

  allAmenities: AmenityI[] = [];
  filteredAmenities: AmenityI[] = [];
  usageByAmenity = new Map<number, number>();

  search = '';
  statusFilter: StatusFilter = 'ALL';

  showDrawer = false;
  drawerMode: DrawerMode = 'create';
  editingId: number | null = null;

  form: {
    name: string;
    description: string;
    icon: string;
    is_active: boolean;
  } = {
    name: '',
    description: '',
    icon: AMENITY_ICON_CATALOG[0]?.value || '',
    is_active: true
  };

  showDeleteConfirm = false;
  deleteTarget: AmenityI | null = null;

  toastVisible = false;
  toastText = '';
  toastKind: ToastKind = 'info';
  private toastTimer?: ReturnType<typeof setTimeout>;

  readonly iconCatalog = AMENITY_ICON_CATALOG;

  constructor(private roomService: RoomService) {
    this.form = this.emptyForm();
  }

  ngOnInit(): void {
    this.loadData();
  }

  get totalAmenities(): number {
    return this.allAmenities.length;
  }

  get activeAmenities(): number {
    return this.allAmenities.filter((item) => !!item.is_active).length;
  }

  get inactiveAmenities(): number {
    return this.allAmenities.filter((item) => !item.is_active).length;
  }

  get usedAmenities(): number {
    return this.allAmenities.filter((item) => this.getUsageCount(item.id) > 0).length;
  }

  trackByAmenity(_: number, item: AmenityI): number {
    return item.id;
  }

  loadData(): void {
    this.loading = true;
    this.loadWarning = '';
    forkJoin({
      amenitiesResult: this.roomService.listAmenities().pipe(
        map((data) => ({ data, failed: false })),
        catchError(() => of({ data: [] as AmenityI[], failed: true }))
      ),
      roomsResult: this.roomService.listRooms().pipe(
        map((data) => ({ data, failed: false })),
        catchError(() => of({ data: [] as RoomI[], failed: true }))
      )
    }).subscribe({
      next: ({ amenitiesResult, roomsResult }) => {
        this.loading = false;
        this.allAmenities = this.sortAmenities(amenitiesResult.data);
        this.usageByAmenity = this.buildUsageMap(roomsResult.data);
        this.applyFilters();

        if (amenitiesResult.failed) {
          this.loadWarning = 'No se pudieron cargar amenidades. Revisa permisos de acceso.';
          this.toast(this.loadWarning, 'danger');
        } else if (roomsResult.failed) {
          this.loadWarning = 'No se pudo calcular el uso de amenidades por habitacion.';
          this.toast(this.loadWarning, 'info');
        }
      },
      error: () => {
        this.loading = false;
        this.allAmenities = [];
        this.filteredAmenities = [];
        this.usageByAmenity.clear();
        this.toast('No se pudo cargar amenidades.', 'danger');
      }
    });
  }

  applyFilters(): void {
    const q = this.search.trim().toLowerCase();

    this.filteredAmenities = this.allAmenities.filter((item) => {
      const matchesStatus =
        this.statusFilter === 'ALL' ||
        (this.statusFilter === 'ACTIVE' && !!item.is_active) ||
        (this.statusFilter === 'INACTIVE' && !item.is_active);

      const pool = [item.name, item.description || '', item.icon || ''].join(' ').toLowerCase();
      const matchesSearch = !q || pool.includes(q);

      return matchesStatus && matchesSearch;
    });
  }

  openCreate(): void {
    this.drawerMode = 'create';
    this.editingId = null;
    this.form = this.emptyForm();
    this.showDrawer = true;
  }

  openEdit(item: AmenityI): void {
    this.drawerMode = 'edit';
    this.editingId = item.id;
    this.form = {
      name: item.name || '',
      description: item.description || '',
      icon: this.isCatalogIcon(item.icon) ? item.icon! : this.iconCatalog[0].value,
      is_active: item.is_active !== false
    };
    this.showDrawer = true;
  }

  closeDrawer(): void {
    if (this.saving) return;
    this.showDrawer = false;
  }

  selectIcon(icon: string): void {
    this.form.icon = icon;
  }

  saveAmenity(): void {
    if (this.saving) return;

    const name = (this.form.name || '').trim();
    const description = (this.form.description || '').trim();
    const icon = (this.form.icon || '').trim();

    if (!name) {
      this.toast('El nombre es obligatorio.', 'danger');
      return;
    }

    if (!this.isCatalogIcon(icon)) {
      this.toast('Selecciona un icono del catalogo.', 'danger');
      return;
    }

    const payload: Partial<AmenityI> = {
      name,
      description,
      icon,
      is_active: !!this.form.is_active
    };

    this.saving = true;
    if (this.drawerMode === 'edit' && this.editingId) {
      this.roomService.updateAmenity(this.editingId, payload).subscribe({
        next: () => {
          this.saving = false;
          this.showDrawer = false;
          this.toast('Amenidad actualizada.', 'success');
          this.loadData();
        },
        error: (error) => {
          this.saving = false;
          this.toast(this.extractErrorMessage(error, 'No se pudo actualizar la amenidad.'), 'danger');
        }
      });
      return;
    }

    this.roomService.createAmenity(payload).subscribe({
      next: () => {
        this.saving = false;
        this.showDrawer = false;
        this.toast('Amenidad creada.', 'success');
        this.loadData();
      },
      error: (error) => {
        this.saving = false;
        this.toast(this.extractErrorMessage(error, 'No se pudo crear la amenidad.'), 'danger');
      }
    });
  }

  askDelete(item: AmenityI): void {
    this.deleteTarget = item;
    this.showDeleteConfirm = true;
  }

  confirmDelete(): void {
    if (!this.deleteTarget) return;
    const targetId = this.deleteTarget.id;

    this.roomService.deleteAmenity(targetId).subscribe({
      next: () => {
        this.showDeleteConfirm = false;
        this.deleteTarget = null;
        this.toast('Amenidad eliminada.', 'success');
        this.loadData();
      },
      error: (error) => {
        this.showDeleteConfirm = false;
        this.deleteTarget = null;
        this.toast(this.extractErrorMessage(error, 'No se pudo eliminar la amenidad.'), 'danger');
      }
    });
  }

  getUsageCount(id: number): number {
    return this.usageByAmenity.get(id) || 0;
  }

  formatDate(value?: string): string {
    if (!value) return 'N/D';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return 'N/D';
    return new Intl.DateTimeFormat('es-CO', { dateStyle: 'medium' }).format(date);
  }

  defaultIcon(): string {
    return this.iconCatalog[0].value;
  }

  private emptyForm() {
    return {
      name: '',
      description: '',
      icon: this.iconCatalog[0].value,
      is_active: true
    };
  }

  private isCatalogIcon(icon?: string | null): boolean {
    if (!icon) return false;
    return this.iconCatalog.some((item) => item.value === icon);
  }

  private sortAmenities(items: AmenityI[]): AmenityI[] {
    return [...items].sort((a, b) => (a.name || '').localeCompare(b.name || '', 'es', { sensitivity: 'base' }));
  }

  private buildUsageMap(rooms: RoomI[]): Map<number, number> {
    const usage = new Map<number, number>();
    for (const room of rooms) {
      if (!Array.isArray(room.amenities)) continue;
      for (const amenity of room.amenities) {
        if (typeof amenity?.id !== 'number') continue;
        usage.set(amenity.id, (usage.get(amenity.id) || 0) + 1);
      }
    }
    return usage;
  }

  private toast(message: string, kind: ToastKind = 'info'): void {
    this.toastText = message;
    this.toastKind = kind;
    this.toastVisible = true;
    if (this.toastTimer) clearTimeout(this.toastTimer);
    this.toastTimer = setTimeout(() => {
      this.toastVisible = false;
    }, 2600);
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
