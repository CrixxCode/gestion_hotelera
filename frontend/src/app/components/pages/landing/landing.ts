import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

interface NavLink {
  label: string;
  sectionId: string;
}

interface HeroStat {
  value: string;
  label: string;
  detail: string;
  icon: string;
}

interface PainPoint {
  title: string;
  description: string;
  icon: string;
}

interface SolutionStep {
  title: string;
  description: string;
}

interface FeatureItem {
  title: string;
  description: string;
  icon: string;
}

interface BenefitItem {
  title: string;
  description: string;
  icon: string;
}

interface AudienceItem {
  title: string;
  detail: string;
  icon: string;
}

@Component({
  selector: 'app-landing',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './landing.html',
  styleUrl: './landing.css',
})
export class LandingPage {
  readonly year = new Date().getFullYear();

  readonly navLinks: NavLink[] = [
    { label: 'Problemas', sectionId: 'problemas' },
    { label: 'Solucion', sectionId: 'solucion' },
    { label: 'Funcionalidades', sectionId: 'funcionalidades' },
    { label: 'Beneficios', sectionId: 'beneficios' },
    { label: 'Para quien', sectionId: 'publico' },
  ];

  readonly heroStats: HeroStat[] = [
    {
      value: 'Todo en uno',
      label: 'Operacion centralizada',
      detail: 'Reservas, habitaciones, pagos, servicios e inventario conectados.',
      icon: 'pi pi-objects-column',
    },
    {
      value: 'Menos reprocesos',
      label: 'Flujos estandarizados',
      detail: 'Check-in, facturacion y reportes en un mismo ciclo operativo.',
      icon: 'pi pi-sync',
    },
    {
      value: 'Control diario',
      label: 'Datos para decidir',
      detail: 'Visualiza ocupacion, ingresos y rendimiento de forma clara.',
      icon: 'pi pi-chart-line',
    },
  ];

  readonly painPoints: PainPoint[] = [
    {
      title: 'Reservas desorganizadas',
      description:
        'Confirmaciones en varios canales y datos duplicados generan sobreventas o huecos de ocupacion.',
      icon: 'pi pi-calendar-times',
    },
    {
      title: 'Control manual de habitaciones',
      description:
        'Actualizar estados en hojas de calculo retrasa la operacion de recepcion y housekeeping.',
      icon: 'pi pi-building',
    },
    {
      title: 'Errores en pagos y facturacion',
      description:
        'Cobros incompletos, notas de ajuste dispersas y conciliacion lenta afectan el flujo de caja.',
      icon: 'pi pi-credit-card',
    },
    {
      title: 'Reportes poco accionables',
      description:
        'Sin indicadores confiables es dificil anticipar temporadas, costos y demanda real.',
      icon: 'pi pi-chart-bar',
    },
    {
      title: 'Inventario y servicios sin trazabilidad',
      description:
        'No saber consumos por habitacion o servicio impacta costos y calidad de atencion.',
      icon: 'pi pi-box',
    },
  ];

  readonly solutionSteps: SolutionStep[] = [
    {
      title: 'Centraliza la operacion de tu hotel en una sola plataforma',
      description:
        'Wayra concentra recepcion, caja, inventario y administracion para que tu equipo trabaje con el mismo dato.',
    },
    {
      title: 'Automatiza tareas clave sin perder control',
      description:
        'Disponibilidad, cargos, pagos y estados operativos se actualizan en tiempo real entre areas.',
    },
    {
      title: 'Toma decisiones con reportes claros',
      description:
        'Consulta indicadores de ocupacion, ingresos y servicios para ajustar estrategia comercial y operativa.',
    },
  ];

  readonly features: FeatureItem[] = [
    {
      title: 'Gestion de reservas',
      description: 'Registra, modifica y da seguimiento a reservas con estado y trazabilidad completa.',
      icon: 'pi pi-calendar',
    },
    {
      title: 'Habitaciones y disponibilidad',
      description: 'Controla tipos, tarifas, ocupacion y estados operativos por habitacion.',
      icon: 'pi pi-home',
    },
    {
      title: 'Clientes y huespedes',
      description: 'Consolida datos de clientes para check-in agil y mejor servicio.',
      icon: 'pi pi-id-card',
    },
    {
      title: 'Pagos, facturas y notas de credito',
      description: 'Administra cobros, saldos y documentos de forma ordenada y auditable.',
      icon: 'pi pi-wallet',
    },
    {
      title: 'Servicios, paquetes y promociones',
      description: 'Configura ofertas y servicios extra para aumentar el valor por reserva.',
      icon: 'pi pi-megaphone',
    },
    {
      title: 'Inventario y control financiero',
      description: 'Monitorea entradas, salidas y costos para evitar quiebres o sobrecostos.',
      icon: 'pi pi-box',
    },
    {
      title: 'Reportes administrativos',
      description: 'Analiza ocupacion, ingresos y actividad con informacion lista para gestion.',
      icon: 'pi pi-chart-line',
    },
    {
      title: 'Roles, usuarios y permisos',
      description: 'Protege la operacion con accesos por rol y control por area.',
      icon: 'pi pi-shield',
    },
  ];

  readonly benefits: BenefitItem[] = [
    {
      title: 'Ahorro de tiempo operativo',
      description: 'Tu equipo dedica menos tiempo a tareas manuales y mas tiempo al huesped.',
      icon: 'pi pi-clock',
    },
    {
      title: 'Menos errores diarios',
      description: 'Procesos estandarizados reducen errores en reservas, cobros y registros.',
      icon: 'pi pi-check-circle',
    },
    {
      title: 'Mejor control administrativo',
      description: 'Supervisa indicadores y operaciones sin depender de reportes aislados.',
      icon: 'pi pi-briefcase',
    },
    {
      title: 'Experiencia mas fluida para el huesped',
      description: 'Check-in agil, informacion clara y mejor coordinacion entre areas.',
      icon: 'pi pi-star',
    },
    {
      title: 'Informacion centralizada',
      description: 'Una sola fuente de datos para recepcion, caja, administracion y gerencia.',
      icon: 'pi pi-database',
    },
    {
      title: 'Decisiones basadas en reportes',
      description: 'Evalua resultados con datos actualizados y consistentes.',
      icon: 'pi pi-chart-scatter',
    },
  ];

  readonly audiences: AudienceItem[] = [
    {
      title: 'Hoteles pequenos y medianos',
      detail: 'Estandariza la gestion sin procesos complejos ni hojas dispersas.',
      icon: 'pi pi-building-columns',
    },
    {
      title: 'Hostales',
      detail: 'Controla alta rotacion de reservas y recepcion con mayor orden.',
      icon: 'pi pi-building',
    },
    {
      title: 'Apartahoteles',
      detail: 'Gestiona estancias, servicios y disponibilidad desde un mismo panel.',
      icon: 'pi pi-home',
    },
    {
      title: 'Alojamientos turisticos',
      detail: 'Centraliza operacion y control para crecer con procesos mas profesionales.',
      icon: 'pi pi-globe',
    },
    {
      title: 'Administradores hoteleros',
      detail: 'Visualiza indicadores clave y toma decisiones con respaldo operativo.',
      icon: 'pi pi-users',
    },
  ];

  mobileMenuOpen = false;

  toggleMobileMenu(): void {
    this.mobileMenuOpen = !this.mobileMenuOpen;
  }

  closeMobileMenu(): void {
    this.mobileMenuOpen = false;
  }

  scrollToSection(event: Event, sectionId: string): void {
    event.preventDefault();

    const section = document.getElementById(sectionId);
    if (!section) return;

    const header = document.querySelector('.wayra-header') as HTMLElement | null;
    const headerOffset = header?.offsetHeight ?? 0;
    const sectionTop = section.getBoundingClientRect().top + window.scrollY;
    const targetTop = Math.max(sectionTop - headerOffset - 12, 0);
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    window.scrollTo({
      top: targetTop,
      behavior: prefersReducedMotion ? 'auto' : 'smooth',
    });

    window.history.replaceState(null, '', `#${sectionId}`);
    this.closeMobileMenu();
  }

  trackByIndex(index: number): number {
    return index;
  }
}
