import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { environment } from '../../enviorements/environment';
import { AuthService } from './auth/auth';
import {
  ReservationDetailI,
  ReservationGuestI,
  ReservationGuestPayloadI,
  ReservationI,
  ReservationRoomI,
  ReservationRoomPayloadI,
  ReservationWritePayloadI
} from '../modules/reservations/reservation-model';

type DRFPaginated<T> = {
  results?: T[];
};

@Injectable({
  providedIn: 'root'
})
export class ReservationService {
  private readonly apiBase = (environment.API_URI || 'http://localhost:8000').replace(/\/$/, '');
  private readonly reservationsUrl = `${this.apiBase}/api/reservations/`;
  private readonly reservationRoomsUrl = `${this.apiBase}/api/reservation-rooms/`;
  private readonly reservationGuestsUrl = `${this.apiBase}/api/reservation-guests/`;

  constructor(
    private http: HttpClient,
    private auth: AuthService
  ) {}

  listReservations(filters?: {
    search?: string;
    ordering?: string;
  }): Observable<ReservationI[]> {
    let params = new HttpParams();

    if (filters?.search?.trim()) {
      params = params.set('search', filters.search.trim());
    }

    if (filters?.ordering?.trim()) {
      params = params.set('ordering', filters.ordering.trim());
    }

    return this.http
      .get<ReservationI[] | DRFPaginated<ReservationI>>(this.reservationsUrl, {
        withCredentials: true,
        params
      })
      .pipe(map((res) => this.unwrapArray<ReservationI>(res)));
  }

  getReservationById(id: number): Observable<ReservationDetailI> {
    return this.http.get<ReservationDetailI>(`${this.reservationsUrl}${id}/`, {
      withCredentials: true
    });
  }

  createReservation(payload: ReservationWritePayloadI): Observable<ReservationI> {
    return this.http.post<ReservationI>(
      this.reservationsUrl,
      this.normalizePayload(payload),
      this.auth.buildCsrfRequestOptions()
    );
  }

  updateReservation(id: number, payload: Partial<ReservationWritePayloadI>): Observable<ReservationI> {
    return this.http.patch<ReservationI>(
      `${this.reservationsUrl}${id}/`,
      this.normalizePayload(payload),
      this.auth.buildCsrfRequestOptions()
    );
  }

  confirmReservation(id: number): Observable<ReservationDetailI> {
    return this.http.post<ReservationDetailI>(
      `${this.reservationsUrl}${id}/confirm/`,
      {},
      this.auth.buildCsrfRequestOptions()
    );
  }

  checkInReservation(id: number): Observable<ReservationDetailI> {
    return this.http.post<ReservationDetailI>(
      `${this.reservationsUrl}${id}/check-in/`,
      {},
      this.auth.buildCsrfRequestOptions()
    );
  }

  checkOutReservation(id: number): Observable<ReservationDetailI> {
    return this.http.post<ReservationDetailI>(
      `${this.reservationsUrl}${id}/check-out/`,
      {},
      this.auth.buildCsrfRequestOptions()
    );
  }

  cancelReservation(id: number): Observable<ReservationDetailI> {
    return this.http.post<ReservationDetailI>(
      `${this.reservationsUrl}${id}/cancel/`,
      {},
      this.auth.buildCsrfRequestOptions()
    );
  }

  deleteReservation(id: number): Observable<void> {
    return this.http.delete<void>(`${this.reservationsUrl}${id}/`, this.auth.buildCsrfRequestOptions());
  }

  listReservationRooms(filters?: { reservation?: number }): Observable<ReservationRoomI[]> {
    let params = new HttpParams();

    if (filters?.reservation) {
      params = params.set('search', String(filters.reservation));
    }

    return this.http
      .get<ReservationRoomI[] | DRFPaginated<ReservationRoomI>>(this.reservationRoomsUrl, {
        withCredentials: true,
        params
      })
      .pipe(map((res) => this.unwrapArray<ReservationRoomI>(res)));
  }

  createReservationRoom(payload: ReservationRoomPayloadI): Observable<ReservationRoomI> {
    return this.http.post<ReservationRoomI>(
      this.reservationRoomsUrl,
      this.normalizeRoomPayload(payload),
      this.auth.buildCsrfRequestOptions()
    );
  }

  updateReservationRoom(id: number, payload: Partial<ReservationRoomPayloadI>): Observable<ReservationRoomI> {
    return this.http.patch<ReservationRoomI>(
      `${this.reservationRoomsUrl}${id}/`,
      this.normalizeRoomPayload(payload),
      this.auth.buildCsrfRequestOptions()
    );
  }

  deleteReservationRoom(id: number): Observable<void> {
    return this.http.delete<void>(`${this.reservationRoomsUrl}${id}/`, this.auth.buildCsrfRequestOptions());
  }

  listReservationGuests(filters?: { reservation?: number }): Observable<ReservationGuestI[]> {
    let params = new HttpParams();

    if (filters?.reservation) {
      params = params.set('search', String(filters.reservation));
    }

    return this.http
      .get<ReservationGuestI[] | DRFPaginated<ReservationGuestI>>(this.reservationGuestsUrl, {
        withCredentials: true,
        params
      })
      .pipe(map((res) => this.unwrapArray<ReservationGuestI>(res)));
  }

  createReservationGuest(payload: ReservationGuestPayloadI): Observable<ReservationGuestI> {
    return this.http.post<ReservationGuestI>(
      this.reservationGuestsUrl,
      this.normalizeGuestPayload(payload),
      this.auth.buildCsrfRequestOptions()
    );
  }

  private unwrapArray<T>(res: unknown): T[] {
    if (Array.isArray(res)) return res as T[];
    if (res && typeof res === 'object') {
      const maybeResults = (res as Record<string, unknown>)['results'];
      if (Array.isArray(maybeResults)) return maybeResults as T[];
    }
    return [];
  }

  private normalizePayload(payload: Partial<ReservationWritePayloadI>): Partial<ReservationWritePayloadI> {
    const normalized: Partial<ReservationWritePayloadI> = { ...payload };

    if (typeof normalized.client === 'string') {
      normalized.client = Number(normalized.client);
    }

    if (typeof normalized.origin === 'string') {
      normalized.origin = Number(normalized.origin);
    }

    if (normalized.promo_code !== undefined) {
      normalized.promo_code = normalized.promo_code ? String(normalized.promo_code).trim() : null;
    }

    if (normalized.notes !== undefined) {
      normalized.notes = normalized.notes ? String(normalized.notes).trim() : null;
    }

    if (normalized.total_discount !== undefined && normalized.total_discount !== null) {
      normalized.total_discount = Number(normalized.total_discount);
    }

    return normalized;
  }

  private normalizeRoomPayload(payload: Partial<ReservationRoomPayloadI>): Partial<ReservationRoomPayloadI> {
    const normalized: Partial<ReservationRoomPayloadI> = { ...payload };

    if (typeof normalized.reservation === 'string') {
      normalized.reservation = Number(normalized.reservation);
    }

    if (typeof normalized.room === 'string') {
      normalized.room = Number(normalized.room);
    }

    if (normalized.night_rate !== undefined && normalized.night_rate !== null) {
      normalized.night_rate = Number(normalized.night_rate);
    }

    if (normalized.adults !== undefined && normalized.adults !== null) {
      normalized.adults = Number(normalized.adults);
    }

    if (normalized.children !== undefined && normalized.children !== null) {
      normalized.children = Number(normalized.children);
    }

    if (normalized.meal_plan !== undefined && normalized.meal_plan !== null) {
      normalized.meal_plan = Number(normalized.meal_plan);
    }

    return normalized;
  }

  private normalizeGuestPayload(payload: Partial<ReservationGuestPayloadI>): Partial<ReservationGuestPayloadI> {
    const normalized: Partial<ReservationGuestPayloadI> = { ...payload };

    if (typeof normalized.reservation === 'string') {
      normalized.reservation = Number(normalized.reservation);
    }

    if (typeof normalized.document_type === 'string') {
      normalized.document_type = Number(normalized.document_type);
    }

    if (normalized.document_number !== undefined) {
      normalized.document_number = String(normalized.document_number || '').trim();
    }

    if (normalized.first_name !== undefined) {
      normalized.first_name = String(normalized.first_name || '').trim();
    }

    if (normalized.last_name !== undefined) {
      normalized.last_name = String(normalized.last_name || '').trim();
    }

    if (normalized.birth_date !== undefined) {
      normalized.birth_date = normalized.birth_date ? String(normalized.birth_date).trim() : null;
    }

    if (normalized.nationality !== undefined) {
      normalized.nationality = normalized.nationality ? String(normalized.nationality).trim() : null;
    }

    if (normalized.blood_type !== undefined) {
      normalized.blood_type = normalized.blood_type ? String(normalized.blood_type).trim() : null;
    }

    if (normalized.emergency_contact_name !== undefined) {
      normalized.emergency_contact_name = normalized.emergency_contact_name
        ? String(normalized.emergency_contact_name).trim()
        : null;
    }

    if (normalized.emergency_contact_phone !== undefined) {
      normalized.emergency_contact_phone = normalized.emergency_contact_phone
        ? String(normalized.emergency_contact_phone).trim()
        : null;
    }

    return normalized;
  }
}
