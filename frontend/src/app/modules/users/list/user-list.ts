import { Component, OnInit } from '@angular/core';
import { CommonModule, NgClass } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { UserService } from '../../../services/user';
import { UserI } from '../user-model';

@Component({
  selector: 'app-user-list',
  standalone: true,
  templateUrl: './user-list.html',
  styleUrls: ['./user-list.css'],
  imports: [CommonModule, FormsModule, NgClass],
})
export class UserList implements OnInit {
  users: UserI[] = [];
  filteredUsers: UserI[] = [];
  loading = true;
  globalFilter = '';
  first = 0;
  rows = 6;

  constructor(private userService: UserService) {}

  ngOnInit(): void {
    this.loadUsers();
  }

  /** Carga los usuarios desde el backend */
  loadUsers(): void {
    this.userService.getUsers().subscribe({
      next: (data) => {
        this.users = data;
        this.filteredUsers = data;
        this.loading = false;
      },
      error: () => {
        window.alert('❌ Error al cargar los usuarios.');
        this.loading = false;
      },
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

  /** Confirmación y eliminación lógica */
  confirmDelete(user: UserI): void {
    const confirmed = window.confirm(
      `¿Deseas eliminar a ${user.first_name} ${user.last_name}?`
    );
    if (confirmed) {
      this.userService.deleteUserLogic(user.id!).subscribe({
        next: () => {
          window.alert('✅ Usuario eliminado correctamente.');
          this.loadUsers();
        },
        error: () => {
          window.alert('❌ No se pudo eliminar el usuario.');
        },
      });
    }
  }

  /** Acciones */
  onEdit(user: UserI): void {
    window.alert(`✏️ Editar usuario: ${user.username}`);
  }

  onView(user: UserI): void {
    window.alert(`👁️ Ver detalles de: ${user.username}`);
  }

  /** Paginación manual */
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
