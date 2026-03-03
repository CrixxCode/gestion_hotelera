import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { UserI } from '../modules/users/user-model';
import { AuthService } from './auth/auth';

interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

@Injectable({ providedIn: 'root' })
export class UserService {
  private apiUrl = 'http://127.0.0.1:8000/api/users/';

  constructor(
    private http: HttpClient,
    private authService: AuthService
  ) { }

  /** Obtiene la lista de usuarios */
  getUsers(): Observable<UserI[]> {
    return this.http
      .get<UserI[] | PaginatedResponse<UserI>>(
        this.apiUrl,
        this.authService.buildCsrfRequestOptions()
      )
      .pipe(
        map((response): UserI[] =>
          Array.isArray(response) ? response : response.results ?? []
        ),
        map((users): UserI[] =>
          users.map((user): UserI => {
            const role = user.role ?? user.roles?.[0] ?? null;
            const roles = user.roles ?? (role ? [role] : []);
            const rawStatus =
              user.status ??
              (typeof user.is_active === 'boolean'
                ? user.is_active
                  ? 'ACTIVE'
                  : 'INACTIVE'
                : undefined);
            const normalizedStatus =
              typeof rawStatus === 'string' ? rawStatus.toUpperCase() : undefined;
            const isActive =
              typeof user.is_active === 'boolean'
                ? user.is_active
                : normalizedStatus === 'ACTIVE';

            return {
              ...user,
              role,
              roles,
              status: normalizedStatus ?? (isActive ? 'ACTIVE' : 'INACTIVE'),
              is_active: isActive,
            } as UserI; // 👈 Aquí TypeScript acepta el tipo final
          })
        )
      );
  }

  /** Crea un nuevo usuario */
  createUser(user: UserI, avatarFile?: File): Observable<UserI> {
    const formData = new FormData();

    // Campos básicos
    formData.append('first_name', user.first_name);
    formData.append('last_name', user.last_name);
    formData.append('username', user.username);
    formData.append('email', user.email);
    formData.append('password', user.password || '');

    // Avatar (solo si se selecciona)
    if (avatarFile) {
      formData.append('avatar', avatarFile);
    }

    // Estado (usar is_active)
    formData.append('is_active', user.is_active ? 'true' : 'false');

    // Rol (si usas un solo rol)
    if (user.role && user.role.id) {
      formData.append('role', String(user.role.id));
    }

    return this.http.post<UserI>(
      this.apiUrl,
      formData,
      this.authService.buildCsrfRequestOptions()
    );
  }

  /** Actualiza un usuario existente */
  updateUser(id: number, user: UserI, avatarFile?: File): Observable<UserI> {
    const formData = new FormData();
    formData.append('first_name', user.first_name);
    formData.append('last_name', user.last_name);
    formData.append('username', user.username);
    formData.append('email', user.email);
    formData.append('is_active', user.is_active ? 'true' : 'false');

    if (avatarFile) {
      formData.append('avatar', avatarFile);
    }

    return this.http.patch<UserI>(
      `${this.apiUrl}${id}/`,
      formData,
      this.authService.buildCsrfRequestOptions()
    );
  }


  /** Elimina fisicamente un usuario */
  deleteUser(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}${id}/`, this.authService.buildCsrfRequestOptions());
  }

  /** Elimina logicamente un usuario (por ejemplo, desactiva el estado) */
  deleteUserLogic(id: number): Observable<UserI> {
    // Supone que el backend permite PATCH a /api/users/:id/ con {"is_active": false}
    const body = { is_active: false }; // o { status: 'INACTIVE' } segun tu modelo
    return this.http.patch<UserI>(
      `${this.apiUrl}${id}/`,
      body,
      this.authService.buildCsrfRequestOptions()
    );
  }
}
