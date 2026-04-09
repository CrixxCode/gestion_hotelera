import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { environment } from '../../enviorements/environment';
import { AuthService } from './auth/auth';
import { PromotionFormPayload, PromotionI } from '../modules/promotions/promotion-model';

type DRFPaginated<T> = {
  results?: T[];
};

@Injectable({
  providedIn: 'root'
})
export class PromotionsService {
  private readonly apiBase = (environment.API_URI || 'http://localhost:8000').replace(/\/$/, '');
  private readonly promotionsUrl = `${this.apiBase}/api/promotions/`;

  constructor(
    private http: HttpClient,
    private auth: AuthService
  ) {}

  listPromotions(filters?: {
    search?: string;
    ordering?: string;
  }): Observable<PromotionI[]> {
    let params = new HttpParams();

    if (filters?.search?.trim()) {
      params = params.set('search', filters.search.trim());
    }

    if (filters?.ordering?.trim()) {
      params = params.set('ordering', filters.ordering.trim());
    }

    return this.http
      .get<PromotionI[] | DRFPaginated<PromotionI>>(this.promotionsUrl, {
        withCredentials: true,
        params
      })
      .pipe(map((res) => this.unwrapArray<PromotionI>(res)));
  }

  getPromotionById(id: number): Observable<PromotionI> {
    return this.http.get<PromotionI>(`${this.promotionsUrl}${id}/`, { withCredentials: true });
  }

  createPromotion(payload: PromotionFormPayload): Observable<PromotionI> {
    return this.http.post<PromotionI>(
      this.promotionsUrl,
      this.normalizeCreatePayload(payload),
      this.auth.buildCsrfRequestOptions()
    );
  }

  updatePromotion(id: number, payload: Partial<PromotionFormPayload>): Observable<PromotionI> {
    return this.http.patch<PromotionI>(
      `${this.promotionsUrl}${id}/`,
      this.normalizePatchPayload(payload),
      this.auth.buildCsrfRequestOptions()
    );
  }

  deletePromotion(id: number): Observable<void> {
    return this.http.delete<void>(`${this.promotionsUrl}${id}/`, this.auth.buildCsrfRequestOptions());
  }

  private unwrapArray<T>(res: unknown): T[] {
    if (Array.isArray(res)) return res as T[];
    if (res && typeof res === 'object' && Array.isArray((res as DRFPaginated<T>).results)) {
      return (res as DRFPaginated<T>).results as T[];
    }
    return [];
  }

  private normalizeCreatePayload(payload: PromotionFormPayload): PromotionFormPayload {
    return {
      hotel_settings: Number(payload.hotel_settings),
      discount_type: Number(payload.discount_type),
      service: this.normalizeNullableId(payload.service),
      package: this.normalizeNullableId(payload.package),
      name: (payload.name || '').trim(),
      code: this.normalizeNullableString(payload.code),
      description: (payload.description || '').trim(),
      discount_value: this.normalizeDiscountValue(payload.discount_value),
      start_date: this.normalizeDate(payload.start_date),
      end_date: this.normalizeDate(payload.end_date),
      is_active: !!payload.is_active,
      is_public: !!payload.is_public
    };
  }

  private normalizePatchPayload(payload: Partial<PromotionFormPayload>): Partial<PromotionFormPayload> {
    const normalized: Partial<PromotionFormPayload> = {};

    if (typeof payload.hotel_settings === 'number') {
      normalized.hotel_settings = Number(payload.hotel_settings);
    }

    if (typeof payload.discount_type === 'number') {
      normalized.discount_type = Number(payload.discount_type);
    }

    if (payload.service !== undefined) {
      normalized.service = this.normalizeNullableId(payload.service);
    }

    if (payload.package !== undefined) {
      normalized.package = this.normalizeNullableId(payload.package);
    }

    if (typeof payload.name === 'string') {
      normalized.name = payload.name.trim();
    }

    if (payload.code !== undefined) {
      normalized.code = this.normalizeNullableString(payload.code);
    }

    if (typeof payload.description === 'string') {
      normalized.description = payload.description.trim();
    }

    if (typeof payload.discount_value === 'number') {
      normalized.discount_value = this.normalizeDiscountValue(payload.discount_value);
    }

    if (typeof payload.start_date === 'string') {
      normalized.start_date = this.normalizeDate(payload.start_date);
    }

    if (typeof payload.end_date === 'string') {
      normalized.end_date = this.normalizeDate(payload.end_date);
    }

    if (typeof payload.is_active === 'boolean') {
      normalized.is_active = payload.is_active;
    }

    if (typeof payload.is_public === 'boolean') {
      normalized.is_public = payload.is_public;
    }

    return normalized;
  }

  private normalizeNullableId(value: unknown): number | null {
    if (typeof value !== 'number') return null;
    const normalized = Number(value);
    if (!Number.isInteger(normalized) || normalized <= 0) return null;
    return normalized;
  }

  private normalizeNullableString(value: unknown): string | null {
    if (typeof value !== 'string') return null;
    const trimmed = value.trim();
    return trimmed || null;
  }

  private normalizeDiscountValue(value: unknown): number {
    const parsed = Number(value);
    if (Number.isNaN(parsed) || parsed <= 0) return 0;
    return Number(parsed.toFixed(2));
  }

  private normalizeDate(value: unknown): string {
    if (typeof value !== 'string') return '';
    return value.trim();
  }
}
