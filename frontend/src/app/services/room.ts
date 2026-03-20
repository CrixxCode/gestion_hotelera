import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { environment } from '../../enviorements/environment';
import { AuthService } from './auth/auth';
import {
  AmenityI,
  HotelFloorI,
  RateI,
  RoomFormPayload,
  RoomI,
  RoomPanelI,
  RoomTypeI,
  RoomVisualStatus
} from '../modules/rooms/room-model';

@Injectable({
  providedIn: 'root'
})
export class RoomService {
  private readonly apiBase = (environment.API_URI || 'http://localhost:8000').replace(/\/$/, '');
  private readonly roomsUrl = `${this.apiBase}/api/rooms/`;
  private readonly roomTypesUrl = `${this.apiBase}/api/room-types/`;
  private readonly amenitiesUrl = `${this.apiBase}/api/amenities/`;
  private readonly ratesUrl = `${this.apiBase}/api/rates/`;
  private readonly floorsUrl = `${this.apiBase}/api/hotel-floors/`;

  constructor(
    private http: HttpClient,
    private auth: AuthService
  ) {}

  listRooms(filters?: {
    search?: string;
    status?: RoomVisualStatus | 'ALL';
    floor?: number | 'ALL';
    ordering?: string;
  }): Observable<RoomI[]> {
    let params = new HttpParams();

    if (filters?.search?.trim()) {
      params = params.set('search', filters.search.trim());
    }

    if (filters?.status && filters.status !== 'ALL' && filters.status !== 'POR_SALIR_HOY') {
      params = params.set('status', filters.status);
    }

    if (filters?.floor && filters.floor !== 'ALL') {
      params = params.set('floor', String(filters.floor));
    }

    if (filters?.ordering) {
      params = params.set('ordering', filters.ordering);
    }

    return this.http
      .get<RoomI[] | { results?: RoomI[] }>(this.roomsUrl, { withCredentials: true, params })
      .pipe(map((res) => this.unwrapArray<RoomI>(res)));
  }

  getRoomById(id: number): Observable<RoomI> {
    return this.http.get<RoomI>(`${this.roomsUrl}${id}/`, { withCredentials: true });
  }

  getRoomPanel(id: number): Observable<RoomPanelI> {
    return this.http.get<RoomPanelI>(`${this.roomsUrl}${id}/panel/`, { withCredentials: true });
  }

  createRoom(payload: RoomFormPayload): Observable<RoomI> {
    return this.http.post<RoomI>(
      this.roomsUrl,
      this.normalizePayload(payload),
      this.auth.buildCsrfRequestOptions()
    );
  }

  updateRoom(id: number, payload: RoomFormPayload): Observable<RoomI> {
    return this.http.patch<RoomI>(
      `${this.roomsUrl}${id}/`,
      this.normalizePayload(payload),
      this.auth.buildCsrfRequestOptions()
    );
  }

  deleteRoom(id: number): Observable<void> {
    return this.http.delete<void>(`${this.roomsUrl}${id}/`, this.auth.buildCsrfRequestOptions());
  }

  listRoomTypes(): Observable<RoomTypeI[]> {
    return this.http
      .get<RoomTypeI[] | { results?: RoomTypeI[] }>(this.roomTypesUrl, { withCredentials: true })
      .pipe(map((res) => this.unwrapArray<RoomTypeI>(res)));
  }

  listAmenities(): Observable<AmenityI[]> {
    return this.http
      .get<AmenityI[] | { results?: AmenityI[] }>(this.amenitiesUrl, { withCredentials: true })
      .pipe(map((res) => this.unwrapArray<AmenityI>(res)));
  }

  listRates(): Observable<RateI[]> {
    return this.http
      .get<RateI[] | { results?: RateI[] }>(this.ratesUrl, { withCredentials: true })
      .pipe(map((res) => this.unwrapArray<RateI>(res)));
  }

  listFloors(): Observable<HotelFloorI[]> {
    return this.http
      .get<HotelFloorI[] | { results?: HotelFloorI[] }>(this.floorsUrl, { withCredentials: true })
      .pipe(map((res) => this.unwrapArray<HotelFloorI>(res)));
  }

  private unwrapArray<T>(res: unknown): T[] {
    if (Array.isArray(res)) return res as T[];
    if (res && typeof res === 'object') {
      const maybeResults = (res as Record<string, unknown>)['results'];
      if (Array.isArray(maybeResults)) return maybeResults as T[];
    }
    return [];
  }

  private normalizePayload(payload: RoomFormPayload): RoomFormPayload {
    const normalized: RoomFormPayload = {
      number: (payload.number || '').trim(),
      floor: Number(payload.floor),
      status: payload.status,
      notes: (payload.notes || '').trim(),
      amenity_ids: Array.isArray(payload.amenity_ids) ? payload.amenity_ids : []
    };

    if (payload.room_type) {
      normalized.room_type = Number(payload.room_type);
    } else {
      normalized.room_type = null;
    }

    return normalized;
  }
}
