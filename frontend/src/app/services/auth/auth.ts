// auth.service.ts
import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable, switchMap, map } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly apiProtocol = window.location.protocol.startsWith('http') ? window.location.protocol : 'http:';
  private readonly apiHost = window.location.hostname || 'localhost';
  private readonly apiPort = '8000';
  private readonly apiBase = `${this.apiProtocol}//${this.apiHost}:${this.apiPort}`;

  private csrfUrl = `${this.apiBase}/api/auth/csrf/`;
  private loginUrl = `${this.apiBase}/api/auth/login/`;
  private logoutUrl = `${this.apiBase}/api/auth/logout/`;
  private meUrl = `${this.apiBase}/api/auth/me/`;  // Endpoint para la información del usuario

  constructor(private http: HttpClient) { }

  /** Obtiene el token CSRF */
  getCsrfToken(): Observable<any> {
    return this.http.get(this.csrfUrl, { withCredentials: true });
  }

  /** Inicia sesión (flujo completo con CSRF) */
  login(username: string, password: string): Observable<any> {
    // Paso 1: obtener CSRF cookie
    return this.getCsrfToken().pipe(
      // Paso 2: hacer login con token y credenciales
      switchMap(() =>
        this.http.post(
          this.loginUrl,
          { username, password },
          this.buildCsrfRequestOptions() // incluye X-CSRFToken + withCredentials
        )
      )
    );
  }

  /** Cierra sesión */
  logout(): Observable<any> {
    return this.getCsrfToken().pipe(
      switchMap(() =>
        this.http.post(
          this.logoutUrl,
          {},
          this.buildCsrfRequestOptions()
        )
      )
    );
  }

  /** Verifica si el usuario está autenticado */
  checkSession(): Observable<boolean> {
    return this.http.get(this.meUrl, { withCredentials: true }).pipe(
      map((res: any) => !!res?.username)
    );
  }

  /** Obtiene la información del usuario (nombre y rol) */
  getUserInfo(): Observable<any> {
    return this.http.get(this.meUrl, { withCredentials: true });
  }

  /** Devuelve la URL base del backend (útil para componer recursos como media) */
  getApiBaseUrl(): string {
    return this.apiBase;
  }

  /** Normaliza rutas devueltas por la API a URLs completas */
  buildMediaUrl(path?: string | null): string {
    if (!path) {
      return '';
    }
    if (/^https?:\/\//i.test(path)) {
      return path;
    }
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    return `${this.apiBase}${normalizedPath}`;
  }

  getCookie(name: string): string | null {
    const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
    return match ? decodeURIComponent(match[2]) : null;
  }

  buildCsrfRequestOptions() {
    const options: { withCredentials: true; headers?: HttpHeaders } = { withCredentials: true };
    const token = this.getCookie('csrftoken');
    if (token) {
      options.headers = new HttpHeaders({ 'X-CSRFToken': token });
    }
    return options;
  }
}
