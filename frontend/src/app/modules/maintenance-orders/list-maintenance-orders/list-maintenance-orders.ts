import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { catchError, forkJoin, of } from 'rxjs';
import { ConfirmationService } from 'primeng/api';
import { MasterDataI } from '../../../components/pages/master-data/master-data-model';
import { openActionConfirmation } from '../../../services/action-confirmations';
import { MaintenanceOrdersService } from '../../../services/maintenance-order';
import { MasterDataService } from '../../../services/master-data.service';
import { RoomService } from '../../../services/room';
import { RoomI } from '../../rooms/room-model';
import { CreateMaintenanceOrder } from '../create-maintenance-order/create-maintenance-order';
import { DetailMaintenanceOrder } from '../detail-maintenance-order/detail-maintenance-order';
import { MaintenanceOrderI } from '../maintenance-order-model';

type MaintenanceOrderViewMode = 'cards' | 'table';

type MaintenancePriorityTone = {
  icon: string;
  iconBg: string;
  iconColor: string;
  cover: string;
  badgeBg: string;
  badgeColor: string;
  accent: string;
};

type MaintenanceOrderGroup = {
  key: string;
  label: string;
  code: string;
  order: number;
  tone: MaintenancePriorityTone;
  items: MaintenanceOrderI[];
};

const PRIORITY_TONES: Record<string, MaintenancePriorityTone> = {
  URGENTE: {
    icon: 'fa-solid fa-triangle-exclamation',
    iconBg: '#fef2f2',
    iconColor: '#b42318',
    cover: 'linear-gradient(135deg, #7f1d1d 0%, #dc2626 100%)',
    badgeBg: '#fee2e2',
    badgeColor: '#b42318',
    accent: '#ef4444'
  },
  ALTA: {
    icon: 'fa-solid fa-bolt',
    iconBg: '#fff7ed',
    iconColor: '#c2410c',
    cover: 'linear-gradient(135deg, #7c2d12 0%, #f97316 100%)',
    badgeBg: '#ffedd5',
    badgeColor: '#c2410c',
    accent: '#fb923c'
  },
  MEDIA: {
    icon: 'fa-solid fa-screwdriver-wrench',
    iconBg: '#e0f2fe',
    iconColor: '#0369a1',
    cover: 'linear-gradient(135deg, #0c4a6e 0%, #0ea5e9 100%)',
    badgeBg: '#e0f2fe',
    badgeColor: '#0369a1',
    accent: '#0ea5e9'
  },
  BAJA: {
    icon: 'fa-solid fa-toolbox',
    iconBg: '#dcfce7',
    iconColor: '#15803d',
    cover: 'linear-gradient(135deg, #14532d 0%, #16a34a 100%)',
    badgeBg: '#dcfce7',
    badgeColor: '#15803d',
    accent: '#22c55e'
  },
  DEFAULT: {
    icon: 'fa-solid fa-helmet-safety',
    iconBg: '#e6edf7',
    iconColor: '#1f3f73',
    cover: 'linear-gradient(135deg, #1f365f 0%, #3d659f 100%)',
    badgeBg: '#e6edf7',
    badgeColor: '#1f3f73',
    accent: '#335f9d'
  }
};

@Component({
  selector: 'app-list-maintenance-orders',
  standalone: true,
  imports: [CommonModule, FormsModule, CreateMaintenanceOrder, DetailMaintenanceOrder],
  templateUrl: './list-maintenance-orders.html',
  styleUrls: ['./list-maintenance-orders.css']
})
export class ListMaintenanceOrders implements OnInit {
  loading = false;
  errorMessage = '';
  infoMessage = '';
  viewMode: MaintenanceOrderViewMode = 'cards';

  maintenanceOrders: MaintenanceOrderI[] = [];
  filteredMaintenanceOrders: MaintenanceOrderI[] = [];
  groupedMaintenanceOrders: MaintenanceOrderGroup[] = [];
  rooms: RoomI[] = [];
  priorities: MasterDataI[] = [];
  statuses: MasterDataI[] = [];

  search = '';
  statusFilter = 'ALL';
  selectedPriorityFilter = 'ALL';
  selectedRoomFilter = 'ALL';

  statusFilterOptions: Array<{ value: string; label: string }> = [{ value: 'ALL', label: 'Todos los estados' }];
  priorityFilterOptions: Array<{ value: string; label: string }> = [{ value: 'ALL', label: 'Todas las prioridades' }];
  roomFilterOptions: Array<{ value: string; label: string }> = [{ value: 'ALL', label: 'Todas las habitaciones' }];

  showCreateDrawer = false;
  selectedMaintenanceOrder: MaintenanceOrderI | null = null;

  private roomMap = new Map<number, RoomI>();
  private priorityMap = new Map<string, MasterDataI>();
  private statusMap = new Map<string, MasterDataI>();
  private priorityOrderMap = new Map<string, number>();
  private statusCodeByNormalized = new Map<string, string>();
  private highlightedByGroup = new Map<string, Set<number>>();

  constructor(
    private maintenanceOrdersService: MaintenanceOrdersService,
    private roomService: RoomService,
    private masterDataService: MasterDataService,
    private confirmationService: ConfirmationService
  ) {}

  ngOnInit(): void {
    this.loadCatalogData();
  }

  get totalOrders(): number {
    return this.maintenanceOrders.length;
  }

  get pendingOrders(): number {
    return this.maintenanceOrders.filter((order) => this.normalizeCode(order.status) === 'PENDIENTE').length;
  }

  get inProgressOrders(): number {
    return this.maintenanceOrders.filter((order) => this.normalizeCode(order.status) === 'ENPROCESO').length;
  }

  get completedOrders(): number {
    return this.maintenanceOrders.filter((order) => this.normalizeCode(order.status) === 'COMPLETADA').length;
  }

  get canCreateOrder(): boolean {
    return this.rooms.length > 0 && this.priorities.length > 0 && this.statuses.length > 0;
  }

  loadCatalogData(): void {
    this.loading = true;
    this.errorMessage = '';
    const selectedId = this.selectedMaintenanceOrder?.id ?? null;

    forkJoin({
      maintenanceOrders: this.maintenanceOrdersService
        .listMaintenanceOrders()
        .pipe(catchError(() => of([] as MaintenanceOrderI[]))),
      rooms: this.roomService.listRooms().pipe(catchError(() => of([] as RoomI[]))),
      priorities: this.masterDataService
        .listMasterData({ group: 'MAINTENANCE_PRIORITY', is_active: 'true', ordering: 'sort_order,name' })
        .pipe(catchError(() => of([] as MasterDataI[]))),
      statuses: this.masterDataService
        .listMasterData({ group: 'MAINTENANCE_STATUS', is_active: 'true', ordering: 'sort_order,name' })
        .pipe(catchError(() => of([] as MasterDataI[])))
    }).subscribe({
      next: ({ maintenanceOrders, rooms, priorities, statuses }) => {
        this.loading = false;
        this.maintenanceOrders = maintenanceOrders;
        this.rooms = rooms;
        this.priorities = priorities;
        this.statuses = statuses;

        if (selectedId) {
          this.selectedMaintenanceOrder = maintenanceOrders.find((order) => order.id === selectedId) || null;
        }

        this.buildMaps();
        this.buildFilterOptions();
        this.applyFilters();

        if (!rooms.length) {
          this.infoMessage = 'No hay habitaciones disponibles para crear ordenes.';
        } else if (!priorities.length) {
          this.infoMessage = 'No hay prioridades de mantenimiento activas en master data.';
        } else if (!statuses.length) {
          this.infoMessage = 'No hay estados de mantenimiento activos en master data.';
        } else {
          this.infoMessage = '';
        }
      },
      error: () => {
        this.loading = false;
        this.errorMessage = 'No fue posible cargar las ordenes de mantenimiento.';
      }
    });
  }

  refreshMaintenanceOrders(): void {
    this.loadCatalogData();
  }

  exportCsv(): void {
    if (!this.filteredMaintenanceOrders.length) return;

    const headers = [
      'codigo',
      'habitacion',
      'titulo',
      'prioridad',
      'estado',
      'reportado_en',
      'finalizado_en',
      'descripcion'
    ];
    const rows = this.filteredMaintenanceOrders.map((order) => {
      const row = [
        this.getOrderCode(order),
        this.getRoomLabel(order),
        this.getTitleLabel(order),
        this.getPriorityLabel(order),
        this.getStatusLabel(order),
        this.formatDateTime(order.reported_at),
        this.formatDateTime(order.completed_at),
        this.getDescriptionLabel(order)
      ];

      return row.map((cell) => this.escapeCsvCell(cell)).join(',');
    });

    const csv = [headers.join(','), ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `ordenes-mantenimiento-${this.formatFileDate(new Date())}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  applyFilters(): void {
    const searchValue = this.normalizeSearch(this.search);

    this.filteredMaintenanceOrders = this.maintenanceOrders.filter((order) => {
      const statusMatch =
        this.statusFilter === 'ALL' || this.normalizeCode(order.status) === this.normalizeCode(this.statusFilter);

      const priorityMatch =
        this.selectedPriorityFilter === 'ALL' ||
        this.normalizeCode(this.getPriorityCode(order)) === this.normalizeCode(this.selectedPriorityFilter);

      const roomMatch = this.selectedRoomFilter === 'ALL' || this.getRoomKey(order) === this.selectedRoomFilter;

      const searchPool = [
        this.getOrderCode(order),
        this.getRoomLabel(order),
        this.getTitleLabel(order),
        this.getDescriptionLabel(order),
        this.getPriorityLabel(order),
        this.getStatusLabel(order),
        order.reported_at || '',
        order.completed_at || ''
      ]
        .join(' ')
        .toLowerCase();

      const searchMatch = !searchValue || searchPool.includes(searchValue);
      return statusMatch && priorityMatch && roomMatch && searchMatch;
    });

    this.groupedMaintenanceOrders = this.buildGroups(this.filteredMaintenanceOrders);
  }

  setViewMode(mode: MaintenanceOrderViewMode): void {
    this.viewMode = mode;
  }

  openCreateDrawer(): void {
    this.selectedMaintenanceOrder = null;
    this.showCreateDrawer = true;
  }

  closeCreateDrawer(): void {
    this.showCreateDrawer = false;
  }

  onMaintenanceOrderCreated(): void {
    this.showCreateDrawer = false;
    this.refreshMaintenanceOrders();
  }

  openDetail(order: MaintenanceOrderI): void {
    this.showCreateDrawer = false;
    this.selectedMaintenanceOrder = order;
  }

  closeDetail(): void {
    this.selectedMaintenanceOrder = null;
  }

  advanceOrderStatus(order: MaintenanceOrderI): void {
    this.errorMessage = '';
    const nextCode = this.resolveNextStatusCode(order);
    if (!nextCode) return;

    const nextNormalized = this.normalizeCode(nextCode);
    const payload = {
      status: nextCode,
      completed_at: nextNormalized === 'COMPLETADA' ? this.toDateTimeLocal(new Date()) : null
    };

    this.maintenanceOrdersService.updateMaintenanceOrder(order.id, payload).subscribe({
      next: () => {
        this.refreshMaintenanceOrders();
      },
      error: () => {
        this.errorMessage = 'No fue posible actualizar el estado de la orden.';
      }
    });
  }

  confirmDelete(order: MaintenanceOrderI): void {
    openActionConfirmation(this.confirmationService, {
      action: 'delete',
      target: this.getOrderCode(order),
      onAccept: () => {
        this.errorMessage = '';
        this.maintenanceOrdersService.deleteMaintenanceOrder(order.id).subscribe({
          next: () => {
            if (this.selectedMaintenanceOrder?.id === order.id) {
              this.closeDetail();
            }
            this.refreshMaintenanceOrders();
          },
          error: () => {
            this.errorMessage = 'No fue posible eliminar la orden seleccionada.';
          }
        });
      }
    });
  }

  getRoomLabel(order: MaintenanceOrderI): string {
    if (order.room_number?.trim()) return `Habitacion ${order.room_number.trim()}`;

    if (typeof order.room === 'number' && order.room > 0) {
      const room = this.roomMap.get(order.room);
      if (room?.number?.trim()) return `Habitacion ${room.number.trim()}`;
      return `Habitacion #${order.room}`;
    }

    return 'Habitacion no definida';
  }

  getOrderCode(order: MaintenanceOrderI): string {
    return `OM-${String(order.id).padStart(4, '0')}`;
  }

  getTitleLabel(order: MaintenanceOrderI): string {
    const title = String(order.title || '').trim();
    if (title) return title;
    return 'Sin titulo';
  }

  getDescriptionLabel(order: MaintenanceOrderI): string {
    const description = order.description?.trim();
    if (description) return description;
    return 'Sin descripcion tecnica.';
  }

  getPriorityLabel(order: MaintenanceOrderI): string {
    const fromRecord = order.priority_label?.trim();
    if (fromRecord) return fromRecord;

    const catalog = this.priorityMap.get(this.normalizeCode(order.priority));
    if (catalog?.name?.trim()) return catalog.name.trim();

    return this.toTitleLabel(order.priority || 'Sin prioridad');
  }

  getStatusLabel(order: MaintenanceOrderI): string {
    const fromRecord = order.status_label?.trim();
    if (fromRecord) return fromRecord;

    const catalog = this.statusMap.get(this.normalizeCode(order.status));
    if (catalog?.name?.trim()) return catalog.name.trim();

    return this.toTitleLabel(order.status || 'Sin estado');
  }

  getStatusTone(order: MaintenanceOrderI): { bg: string; color: string; dot: string } {
    const code = this.normalizeCode(order.status);
    if (code === 'COMPLETADA') return { bg: '#dcfce7', color: '#15803d', dot: '#22c55e' };
    if (code === 'ENPROCESO') return { bg: '#e0f2fe', color: '#0369a1', dot: '#0ea5e9' };
    if (code === 'CANCELADA') return { bg: '#eef2f7', color: '#64748b', dot: '#94a3b8' };
    return { bg: '#fff7ed', color: '#c2410c', dot: '#f97316' };
  }

  getPriorityBadgeTone(order: MaintenanceOrderI): { bg: string; color: string; dot: string } {
    const tone = this.resolvePriorityTone(order);
    return {
      bg: tone.badgeBg,
      color: tone.badgeColor,
      dot: tone.accent
    };
  }

  getGroupTone(group: MaintenanceOrderGroup): MaintenancePriorityTone {
    return group.tone;
  }

  isHighlighted(groupKey: string, orderId: number): boolean {
    return this.highlightedByGroup.get(groupKey)?.has(orderId) || false;
  }

  isDelayed(order: MaintenanceOrderI): boolean {
    const status = this.normalizeCode(order.status);
    if (status === 'COMPLETADA' || status === 'CANCELADA') return false;

    const reported = this.parseDate(order.reported_at);
    if (!reported) return false;

    const now = new Date();
    const diffMs = now.getTime() - reported.getTime();
    const diffHours = diffMs / (1000 * 60 * 60);
    return diffHours >= 48;
  }

  getProgressActionLabel(order: MaintenanceOrderI): string {
    const status = this.normalizeCode(order.status);
    if (status === 'COMPLETADA' || status === 'CANCELADA') return 'Reabrir';
    if (status === 'ENPROCESO') return 'Completar';
    return 'Iniciar';
  }

  getProgressActionIcon(order: MaintenanceOrderI): string {
    const status = this.normalizeCode(order.status);
    if (status === 'COMPLETADA' || status === 'CANCELADA') return 'fa-solid fa-rotate-left';
    if (status === 'ENPROCESO') return 'fa-solid fa-check';
    return 'fa-solid fa-play';
  }

  trackByOrder(_: number, order: MaintenanceOrderI): number {
    return order.id;
  }

  trackByGroup(_: number, group: MaintenanceOrderGroup): string {
    return group.key;
  }

  formatDateTime(value: string | null | undefined): string {
    if (!value) return 'Sin fecha';
    const parsed = this.parseDate(value);
    if (!parsed) return String(value);

    return parsed.toLocaleString('es-CO', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  private buildMaps(): void {
    this.roomMap = new Map(this.rooms.map((room) => [room.id, room]));

    this.priorityMap.clear();
    this.priorityOrderMap.clear();
    for (const priorityItem of this.priorities) {
      const normalized = this.normalizeCode(priorityItem.code);
      this.priorityMap.set(normalized, priorityItem);
      this.priorityOrderMap.set(normalized, Number(priorityItem.sort_order || 0));
    }

    this.statusMap.clear();
    this.statusCodeByNormalized.clear();
    for (const statusItem of this.statuses) {
      const normalized = this.normalizeCode(statusItem.code);
      this.statusMap.set(normalized, statusItem);
      this.statusCodeByNormalized.set(normalized, statusItem.code);
    }
  }

  private buildFilterOptions(): void {
    const sortedStatuses = [...this.statuses].sort((a, b) => {
      const byOrder = Number(a.sort_order || 0) - Number(b.sort_order || 0);
      if (byOrder !== 0) return byOrder;
      return (a.name || '').localeCompare(b.name || '', 'es', { sensitivity: 'base' });
    });

    this.statusFilterOptions = [
      { value: 'ALL', label: 'Todos los estados' },
      ...sortedStatuses.map((statusItem) => ({
        value: statusItem.code,
        label: statusItem.name || this.toTitleLabel(statusItem.code)
      }))
    ];

    const sortedPriorities = [...this.priorities].sort((a, b) => {
      const byOrder = Number(a.sort_order || 0) - Number(b.sort_order || 0);
      if (byOrder !== 0) return byOrder;
      return (a.name || '').localeCompare(b.name || '', 'es', { sensitivity: 'base' });
    });

    this.priorityFilterOptions = [
      { value: 'ALL', label: 'Todas las prioridades' },
      ...sortedPriorities.map((priorityItem) => ({
        value: priorityItem.code,
        label: priorityItem.name || this.toTitleLabel(priorityItem.code)
      }))
    ];

    const roomCounts = new Map<string, { label: string; count: number }>();
    for (const order of this.maintenanceOrders) {
      const key = this.getRoomKey(order);
      const label = this.getRoomLabel(order);
      const current = roomCounts.get(key) || { label, count: 0 };
      current.count += 1;
      roomCounts.set(key, current);
    }

    const roomOptions = Array.from(roomCounts.entries())
      .map(([key, data]) => ({
        value: key,
        label: `${data.label} (${data.count})`
      }))
      .sort((a, b) => a.label.localeCompare(b.label, 'es', { numeric: true }));

    this.roomFilterOptions = [{ value: 'ALL', label: 'Todas las habitaciones' }, ...roomOptions];

    if (!this.statusFilterOptions.some((option) => option.value === this.statusFilter)) {
      this.statusFilter = 'ALL';
    }
    if (!this.priorityFilterOptions.some((option) => option.value === this.selectedPriorityFilter)) {
      this.selectedPriorityFilter = 'ALL';
    }
    if (!this.roomFilterOptions.some((option) => option.value === this.selectedRoomFilter)) {
      this.selectedRoomFilter = 'ALL';
    }
  }

  private buildGroups(orders: MaintenanceOrderI[]): MaintenanceOrderGroup[] {
    const groupsMap = new Map<string, MaintenanceOrderGroup>();

    for (const order of orders) {
      const key = this.getPriorityKey(order);
      const label = this.getPriorityLabel(order);
      const code = this.getPriorityCode(order);
      const tone = this.resolvePriorityTone(order);
      const orderValue = this.resolvePriorityOrder(code);

      if (!groupsMap.has(key)) {
        groupsMap.set(key, {
          key,
          label,
          code,
          tone,
          order: orderValue,
          items: []
        });
      }

      groupsMap.get(key)?.items.push(order);
    }

    const groups = Array.from(groupsMap.values()).sort((a, b) => {
      if (a.order !== b.order) return a.order - b.order;
      return a.label.localeCompare(b.label, 'es', { sensitivity: 'base' });
    });

    this.highlightedByGroup.clear();
    for (const group of groups) {
      const delayed = group.items.filter((order) => this.isDelayed(order));
      if (delayed.length > 0) {
        this.highlightedByGroup.set(group.key, new Set(delayed.slice(0, 2).map((order) => order.id)));
        continue;
      }

      const inProgress = group.items
        .filter((order) => this.normalizeCode(order.status) === 'ENPROCESO')
        .slice(0, 1)
        .map((order) => order.id);
      this.highlightedByGroup.set(group.key, new Set(inProgress));
    }

    return groups;
  }

  private getPriorityKey(order: MaintenanceOrderI): string {
    const normalized = this.normalizeCode(this.getPriorityCode(order));
    if (normalized) return `priority:${normalized}`;
    return 'priority:unknown';
  }

  private getPriorityCode(order: MaintenanceOrderI): string {
    const raw = String(order.priority || '').trim();
    if (raw) return raw;
    return '';
  }

  private getRoomKey(order: MaintenanceOrderI): string {
    if (typeof order.room === 'number' && order.room > 0) return `room:${order.room}`;
    if (order.room_number?.trim()) return `room-number:${order.room_number.trim()}`;
    return 'room:unknown';
  }

  private resolvePriorityTone(order: MaintenanceOrderI): MaintenancePriorityTone {
    const normalized = this.normalizeCode(this.getPriorityCode(order));
    return PRIORITY_TONES[normalized] || PRIORITY_TONES['DEFAULT'];
  }

  private resolvePriorityOrder(code: string): number {
    const normalized = this.normalizeCode(code);
    const fromCatalog = this.priorityOrderMap.get(normalized);
    if (typeof fromCatalog === 'number') return fromCatalog;
    return 999;
  }

  private resolveNextStatusCode(order: MaintenanceOrderI): string | null {
    const current = this.normalizeCode(order.status);

    if (current === 'ENPROCESO') {
      return this.findStatusCode('COMPLETADA') || this.findStatusCode('PENDIENTE') || null;
    }

    if (current === 'COMPLETADA' || current === 'CANCELADA') {
      return this.findStatusCode('PENDIENTE') || this.findStatusCode('ENPROCESO') || null;
    }

    return this.findStatusCode('ENPROCESO') || this.findStatusCode('PENDIENTE') || null;
  }

  private findStatusCode(normalizedCode: string): string | null {
    return this.statusCodeByNormalized.get(this.normalizeCode(normalizedCode)) || null;
  }

  private toTitleLabel(value: unknown): string {
    return String(value || '')
      .trim()
      .replace(/_/g, ' ')
      .toLowerCase()
      .replace(/\b\w/g, (char) => char.toUpperCase());
  }

  private normalizeCode(value: unknown): string {
    return String(value || '')
      .trim()
      .toUpperCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[^A-Z0-9]/g, '');
  }

  private normalizeSearch(value: string): string {
    return String(value || '').trim().toLowerCase();
  }

  private parseDate(value: string | null | undefined): Date | null {
    if (!value) return null;
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return null;
    return parsed;
  }

  private toDateTimeLocal(date: Date): string {
    const year = date.getFullYear();
    const month = `${date.getMonth() + 1}`.padStart(2, '0');
    const day = `${date.getDate()}`.padStart(2, '0');
    const hours = `${date.getHours()}`.padStart(2, '0');
    const minutes = `${date.getMinutes()}`.padStart(2, '0');
    return `${year}-${month}-${day}T${hours}:${minutes}`;
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
