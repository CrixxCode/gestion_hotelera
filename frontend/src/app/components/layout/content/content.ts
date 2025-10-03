import { Component } from '@angular/core';
import { ActivatedRoute, NavigationEnd, Router } from '@angular/router';
import { filter } from 'rxjs/operators';
import { MenuItem } from 'primeng/api';
import { RouterOutlet } from '@angular/router';
import { BreadcrumbModule } from 'primeng/breadcrumb';

@Component({
  selector: 'app-content',
  imports: [RouterOutlet, BreadcrumbModule],
  templateUrl: './content.html',
  standalone: true,
})
export class Content {
  items: MenuItem[] = [];
  home: MenuItem = { icon: 'pi pi-home', routerLink: '/dashboard' };

  constructor(private router: Router, private route: ActivatedRoute) {
    this.router.events
      .pipe(filter(event => event instanceof NavigationEnd))
      .subscribe(() => {
        this.buildBreadcrumb();
      });
  }

  buildBreadcrumb() {
    const segments = this.router.url.split('/').filter(seg => seg);
    this.items = segments.map((seg, index) => {
      const url = '/' + segments.slice(0, index + 1).join('/');
      return { label: this.formatLabel(seg), routerLink: url };
    });
  }

  private formatLabel(segment: string): string {
    // Opcional: mejorar nombres (ej. reservas → Reservas)
    return segment.charAt(0).toUpperCase() + segment.slice(1);
  }
}
