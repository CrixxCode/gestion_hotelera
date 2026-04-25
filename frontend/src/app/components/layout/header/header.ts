import { CommonModule } from '@angular/common';
import { Component, EventEmitter, HostListener, OnInit, Output } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, forkJoin, of } from 'rxjs';
import { ItemI } from '../../../modules/items/item-model';
import { MaintenanceOrderI } from '../../../modules/maintenance-orders/maintenance-order-model';
import { ReservationI } from '../../../modules/reservations/reservation-model';
import { AuthService } from '../../../services/auth/auth';
import { ItemsService } from '../../../services/item';
import { MaintenanceOrdersService } from '../../../services/maintenance-order';
import { NotificationStateService } from '../../../services/notification-state';
import { ReservationService } from '../../../services/reservation';
import { LogoutScreen } from '../../pages/logout-screen/logout-screen';

type NotificationTone = 'warning' | 'info' | 'success';
type NavigationQuery = Record<string, string | number | boolean>;

interface HeaderNotification {
  id: string;
  title: string;
  detail: string;
  age: string;
  icon: string;
  tone: NotificationTone;
  route: string;
  unread: boolean;
  queryParams?: NavigationQuery;
}

@Component({
  selector: 'app-header',
  standalone: true,
  imports: [CommonModule, LogoutScreen],
  templateUrl: './header.html',
  styleUrl: './header.css',
})
export class Header implements OnInit {
  @Output() menuToggle = new EventEmitter<void>();

  menuOpen = false;
  notificationsOpen = false;
  notificationsLoading = false;
  notificationsError = '';
  notifications: HeaderNotification[] = [];
  darkMode = false;
  showLogout = false;
  userName = '';
  userRole = '';
  userAvatar = 'avatar/default-avatar.png';

  private readonly defaultAvatar = 'avatar/default-avatar.png';
  private readonly logoutAnimationDuration = 1000;
  private readonly maxNotificationAgeDays = 7;
  private readonly reservationAutoCancelMarker = 'AUTOCANCEL_OVERDUE:';
  private readonly themePrimaryStorageKey = 'gh_theme_primary';
  private readonly themeSecondaryStorageKey = 'gh_theme_secondary';
  private readonly defaultThemePrimaryColor = '#0f1f41';
  private readonly defaultThemeSecondaryColor = '#112853';
  private readNotificationIds = new Set<string>();

  constructor(
    private authService: AuthService,
    private router: Router,
    private itemsService: ItemsService,
    private maintenanceOrdersService: MaintenanceOrdersService,
    private reservationService: ReservationService,
    private notificationStateService: NotificationStateService
  ) {}

  get unreadCount(): number {
    return this.notifications.reduce((sum, notification) => sum + (notification.unread ? 1 : 0), 0);
  }

  get readCount(): number {
    return this.notifications.reduce((sum, notification) => sum + (notification.unread ? 0 : 1), 0);
  }

  get actionableNotificationCount(): number {
    return this.notifications.filter((notification) => notification.id !== 'none').length;
  }

  ngOnInit(): void {
    this.darkMode = false;
    document.documentElement.classList.remove('my-app-dark');
    document.documentElement.classList.remove('dark');
    this.applyStoredThemeCustomization();
    this.loadUserInfo();
  }

  loadUserInfo(): void {
    this.authService.getUserInfo().subscribe({
      next: (res: any) => {
        this.userName = res.username || 'Usuario';
        this.userRole = this.resolveUserRole(res);
        this.loadReadNotificationIds();
        const resolvedAvatar = this.authService.buildMediaUrl(res.avatar);
        this.userAvatar = resolvedAvatar || this.defaultAvatar;
      },
      error: () => {
        this.userName = 'Invitado';
        this.userRole = 'Sin rol';
        this.userAvatar = this.defaultAvatar;
        this.readNotificationIds = new Set<string>();
        this.notifications = this.applyReadState(this.notifications);
      },
    });
  }

  toggleMenu(): void {
    this.menuOpen = !this.menuOpen;
    if (this.menuOpen) {
      this.notificationsOpen = false;
    }
  }

  toggleNotifications(): void {
    this.notificationsOpen = !this.notificationsOpen;
    if (this.notificationsOpen) {
      this.menuOpen = false;
      if (!this.notifications.length && !this.notificationsLoading) {
        this.loadNotifications();
      }
    }
  }

  refreshNotifications(): void {
    this.loadNotifications();
  }

  markNotificationsAsRead(): void {
    const keys = this.notifications
      .filter((notification) => notification.id !== 'none')
      .map((notification) => notification.id);
    if (!keys.length) return;

    keys.forEach((key) => this.readNotificationIds.add(key));
    this.notifications = this.applyReadState(this.notifications);

    this.notificationStateService
      .markRead(keys)
      .pipe(catchError(() => of(void 0)))
      .subscribe();
  }

  markNotificationsAsUnread(): void {
    const keys = this.notifications
      .filter((notification) => notification.id !== 'none')
      .map((notification) => notification.id);
    if (!keys.length) return;

    keys.forEach((key) => this.readNotificationIds.delete(key));
    this.notifications = this.applyReadState(this.notifications);

    this.notificationStateService
      .markUnread(keys)
      .pipe(catchError(() => of(void 0)))
      .subscribe();
  }

  openNotification(notification: HeaderNotification): void {
    if (notification.id !== 'none' && notification.unread) {
      this.readNotificationIds.add(notification.id);
      this.notificationStateService
        .markRead([notification.id])
        .pipe(catchError(() => of(void 0)))
        .subscribe();
    }
    this.notifications = this.applyReadState(this.notifications);
    this.notificationsOpen = false;
    void this.router.navigate([notification.route], notification.queryParams ? { queryParams: notification.queryParams } : undefined);
  }

  openAllNotifications(): void {
    this.markNotificationsAsRead();
    this.notificationsOpen = false;
    void this.router.navigate(['/actividad']);
  }

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    const target = event.target as HTMLElement;
    if (!target.closest('.user-menu')) {
      this.menuOpen = false;
    }
    if (!target.closest('.notifications-menu')) {
      this.notificationsOpen = false;
    }
  }

  openProfile(): void {
    this.menuOpen = false;
    this.notificationsOpen = false;
    void this.router.navigate(['/mi-perfil']);
  }

  openSettings(): void {
    this.menuOpen = false;
    this.notificationsOpen = false;
    void this.router.navigate(['/hotel-config']);
  }

  toggleTheme(): void {
    this.darkMode = !this.darkMode;
    document.documentElement.classList.toggle('my-app-dark', this.darkMode);
    document.documentElement.classList.toggle('dark', this.darkMode);
    this.menuOpen = false;
    this.notificationsOpen = false;
  }

  logout(): void {
    this.menuOpen = false;
    this.notificationsOpen = false;
    this.showLogout = true;
    this.authService.logout().subscribe({
      next: () => this.finishLogoutTransition(),
      error: () => this.finishLogoutTransition(),
    });
  }

  private finishLogoutTransition(): void {
    setTimeout(() => {
      this.router.navigate(['/login']).finally(() => {
        this.showLogout = false;
      });
    }, this.logoutAnimationDuration);
  }

  private applyStoredThemeCustomization(): void {
    if (typeof window === 'undefined' || typeof document === 'undefined') return;

    const normalizeColor = (value: string | null, fallback: string): string => {
      const candidate = String(value || '').trim();
      return /^#[\da-fA-F]{6}$/.test(candidate) ? candidate.toLowerCase() : fallback;
    };

    const resolveOnBrandColor = (hexColor: string): string => {
      const normalized = normalizeColor(hexColor, this.defaultThemePrimaryColor).slice(1);
      const red = parseInt(normalized.slice(0, 2), 16) / 255;
      const green = parseInt(normalized.slice(2, 4), 16) / 255;
      const blue = parseInt(normalized.slice(4, 6), 16) / 255;
      const linearize = (channel: number): number =>
        channel <= 0.03928 ? channel / 12.92 : Math.pow((channel + 0.055) / 1.055, 2.4);

      const luminance = 0.2126 * linearize(red) + 0.7152 * linearize(green) + 0.0722 * linearize(blue);
      return luminance > 0.45 ? '#0f172a' : '#ffffff';
    };

    const primary = normalizeColor(localStorage.getItem(this.themePrimaryStorageKey), this.defaultThemePrimaryColor);
    const secondary = normalizeColor(localStorage.getItem(this.themeSecondaryStorageKey), this.defaultThemeSecondaryColor);

    const root = document.documentElement;
    root.style.setProperty('--gh-brand', primary);
    root.style.setProperty('--gh-brand-hover', secondary);
    root.style.setProperty('--gh-brand-secondary', secondary);
    root.style.setProperty('--gh-on-brand', resolveOnBrandColor(primary));
  }

  private loadNotifications(): void {
    this.notificationsLoading = true;
    this.notificationsError = '';

    forkJoin({
      items: this.itemsService.listItems({ ordering: 'stock' }).pipe(catchError(() => of([] as ItemI[]))),
      maintenance: this.maintenanceOrdersService
        .listMaintenanceOrders({ ordering: '-reported_at' })
        .pipe(catchError(() => of([] as MaintenanceOrderI[]))),
      reservations: this.reservationService
        .listReservations({ ordering: 'expected_check_in', include_finished: false, page_size: 200 })
        .pipe(catchError(() => of([] as ReservationI[]))),
    }).subscribe({
      next: ({ items, maintenance, reservations }) => {
        this.notifications = this.applyReadState(this.buildNotifications(items, maintenance, reservations));
        this.notificationsLoading = false;
      },
      error: () => {
        this.notificationsLoading = false;
        this.notificationsError = 'No fue posible cargar las notificaciones.';
      },
    });
  }

  private buildNotifications(
    items: ItemI[],
    maintenanceOrders: MaintenanceOrderI[],
    reservations: ReservationI[]
  ): HeaderNotification[] {
    const notifications: HeaderNotification[] = [];

    items
      .filter((item) => item.minimum_stock > 0 && item.stock <= item.minimum_stock)
      .slice(0, 3)
      .forEach((item) => {
        const occurredAt = this.parseDateTime(item.updated_at || item.created_at || null);
        if (this.isOlderThanMaxDays(occurredAt, this.maxNotificationAgeDays)) return;

        notifications.push({
          id: `item-${item.id}`,
          title: 'Stock bajo',
          detail: `${item.name} - ${item.stock} unidades`,
          age: this.relativeFromNow(occurredAt),
          icon: 'fa-solid fa-triangle-exclamation',
          tone: 'warning',
          route: '/items',
          unread: true,
          queryParams: { search: item.name },
        });
      });

    maintenanceOrders
      .filter((order) => !String(order.status_label || order.status || '').toUpperCase().includes('COMPLET'))
      .slice(0, 3)
      .forEach((order) => {
        const occurredAt = this.parseDateTime(order.reported_at || null);
        if (this.isOlderThanMaxDays(occurredAt, this.maxNotificationAgeDays)) return;

        notifications.push({
          id: `mnt-${order.id}`,
          title: 'Mantenimiento pendiente',
          detail: `${order.title} - Hab. ${order.room_number || order.room || '-'}`,
          age: this.relativeFromNow(occurredAt),
          icon: 'fa-solid fa-screwdriver-wrench',
          tone: 'info',
          route: '/ordenes-mantenimiento',
          unread: true,
          queryParams: { search: order.title },
        });
      });

    const today = this.getToday();
    reservations
      .filter((reservation) => {
        const checkIn = this.parseDateOnly(reservation.expected_check_in);
        if (!checkIn || this.isCanceledReservation(reservation) || reservation.real_check_in) return false;
        const diff = this.dayDifference(today, checkIn);
        return diff >= 0 && diff <= 1;
      })
      .slice(0, 3)
      .forEach((reservation) => {
        const checkIn = this.parseDateOnly(reservation.expected_check_in);
        const diff = checkIn ? this.dayDifference(today, checkIn) : 0;
        notifications.push({
          id: `res-${reservation.id}`,
          title: 'Check-in proximo',
          detail: reservation.client_full_name || `Cliente #${reservation.client}`,
          age: diff === 0 ? 'Llega hoy' : 'Llega manana',
          icon: 'fa-regular fa-calendar-check',
          tone: 'info',
          route: '/reservas',
          unread: true,
          queryParams: { search: String(reservation.id) },
        });
      });

    reservations
      .filter((reservation) => this.isCanceledReservation(reservation))
      .map((reservation) => ({
        reservation,
        cancelledAt: this.extractReservationAutoCancelDate(reservation),
      }))
      .filter((entry) => !!entry.cancelledAt && !this.isOlderThanMaxDays(entry.cancelledAt, this.maxNotificationAgeDays))
      .sort((a, b) => (b.cancelledAt?.getTime() || 0) - (a.cancelledAt?.getTime() || 0))
      .slice(0, 3)
      .forEach(({ reservation, cancelledAt }) => {
        notifications.push({
          id: `res-autocancel-${reservation.id}`,
          title: 'Reserva auto-cancelada',
          detail: `${reservation.client_full_name || `Cliente #${reservation.client}`} - sin check-in`,
          age: this.relativeFromNow(cancelledAt),
          icon: 'fa-solid fa-ban',
          tone: 'warning',
          route: '/reservas',
          unread: true,
          queryParams: { search: String(reservation.id) },
        });
      });

    if (!notifications.length) {
      return [
        {
          id: 'none',
          title: 'Sin alertas activas',
          detail: 'No hay notificaciones pendientes por ahora.',
          age: 'Ahora',
          icon: 'fa-solid fa-circle-check',
          tone: 'success',
          route: '/dashboard',
          unread: false,
        },
      ];
    }

    return notifications.slice(0, 8);
  }

  private isCanceledReservation(reservation: ReservationI): boolean {
    return String(reservation.status_code || reservation.status_name || '').toUpperCase().includes('CANCEL');
  }

  private extractReservationAutoCancelDate(reservation: ReservationI): Date | null {
    const notes = String(reservation.notes || '');
    if (!notes) return null;

    const pattern = new RegExp(`${this.reservationAutoCancelMarker}([^\\]\\s]+)`, 'i');
    const match = pattern.exec(notes);
    if (!match || !match[1]) return null;

    const parsed = new Date(match[1]);
    if (Number.isNaN(parsed.getTime())) return null;
    return parsed;
  }

  private getToday(): Date {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), now.getDate());
  }

  private parseDateOnly(value?: string | null): Date | null {
    if (!value) return null;
    const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value.trim());
    if (!match) return null;
    return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  }

  private dayDifference(from: Date, to: Date): number {
    const start = new Date(from.getFullYear(), from.getMonth(), from.getDate()).getTime();
    const end = new Date(to.getFullYear(), to.getMonth(), to.getDate()).getTime();
    return Math.round((end - start) / 86400000);
  }

  private parseDateTime(value?: string | null): Date | null {
    if (!value) return null;
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return null;
    return date;
  }

  private relativeFromNow(value?: Date | string | null): string {
    if (!value) return 'Reciente';
    const date = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(date.getTime())) return 'Reciente';
    const minutes = Math.max(1, Math.round((Date.now() - date.getTime()) / 60000));
    if (minutes < 60) return `Hace ${minutes} min`;
    const hours = Math.round(minutes / 60);
    if (hours < 24) return `Hace ${hours} h`;
    return `Hace ${Math.round(hours / 24)} d`;
  }

  private isOlderThanMaxDays(date: Date | null, maxDays: number): boolean {
    if (!date) return false;
    const today = this.getToday();
    const notificationDay = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    const diffDays = this.dayDifference(notificationDay, today);
    return diffDays > maxDays;
  }

  private applyReadState(notifications: HeaderNotification[]): HeaderNotification[] {
    return notifications.map((notification) => {
      if (notification.id === 'none') {
        return { ...notification, unread: false };
      }
      return { ...notification, unread: !this.readNotificationIds.has(notification.id) };
    });
  }

  private loadReadNotificationIds(): void {
    this.notificationStateService
      .listReadKeys()
      .pipe(catchError(() => of([] as string[])))
      .subscribe((keys) => {
        this.readNotificationIds = new Set<string>(keys);
        this.notifications = this.applyReadState(this.notifications);
      });
  }

  private resolveUserRole(user: any): string {
    if (user?.role) {
      return user.role;
    }
    const firstRole = Array.isArray(user?.roles) ? user.roles[0]?.name : null;
    return firstRole || 'Usuario';
  }
}
