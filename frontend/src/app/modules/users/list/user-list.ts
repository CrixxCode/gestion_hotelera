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

// Componentes hijos
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
  first = 0;
  rows = 6;

  //  Usuario seleccionado
  selectedUser: UserI | null = null;

  //  DiÃƒÆ’Ã‚Â¡logos
  visibleRegisterDialog = false;
  visibleEditDialog = false;
  visibleViewDialog = false;

  constructor(
    private userService: UserService,
    private messageService: MessageService,
    private confirmationService: ConfirmationService
  ) { }

  ngOnInit(): void {
    this.loadUsers();
  }

  /** Carga los usuarios desde el backend */
  loadUsers(): void {
    this.loading = true;
    this.userService.getUsers().subscribe({
      next: (data) => {
        this.users = data;
        this.filteredUsers = data;
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

  /** Filtro global */
  onFilterChange(): void {
    const query = this.globalFilter.toLowerCase().trim();
    this.filteredUsers = this.users.filter((u) =>
      [u.username, u.email, u.first_name, u.last_name]
        .join(' ')
        .toLowerCase()
        .includes(query)
    );
    this.first = 0;
  }

  // =============================
  //  CREAR USUARIO
  // =============================
  openRegisterDialog(): void {
    this.visibleRegisterDialog = true;
  }

  closeRegisterDialog(): void {
    this.visibleRegisterDialog = false;
    this.loadUsers(); // ÃƒÂ°Ã…Â¸Ã¢â‚¬ÂÃ‚Â recargar lista despuÃƒÆ’Ã‚Â©s de registrar
  }

  // =============================
  //  EDITAR USUARIO
  // =============================
  onEdit(user: UserI): void {
    this.selectedUser = user;
    this.visibleEditDialog = true;
  }

  /** Mostrar toast de actualizaciÃƒÆ’Ã‚Â³n */
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
    this.loadUsers(); // ÃƒÂ°Ã…Â¸Ã¢â‚¬ÂÃ‚Â recargar lista despuÃƒÆ’Ã‚Â©s de actualizar
  }

  // =============================
  //  VER DETALLES
  // =============================
  onView(user: UserI): void {
    this.selectedUser = user;
    this.visibleViewDialog = true;
  }

  // =============================
  //  ELIMINAR USUARIO
  // =============================
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
        this.userService.deleteUserLogic(user.id!).subscribe({
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

  // =============================
  //  PAGINACIÃƒÆ’Ã¢â‚¬Å“N MANUAL
  // =============================
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

  get currentPage(): number {
    return Math.floor(this.first / this.rows) + 1;
  }

  get totalPages(): number {
    return Math.ceil(this.filteredUsers.length / this.rows);
  }
}
