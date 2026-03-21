import { Component, OnDestroy, OnInit } from '@angular/core';
import { Router, RouterModule } from '@angular/router';
import { CommonModule } from '@angular/common';
import { AuthService, MenuItem, MeResponse } from '../../../services/auth/auth';

@Component({
  selector: 'app-aside',
  standalone: true,
  imports: [RouterModule, CommonModule],
  templateUrl: './aside.html',
  styleUrls: ['./aside.css']
})
export class Aside implements OnInit, OnDestroy {
  menu: MenuItem[] = [];
  openGroups: Record<string, boolean> = {};
  currentTime = '';
  currentDate = '';
  private clockTimer?: ReturnType<typeof setInterval>;

  constructor(
    private authService: AuthService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.startClock();
    this.authService.getUserInfo().subscribe({
      next: (user: MeResponse) => {
        const rawMenu = Array.isArray(user.menu) ? user.menu : [];
        this.menu = this.normalizeSecurityGroup(rawMenu);

        // Inicializa estados
        this.openGroups = {};

        // Auto-abrir grupos que contengan la ruta actual
        const currentUrl = this.router.url || '';

        for (const item of this.menu) {
          if (this.isGroup(item)) {
            const hasActiveChild = (item.children || []).some(ch => (ch.route || '') === currentUrl);
            this.openGroups[item.id] = hasActiveChild;
          }
        }
      },
      error: () => {
        this.menu = [];
        this.openGroups = {};
      }
    });
  }

  ngOnDestroy(): void {
    if (this.clockTimer) {
      clearInterval(this.clockTimer);
    }
  }

  toggleGroup(id: string): void {
    this.openGroups[id] = !this.openGroups[id];
  }

  isOpen(id: string): boolean {
    return !!this.openGroups[id];
  }

  isGroup(item: MenuItem): boolean {
    return Array.isArray(item.children) && item.children.length > 0;
  }

  private normalizeSecurityGroup(menu: MenuItem[]): MenuItem[] {
    const securityLabel = 'seguridad';
    const securityRoutes = new Set(['/usuarios', '/roles', '/recursos']);

    const normalized = this.normalizeMenuRoutes(menu);
    const hasSecurityGroup = normalized.some(
      (item) => (item.label || '').trim().toLowerCase() === securityLabel
    );

    const extractedItems: MenuItem[] = [];
    const extractedIds = new Set<string>();

    for (const item of normalized) {
      if (!this.isGroup(item) && item.route && securityRoutes.has(item.route)) {
        extractedItems.push(item);
        extractedIds.add(item.id);
      }
    }

    if (extractedItems.length === 0) {
      return normalized;
    }

    const filteredTopLevel = normalized.filter((item) => !extractedIds.has(item.id));

    if (hasSecurityGroup) {
      const updated = [...filteredTopLevel];
      const securityIndex = updated.findIndex(
        (item) => (item.label || '').trim().toLowerCase() === securityLabel
      );
      if (securityIndex < 0) return updated;

      const existingSecurity = { ...updated[securityIndex] };
      const existingChildren = Array.isArray(existingSecurity.children) ? [...existingSecurity.children] : [];
      const existingChildRoutes = new Set(existingChildren.map((child) => child.route || ''));

      for (const item of extractedItems) {
        if (item.route && !existingChildRoutes.has(item.route)) {
          existingChildren.push(item);
        }
      }

      existingSecurity.children = existingChildren;
      existingSecurity.icon = existingSecurity.icon || 'fa-solid fa-shield-halved';
      updated[securityIndex] = existingSecurity;
      return updated;
    }

    const firstExtractedIndex = normalized.findIndex((item) => extractedIds.has(item.id));
    const insertAt = firstExtractedIndex >= 0 ? firstExtractedIndex : filteredTopLevel.length;

    const securityGroup: MenuItem = {
      id: 'security-group',
      label: 'Seguridad',
      icon: 'fa-solid fa-shield-halved',
      route: '',
      children: extractedItems
    };

    return [
      ...filteredTopLevel.slice(0, insertAt),
      securityGroup,
      ...filteredTopLevel.slice(insertAt)
    ];
  }

  private normalizeMenuRoutes(items: MenuItem[]): MenuItem[] {
    return items.map((item) => ({
      ...item,
      route: this.normalizeRoute(item.route),
      children: Array.isArray(item.children) ? this.normalizeMenuRoutes(item.children) : item.children
    }));
  }

  private normalizeRoute(route?: string): string {
    const safe = (route || '').trim();
    if (!safe) return '';
    return safe.startsWith('/') ? safe : `/${safe}`;
  }

  private startClock(): void {
    const locale = 'es-CO';
    const timeZone = 'America/Bogota';
    const timeFormatter = new Intl.DateTimeFormat(locale, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true,
      timeZone,
    });
    const dateFormatter = new Intl.DateTimeFormat(locale, {
      weekday: 'long',
      day: '2-digit',
      month: 'long',
      year: 'numeric',
      timeZone,
    });

    const updateClock = () => {
      const now = new Date();
      this.currentTime = timeFormatter.format(now);
      const date = dateFormatter.format(now);
      this.currentDate = date.charAt(0).toUpperCase() + date.slice(1);
    };

    updateClock();
    this.clockTimer = setInterval(updateClock, 1000);
  }
}
