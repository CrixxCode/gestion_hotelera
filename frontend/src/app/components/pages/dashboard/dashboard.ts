import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ChartModule } from 'primeng/chart';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, ChartModule, FormsModule],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css',
})
export class Dashboard {
  constructor(private router: Router) {
    this.generateCalendar();

    // === Inicializar gráfica de ocupación semanal ===
    this.occWeekData = {
      labels: ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'],
      datasets: [
        {
          label: 'Ocupación',
          data: this.occDataByMonth['Octubre'],
          borderColor: '#1E40AF',
          backgroundColor: 'rgba(30,64,175,0.1)',
          fill: true,
          tension: 0.3,
        },
      ],
    };

    this.occWeekOptions = {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          ticks: { callback: (v: number) => `${v}%` },
          grid: { color: '#E5E7EB' },
        },
        x: { grid: { display: false } },
      },
    };
  }

  // ============ KPIs dinámicos ============
  kpis = [
    {
      label: 'Ocupación',
      value: '78%',
      help: 'vs. capacidad total',
      icon: 'fa-bed',
      tone: 'blue',
    },
    {
      label: 'Ingresos hoy',
      value: '$4,250',
      help: '↑ 12% respecto a ayer',
      icon: 'fa-dollar-sign',
      tone: 'green',
    },
    {
      label: 'Check-ins hoy',
      value: '12',
      help: 'Próximo en 35 min',
      icon: 'fa-right-to-bracket',
      tone: 'violet',
    },
    {
      label: 'Check-outs hoy',
      value: '8',
      help: '2 con retraso',
      icon: 'fa-right-from-bracket',
      tone: 'slate',
    },
    {
      label: 'RevPAR',
      value: '$245.700',
      help: 'Ingreso por hab. disponible',
      icon: 'fa-chart-line',
      tone: 'blue',
    },
  ];

  // ============ Filtro de mes ============
  months = [
    'Enero',
    'Febrero',
    'Marzo',
    'Abril',
    'Mayo',
    'Junio',
    'Julio',
    'Agosto',
    'Septiembre',
    'Octubre',
    'Noviembre',
    'Diciembre',
  ];
  selectedMonth = 'Octubre';

  // ============ Ocupación por semana ============
  occWeekData: any;
  occWeekOptions: any;
  occDataByMonth: Record<string, number[]> = {
    Enero: [55, 60, 62, 65, 68, 70, 72],
    Febrero: [62, 65, 70, 73, 75, 78, 80],
    Marzo: [65, 68, 70, 72, 74, 76, 78],
    Octubre: [65, 70, 75, 78, 82, 85, 80],
  };

  updateOccData() {
    const data = this.occDataByMonth[this.selectedMonth] || [];
    this.occWeekData.datasets[0].data = data;
    this.occWeekData = { ...this.occWeekData }; // forzar refresco
  }

  // ============ Habitaciones por categoría ============
  roomCatData = {
    labels: ['Individual', 'Doble', 'Suite', 'Familiar'],
    datasets: [
      {
        data: [25, 35, 20, 10],
        backgroundColor: ['#2563EB', '#10B981', '#F59E0B', '#EF4444'],
        borderWidth: 0,
      },
    ],
  };
  roomCatOptions = {
    responsive: true,
    plugins: { legend: { position: 'bottom' } },
  };

  // ============ Calendario ============
  currentDate = new Date();
  currentMonth = this.currentDate.getMonth();
  currentYear = this.currentDate.getFullYear();
  currentMonthName = this.months[this.currentMonth];
  weekDays = ['D', 'L', 'M', 'X', 'J', 'V', 'S'];
  calendarMatrix: any[][] = [];

  generateCalendar() {
    const firstDay = new Date(this.currentYear, this.currentMonth, 1);
    const startDay = firstDay.getDay();
    const daysInMonth = new Date(
      this.currentYear,
      this.currentMonth + 1,
      0
    ).getDate();
    const prevDays = new Date(this.currentYear, this.currentMonth, 0).getDate();

    this.calendarMatrix = [];
    let week = [];

    for (let i = 0; i < startDay; i++) {
      week.push({ num: prevDays - startDay + i + 1, current: false });
    }

    for (let day = 1; day <= daysInMonth; day++) {
      week.push({ num: day, current: true });
      if (week.length === 7) {
        this.calendarMatrix.push(week);
        week = [];
      }
    }

    if (week.length > 0) {
      const next = 1;
      while (week.length < 7) {
        week.push({ num: next + week.length, current: false });
      }
      this.calendarMatrix.push(week);
    }
  }

  prevMonth() {
    if (this.currentMonth === 0) {
      this.currentMonth = 11;
      this.currentYear--;
    } else this.currentMonth--;
    this.currentMonthName = this.months[this.currentMonth];
    this.generateCalendar();
  }

  nextMonth() {
    if (this.currentMonth === 11) {
      this.currentMonth = 0;
      this.currentYear++;
    } else this.currentMonth++;
    this.currentMonthName = this.months[this.currentMonth];
    this.generateCalendar();
  }

  selectDay(day: any) {
    if (day.current)
      alert(`Fecha seleccionada: ${day.num} ${this.currentMonthName} ${this.currentYear}`);
  }

  // ============ Próximas llegadas ============
  nextArrivals = [
    {
      client: 'María González',
      room: '301 - Suite',
      arrival: 'Hoy, 14:00',
      departure: '20/10/2025',
      status: 'Pendiente',
    },
    {
      client: 'Carlos Rodríguez',
      room: '205 - Doble',
      arrival: 'Hoy, 15:30',
      departure: '19/10/2025',
      status: 'Pendiente',
    },
    {
      client: 'Ana Martínez',
      room: '110 - Individual',
      arrival: 'Hoy, 18:00',
      departure: '18/10/2025',
      status: 'Pendiente',
    },
  ];

  goToCheckin(guest: any) {
    this.router.navigate(['/checkin', guest.client]);
  }

  // ============ NUEVAS SECCIONES ============

  // 🕓 Reservas recientes
  recentBookings = [
    { client: 'Laura Pérez', room: '104 - Doble', date: '16/10/2025' },
    { client: 'Jorge Castillo', room: '302 - Suite', date: '16/10/2025' },
    { client: 'Valentina López', room: '207 - Familiar', date: '15/10/2025' },
    { client: 'Andrés Díaz', room: '118 - Individual', date: '15/10/2025' },
  ];

  // ✅ Últimos check-in
  recentCheckins = [
    { client: 'María González', room: '301 - Suite', time: '09:15' },
    { client: 'Pedro Torres', room: '208 - Doble', time: '09:40' },
    { client: 'Lucía Romero', room: '110 - Individual', time: '10:00' },
  ];

  // 🚪 Últimos check-out
  recentCheckouts = [
    { client: 'Carlos Ruiz', room: '215 - Doble', time: '08:30' },
    { client: 'Ana Morales', room: '320 - Suite', time: '09:05' },
    { client: 'Miguel Castro', room: '106 - Individual', time: '09:20' },
  ];

  // 💰 Pendientes de pago
  pendingPayments = [
    { client: 'Tatiana Gómez', amount: '$340.000' },
    { client: 'Sergio Ramírez', amount: '$210.000' },
    { client: 'Verónica Salas', amount: '$480.000' },
    { client: 'Oscar Fuentes', amount: '$155.000' },
  ];
}

