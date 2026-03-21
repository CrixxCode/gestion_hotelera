import { Component, OnInit } from '@angular/core';
import { ClientI } from '../client-model';
import { ClientsService } from '../../../services/client';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CreateClient } from '../create-client/create-client';
import { UpdateClient } from '../update-client/update-client';
import { ConfirmDialogModule } from 'primeng/confirmdialog';
import { ConfirmationService } from 'primeng/api';

@Component({
  selector: 'app-show-client',
  templateUrl: './list-clients.html',
  styleUrls: ['./list-clients.css'],
  standalone: true,
  imports: [CommonModule, FormsModule, CreateClient, UpdateClient, ConfirmDialogModule],
  providers: [ConfirmationService]
})
export class ListClients implements OnInit {
  clients: ClientI[] = [];
  filteredClients: ClientI[] = [];
  paginatedClients: ClientI[] = [];

  search = '';
  statusFilter = 'ALL';
  typeFilter = 'ALL';

  selectedClient: ClientI | null = null;
  showCreateOverlay = false;
  showUpdateOverlay = false;
  clientToEdit: ClientI | null = null;

  currentPage = 1;
  perPage = 6;
  totalPages = 0;

  loading = false;

  statCards = [
    {
      label: 'Total clientes',
      value: '0',
      sub: 'Registrados',
      icon: 'fa-solid fa-users',
      color: '#3b82f6',
      bg: '#e8f1ff'
    },
    {
      label: 'Clientes VIP',
      value: '0',
      sub: 'Alto valor',
      icon: 'fa-solid fa-star',
      color: '#d97706',
      bg: '#fff6df'
    },
    {
      label: 'Huespedes actuales',
      value: '0',
      sub: 'En estancia',
      icon: 'fa-solid fa-user-check',
      color: '#059669',
      bg: '#e8faf2'
    },
    {
      label: 'Clientes nuevos',
      value: '0',
      sub: 'Este mes',
      icon: 'fa-solid fa-user-plus',
      color: '#7c3aed',
      bg: '#f3edff'
    }
  ];

  constructor(
    private clientsService: ClientsService,
    private confirmationService: ConfirmationService
  ) { }

  ngOnInit(): void {
    this.loadClients();
  }

  loadClients(): void {
    this.loading = true;

    this.clientsService.listClients().subscribe({
      next: (data) => {
        this.clients = data;
        this.updateStats();
        this.applyFilters();
        this.loading = false;
      },
      error: (error) => {
        console.error('Error loading clients:', error);
        this.loading = false;
      }
    });
  }

  updateStats(): void {
    const totalClients = this.clients.length;
    const vipClients = this.clients.filter((c) => this.normalizeType(c.client_type) === 'VIP').length;
    const currentGuests = this.clients.filter((c) => this.normalizeStatus(c.status) === 'HUESPED_ACTUAL').length;
    const now = new Date();
    const newClients = this.clients.filter((c) => {
      if (!c.created_at) return false;
      const createdAt = new Date(c.created_at);
      if (Number.isNaN(createdAt.getTime())) return false;
      return createdAt.getMonth() === now.getMonth() && createdAt.getFullYear() === now.getFullYear();
    }).length;

    this.statCards[0].value = totalClients.toString();
    this.statCards[1].value = vipClients.toString();
    this.statCards[2].value = currentGuests.toString();
    this.statCards[3].value = newClients.toString();
  }

  applyFilters(): void {
    this.filteredClients = this.clients.filter((client) => {
      const searchValue = this.search.toLowerCase().trim();

      const matchesSearch =
        !searchValue ||
        client.full_name?.toLowerCase().includes(searchValue) ||
        client.first_name?.toLowerCase().includes(searchValue) ||
        client.last_name?.toLowerCase().includes(searchValue) ||
        client.email?.toLowerCase().includes(searchValue) ||
        client.document_number?.toLowerCase().includes(searchValue) ||
        client.country?.toLowerCase().includes(searchValue);

      const matchesStatus =
        this.statusFilter === 'ALL' || this.normalizeStatus(client.status) === this.statusFilter;

      const matchesType =
        this.typeFilter === 'ALL' || this.normalizeType(client.client_type) === this.typeFilter;

      return !!matchesSearch && matchesStatus && matchesType;
    });

    this.currentPage = 1;
    this.updatePagination();
  }

  updatePagination(): void {
    this.totalPages = Math.ceil(this.filteredClients.length / this.perPage);

    const start = (this.currentPage - 1) * this.perPage;
    const end = start + this.perPage;

    this.paginatedClients = this.filteredClients.slice(start, end);
  }

  changePage(page: number): void {
    if (page < 1 || page > this.totalPages) return;
    this.currentPage = page;
    this.updatePagination();
  }

  openDetail(client: ClientI): void {
    this.selectedClient = client;
  }

  openCreateOverlay(): void {
    this.showUpdateOverlay = false;
    this.selectedClient = null;
    this.showCreateOverlay = true;
  }

  closeCreateOverlay(): void {
    this.showCreateOverlay = false;
  }

  onClientCreated(): void {
    this.showCreateOverlay = false;
    this.loadClients();
  }

  openUpdateOverlay(client: ClientI | null | undefined): void {
    if (!client) return;
    this.showCreateOverlay = false;
    this.selectedClient = null;
    this.clientToEdit = client;
    this.showUpdateOverlay = true;
  }

  closeUpdateOverlay(): void {
    this.showUpdateOverlay = false;
    this.clientToEdit = null;
  }

  onClientUpdated(): void {
    this.showUpdateOverlay = false;
    this.clientToEdit = null;
    this.selectedClient = null;
    this.loadClients();
  }

  confirmDelete(client: ClientI | null | undefined): void {
    if (!client?.id) return;

    const fullName = client.full_name || `${client.first_name} ${client.last_name}`;

    this.confirmationService.confirm({
      message: `Deseas eliminar a ${fullName}?`,
      header: 'Confirmar eliminacion',
      icon: 'pi pi-exclamation-triangle',
      acceptLabel: 'Si, eliminar',
      rejectLabel: 'Cancelar',
      key: 'clientDelete',
      acceptButtonStyleClass: 'p-button-danger',
      rejectButtonStyleClass: 'p-button-secondary p-button-outlined',
      defaultFocus: 'reject',
      accept: () => {
        this.clientsService.deleteClient(client.id!).subscribe({
          next: () => {
            this.selectedClient = null;
            this.loadClients();
          },
          error: (error) => {
            console.error('No se pudo eliminar el cliente:', error);
          }
        });
      }
    });
  }

  closeDetail(): void {
    this.selectedClient = null;
  }

  getStatusLabel(status: string | undefined): string {
    const normalized = this.normalizeStatus(status);

    switch (normalized) {
      case 'ACTIVO':
        return 'Activo';
      case 'INACTIVO':
        return 'Inactivo';
      case 'HUESPED_ACTUAL':
        return 'Huesped actual';
      default:
        return 'Sin estado';
    }
  }

  getTypeLabel(type: string | undefined): string {
    const normalized = this.normalizeType(type);

    switch (normalized) {
      case 'VIP':
        return 'VIP';
      case 'FRECUENTE':
        return 'Frecuente';
      case 'REGULAR':
        return 'Regular';
      default:
        return 'Sin tipo';
    }
  }

  getStatusStyles(status: string | undefined): { bg: string; color: string; dot: string } {
    const normalized = this.normalizeStatus(status);

    switch (normalized) {
      case 'ACTIVO':
        return { bg: '#ecfdf5', color: '#059669', dot: '#10b981' };
      case 'INACTIVO':
        return { bg: '#f3f4f6', color: '#6b7280', dot: '#9ca3af' };
      case 'HUESPED_ACTUAL':
        return { bg: '#eff6ff', color: '#2563eb', dot: '#3b82f6' };
      default:
        return { bg: '#f3f4f6', color: '#6b7280', dot: '#9ca3af' };
    }
  }

  getTypeStyles(type: string | undefined): { bg: string; color: string } {
    const normalized = this.normalizeType(type);

    switch (normalized) {
      case 'VIP':
        return { bg: '#fffbeb', color: '#d97706' };
      case 'FRECUENTE':
        return { bg: '#f5f3ff', color: '#7c3aed' };
      case 'REGULAR':
        return { bg: '#f3f4f6', color: '#6b7280' };
      default:
        return { bg: '#f3f4f6', color: '#6b7280' };
    }
  }

  getInitials(client: ClientI): string {
    const first = client.first_name?.trim().charAt(0) || '';
    const last = client.last_name?.trim().charAt(0) || '';
    return `${first}${last}`.toUpperCase() || 'CL';
  }

  getCountryCode(country?: string): string {
    if (!country) return '--';
    return country.trim().slice(0, 2).toUpperCase();
  }

  getClientSinceYear(client: ClientI): string {
    const date = client.created_at ? new Date(client.created_at) : null;
    if (!date || Number.isNaN(date.getTime())) return 'N/D';
    return `${date.getFullYear()}`;
  }

  getEstimatedSpent(client: ClientI): string {
    const nights = client.total_stay_nights || 0;
    const estimated = nights * 210000;

    return new Intl.NumberFormat('es-CO', {
      style: 'currency',
      currency: 'COP',
      maximumFractionDigits: 0
    }).format(estimated);
  }

  getClientPreferences(client: ClientI): string[] {
    const normalized = this.normalizeType(client.client_type);

    if (normalized === 'VIP') return ['Suite premium', 'Traslado aeropuerto'];
    if (normalized === 'FRECUENTE') return ['Desayuno incluido', 'Check-in agil'];
    return ['Habitacion doble', 'Solicitudes basicas'];
  }

  formatDate(date: string | null | undefined): string {
    if (!date) return 'No registra';

    const parsedDate = new Date(date);
    if (Number.isNaN(parsedDate.getTime())) return date;

    return parsedDate.toLocaleDateString('es-CO', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  }

  trackByClient(index: number, client: ClientI): number | undefined {
    return client.id;
  }

  private normalizeStatus(status: string | undefined): 'ACTIVO' | 'INACTIVO' | 'HUESPED_ACTUAL' | '' {
    if (!status) return '';
    const value = status.toUpperCase();

    if (value === 'ACTIVO' || value === 'ACTIVE') return 'ACTIVO';
    if (value === 'INACTIVO' || value === 'INACTIVE') return 'INACTIVO';
    if (value === 'HUESPED_ACTUAL' || value === 'CURRENT_GUEST') return 'HUESPED_ACTUAL';

    return '';
  }

  private normalizeType(type: string | undefined): 'VIP' | 'FRECUENTE' | 'REGULAR' | '' {
    if (!type) return '';
    const value = type.toUpperCase();

    if (value === 'VIP') return 'VIP';
    if (value === 'FRECUENTE' || value === 'FREQUENT') return 'FRECUENTE';
    if (value === 'REGULAR') return 'REGULAR';

    return '';
  }
}
