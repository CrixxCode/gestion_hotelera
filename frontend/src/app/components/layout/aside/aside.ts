import { Component, OnInit, ViewEncapsulation } from '@angular/core';
import { MenuItem } from 'primeng/api';
import { PanelMenu } from 'primeng/panelmenu';

@Component({
  selector: 'app-aside',
  standalone: true,
  imports: [PanelMenu],
  templateUrl: './aside.html',
  styleUrl: './aside.css',
  encapsulation: ViewEncapsulation.None
})
export class Aside implements OnInit {
  items: MenuItem[] = [];

  ngOnInit() {
    this.items = [
      {
        label: 'Dashboard',
        icon: 'fa-solid fa-house',
        routerLink: ['/dashboard']
      },
      {
        label: 'Reservas',
        icon: 'fa-solid fa-calendar',
        items: [
          { label: 'Nueva Reserva', icon: 'pi pi-plus', routerLink: ['/reservas/nueva'] },
          { label: 'Listado Reservas', icon: 'pi pi-list', routerLink: ['/reservas'] },
          { label: 'Check-in / Check-out', icon: 'pi pi-sign-in', routerLink: ['/reservas/check'] },
        ]
      },
      {
        label: 'Clientes & Huéspedes',
        icon: 'fa-solid fa-users',
        items: [
          { label: 'Clientes', icon: 'pi pi-id-card', routerLink: ['/clientes'] },
          { label: 'Huéspedes', icon: 'pi pi-user', routerLink: ['/huespedes'] }
        ]
      },
      {
        label: 'Habitaciones',
        icon: 'fa-solid fa-hotel',
        items: [
          { label: 'Habitaciones', icon: 'pi pi-home', routerLink: ['/habitaciones'] },
          { label: 'Estados', icon: 'pi pi-refresh', routerLink: ['/habitaciones/estados'] },
          { label: 'Calendario', icon: 'pi pi-calendar-times', routerLink: ['/habitaciones/calendario'] }
        ]
      },
      {
        label: 'Tarifas & Paquetes',
        icon: 'fa-solid fa-dollar-sign',
        items: [
          { label: 'Tarifas', icon: 'pi pi-tag', routerLink: ['/tarifas'] },
          { label: 'Paquetes', icon: 'pi pi-briefcase', routerLink: ['/paquetes'] }
        ]
      },
      {
        label: 'Servicios & Consumos',
        icon: 'fa-solid fa-concierge-bell',
        items: [
          { label: 'Servicios', icon: 'pi pi-cog', routerLink: ['/servicios'] },
          { label: 'Artículos', icon: 'pi pi-shopping-bag', routerLink: ['/articulos'] },
          { label: 'Consumos', icon: 'pi pi-shopping-cart', routerLink: ['/consumos'] }
        ]
      },
      {
        label: 'Inventario',
        icon: 'fa-solid fa-boxes',
        routerLink: ['/inventario']
      },
      {
        label: 'Facturación & Pagos',
        icon: 'fa-solid fa-file-invoice-dollar',
        items: [
          { label: 'Facturas', icon: 'pi pi-file', routerLink: ['/facturas'] },
          { label: 'Pagos', icon: 'pi pi-wallet', routerLink: ['/pagos'] },
          { label: 'Cargos', icon: 'pi pi-exclamation-triangle', routerLink: ['/cargos'] },
          { label: 'Descuentos', icon: 'pi pi-percentage', routerLink: ['/descuentos'] }
        ]
      },
      {
        label: 'Seguridad',
        icon: 'fa-solid fa-shield-alt',
        items: [
          { label: 'Usuarios', icon: 'pi pi-user', routerLink: ['/usuarios'] },
          { label: 'Roles', icon: 'pi pi-lock', routerLink: ['/roles'] }
        ]
      },
      {
        label: 'Reportes',
        icon: 'fa-solid fa-chart-bar',
        routerLink: ['/reportes']
      },
      {
        label: 'Configuración',
        icon: 'fa-solid fa-cogs',
        routerLink: ['/config']
      }
    ];
  }
}
