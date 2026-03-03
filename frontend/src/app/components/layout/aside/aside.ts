import { Component, OnInit } from '@angular/core';
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
export class Aside implements OnInit {
  menu: MenuItem[] = [];
  openGroups: Record<string, boolean> = {};

  constructor(
    private authService: AuthService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.authService.getUserInfo().subscribe({
      next: (user: MeResponse) => {
        this.menu = Array.isArray(user.menu) ? user.menu : [];

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

  toggleGroup(id: string): void {
    this.openGroups[id] = !this.openGroups[id];
  }

  isOpen(id: string): boolean {
    return !!this.openGroups[id];
  }

  isGroup(item: MenuItem): boolean {
    return Array.isArray(item.children) && item.children.length > 0;
  }
}