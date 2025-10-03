import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ChartModule } from 'primeng/chart';

type BasicGuest = {
  code: string;
  guest: string;
  room?: string;
  roomType: string;
  nights?: number;
  when: string;         // fecha/hora corta para card
  source?: 'Directo'|'OTA'|'Agencia';
  amount?: string;      // para pagos
};

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, ChartModule],
  templateUrl: './dashboard.html'
})
export class Dashboard {
  // ===== KPI rápidos (muestra en cards arriba) =====
  kpis = [
    { label: 'Ocupación', value: '78%', help: 'vs. capacidad total' },
    { label: 'ADR', value: '$ 315.000', help: 'Tarifa diaria promedio' },
    { label: 'RevPAR', value: '$ 245.700', help: 'Ingreso por hab. disp.' },
    { label: 'Ingresos (hoy)', value: '$ 12.8M', help: 'Alojamiento + consumos' },
  ];

  // ===== Cards de listas (datos falsos) =====
  lastReservations: BasicGuest[] = [
    { code: 'R-20460', guest: 'N. Rivera',   roomType: 'Standard Queen', nights: 2, source: 'OTA',     when: 'hace 15 min' },
    { code: 'R-20459', guest: 'S. Torres',   roomType: 'Suite Jr',       nights: 1, source: 'Directo', when: 'hace 32 min' },
    { code: 'R-20458', guest: 'E. Díaz',     roomType: 'Twin Superior',  nights: 4, source: 'Agencia', when: 'hace 1 h' },
    { code: 'R-20457', guest: 'M. Castro',   roomType: 'Deluxe King',    nights: 2, source: 'Directo', when: 'hace 2 h' },
  ];

  lastCheckins: BasicGuest[] = [
    { code: 'R-20431', guest: 'L. Gómez',   room: '312', roomType: 'Standard Queen', when: '13:42' },
    { code: 'R-20429', guest: 'P. Aguilar', room: '507', roomType: 'Twin Superior',  when: '12:55' },
    { code: 'R-20427', guest: 'C. Díaz',    room: '221', roomType: 'Deluxe King',    when: '12:20' },
  ];

  lastCheckouts: BasicGuest[] = [
    { code: 'R-20390', guest: 'A. Pérez',  room: '215', roomType: 'Twin Superior',  when: '10:33' },
    { code: 'R-20388', guest: 'M. Arias',  room: '406', roomType: 'Deluxe King',    when: '10:10' },
    { code: 'R-20385', guest: 'S. Ruiz',   room: '118', roomType: 'Standard Queen', when: '09:55' },
  ];

  pendingPayments: BasicGuest[] = [
    { code: 'R-20412', guest: 'J. Rojas',  room: '334', roomType: 'Deluxe King', amount: '$ 420.000', when: 'vence hoy' },
    { code: 'R-20405', guest: 'E. Mena',   room: '142', roomType: 'Twin Superior', amount: '$ 180.000', when: 'venció ayer' },
    { code: 'R-20399', guest: 'D. Soto',   room: '510', roomType: 'Suite Jr', amount: '$ 1.250.000', when: 'venc. 2 días' },
  ];

  outOfOrderRooms = [
    { room: '803', reason: 'Mantenimiento A/C', eta: '2 días' },
    { room: '109', reason: 'Pintura',           eta: '1 día'  },
  ];

  // ===== Charts (con tamaño controlado) =====
  occData: any; occOptions: any;           // doughnut ocupación
  revenueData: any; revenueOptions: any;   // barras ingresos por canal
  occTrendData: any; occTrendOptions: any; // línea ocupación 14 días

  constructor() {
    const black = '#111827';
    const gray = '#6B7280';
    const gold = '#F59E0B';
    const blue = '#1E40AF';

    // DONA Ocupación
    this.occData = {
      labels: ['Ocupadas', 'Disponibles', 'Fuera de servicio'],
      datasets: [{ data: [64, 14, 4], backgroundColor: ['#2563EB', '#10B981', '#F87171'], borderWidth: 0 }]
    };
    this.occOptions = {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '60%',
      layout: { padding: 8 },
      plugins: { legend: { position: 'bottom', labels: { color: black } } }
    };

    // BARRAS Ingresos por canal
    this.revenueData = {
      labels: ['Directo', 'OTA', 'Agencia'],
      datasets: [
        { label: 'Alojamiento', data: [8.2, 5.6, 3.1], backgroundColor: blue },
        { label: 'Consumos',    data: [2.1, 1.4, 0.8], backgroundColor: gold }
      ]
    };
    this.revenueOptions = {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { ticks: { color: gray }, grid: { display: false } },
        y: { ticks: { color: gray, callback: (v: number) => `$ ${v}M` }, grid: { color: '#E5E7EB' } }
      },
      plugins: { legend: { labels: { color: black } } }
    };

    // LÍNEA Ocupación 14 días
    const days = Array.from({ length: 14 }, (_, i) => `D-${13 - i}`);
    const occSeries = [62, 59, 61, 65, 66, 68, 64, 63, 67, 70, 72, 74, 76, 78];
    this.occTrendData = {
      labels: days,
      datasets: [{ label: 'Ocupación', data: occSeries, borderColor: blue, backgroundColor: 'rgba(30,64,175,0.15)', tension: 0.3, fill: true, pointRadius: 2 }]
    };
    this.occTrendOptions = {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { ticks: { color: gray }, grid: { display: false } },
        y: { ticks: { color: gray, callback: (v: number) => `${v}%` }, grid: { color: '#E5E7EB' } }
      },
      plugins: { legend: { labels: { color: black } } }
    };
  }
}
