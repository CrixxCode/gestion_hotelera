import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { catchError, forkJoin, map, of } from 'rxjs';
import { ResourcesService, RoleLite, Resource } from '../../../services/resources.service';

type ToastKind = 'success' | 'danger' | 'info';
type StateFilter = 'all' | 'active' | 'inactive';
type DrawerMode = 'view' | 'create' | 'edit';

interface FilterOption {
  value: string;
  label: string;
  count: number;
}

interface ResourceFormModel {
  key: string;
  name: string;
  description: string;
  link: string;
  link_backend: string;
  icon: string;
  order: number;
  is_menu: boolean;
  parent: string | null;
}

@Component({
  selector: 'app-recursos',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './recursos.html',
  styleUrls: ['./recursos.css'],
})
export class RecursosComponent implements OnInit {
  roles: RoleLite[] = [];
  resources: Resource[] = [];

  loadingRoles = false;
  loadingResources = false;
  loadingRoleUsage = false;

  searchQuery = '';
  moduleFilter = 'all';
  actionFilter = 'all';
  stateFilter: StateFilter = 'all';

  moduleOptions: FilterOption[] = [{ value: 'all', label: 'Todos los modulos', count: 0 }];
  actionOptions: FilterOption[] = [{ value: 'all', label: 'Todas las acciones', count: 0 }];

  showDrawer = false;
  drawerMode: DrawerMode = 'view';
  selectedResource: Resource | null = null;
  editingId: string | null = null;

  form: ResourceFormModel = this.emptyForm();
  formModule = '';
  formAction = '';

  showDeleteConfirm = false;
  deleteTarget: Resource | null = null;

  toastVisible = false;
  toastText = '';
  toastKind: ToastKind = 'info';
  private toastTimer?: ReturnType<typeof setTimeout>;
  private searchDebounce?: ReturnType<typeof setTimeout>;

  private readonly roleCountByResource: Record<string, number> = {};
  private readonly roleNamesByResource: Record<string, string[]> = {};

  private readonly moduleLabelMap: Record<string, string> = {
    dashboard: 'Dashboard',
    users: 'Seguridad',
    roles: 'Seguridad',
    resources: 'Seguridad',
    auth: 'Seguridad',
    reservations: 'Reservas',
    booking: 'Reservas',
    clients: 'Clientes & Huespedes',
    rooms: 'Habitaciones',
    services: 'Servicios',
    inventory: 'Inventario',
    billing: 'Facturacion',
    payments: 'Facturacion',
    reports: 'Reportes',
    config: 'Configuracion',
    settings: 'Configuracion',
    master: 'Configuracion',
  };

  private readonly actionLabelMap: Record<string, string> = {
    create: 'Crear',
    add: 'Crear',
    read: 'Ver',
    view: 'Ver',
    list: 'Ver',
    update: 'Editar',
    edit: 'Editar',
    write: 'Editar',
    delete: 'Eliminar',
    remove: 'Eliminar',
    destroy: 'Eliminar',
    reject: 'Rechazar',
    assign: 'Asignar',
    change: 'Cambiar',
  };

  constructor(private svc: ResourcesService) {}

  ngOnInit(): void {
    this.loadRoles();
    this.loadResources('');
  }

  trackById(_: number, item: { id: string } | null | undefined): string | undefined {
    return item?.id;
  }

  onSearchInput(): void {
    if (this.searchDebounce) clearTimeout(this.searchDebounce);
    this.searchDebounce = setTimeout(() => {
      this.loadResources(this.searchQuery);
    }, 260);
  }

  clearSearch(): void {
    if (!this.searchQuery) return;
    this.searchQuery = '';
    this.loadResources('');
  }

  loadRoles(): void {
    this.loadingRoles = true;
    this.svc.listRoles().subscribe({
      next: (data) => {
        this.roles = Array.isArray(data) ? data : [];
        this.loadingRoles = false;
        this.refreshRoleUsage();
      },
      error: () => {
        this.roles = [];
        this.loadingRoles = false;
        this.toast('No se pudieron cargar los roles.', 'danger');
      },
    });
  }

  loadResources(query: string): void {
    this.loadingResources = true;
    this.svc.listResources(query || '').subscribe({
      next: (data) => {
        this.resources = this.sortResources(Array.isArray(data) ? data : []);
        this.loadingResources = false;
        this.rebuildFilterOptions();
        this.refreshSelectionReference();
      },
      error: () => {
        this.resources = [];
        this.loadingResources = false;
        this.rebuildFilterOptions();
        this.toast('No se pudieron cargar los recursos.', 'danger');
      },
    });
  }

  filteredResources(): Resource[] {
    const moduleFilter = this.moduleFilter;
    const actionFilter = this.actionFilter;
    const stateFilter = this.stateFilter;

    return this.resources.filter((resource) => {
      const moduleKey = this.resourceModuleKey(resource);
      const actionKey = this.resourceActionKey(resource);
      const isActive = !!resource.is_menu;

      if (moduleFilter !== 'all' && moduleKey !== moduleFilter) return false;
      if (actionFilter !== 'all' && actionKey !== actionFilter) return false;
      if (stateFilter === 'active' && !isActive) return false;
      if (stateFilter === 'inactive' && isActive) return false;
      return true;
    });
  }

  totalResources(): number {
    return this.resources.length;
  }

  activeResources(): number {
    return this.resources.filter((resource) => !!resource.is_menu).length;
  }

  inactiveResources(): number {
    return this.totalResources() - this.activeResources();
  }

  modulesCount(): number {
    return new Set(this.resources.map((resource) => this.resourceModuleKey(resource))).size;
  }

  activePercent(): number {
    if (!this.totalResources()) return 0;
    return Math.round((this.activeResources() / this.totalResources()) * 100);
  }

  resourceRolesCount(resourceId: string): number {
    return this.roleCountByResource[resourceId] ?? 0;
  }

  resourceRolesNames(resourceId: string): string {
    const names = this.roleNamesByResource[resourceId] || [];
    if (!names.length) return 'Sin roles asignados';
    return names.join(', ');
  }

  resourceModuleLabel(resource: Resource): string {
    return this.moduleLabel(this.resourceModuleKey(resource));
  }

  resourceActionLabel(resource: Resource): string {
    return this.actionLabel(this.resourceActionKey(resource));
  }

  resourceStateLabel(resource: Resource): string {
    return resource.is_menu ? 'Activo' : 'Inactivo';
  }

  actionTone(resource: Resource): string {
    const action = this.resourceActionKey(resource);
    if (['create', 'add', 'assign'].includes(action)) return 'create';
    if (['read', 'view', 'list'].includes(action)) return 'view';
    if (['update', 'edit', 'write', 'change'].includes(action)) return 'edit';
    if (['delete', 'remove', 'destroy'].includes(action)) return 'danger';
    return 'neutral';
  }

  resourceInitial(resource: Resource): string {
    const label = this.resourceModuleLabel(resource);
    return label ? label.charAt(0).toUpperCase() : 'R';
  }

  resourceAccent(resource: Resource): string {
    const key = this.resourceModuleKey(resource);
    const palette: Record<string, string> = {
      dashboard: '#2563eb',
      users: '#ef4444',
      roles: '#ef4444',
      resources: '#ef4444',
      auth: '#ef4444',
      reservations: '#8b5cf6',
      booking: '#8b5cf6',
      clients: '#10b981',
      rooms: '#f59e0b',
      services: '#0ea5e9',
      inventory: '#6366f1',
      billing: '#14b8a6',
      payments: '#14b8a6',
      reports: '#7c3aed',
      config: '#64748b',
      settings: '#64748b',
      master: '#64748b',
    };
    return palette[key] || '#334155';
  }

  resourceIconClass(resource: Resource): string {
    const icon = (resource.icon || '').trim();
    return icon || 'fa-solid fa-shield-halved';
  }

  moduleIconClass(resource: Resource): string {
    const parent = this.findModuleParentResource(resource);
    const parentIcon = (parent?.icon || '').trim();
    if (parentIcon) return parentIcon;

    const ownIcon = (resource.icon || '').trim();
    if (ownIcon) return ownIcon;

    return 'fa-solid fa-shield-halved';
  }

  openCreate(): void {
    this.drawerMode = 'create';
    this.selectedResource = null;
    this.editingId = null;
    this.form = this.emptyForm();
    this.formModule = '';
    this.formAction = '';
    this.showDrawer = true;
  }

  openView(resource: Resource): void {
    this.drawerMode = 'view';
    this.selectedResource = resource;
    this.editingId = null;
    this.showDrawer = true;
  }

  openEdit(resource: Resource): void {
    this.drawerMode = 'edit';
    this.selectedResource = resource;
    this.editingId = resource.id;
    this.form = {
      key: resource.key || '',
      name: resource.name || '',
      description: resource.description || '',
      link: resource.link || '',
      link_backend: resource.link_backend || '',
      icon: resource.icon || '',
      order: resource.order ?? 0,
      is_menu: resource.is_menu ?? true,
      parent: resource.parent ?? null,
    };
    const parts = this.parseKeyParts(this.form.key);
    this.formModule = parts.module;
    this.formAction = parts.action;
    this.showDrawer = true;
  }

  closeDrawer(): void {
    this.showDrawer = false;
  }

  onFormKeyInput(): void {
    const parts = this.parseKeyParts(this.form.key);
    this.formModule = parts.module;
    this.formAction = parts.action;
  }

  onClassificationChange(): void {
    const moduleKey = this.normalizeToken(this.formModule);
    const actionKey = this.normalizeToken(this.formAction);
    if (!moduleKey && !actionKey) return;
    if (moduleKey && actionKey) {
      this.form.key = `${moduleKey}.${actionKey}`;
      return;
    }
    this.form.key = moduleKey || actionKey;
  }

  saveResource(): void {
    const payload: Partial<Resource> = {
      key: this.normalizeToken(this.form.key),
      name: (this.form.name || '').trim(),
      description: (this.form.description || '').trim(),
      link: (this.form.link || '').trim(),
      link_backend: (this.form.link_backend || '').trim(),
      icon: (this.form.icon || '').trim(),
      order: this.safeNumber(this.form.order),
      is_menu: !!this.form.is_menu,
      parent: this.form.parent || null,
    };

    if (!payload.key || !payload.name) {
      this.toast('Codigo y nombre son obligatorios.', 'danger');
      return;
    }

    if (this.drawerMode === 'edit' && this.editingId) {
      this.svc.updateResource(this.editingId, payload).subscribe({
        next: () => {
          this.toast('Recurso actualizado.', 'success');
          this.showDrawer = false;
          this.loadResources(this.searchQuery);
        },
        error: (error) => this.toast(this.extractErrorMessage(error, 'No se pudo actualizar el recurso.'), 'danger'),
      });
      return;
    }

    this.svc.createResource(payload).subscribe({
      next: () => {
        this.toast('Recurso creado.', 'success');
        this.showDrawer = false;
        this.loadResources(this.searchQuery);
      },
      error: (error) => this.toast(this.extractErrorMessage(error, 'No se pudo crear el recurso.'), 'danger'),
    });
  }

  askDelete(resource: Resource): void {
    this.deleteTarget = resource;
    this.showDeleteConfirm = true;
  }

  confirmDelete(): void {
    if (!this.deleteTarget) return;
    const deleting = this.deleteTarget;

    this.svc.deleteResource(deleting.id).subscribe({
      next: () => {
        this.toast('Recurso eliminado.', 'success');
        this.showDeleteConfirm = false;
        this.deleteTarget = null;
        if (this.selectedResource?.id === deleting.id) {
          this.showDrawer = false;
          this.selectedResource = null;
          this.editingId = null;
        }
        this.loadResources(this.searchQuery);
        this.refreshRoleUsage();
      },
      error: () => this.toast('No se pudo eliminar el recurso.', 'danger'),
    });
  }

  exportResourcesCsv(): void {
    const rows = this.filteredResources();
    if (!rows.length) {
      this.toast('No hay datos para exportar.', 'info');
      return;
    }

    const header = ['Recurso', 'Codigo', 'Modulo', 'Accion', 'Roles', 'Estado'];
    const lines = rows.map((resource) =>
      [
        resource.name || '',
        resource.key || '',
        this.resourceModuleLabel(resource),
        this.resourceActionLabel(resource),
        String(this.resourceRolesCount(resource.id)),
        this.resourceStateLabel(resource),
      ].map((field) => this.escapeCsv(field)).join(',')
    );

    const csv = [header.join(','), ...lines].join('\n');
    const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `recursos-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  copyText(text: string): void {
    const safe = (text || '').trim();
    if (!safe) return;

    if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(safe).then(
        () => this.toast('Codigo copiado.', 'success'),
        () => this.toast('No se pudo copiar el codigo.', 'danger')
      );
      return;
    }

    const helper = document.createElement('textarea');
    helper.value = safe;
    helper.style.position = 'fixed';
    helper.style.opacity = '0';
    document.body.appendChild(helper);
    helper.select();
    const copied = document.execCommand('copy');
    document.body.removeChild(helper);
    if (copied) this.toast('Codigo copiado.', 'success');
    else this.toast('No se pudo copiar el codigo.', 'danger');
  }

  parentOptions(): Resource[] {
    if (this.drawerMode !== 'edit' || !this.editingId) return this.resources;
    return this.resources.filter((resource) => resource.id !== this.editingId);
  }

  formModuleChoices(): string[] {
    const known = this.moduleOptions.filter((item) => item.value !== 'all').map((item) => item.value);
    const extra = ['dashboard', 'users', 'clients', 'roles', 'resources', 'auth', 'rooms', 'reservations'];
    const set = new Set<string>([...known, ...extra]);
    if (this.formModule) set.add(this.formModule);
    return Array.from(set).sort((a, b) => this.moduleLabel(a).localeCompare(this.moduleLabel(b), 'es'));
  }

  formActionChoices(): string[] {
    const known = this.actionOptions.filter((item) => item.value !== 'all').map((item) => item.value);
    const extra = ['read', 'view', 'create', 'write', 'update', 'delete', 'assign', 'remove', 'change'];
    const set = new Set<string>([...known, ...extra]);
    if (this.formAction) set.add(this.formAction);
    return Array.from(set).sort((a, b) => this.actionLabel(a).localeCompare(this.actionLabel(b), 'es'));
  }

  private refreshRoleUsage(): void {
    if (!this.roles.length) {
      this.clearRoleUsageMaps();
      return;
    }

    this.loadingRoleUsage = true;

    const requests = this.roles.map((role) =>
      this.svc.roleResources(role.id).pipe(
        map((resources) => ({
          role,
          resources: Array.isArray(resources) ? resources : [],
        })),
        catchError(() =>
          of({
            role,
            resources: [] as Resource[],
          })
        )
      )
    );

    forkJoin(requests).subscribe({
      next: (items) => {
        this.clearRoleUsageMaps();

        items.forEach((item) => {
          item.resources.forEach((resource) => {
            const currentCount = this.roleCountByResource[resource.id] ?? 0;
            this.roleCountByResource[resource.id] = currentCount + 1;

            const currentNames = this.roleNamesByResource[resource.id] || [];
            if (!currentNames.includes(item.role.name)) {
              this.roleNamesByResource[resource.id] = [...currentNames, item.role.name].sort((a, b) =>
                a.localeCompare(b, 'es')
              );
            }
          });
        });

        this.loadingRoleUsage = false;
      },
      error: () => {
        this.loadingRoleUsage = false;
      },
    });
  }

  private rebuildFilterOptions(): void {
    const moduleCounter = new Map<string, number>();
    const actionCounter = new Map<string, number>();

    this.resources.forEach((resource) => {
      const moduleKey = this.resourceModuleKey(resource);
      const actionKey = this.resourceActionKey(resource);
      moduleCounter.set(moduleKey, (moduleCounter.get(moduleKey) ?? 0) + 1);
      actionCounter.set(actionKey, (actionCounter.get(actionKey) ?? 0) + 1);
    });

    this.moduleOptions = [
      { value: 'all', label: 'Todos los modulos', count: this.resources.length },
      ...Array.from(moduleCounter.entries())
        .map(([value, count]) => ({ value, count, label: this.moduleLabel(value) }))
        .sort((a, b) => a.label.localeCompare(b.label, 'es')),
    ];

    this.actionOptions = [
      { value: 'all', label: 'Todas las acciones', count: this.resources.length },
      ...Array.from(actionCounter.entries())
        .map(([value, count]) => ({ value, count, label: this.actionLabel(value) }))
        .sort((a, b) => a.label.localeCompare(b.label, 'es')),
    ];

    const hasModuleFilter = this.moduleOptions.some((item) => item.value === this.moduleFilter);
    if (!hasModuleFilter) this.moduleFilter = 'all';

    const hasActionFilter = this.actionOptions.some((item) => item.value === this.actionFilter);
    if (!hasActionFilter) this.actionFilter = 'all';
  }

  private resourceModuleKey(resource: Resource): string {
    const parts = this.parseKeyParts(resource.key || '');
    return parts.module || 'general';
  }

  private resourceActionKey(resource: Resource): string {
    const parts = this.parseKeyParts(resource.key || '');
    return parts.action || 'general';
  }

  private findModuleParentResource(resource: Resource): Resource | null {
    if (resource.parent) {
      const directParent = this.resources.find((candidate) => candidate.id === resource.parent) || null;
      if (directParent) return directParent;
    }

    const familyKey = this.normalizeFamilyKey(this.resourceModuleKey(resource));
    if (!familyKey) return null;

    const candidates = this.resources
      .filter((candidate) => candidate.id !== resource.id)
      .filter((candidate) => this.normalizeFamilyKey(this.resourceModuleKey(candidate)) === familyKey);

    if (!candidates.length) return null;

    const sorted = [...candidates].sort((a, b) => {
      const scoreA = this.moduleParentScore(a);
      const scoreB = this.moduleParentScore(b);
      if (scoreA !== scoreB) return scoreA - scoreB;

      const orderA = a.order ?? 0;
      const orderB = b.order ?? 0;
      if (orderA !== orderB) return orderA - orderB;

      return (a.name || '').localeCompare(b.name || '', 'es');
    });

    return sorted[0] || null;
  }

  private moduleParentScore(resource: Resource): number {
    let score = 0;
    if (!resource.is_menu) score += 40;

    const action = this.resourceActionKey(resource);
    if (['read', 'view', 'list'].includes(action)) score -= 20;
    if (['create', 'add'].includes(action)) score += 8;
    if (['write', 'update', 'edit'].includes(action)) score += 10;
    if (['delete', 'remove', 'destroy'].includes(action)) score += 12;

    if (!(resource.icon || '').trim()) score += 15;

    return score;
  }

  private normalizeFamilyKey(value: string): string {
    return (value || '')
      .trim()
      .toLowerCase()
      .replace(/[-\s]+/g, '_');
  }

  private parseKeyParts(key: string): { module: string; action: string } {
    const safe = (key || '').trim().toLowerCase();
    if (!safe) return { module: '', action: '' };
    const parts = safe.split('.').filter((part) => !!part);
    if (!parts.length) return { module: '', action: '' };
    if (parts.length === 1) return { module: parts[0], action: '' };
    return { module: parts[0], action: parts[parts.length - 1] };
  }

  private moduleLabel(moduleKey: string): string {
    const key = (moduleKey || '').toLowerCase();
    if (this.moduleLabelMap[key]) return this.moduleLabelMap[key];
    if (!key) return 'General';
    return key.charAt(0).toUpperCase() + key.slice(1);
  }

  private actionLabel(actionKey: string): string {
    const key = (actionKey || '').toLowerCase();
    if (this.actionLabelMap[key]) return this.actionLabelMap[key];
    if (!key) return 'General';
    return key.charAt(0).toUpperCase() + key.slice(1);
  }

  private emptyForm(): ResourceFormModel {
    return {
      key: '',
      name: '',
      description: '',
      link: '',
      link_backend: '',
      icon: '',
      order: 0,
      is_menu: true,
      parent: null,
    };
  }

  private safeNumber(value: unknown): number {
    const numeric = Number(value);
    if (!Number.isFinite(numeric) || numeric < 0) return 0;
    return Math.floor(numeric);
  }

  private normalizeToken(value: string): string {
    return (value || '').trim().toLowerCase().replace(/\s+/g, '_');
  }

  private sortResources(resources: Resource[]): Resource[] {
    return [...resources].sort((a, b) => {
      const orderA = a.order ?? 0;
      const orderB = b.order ?? 0;
      if (orderA !== orderB) return orderA - orderB;
      return (a.name || '').localeCompare(b.name || '', 'es');
    });
  }

  private refreshSelectionReference(): void {
    if (this.selectedResource) {
      this.selectedResource = this.resources.find((item) => item.id === this.selectedResource?.id) || null;
      if (!this.selectedResource && this.drawerMode === 'view') {
        this.showDrawer = false;
      }
    }
  }

  private clearRoleUsageMaps(): void {
    Object.keys(this.roleCountByResource).forEach((key) => delete this.roleCountByResource[key]);
    Object.keys(this.roleNamesByResource).forEach((key) => delete this.roleNamesByResource[key]);
  }

  private escapeCsv(value: string): string {
    const escaped = (value || '').replace(/"/g, '""');
    return `"${escaped}"`;
  }

  private toast(message: string, kind: ToastKind = 'info'): void {
    this.toastText = message;
    this.toastKind = kind;
    this.toastVisible = true;
    if (this.toastTimer) clearTimeout(this.toastTimer);
    this.toastTimer = setTimeout(() => {
      this.toastVisible = false;
    }, 2500);
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
