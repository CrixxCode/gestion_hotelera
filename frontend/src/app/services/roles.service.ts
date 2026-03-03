import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { environment } from '../../enviorements/environment';
import { AuthService } from './auth/auth';

export interface Role {
  id: string;
  name: string;
  slug: string;
  description?: string;
}

export interface UserMini {
  id: string;
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  is_active: boolean;
  avatar?: string | null;
}

type DRFPaginated<T> = {
  count?: number;
  next?: string | null;
  previous?: string | null;
  results?: T[];
};

@Injectable({ providedIn: 'root' })
export class RolesService {
  private readonly apiBase = (environment.API_URI || 'http://localhost:8000').replace(/\/$/, '');
  private readonly rolesUrl = `${this.apiBase}/api/roles/`;

  constructor(private http: HttpClient, private auth: AuthService) {}

  private unwrapArray<T>(res: any): T[] {
    if (Array.isArray(res)) return res;
    if (res && Array.isArray(res.results)) return (res as DRFPaginated<T>).results as T[];
    if (res && Array.isArray(res.data)) return res.data as T[]; // por si algún wrapper
    return [];
  }

  listRoles(): Observable<Role[]> {
    return this.http.get<any>(this.rolesUrl, { withCredentials: true }).pipe(
      map((res) => this.unwrapArray<Role>(res))
    );
  }

  createRole(payload: Partial<Role>): Observable<Role> {
    return this.http.post<Role>(this.rolesUrl, payload, this.auth.buildCsrfRequestOptions());
  }

  updateRole(id: string, payload: Partial<Role>): Observable<Role> {
    return this.http.patch<Role>(`${this.rolesUrl}${id}/`, payload, this.auth.buildCsrfRequestOptions());
  }

  deleteRole(id: string): Observable<any> {
    return this.http.delete(`${this.rolesUrl}${id}/`, this.auth.buildCsrfRequestOptions());
  }

  roleUsers(roleId: string): Observable<UserMini[]> {
    return this.http.get<any>(`${this.rolesUrl}${roleId}/users/`, { withCredentials: true }).pipe(
      map((res) => this.unwrapArray<UserMini>(res))
    );
  }

  usersCatalog(q: string = ''): Observable<UserMini[]> {
    const qs = q ? `?q=${encodeURIComponent(q)}` : '';
    return this.http.get<any>(`${this.rolesUrl}users-catalog/${qs}`, { withCredentials: true }).pipe(
      map((res) => this.unwrapArray<UserMini>(res))
    );
  }

  assignUsers(roleId: string, userIds: string[]): Observable<any> {
    return this.http.post(
      `${this.rolesUrl}${roleId}/assign-users/`,
      { user_ids: userIds },
      this.auth.buildCsrfRequestOptions()
    );
  }

  removeUsers(roleId: string, userIds: string[]): Observable<any> {
    return this.http.post(
      `${this.rolesUrl}${roleId}/remove-users/`,
      { user_ids: userIds },
      this.auth.buildCsrfRequestOptions()
    );
  }
}