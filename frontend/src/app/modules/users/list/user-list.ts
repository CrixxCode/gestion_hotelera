import { Component, OnInit } from '@angular/core';
import { CommonModule, NgClass } from '@angular/common';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { UserService } from '../../../services/user';
import { UserI } from '../user-model';

// PrimeNG
import { ToastModule } from 'primeng/toast';
import { ConfirmDialogModule } from 'primeng/confirmdialog';
import { DialogModule } from 'primeng/dialog';
import { MessageService, ConfirmationService } from 'primeng/api';

// Child components
import { UserRegister } from '../register/register';
import { UserProfile } from '../profile/profile';
import { UserUpdate } from '../update/update';

@Component({
  selector: 'app-user-list',
  standalone: true,
  templateUrl: './user-list.html',
  styleUrls: ['./user-list.css'],
  imports: [
    CommonModule,
    FormsModule,
    ReactiveFormsModule,
    NgClass,
    ToastModule,
    ConfirmDialogModule,
    DialogModule,
    UserRegister,
    UserProfile,
    UserUpdate
  ],
  providers: [MessageService, ConfirmationService]
})
export class UserList implements OnInit {
  users: UserI[] = [];
  filteredUsers: UserI[] = [];

  loading = true;
  globalFilter = '';
  statusFilter: 'ALL' | 'ACTIVE' | 'INACTIVE' = 'ALL';
  roleFilter: 'ALL' | 'WITH_ROLE' | 'WITHOUT_ROLE' = 'ALL';

  first = 0;
  rows = 6;

  selectedUser: UserI | null = null;

  visibleRegisterDialog = false;
  visibleEditDialog = false;
  visibleViewDialog = false;

  statCards = [
    {
      label: 'Total usuarios',
      value: '0',
      sub: 'Cuentas registradas',
      icon: 'fa-solid fa-users',
      color: '#3b82f6',
      bg: '#e8f1ff'
    },
    {
      label: 'Usuarios activos',
      value: '0',
      sub: 'Acceso habilitado',
      icon: 'fa-solid fa-user-check',
      color: '#059669',
      bg: '#e8faf2'
    },
    {
      label: 'Con roles',
      value: '0',
      sub: 'Permisos asignados',
      icon: 'fa-solid fa-shield-halved',
      color: '#d97706',
      bg: '#fff6df'
    },
    {
      label: 'Nuevos este mes',
      value: '0',
      sub: 'Altas recientes',
      icon: 'fa-solid fa-user-plus',
      color: '#7c3aed',
      bg: '#f3edff'
    }
  ];

  constructor(
    private userService: UserService,
    private messageService: MessageService,
    private confirmationService: ConfirmationService
  ) {}

  ngOnInit(): void {
    this.loadUsers();
  }

  loadUsers(): void {
    this.loading = true;
    this.userService.getUsers().subscribe({
      next: (data) => {
        this.users = data;
        this.updateStats();
        this.applyFilters();
        this.loading = false;
      },
      error: () => {
        this.messageService.add({
          severity: 'error',
          summary: 'Error',
          detail: 'No se pudieron cargar los usuarios.',
          life: 3000
        });
        this.loading = false;
      }
    });
  }

  onFilterChange(): void {
    this.applyFilters();
  }

  applyFilters(): void {
    const query = this.globalFilter.toLowerCase().trim();

    this.filteredUsers = this.users.filter((user) =>
      this.matchesSearch(user, query) &&
      this.matchesStatus(user) &&
      this.matchesRole(user)
    );

    this.first = 0;
  }

  openRegisterDialog(): void {
    this.visibleRegisterDialog = true;
  }

  closeRegisterDialog(): void {
    this.visibleRegisterDialog = false;
    this.loadUsers();
  }

  onEdit(user: UserI): void {
    this.selectedUser = user;
    this.visibleEditDialog = true;
  }

  onUserUpdated(): void {
    this.messageService.add({
      severity: 'success',
      summary: 'Usuario actualizado',
      detail: 'Los cambios se guardaron correctamente.',
      life: 3000
    });
  }

  closeEditDialog(): void {
    this.visibleEditDialog = false;
    this.loadUsers();
  }

  onView(user: UserI): void {
    this.selectedUser = user;
    this.visibleViewDialog = true;
  }

  confirmDelete(user: UserI): void {
    this.confirmationService.confirm({
      message: `Deseas eliminar a ${user.first_name} ${user.last_name}?`,
      header: 'Confirmar eliminacion',
      icon: 'pi pi-exclamation-triangle',
      acceptLabel: 'Si, eliminar',
      rejectLabel: 'Cancelar',
      key: 'userDelete',
      acceptButtonStyleClass: 'p-button-danger',
      rejectButtonStyleClass: 'p-button-secondary p-button-outlined',
      defaultFocus: 'reject',
      accept: () => {
        if (!user.id) return;

        this.userService.deleteUserLogic(user.id).subscribe({
          next: () => {
            this.messageService.add({
              severity: 'success',
              summary: 'Eliminado',
              detail: 'Usuario eliminado correctamente.',
              life: 3000
            });
            this.loadUsers();
          },
          error: () => {
            this.messageService.add({
              severity: 'error',
              summary: 'Error',
              detail: 'No se pudo eliminar el usuario.',
              life: 3000
            });
          }
        });
      }
    });
  }

  nextPage(): void {
    if (this.first + this.rows < this.filteredUsers.length) {
      this.first += this.rows;
    }
  }

  previousPage(): void {
    if (this.first > 0) {
      this.first -= this.rows;
    }
  }

  goToPage(page: number): void {
    const total = this.totalPages || 1;
    if (page < 1 || page > total) return;
    this.first = (page - 1) * this.rows;
  }

  get currentPage(): number {
    return Math.floor(this.first / this.rows) + 1;
  }

  get totalPages(): number {
    return Math.ceil(this.filteredUsers.length / this.rows);
  }

  get visibleUsers(): UserI[] {
    return this.filteredUsers.slice(this.first, this.first + this.rows);
  }

  getPageStart(): number {
    if (this.filteredUsers.length === 0) return 0;
    return this.first + 1;
  }

  getPageEnd(): number {
    return Math.min(this.first + this.rows, this.filteredUsers.length);
  }

  getPages(): number[] {
    return Array.from({ length: this.totalPages }, (_, index) => index + 1);
  }

  getActiveCount(): number {
    return this.users.filter((user) => this.isActive(user)).length;
  }

  getUsersWithRoleCount(): number {
    return this.users.filter((user) => this.hasAnyRole(user)).length;
  }

  getNewThisMonthCount(): number {
    const now = new Date();

    return this.users.filter((user) => {
      const rawDate =
        (user as any).created_at ??
        (user as any).createdAt ??
        (user as any).date_joined ??
        null;

      if (!rawDate) return false;

      const created = new Date(rawDate);
      if (Number.isNaN(created.getTime())) return false;

      return created.getMonth() === now.getMonth() && created.getFullYear() === now.getFullYear();
    }).length;
  }

  getRoleLabel(user: UserI): string {
    if (user.roles && user.roles.length > 0) {
      return user.roles[0].name;
    }

    return user.role?.name || 'Sin rol';
  }

  getExtraRolesCount(user: UserI): number {
    if (!user.roles || user.roles.length <= 1) return 0;
    return user.roles.length - 1;
  }

  isActive(user: UserI): boolean {
    if (user.status) return user.status === 'ACTIVE';
    return !!user.is_active;
  }

  getUserInitials(user: UserI): string {
    const first = user.first_name?.trim().charAt(0) || '';
    const last = user.last_name?.trim().charAt(0) || '';
    return `${first}${last}`.toUpperCase() || 'US';
  }

  resolveAvatar(src?: string | null): string | null {
    if (!src) return null;
    if (src.startsWith('http://') || src.startsWith('https://')) return src;
    return `http://127.0.0.1:8000${src.startsWith('/') ? '' : '/'}${src}`;
  }

  private updateStats(): void {
    this.statCards[0].value = `${this.users.length}`;
    this.statCards[1].value = `${this.getActiveCount()}`;
    this.statCards[2].value = `${this.getUsersWithRoleCount()}`;
    this.statCards[3].value = `${this.getNewThisMonthCount()}`;
  }

  private matchesSearch(user: UserI, query: string): boolean {
    if (!query) return true;

    const searchable = [
      user.username,
      user.email,
      user.first_name,
      user.last_name,
      this.getRoleLabel(user)
    ]
      .join(' ')
      .toLowerCase();

    return searchable.includes(query);
  }

  private matchesStatus(user: UserI): boolean {
    if (this.statusFilter === 'ALL') return true;
    return this.statusFilter === 'ACTIVE' ? this.isActive(user) : !this.isActive(user);
  }

  private matchesRole(user: UserI): boolean {
    if (this.roleFilter === 'ALL') return true;
    return this.roleFilter === 'WITH_ROLE' ? this.hasAnyRole(user) : !this.hasAnyRole(user);
  }

  private hasAnyRole(user: UserI): boolean {
    return (user.roles && user.roles.length > 0) || !!user.role;
  }
}
