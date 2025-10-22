// auth.service.ts
import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable, switchMap, map } from 'rxjs'; 

@Injectable({ providedIn: 'root' })
export class AuthService {
  private csrfUrl = 'http://127.0.0.1:8000/api/auth/csrf/';
  private loginUrl = 'http://127.0.0.1:8000/api/auth/login/';
  private logoutUrl = 'http://127.0.0.1:8000/api/auth/logout/';
  private meUrl = 'http://127.0.0.1:8000/api/auth/me/';  // Aquí está el endpoint para la información del usuario

  constructor(private http: HttpClient) {}

  /** Obtiene el token CSRF */
  getCsrfToken(): Observable<any> {
    return this.http.get(this.csrfUrl, { withCredentials: true });
  }

  /** Inicia sesión */
  login(username: string, password: string): Observable<any> {
    return this.http.post(this.loginUrl, { username, password }, { withCredentials: true });
  }

  /** Cierra sesión */
  logout(): Observable<any> {
    return this.getCsrfToken().pipe(
      switchMap(() => 
        this.http.post(
          this.logoutUrl,
          {},
          {
            withCredentials: true,
            headers: new HttpHeaders({
              'X-CSRFToken': this.getCookie('csrftoken') || ''
            })
          }
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

  private getCookie(name: string): string | null {
    const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
    return match ? decodeURIComponent(match[2]) : null;
  }
}
