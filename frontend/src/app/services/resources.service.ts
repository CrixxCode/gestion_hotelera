import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { environment } from '../../enviorements/environment';
import { AuthService } from './auth/auth';

export interface RoleLite {
  id: string;
  name: string;
  slug: string;
  description?: string;
}

export interface Resource {
  id: string;
  key: string;
  name: string;
  description?: string;
  link?: string;
  link_backend?: string;
  icon?: string;
  order?: number;
  is_menu?: boolean;
  parent?: string | null;
}

type DRFPaginated<T> = { results?: T[] };

@Injectable({ providedIn: 'root' })
export class ResourcesService {
  private readonly apiBase = (environment.API_URI || 'http://localhost:8000').replace(/\/$/, '');
  private readonly rolesUrl = `${this.apiBase}/api/roles/`;
  private readonly resourcesUrl = `${this.apiBase}/api/resources/`;

  constructor(private http: HttpClient, private auth: AuthService) {}

  private unwrapArray<T>(res: any): T[] {
    if (Array.isArray(res)) return res;
    if (res && Array.isArray(res.results)) return (res as DRFPaginated<T>).results as T[];
    return [];
  }

  // -------- Roles (para selección) --------
  listRoles(): Observable<RoleLite[]> {
    return this.http.get<any>(this.rolesUrl, { withCredentials: true }).pipe(
      map(res => this.unwrapArray<RoleLite>(res))
    );
  }

  // -------- Recursos CRUD --------
  listResources(q: string = ''): Observable<Resource[]> {
    const qs = q ? `?q=${encodeURIComponent(q)}` : '';
    return this.http.get<any>(`${this.resourcesUrl}${qs}`, { withCredentials: true }).pipe(
      map(res => this.unwrapArray<Resource>(res))
    );
  }

  createResource(payload: Partial<Resource>): Observable<Resource> {
    return this.http.post<Resource>(this.resourcesUrl, payload, this.auth.buildCsrfRequestOptions());
  }

  updateResource(id: string, payload: Partial<Resource>): Observable<Resource> {
    return this.http.patch<Resource>(`${this.resourcesUrl}${id}/`, payload, this.auth.buildCsrfRequestOptions());
  }

  deleteResource(id: string): Observable<any> {
    return this.http.delete(`${this.resourcesUrl}${id}/`, this.auth.buildCsrfRequestOptions());
  }

  // -------- Rol ↔ Recursos --------
  roleResources(roleId: string): Observable<Resource[]> {
    return this.http.get<any>(`${this.rolesUrl}${roleId}/resources/`, { withCredentials: true }).pipe(
      map(res => this.unwrapArray<Resource>(res))
    );
  }

  assignResources(roleId: string, resourceIds: string[]): Observable<any> {
    return this.http.post(
      `${this.rolesUrl}${roleId}/assign-resources/`,
      { resource_ids: resourceIds },
      this.auth.buildCsrfRequestOptions()
    );
  }

  removeResources(roleId: string, resourceIds: string[]): Observable<any> {
    return this.http.post(
      `${this.rolesUrl}${roleId}/remove-resources/`,
      { resource_ids: resourceIds },
      this.auth.buildCsrfRequestOptions()
    );
  }
}