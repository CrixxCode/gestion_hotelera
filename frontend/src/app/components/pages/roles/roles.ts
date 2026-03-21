import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  ResourcePermission,
  Role,
  RolesService,
} from '../../../services/roles.service';
import { catchError, forkJoin, map, Observable, of, switchMap } from 'rxjs';

type ToastKind = 'success' | 'danger' | 'info';
type StatusFilter = 'all' | 'with_permissions' | 'without_permissions';
type PanelMode = 'view' | 'form';

interface RoleFormModel {
  name: string;
  slug: string;
  description: string;
}

interface PermissionGroup {
  key: string;
  title: string;
  items: ResourcePermission[];
}

@Component({
  selector: 'app-roles',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './roles.html',
  styleUrls: ['./roles.css'],
})
export class RolesComponent implements OnInit {
  roles: Role[] = [];
  loadingRoles = false;
  loadingUsersMeta = false;
  loadingPermissionsCatalog = false;

  rolesQuery = '';
  statusFilter: StatusFilter = 'all';

  userCountByRole: Record<string, number> = {};
  roleOrderById: Record<string, number> = {};

  permissionsCatalog: ResourcePermission[] = [];

  showSidePanel = false;
  panelMode: PanelMode = 'view';
  isEditing = false;
  viewRole: Role | null = null;
  editingRole: Role | null = null;

  roleForm: RoleFormModel = this.emptyRoleForm();
  selectedPermissionIds = new Set<string>();

  readonly colorPalette: string[] = [
    '#ef4444',
    '#3b82f6',
    '#22c55e',
    '#a855f7',
    '#f59e0b',
    '#64748b',
    '#ec4899',
    '#06b6d4',
  ];
  selectedColor = this.colorPalette[1];
  roleColorOverrides: Record<string, string> = {};

  showDeleteConfirm = false;
  roleToDelete: Role | null = null;

  toastVisible = false;
  toastText = '';
  toastKind: ToastKind = 'info';
  private toastTimer?: ReturnType<typeof setTimeout>;

  constructor(private rolesSvc: RolesService) {}

  ngOnInit(): void {
    this.loadPermissionsCatalog();
    this.loadRoles();
  }

  trackById(_: number, item: { id: string } | null | undefined): string | undefined {
    return item?.id;
  }

  filteredRoles(): Role[] {
    const query = this.rolesQuery.trim().toLowerCase();
    return this.roles.filter((role) => {
      const matchesQuery =
        !query ||
        role.name.toLowerCase().includes(query) ||
        role.slug.toLowerCase().includes(query) ||
        (role.description || '').toLowerCase().includes(query);

      if (!matchesQuery) return false;

      if (this.statusFilter === 'with_permissions') {
        return this.permissionCount(role) > 0;
      }
      if (this.statusFilter === 'without_permissions') {
        return this.permissionCount(role) === 0;
      }
      return true;
    });
  }

  totalRoles(): number {
    return this.roles.length;
  }

  activeRoles(): number {
    return this.roles.filter((role) => this.permissionCount(role) > 0).length;
  }

  totalAssignedUsers(): number {
    return Object.values(this.userCountByRole).reduce((acc, value) => acc + value, 0);
  }

  totalPermissionsAvailable(): number {
    return this.permissionsCatalog.length;
  }

  roleUsersCount(roleId: string): number {
    return this.userCountByRole[roleId] ?? 0;
  }

  permissionCount(role: Role): number {
    return (role.resources || []).length;
  }

  isRoleActive(role: Role): boolean {
    return this.permissionCount(role) > 0;
  }

  roleCode(roleId: string): string {
    const order = this.roleOrderById[roleId] ?? 0;
    return `#${String(order).padStart(4, '0')}`;
  }

  roleColor(roleId: string): string {
    const override = this.roleColorOverrides[roleId];
    if (override) return override;
    return this.colorPalette[this.hashString(roleId) % this.colorPalette.length];
  }

  panelHeaderColor(): string {
    if (this.panelMode === 'form' && this.isEditing && this.editingRole) {
      return this.selectedColor;
    }
    if (this.panelMode === 'form' && !this.isEditing) {
      return this.selectedColor;
    }
    if (this.viewRole) {
      return this.roleColor(this.viewRole.id);
    }
    return this.colorPalette[1];
  }

  truncate(text: string, max = 86): string {
    if (!text) return '';
    if (text.length <= max) return text;
    return `${text.slice(0, max - 3)}...`;
  }

  loadRoles(): void {
    this.loadingRoles = true;
    this.rolesSvc.listRoles().subscribe({
      next: (data) => {
        const list = Array.isArray(data) ? data.map((role) => this.normalizeRole(role)) : [];
        this.roles = list;
        this.loadingRoles = false;

        this.roleOrderById = {};
        list.forEach((role, index) => {
          this.roleOrderById[role.id] = index + 1;
        });

        if (!this.permissionsCatalog.length) {
          this.permissionsCatalog = this.permissionsFromRoles(list);
        }

        this.refreshPanelRoleReferences();
        this.loadUsersMetadata();
      },
      error: () => {
        this.roles = [];
        this.loadingRoles = false;
        this.userCountByRole = {};
        this.toast('No se pudieron cargar los roles.', 'danger');
      },
    });
  }

  refreshRoles(): void {
    this.loadRoles();
  }

  loadPermissionsCatalog(): void {
    this.loadingPermissionsCatalog = true;
    this.rolesSvc.listResources('').subscribe({
      next: (data) => {
        this.permissionsCatalog = this.sortPermissions(Array.isArray(data) ? data : []);
        this.loadingPermissionsCatalog = false;
      },
      error: () => {
        this.loadingPermissionsCatalog = false;
        if (!this.permissionsCatalog.length) {
          this.permissionsCatalog = this.permissionsFromRoles(this.roles);
        }
      },
    });
  }

  openCreateRole(): void {
    this.panelMode = 'form';
    this.isEditing = false;
    this.editingRole = null;
    this.viewRole = null;
    this.roleForm = this.emptyRoleForm();
    this.selectedPermissionIds.clear();
    this.selectedColor = this.colorPalette[1];
    this.showSidePanel = true;
  }

  openEditRole(role: Role): void {
    this.panelMode = 'form';
    this.isEditing = true;
    this.editingRole = role;
    this.viewRole = null;
    this.roleForm = {
      name: role.name,
      slug: role.slug,
      description: role.description || '',
    };
    this.selectedPermissionIds = new Set((role.resources || []).map((perm) => perm.id));
    this.selectedColor = this.roleColor(role.id);
    this.showSidePanel = true;

    this.rolesSvc.roleResources(role.id).subscribe({
      next: (resources) => {
        const safe = this.sortPermissions(Array.isArray(resources) ? resources : []);
        this.mergeRoleResources(role.id, safe);
        if (this.isEditing && this.editingRole?.id === role.id) {
          this.selectedPermissionIds = new Set(safe.map((perm) => perm.id));
        }
      },
      error: () => {
        this.toast('No se pudieron cargar los permisos del rol.', 'danger');
      },
    });
  }

  openViewRole(role: Role): void {
    this.panelMode = 'view';
    this.viewRole = role;
    this.isEditing = false;
    this.editingRole = null;
    this.showSidePanel = true;

    this.refreshRoleUsersCount(role.id);
    this.rolesSvc.roleResources(role.id).subscribe({
      next: (resources) => {
        const safe = this.sortPermissions(Array.isArray(resources) ? resources : []);
        this.mergeRoleResources(role.id, safe);
      },
      error: () => {
        this.toast('No se pudieron actualizar los permisos del rol.', 'danger');
      },
    });
  }

  closeSidePanel(): void {
    this.showSidePanel = false;
  }

  askDeleteRole(role: Role): void {
    this.roleToDelete = role;
    this.showDeleteConfirm = true;
  }

  deleteRoleConfirmed(): void {
    if (!this.roleToDelete) return;
    const deletingId = this.roleToDelete.id;

    this.rolesSvc.deleteRole(deletingId).subscribe({
      next: () => {
        this.showDeleteConfirm = false;
        this.roleToDelete = null;

        if (this.viewRole?.id === deletingId || this.editingRole?.id === deletingId) {
          this.showSidePanel = false;
          this.viewRole = null;
          this.editingRole = null;
        }

        this.toast('Rol eliminado.', 'success');
        this.loadRoles();
      },
      error: () => {
        this.toast('No se pudo eliminar el rol.', 'danger');
      },
    });
  }

  saveRole(): void {
    const payload = {
      name: this.roleForm.name.trim(),
      slug: this.roleForm.slug.trim(),
      description: this.roleForm.description.trim(),
    };

    if (!payload.name || !payload.slug) {
      this.toast('Nombre y slug son obligatorios.', 'danger');
      return;
    }

    if (this.isEditing && this.editingRole) {
      const roleId = this.editingRole.id;
      const currentPermissionIds = (this.editingRole.resources || []).map((perm) => perm.id);
      const selectedIds = Array.from(this.selectedPermissionIds);

      this.rolesSvc.updateRole(roleId, payload).pipe(
        switchMap((updated) =>
          this.syncRolePermissions(roleId, currentPermissionIds, selectedIds).pipe(map(() => updated))
        )
      ).subscribe({
        next: () => {
          this.roleColorOverrides[roleId] = this.selectedColor;
          this.showSidePanel = false;
          this.toast('Rol actualizado.', 'success');
          this.loadRoles();
        },
        error: () => {
          this.toast('No se pudo actualizar el rol.', 'danger');
        },
      });
      return;
    }

    const selectedIds = Array.from(this.selectedPermissionIds);
    this.rolesSvc.createRole(payload).pipe(
      switchMap((created) =>
        this.syncRolePermissions(created.id, [], selectedIds).pipe(map(() => created))
      )
    ).subscribe({
      next: (created) => {
        this.roleColorOverrides[created.id] = this.selectedColor;
        this.showSidePanel = false;
        this.toast('Rol creado.', 'success');
        this.loadRoles();
      },
      error: () => {
        this.toast('No se pudo crear el rol.', 'danger');
      },
    });
  }

  exportRolesCsv(): void {
    const rows = this.filteredRoles();
    if (!rows.length) {
      this.toast('No hay datos para exportar.', 'info');
      return;
    }

    const header = ['Codigo', 'Rol', 'Slug', 'Descripcion', 'Usuarios', 'Permisos', 'Estado', 'Creado'];
    const lines = rows.map((role) =>
      [
        this.roleCode(role.id),
        role.name,
        role.slug,
        role.description || '',
        String(this.roleUsersCount(role.id)),
        String(this.permissionCount(role)),
        this.isRoleActive(role) ? 'Activo' : 'Inactivo',
        'N/D',
      ].map((field) => this.escapeCsv(field)).join(',')
    );

    const csv = [header.join(','), ...lines].join('\n');
    const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `roles-permisos-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  setRoleColor(color: string): void {
    this.selectedColor = color;
  }

  isPermissionSelected(permissionId: string): boolean {
    return this.selectedPermissionIds.has(permissionId);
  }

  togglePermission(permissionId: string): void {
    if (this.selectedPermissionIds.has(permissionId)) {
      this.selectedPermissionIds.delete(permissionId);
    } else {
      this.selectedPermissionIds.add(permissionId);
    }
  }

  toggleGroupSelection(group: PermissionGroup): void {
    const isAllSelected = this.isGroupChecked(group);
    if (isAllSelected) {
      group.items.forEach((item) => this.selectedPermissionIds.delete(item.id));
    } else {
      group.items.forEach((item) => this.selectedPermissionIds.add(item.id));
    }
  }

  isGroupChecked(group: PermissionGroup): boolean {
    if (!group.items.length) return false;
    return group.items.every((item) => this.selectedPermissionIds.has(item.id));
  }

  isGroupIndeterminate(group: PermissionGroup): boolean {
    const selected = this.selectedCountInGroup(group);
    return selected > 0 && selected < group.items.length;
  }

  selectedCountInGroup(group: PermissionGroup): number {
    return group.items.filter((item) => this.selectedPermissionIds.has(item.id)).length;
  }

  catalogPermissionGroups(): PermissionGroup[] {
    return this.groupPermissions(this.permissionsCatalog);
  }

  viewPermissionGroups(): PermissionGroup[] {
    return this.groupPermissions(this.viewRole?.resources || []);
  }

  private loadUsersMetadata(): void {
    if (!this.roles.length) {
      this.userCountByRole = {};
      return;
    }

    this.loadingUsersMeta = true;
    const requests = this.roles.map((role) =>
      this.rolesSvc.roleUsers(role.id).pipe(
        map((users) => ({
          roleId: role.id,
          count: Array.isArray(users) ? users.length : 0,
        })),
        catchError(() =>
          of({
            roleId: role.id,
            count: 0,
          })
        )
      )
    );

    forkJoin(requests).subscribe({
      next: (items) => {
        const counts: Record<string, number> = {};
        items.forEach((item) => {
          counts[item.roleId] = item.count;
        });
        this.userCountByRole = counts;
        this.loadingUsersMeta = false;
      },
      error: () => {
        this.userCountByRole = {};
        this.loadingUsersMeta = false;
      },
    });
  }

  private refreshRoleUsersCount(roleId: string): void {
    this.rolesSvc.roleUsers(roleId).subscribe({
      next: (users) => {
        this.userCountByRole = {
          ...this.userCountByRole,
          [roleId]: Array.isArray(users) ? users.length : 0,
        };
      },
      error: () => {
        // Keep previous value if request fails.
      },
    });
  }

  private syncRolePermissions(
    roleId: string,
    currentIds: string[],
    selectedIds: string[]
  ): Observable<void> {
    const current = new Set(currentIds);
    const selected = new Set(selectedIds);

    const toAssign = selectedIds.filter((id) => !current.has(id));
    const toRemove = currentIds.filter((id) => !selected.has(id));

    const requests: Observable<unknown>[] = [];

    if (toAssign.length) {
      requests.push(this.rolesSvc.assignResources(roleId, toAssign));
    }
    if (toRemove.length) {
      requests.push(this.rolesSvc.removeResources(roleId, toRemove));
    }

    if (!requests.length) {
      return of(void 0);
    }

    return forkJoin(requests).pipe(map(() => void 0));
  }

  private mergeRoleResources(roleId: string, resources: ResourcePermission[]): void {
    this.roles = this.roles.map((role) =>
      role.id === roleId ? { ...role, resources: this.sortPermissions(resources) } : role
    );

    if (this.viewRole?.id === roleId) {
      this.viewRole = { ...this.viewRole, resources: this.sortPermissions(resources) };
    }
    if (this.editingRole?.id === roleId) {
      this.editingRole = { ...this.editingRole, resources: this.sortPermissions(resources) };
    }
  }

  private refreshPanelRoleReferences(): void {
    if (this.viewRole) {
      this.viewRole = this.roles.find((role) => role.id === this.viewRole?.id) || null;
      if (!this.viewRole) this.showSidePanel = false;
    }
    if (this.editingRole) {
      this.editingRole = this.roles.find((role) => role.id === this.editingRole?.id) || null;
      if (!this.editingRole) this.showSidePanel = false;
    }
  }

  private normalizeRole(role: Role): Role {
    return {
      ...role,
      resources: this.sortPermissions(Array.isArray(role.resources) ? role.resources : []),
    };
  }

  private permissionsFromRoles(roles: Role[]): ResourcePermission[] {
    const byId = new Map<string, ResourcePermission>();
    roles.forEach((role) => {
      (role.resources || []).forEach((permission) => {
        byId.set(permission.id, permission);
      });
    });
    return this.sortPermissions(Array.from(byId.values()));
  }

  private sortPermissions(resources: ResourcePermission[]): ResourcePermission[] {
    return [...resources].sort((a, b) => {
      const orderA = a.order ?? 0;
      const orderB = b.order ?? 0;
      if (orderA !== orderB) return orderA - orderB;
      return (a.name || '').localeCompare(b.name || '', 'es');
    });
  }

  private groupPermissions(resources: ResourcePermission[]): PermissionGroup[] {
    const grouped = new Map<string, ResourcePermission[]>();
    resources.forEach((permission) => {
      const key = this.permissionGroupKey(permission.key);
      const current = grouped.get(key) || [];
      current.push(permission);
      grouped.set(key, current);
    });

    return Array.from(grouped.entries())
      .map(([key, items]) => ({
        key,
        title: this.permissionGroupTitle(key),
        items: this.sortPermissions(items),
      }))
      .sort((a, b) => this.permissionGroupSort(a.key) - this.permissionGroupSort(b.key));
  }

  private permissionGroupKey(permissionKey: string): string {
    const idx = permissionKey.indexOf('.');
    if (idx <= 0) return 'general';
    return permissionKey.slice(0, idx);
  }

  private permissionGroupTitle(groupKey: string): string {
    const known: Record<string, string> = {
      dashboard: 'Dashboard',
      users: 'Usuarios',
      clients: 'Clientes',
      roles: 'Roles',
      resources: 'Recursos',
      auth: 'Seguridad',
      general: 'General',
    };

    if (known[groupKey]) return known[groupKey];
    if (!groupKey) return 'General';
    return groupKey.charAt(0).toUpperCase() + groupKey.slice(1);
  }

  private permissionGroupSort(groupKey: string): number {
    const order: Record<string, number> = {
      dashboard: 1,
      users: 2,
      clients: 3,
      roles: 4,
      resources: 5,
      auth: 6,
      general: 99,
    };
    return order[groupKey] ?? 98;
  }

  private emptyRoleForm(): RoleFormModel {
    return {
      name: '',
      slug: '',
      description: '',
    };
  }

  private escapeCsv(value: string): string {
    const escaped = value.replace(/"/g, '""');
    return `"${escaped}"`;
  }

  private hashString(value: string): number {
    let hash = 0;
    for (let i = 0; i < value.length; i += 1) {
      hash = (hash * 31 + value.charCodeAt(i)) >>> 0;
    }
    return hash;
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
}
