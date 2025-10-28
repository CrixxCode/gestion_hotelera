import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { UserI } from '../modules/users/user-model';
import { AuthService } from './auth/auth';

@Injectable({ providedIn: 'root' })
export class UserService {
  private apiUrl = 'http://127.0.0.1:8000/api/users/';

  constructor(
    private http: HttpClient,
    private authService: AuthService
  ) {}

  /** 🔹 Obtiene la lista de usuarios */
  getUsers(): Observable<UserI[]> {
    return this.http.get<UserI[]>(this.apiUrl, this.authService.buildCsrfRequestOptions());
  }

  /** 🔹 Elimina físicamente un usuario */
  deleteUser(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}${id}/`, this.authService.buildCsrfRequestOptions());
  }

  /** 🔹 Elimina lógicamente un usuario (por ejemplo, desactiva el estado) */
  deleteUserLogic(id: number): Observable<UserI> {
    // Supone que el backend permite PATCH a /api/users/:id/ con {"is_active": false}
    const body = { is_active: false }; // o { status: 'INACTIVE' } según tu modelo
    return this.http.patch<UserI>(
      `${this.apiUrl}${id}/`,
      body,
      this.authService.buildCsrfRequestOptions()
    );
  }
}
