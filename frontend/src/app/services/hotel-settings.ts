import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../enviorements/environment';
import { AuthService } from './auth/auth';
import { HotelSettings } from '../components/pages/hotel-settings/hotel-setting-model';

@Injectable({ providedIn: 'root' })
export class HotelSettingsService {

  private readonly apiBase = (environment.API_URI || 'http://localhost:8000').replace(/\/$/, '');
  private readonly settingsUrl = `${this.apiBase}/api/hotel-settings/`;

  constructor(
    private http: HttpClient,
    private auth: AuthService
  ) { }

  /**
   * Obtiene la configuración actual del hotel
   */
  getCurrentSettings(): Observable<HotelSettings | null> {
    return this.http.get<HotelSettings | null>(
      `${this.settingsUrl}current/`,
      { withCredentials: true }
    );
  }

  /**
   * Crear configuración inicial del hotel
   */
  createSettings(payload: Partial<HotelSettings>): Observable<HotelSettings> {
    return this.http.post<HotelSettings>(
      this.settingsUrl,
      payload,
      this.auth.buildCsrfRequestOptions()
    );
  }

  /**
   * Actualizar configuración existente
   */
  updateSettings(id: number, payload: Partial<HotelSettings>): Observable<HotelSettings> {
    return this.http.patch<HotelSettings>(
      `${this.settingsUrl}${id}/`,
      payload,
      this.auth.buildCsrfRequestOptions()
    );
  }

  /**
   * Borrar completamente la configuración
   */
  clearSettings(): Observable<any> {
    return this.http.post(
      `${this.settingsUrl}clear/`,
      {},
      this.auth.buildCsrfRequestOptions()
    );
  }

}