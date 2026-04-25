import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

interface LandingStat {
  value: string;
  label: string;
  detail: string;
}

interface LandingModule {
  title: string;
  description: string;
  routes: string;
  tone: 'blue' | 'green' | 'gold' | 'violet' | 'teal' | 'pink';
  icon: string;
}

interface LandingStep {
  title: string;
  description: string;
}

interface LandingArchitectureBlock {
  title: string;
  stack: string;
  bullets: string[];
}

interface FaqItem {
  question: string;
  answer: string;
}

@Component({
  selector: 'app-landing',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './landing.html',
  styleUrl: './landing.css',
})
export class LandingPage {
  readonly stats: LandingStat[] = [
    { value: '31', label: 'rutas funcionales', detail: 'sin contar redirecciones ni comodines' },
    { value: '23', label: 'modulos lazy-load', detail: 'cargados bajo demanda en Angular' },
    { value: '13', label: 'apps de negocio', detail: 'integradas en Django REST' },
    { value: '4', label: 'tableros de reportes', detail: 'ejecutivo, ingresos, ocupacion y servicios' },
  ];

  readonly modules: LandingModule[] = [
    {
      title: 'Reservas y estancias',
      description: 'Gestiona reservas, check-in, check-out, calendario y estados de ocupacion en una sola vista.',
      routes: '/reservas',
      tone: 'blue',
      icon: 'RS',
    },
    {
      title: 'Habitaciones, tipos y tarifas',
      description: 'Administra inventario de habitaciones, tipos, amenidades y tarifas activas para reservas nuevas.',
      routes: '/habitaciones | /tipos-habitacion | /tarifas-habitacion',
      tone: 'teal',
      icon: 'HB',
    },
    {
      title: 'Facturacion y pagos',
      description: 'Controla facturas por reserva, cobros, notas de credito, reembolsos y estado de cartera.',
      routes: '/facturas | /pagos | /reembolsos',
      tone: 'gold',
      icon: 'FC',
    },
    {
      title: 'Inventario operativo',
      description: 'Administra items, inventario por habitacion y movimientos de entrada/salida con alertas de stock.',
      routes: '/items | /inventario-habitaciones | /movimientos-inventario',
      tone: 'green',
      icon: 'IV',
    },
    {
      title: 'Reportes y control financiero',
      description: 'Analiza KPIs, ingresos, ocupacion y servicios con exportacion PDF/CSV y trazabilidad de actividad.',
      routes: '/reportes | /actividad | /control-financiero | /consolidado-ingresos',
      tone: 'violet',
      icon: 'RP',
    },
    {
      title: 'Seguridad y configuracion',
      description: 'RBAC por roles/recursos, usuarios, branding del hotel, politicas de reserva y ajustes operativos.',
      routes: '/usuarios | /roles | /recursos | /hotel-config',
      tone: 'pink',
      icon: 'SG',
    },
  ];

  readonly steps: LandingStep[] = [
    {
      title: 'Configura tu hotel',
      description:
        'Define datos generales, pisos, horarios de check-in/check-out, moneda, impuestos y parametros financieros.',
    },
    {
      title: 'Opera recepcion y caja',
      description:
        'Registra reservas, gestiona estancias, emite facturas y aplica pagos o ajustes de forma centralizada.',
    },
    {
      title: 'Controla y mejora',
      description:
        'Monitorea inventario, mantenimiento, limpieza y reportes para tomar decisiones con datos reales.',
    },
  ];

  readonly architecture: LandingArchitectureBlock[] = [
    {
      title: 'Frontend',
      stack: 'Angular 20 + PrimeNG + Tailwind',
      bullets: [
        'Aplicacion SPA con rutas protegidas y modulos lazy-load.',
        'Vistas operativas para reservas, inventario, facturacion y reportes.',
        'Flujos de interfaz orientados a personal de recepcion y administracion.',
      ],
    },
    {
      title: 'Backend',
      stack: 'Django + Django REST Framework',
      bullets: [
        'API por dominios: clients, rooms, reservations, billing, inventory, finance y reports.',
        'Autenticacion por sesion con CSRF y control de permisos por scopes.',
        'Documentacion tecnica disponible en /api/docs/.',
      ],
    },
    {
      title: 'Seguridad y datos',
      stack: 'RBAC + auditoria operativa',
      bullets: [
        'Gestion de usuarios, roles, recursos y asignacion de accesos.',
        'Registro de actividad y notificaciones para eventos criticos.',
        'Base de datos SQLite por defecto y soporte PostgreSQL por entorno.',
      ],
    },
  ];

  readonly faqs: FaqItem[] = [
    {
      question: '?Necesito instalar software en cada computador del hotel?',
      answer:
        'No. El proyecto funciona con frontend web y backend API centralizado. Cada usuario entra con su cuenta y permisos.',
    },
    {
      question: '?El sistema ya tiene control de roles y permisos?',
      answer:
        'Si. Incluye RBAC con modulos de usuarios, roles y recursos, y validacion por scopes en frontend y backend.',
    },
    {
      question: '?Que operaciones de recepcion estan cubiertas hoy?',
      answer:
        'Reservas, check-in/check-out, gestion de habitaciones, facturacion por estancia, pagos y seguimiento de saldos.',
    },
    {
      question: '?Se puede exportar informacion para gestion administrativa?',
      answer:
        'Si. Diferentes modulos permiten exportacion CSV y el modulo de reportes permite exportar PDF del tablero activo.',
    },
    {
      question: '?Que motor de base de datos usa el proyecto?',
      answer:
        'La configuracion por defecto usa SQLite y puede cambiarse a PostgreSQL mediante variables de entorno.',
    },
  ];

  activeFaqIndex = 0;

  toggleFaq(index: number): void {
    this.activeFaqIndex = this.activeFaqIndex === index ? -1 : index;
  }

  trackByIndex(index: number): number {
    return index;
  }
}
