import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RolesService, Role, UserMini } from '../../../services/roles.service';

type ToastKind = 'success' | 'danger' | 'info';

@Component({
  selector: 'app-roles',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './roles.html',
  styleUrls: ['./roles.css'],
})
export class RolesComponent implements OnInit {
  // Data
  roles: Role[] = [];
  selectedRole: Role | null = null;

  assignedUsers: UserMini[] = [];
  catalogUsers: UserMini[] = []; // resultados del backend

  // UI state
  loadingRoles = false;
  loadingAssigned = false;
  loadingCatalog = false;

  rolesQuery = '';
  qAvailable = '';
  qAssigned = '';

  // Transfer selections
  selectedAvailableIds = new Set<string>();
  selectedAssignedIds = new Set<string>();

  // Drawer create/edit role
  showRoleDrawer = false;
  isEditing = false;
  roleForm: Partial<Role> = { name: '', slug: '', description: '' };

  // Confirm delete
  showDeleteConfirm = false;

  // Toast
  toastVisible = false;
  toastText = '';
  toastKind: ToastKind = 'info';
  private toastTimer?: any;

  // Debounce timers
  private catalogDebounce?: any;

  constructor(private rolesSvc: RolesService) {}

  ngOnInit(): void {
    this.loadRoles();
  }

  trackById(_: number, item: any) {
    return item?.id;
  }

  private toast(msg: string, kind: ToastKind = 'info') {
    this.toastText = msg;
    this.toastKind = kind;
    this.toastVisible = true;
    if (this.toastTimer) clearTimeout(this.toastTimer);
    this.toastTimer = setTimeout(() => (this.toastVisible = false), 2400);
  }

  fullName(u: UserMini): string {
    return `${u.first_name || ''} ${u.last_name || ''}`.trim() || u.username;
  }

  // ---------- Roles ----------
  loadRoles(): void {
    this.loadingRoles = true;
    this.rolesSvc.listRoles().subscribe({
      next: (data) => {
        this.roles = Array.isArray(data) ? data : [];
        this.loadingRoles = false;

        // Si no hay rol seleccionado, preselecciona el primero
        if (!this.selectedRole && this.roles.length) {
          this.selectRole(this.roles[0]);
        }
      },
      error: () => {
        this.roles = [];
        this.loadingRoles = false;
        this.toast('No se pudieron cargar los roles.', 'danger');
      },
    });
  }

  filteredRoles(): Role[] {
    const q = (this.rolesQuery || '').trim().toLowerCase();
    if (!q) return this.roles;
    return this.roles.filter(r =>
      (r.name || '').toLowerCase().includes(q) ||
      (r.slug || '').toLowerCase().includes(q)
    );
  }

  selectRole(role: Role): void {
    this.selectedRole = role;

    // reset transfer selections
    this.selectedAvailableIds.clear();
    this.selectedAssignedIds.clear();
    this.qAvailable = '';
    this.qAssigned = '';

    // cargar asignados + precargar catálogo
    this.loadAssignedUsers();
    this.searchCatalogUsers('');
  }

  openCreateRole(): void {
    this.isEditing = false;
    this.roleForm = { name: '', slug: '', description: '' };
    this.showRoleDrawer = true;
  }

  openEditRole(): void {
    if (!this.selectedRole) return;
    this.isEditing = true;
    this.roleForm = { ...this.selectedRole };
    this.showRoleDrawer = true;
  }

  saveRole(): void {
    const payload = {
      name: (this.roleForm.name || '').trim(),
      slug: (this.roleForm.slug || '').trim(),
      description: (this.roleForm.description || '').trim(),
    };

    if (!payload.name || !payload.slug) {
      this.toast('Nombre y slug son obligatorios.', 'danger');
      return;
    }

    if (this.isEditing && this.selectedRole) {
      this.rolesSvc.updateRole(this.selectedRole.id, payload).subscribe({
        next: (updated) => {
          this.showRoleDrawer = false;
          this.toast('Rol actualizado.', 'success');
          this.loadRoles();
          this.selectedRole = updated;
        },
        error: () => this.toast('No se pudo actualizar el rol.', 'danger'),
      });
    } else {
      this.rolesSvc.createRole(payload).subscribe({
        next: (created) => {
          this.showRoleDrawer = false;
          this.toast('Rol creado.', 'success');
          this.loadRoles();
          this.selectRole(created);
        },
        error: () => this.toast('No se pudo crear el rol.', 'danger'),
      });
    }
  }

  askDeleteRole(): void {
    if (!this.selectedRole) return;
    this.showDeleteConfirm = true;
  }

  deleteRoleConfirmed(): void {
    if (!this.selectedRole) return;

    const deletingId = this.selectedRole.id;
    this.rolesSvc.deleteRole(deletingId).subscribe({
      next: () => {
        this.toast('Rol eliminado.', 'success');
        this.showDeleteConfirm = false;
        this.selectedRole = null;
        this.assignedUsers = [];
        this.catalogUsers = [];
        this.selectedAvailableIds.clear();
        this.selectedAssignedIds.clear();

        this.loadRoles();
      },
      error: () => this.toast('No se pudo eliminar el rol.', 'danger'),
    });
  }

  // ---------- Assigned users ----------
  loadAssignedUsers(): void {
    if (!this.selectedRole) return;

    this.loadingAssigned = true;
    this.rolesSvc.roleUsers(this.selectedRole.id).subscribe({
      next: (users) => {
        this.assignedUsers = Array.isArray(users) ? users : [];
        this.loadingAssigned = false;

        // limpiar selecciones inválidas
        const ids = new Set(this.assignedUsers.map(u => u.id));
        for (const id of Array.from(this.selectedAssignedIds)) {
          if (!ids.has(id)) this.selectedAssignedIds.delete(id);
        }
      },
      error: () => {
        this.assignedUsers = [];
        this.loadingAssigned = false;
        this.toast('No se pudieron cargar los usuarios asignados.', 'danger');
      },
    });
  }

  // ---------- Catalog search ----------
  onCatalogSearchInput(): void {
    if (this.catalogDebounce) clearTimeout(this.catalogDebounce);
    this.catalogDebounce = setTimeout(() => {
      this.searchCatalogUsers(this.qAvailable);
    }, 320);
  }

  searchCatalogUsers(q: string): void {
    this.loadingCatalog = true;
    this.rolesSvc.usersCatalog(q || '').subscribe({
      next: (users) => {
        this.catalogUsers = Array.isArray(users) ? users : [];
        this.loadingCatalog = false;

        // limpiar selección invalida en disponibles
        const availableIds = new Set(this.availableUsers().map(u => u.id));
        for (const id of Array.from(this.selectedAvailableIds)) {
          if (!availableIds.has(id)) this.selectedAvailableIds.delete(id);
        }
      },
      error: () => {
        this.catalogUsers = [];
        this.loadingCatalog = false;
        this.toast('No se pudieron cargar usuarios del catálogo.', 'danger');
      },
    });
  }

  get assignedIds(): Set<string> {
    return new Set(this.assignedUsers.map(u => u.id));
  }

  availableUsers(): UserMini[] {
    const assigned = this.assignedIds;
    let list = (this.catalogUsers || []).filter(u => !assigned.has(u.id));

    // filtro local adicional
    const f = (this.qAvailable || '').trim().toLowerCase();
    if (f) {
      list = list.filter(u =>
        (u.username || '').toLowerCase().includes(f) ||
        (u.email || '').toLowerCase().includes(f) ||
        (u.first_name || '').toLowerCase().includes(f) ||
        (u.last_name || '').toLowerCase().includes(f)
      );
    }
    return list;
  }

  assignedUsersFiltered(): UserMini[] {
    let list = [...(this.assignedUsers || [])];
    const f = (this.qAssigned || '').trim().toLowerCase();
    if (f) {
      list = list.filter(u =>
        (u.username || '').toLowerCase().includes(f) ||
        (u.email || '').toLowerCase().includes(f) ||
        (u.first_name || '').toLowerCase().includes(f) ||
        (u.last_name || '').toLowerCase().includes(f)
      );
    }
    return list;
  }

  // ---------- Transfer actions ----------
  toggleAvailable(id: string): void {
    if (this.selectedAvailableIds.has(id)) this.selectedAvailableIds.delete(id);
    else this.selectedAvailableIds.add(id);
  }

  toggleAssigned(id: string): void {
    if (this.selectedAssignedIds.has(id)) this.selectedAssignedIds.delete(id);
    else this.selectedAssignedIds.add(id);
  }

  selectAllAvailable(): void {
    for (const u of this.availableUsers()) this.selectedAvailableIds.add(u.id);
  }

  clearAvailableSelection(): void {
    this.selectedAvailableIds.clear();
  }

  selectAllAssigned(): void {
    for (const u of this.assignedUsersFiltered()) this.selectedAssignedIds.add(u.id);
  }

  clearAssignedSelection(): void {
    this.selectedAssignedIds.clear();
  }

  assignSelected(): void {
    if (!this.selectedRole) return;
    const ids = Array.from(this.selectedAvailableIds);
    if (!ids.length) return;

    this.rolesSvc.assignUsers(this.selectedRole.id, ids).subscribe({
      next: () => {
        this.toast('Usuarios asignados.', 'success');
        this.selectedAvailableIds.clear();
        this.loadAssignedUsers();
        this.searchCatalogUsers(this.qAvailable);
      },
      error: () => this.toast('No se pudo asignar usuarios.', 'danger'),
    });
  }

  removeSelected(): void {
    if (!this.selectedRole) return;
    const ids = Array.from(this.selectedAssignedIds);
    if (!ids.length) return;

    this.rolesSvc.removeUsers(this.selectedRole.id, ids).subscribe({
      next: () => {
        this.toast('Usuarios removidos del rol.', 'success');
        this.selectedAssignedIds.clear();
        this.loadAssignedUsers();
        this.searchCatalogUsers(this.qAvailable);
      },
      error: () => this.toast('No se pudo remover usuarios.', 'danger'),
    });
  }
}