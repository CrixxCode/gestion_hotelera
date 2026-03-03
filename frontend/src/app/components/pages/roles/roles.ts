import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RolesService, Role, UserMini } from '../../../services/roles.service';


@Component({
  selector: 'app-roles',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './roles.html',
  styleUrls: ['./roles.css'],
})
export class RolesComponent implements OnInit {
  roles: Role[] = [];
  selectedRole: Role | null = null;

  assignedUsers: UserMini[] = [];
  catalogUsers: UserMini[] = [];
  q = '';

  roleFilter = '';

  selectedUserIds = new Set<string>();

  showRoleModal = false;
  roleForm: Partial<Role> = { name: '', slug: '', description: '' };
  isEditing = false;

  loading = false;
  loadingUsers = false;

  // Cache simple para mostrar conteo de usuarios por rol en la lista
  roleUsersCount: Record<string, number> = {};

  constructor(private rolesSvc: RolesService) {}

  ngOnInit(): void {
    this.loadRoles();
  }

  trackById(_: number, item: any) {
    return item?.id;
  }

  filteredRoles(): Role[] {
    const f = (this.roleFilter || '').trim().toLowerCase();
    if (!f) return this.roles;
    return this.roles.filter(r =>
      (r.name || '').toLowerCase().includes(f) ||
      (r.slug || '').toLowerCase().includes(f)
    );
  }

  loadRoles(): void {
    this.loading = true;
    this.rolesSvc.listRoles().subscribe({
      next: (data) => {
        this.roles = Array.isArray(data) ? data : [];
        this.loading = false;

        // Pre-cargar conteos (ligero): 1 request por rol solo si quieres
        // Para no saturar, lo hacemos solo cuando son pocos roles
        this.roleUsersCount = {};
        if (this.roles.length <= 20) {
          for (const r of this.roles) {
            this.rolesSvc.roleUsers(r.id).subscribe({
              next: (users) => (this.roleUsersCount[r.id] = (users || []).length),
              error: () => (this.roleUsersCount[r.id] = 0),
            });
          }
        }
      },
      error: () => {
        this.roles = [];
        this.loading = false;
      },
    });
  }

  selectRole(role: Role): void {
    this.selectedRole = role;
    this.selectedUserIds.clear();
    this.loadAssignedUsers();
    this.searchUsers();
  }

  loadAssignedUsers(): void {
    if (!this.selectedRole) return;
    this.loadingUsers = true;

    this.rolesSvc.roleUsers(this.selectedRole.id).subscribe({
      next: (users) => {
        this.assignedUsers = Array.isArray(users) ? users : [];
        this.loadingUsers = false;

        // Actualiza cache conteo
        this.roleUsersCount[this.selectedRole!.id] = this.assignedUsers.length;
      },
      error: () => {
        this.assignedUsers = [];
        this.loadingUsers = false;
      },
    });
  }

  searchUsers(): void {
    this.rolesSvc.usersCatalog(this.q).subscribe({
      next: (users) => (this.catalogUsers = Array.isArray(users) ? users : []),
      error: () => (this.catalogUsers = []),
    });
  }

  toggleUserSelection(id: string): void {
    if (this.selectedUserIds.has(id)) this.selectedUserIds.delete(id);
    else this.selectedUserIds.add(id);
  }

  assignSelected(): void {
    if (!this.selectedRole) return;
    const ids = Array.from(this.selectedUserIds);
    if (!ids.length) return;

    this.rolesSvc.assignUsers(this.selectedRole.id, ids).subscribe({
      next: () => {
        this.selectedUserIds.clear();
        this.loadAssignedUsers();
      },
    });
  }

  removeUser(userId: string): void {
    if (!this.selectedRole) return;

    this.rolesSvc.removeUsers(this.selectedRole.id, [userId]).subscribe({
      next: () => this.loadAssignedUsers(),
    });
  }

  openCreateRole(): void {
    this.isEditing = false;
    this.roleForm = { name: '', slug: '', description: '' };
    this.showRoleModal = true;
  }

  openEditRole(): void {
    if (!this.selectedRole) return;
    this.isEditing = true;
    this.roleForm = { ...this.selectedRole };
    this.showRoleModal = true;
  }

  saveRole(): void {
    const payload = {
      name: (this.roleForm.name || '').trim(),
      slug: (this.roleForm.slug || '').trim(),
      description: (this.roleForm.description || '').trim(),
    };

    if (!payload.name || !payload.slug) return;

    if (this.isEditing && this.selectedRole) {
      this.rolesSvc.updateRole(this.selectedRole.id, payload).subscribe({
        next: (updated) => {
          this.showRoleModal = false;
          this.loadRoles();
          this.selectedRole = updated;
        },
      });
    } else {
      this.rolesSvc.createRole(payload).subscribe({
        next: (created) => {
          this.showRoleModal = false;
          this.loadRoles();
          this.selectRole(created);
        },
      });
    }
  }

  deleteSelectedRole(): void {
    if (!this.selectedRole) return;
    const id = this.selectedRole.id;

    this.rolesSvc.deleteRole(id).subscribe({
      next: () => {
        this.selectedRole = null;
        this.assignedUsers = [];
        this.catalogUsers = [];
        this.selectedUserIds.clear();
        delete this.roleUsersCount[id];
        this.loadRoles();
      },
    });
  }

  fullName(u: UserMini): string {
    return `${u.first_name || ''} ${u.last_name || ''}`.trim() || u.username;
  }
}