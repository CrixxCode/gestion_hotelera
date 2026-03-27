import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ResourcesService } from '../../../services/resources.service';
import { RoleLite, Resource } from '../../../services/resources.service';

type ToastKind = 'success' | 'danger' | 'info';

@Component({
  selector: 'app-recursos',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './recursos.html',
  styleUrls: ['./recursos.css'],
})
export class RecursosComponent implements OnInit {
  // Roles
  roles: RoleLite[] = [];
  rolesQuery = '';
  selectedRole: RoleLite | null = null;
  loadingRoles = false;

  // Recursos
  qResources = '';
  resources: Resource[] = [];
  loadingResources = false;
  private resourceCatalog = new Map<string, Resource>();

  // Rol ↔ Recursos
  assigned: Resource[] = [];
  loadingAssigned = false;

  selectedAvailableIds = new Set<string>();
  selectedAssignedIds = new Set<string>();

  // Drawer CRUD
  showDrawer = false;
  isEditing = false;
  editingId: string | null = null;
  form: Partial<Resource> = this.emptyForm();

  // Confirm delete
  showDeleteConfirm = false;
  deleteTarget: Resource | null = null;

  // Toast
  toastVisible = false;
  toastText = '';
  toastKind: ToastKind = 'info';
  private toastTimer?: any;

  // debounce
  private resourcesDebounce?: any;

  constructor(private svc: ResourcesService) {}

  ngOnInit(): void {
    this.loadRoles();
    this.loadResources('');
  }

  get totalResources(): number {
    return this.resourceCatalog.size;
  }

  get totalAssigned(): number {
    return this.assigned.length;
  }

  get totalAvailable(): number {
    return this.availableResources().length;
  }

  get totalRoles(): number {
    return this.roles.length;
  }

  private toast(msg: string, kind: ToastKind = 'info') {
    this.toastText = msg;
    this.toastKind = kind;
    this.toastVisible = true;
    if (this.toastTimer) clearTimeout(this.toastTimer);
    this.toastTimer = setTimeout(() => (this.toastVisible = false), 2400);
  }

  trackById(_: number, item: any) {
    return item?.id;
  }

  // -------- Roles --------
  loadRoles(): void {
    this.loadingRoles = true;
    this.svc.listRoles().subscribe({
      next: (data) => {
        this.roles = Array.isArray(data) ? data : [];
        this.loadingRoles = false;

        if (!this.selectedRole && this.roles.length) {
          this.selectRole(this.roles[0]);
        }
      },
      error: () => {
        this.roles = [];
        this.loadingRoles = false;
        this.toast('No se pudieron cargar roles.', 'danger');
      },
    });
  }

  filteredRoles(): RoleLite[] {
    const q = (this.rolesQuery || '').trim().toLowerCase();
    if (!q) return this.roles;
    return this.roles.filter(r =>
      (r.name || '').toLowerCase().includes(q) ||
      (r.slug || '').toLowerCase().includes(q)
    );
  }

  selectRole(role: RoleLite): void {
    this.selectedRole = role;
    this.selectedAvailableIds.clear();
    this.selectedAssignedIds.clear();
    this.loadAssignedForRole();
  }

  // -------- Recursos list / search --------
  onResourcesSearchInput(): void {
    if (this.resourcesDebounce) clearTimeout(this.resourcesDebounce);
    this.resourcesDebounce = setTimeout(() => {
      this.loadResources(this.qResources);
    }, 280);
  }

  loadResources(q: string): void {
    this.loadingResources = true;
    this.svc.listResources(q || '').subscribe({
      next: (data) => {
        this.resources = Array.isArray(data) ? data : [];
        this.upsertResourceCatalog(this.resources);
        this.loadingResources = false;

        // limpia selección disponible inválida
        const avail = new Set(this.availableResources().map(r => r.id));
        for (const id of Array.from(this.selectedAvailableIds)) {
          if (!avail.has(id)) this.selectedAvailableIds.delete(id);
        }
      },
      error: () => {
        this.resources = [];
        this.loadingResources = false;
        this.toast('No se pudieron cargar recursos.', 'danger');
      },
    });
  }

  // -------- Rol ↔ Recursos --------
  private loadAssignedForRole(): void {
    if (!this.selectedRole) return;
    this.loadingAssigned = true;
    this.svc.roleResources(this.selectedRole.id).subscribe({
      next: (data) => {
        this.assigned = Array.isArray(data) ? data : [];
        this.upsertResourceCatalog(this.assigned);
        this.loadingAssigned = false;

        // limpia selección asignados inválida
        const ids = new Set(this.assigned.map(r => r.id));
        for (const id of Array.from(this.selectedAssignedIds)) {
          if (!ids.has(id)) this.selectedAssignedIds.delete(id);
        }
      },
      error: () => {
        this.assigned = [];
        this.loadingAssigned = false;
        this.toast('No se pudieron cargar recursos del rol.', 'danger');
      },
    });
  }

  get assignedIds(): Set<string> {
    return new Set(this.assigned.map(r => r.id));
  }

  availableResources(): Resource[] {
    const assigned = this.assignedIds;
    return (this.resources || []).filter(r => !assigned.has(r.id));
  }

  resolveResourceIcon(resource: Resource): string {
    const visited = new Set<string>();
    let current: Resource | undefined = resource;

    while (current) {
      const ownIcon = (current.icon || '').trim();
      if (ownIcon) return ownIcon;

      const parentId = current.parent || null;
      if (!parentId || visited.has(parentId)) break;
      visited.add(parentId);
      current = this.resourceCatalog.get(parentId);
    }

    return 'fa-solid fa-cube';
  }

  getParentName(resource: Resource): string {
    if (!resource.parent) return '';
    const parent = this.resourceCatalog.get(resource.parent);
    return parent?.name || '';
  }

  toggleAvailable(id: string): void {
    if (this.selectedAvailableIds.has(id)) this.selectedAvailableIds.delete(id);
    else this.selectedAvailableIds.add(id);
  }

  toggleAssigned(id: string): void {
    if (this.selectedAssignedIds.has(id)) this.selectedAssignedIds.delete(id);
    else this.selectedAssignedIds.add(id);
  }

  assignSelected(): void {
    if (!this.selectedRole) return;
    const ids = Array.from(this.selectedAvailableIds);
    if (!ids.length) return;

    this.svc.assignResources(this.selectedRole.id, ids).subscribe({
      next: () => {
        this.toast('Recursos asignados al rol.', 'success');
        this.selectedAvailableIds.clear();
        this.loadAssignedForRole();
      },
      error: () => this.toast('No se pudo asignar recursos.', 'danger'),
    });
  }

  removeSelected(): void {
    if (!this.selectedRole) return;
    const ids = Array.from(this.selectedAssignedIds);
    if (!ids.length) return;

    this.svc.removeResources(this.selectedRole.id, ids).subscribe({
      next: () => {
        this.toast('Recursos removidos del rol.', 'success');
        this.selectedAssignedIds.clear();
        this.loadAssignedForRole();
      },
      error: () => this.toast('No se pudo remover recursos.', 'danger'),
    });
  }

  // -------- CRUD Drawer --------
  emptyForm(): Partial<Resource> {
    return {
      key: '',
      name: '',
      description: '',
      link: '',
      link_backend: '',
      icon: '',
      order: 0,
      is_menu: true,
      parent: null,
    };
  }

  openCreate(): void {
    this.isEditing = false;
    this.editingId = null;
    this.form = this.emptyForm();
    this.showDrawer = true;
  }

  openEdit(r: Resource): void {
    this.isEditing = true;
    this.editingId = r.id;
    this.form = {
      key: r.key,
      name: r.name,
      description: r.description || '',
      link: r.link || '',
      link_backend: r.link_backend || '',
      icon: r.icon || '',
      order: r.order ?? 0,
      is_menu: r.is_menu ?? true,
      parent: r.parent ?? null,
    };
    this.showDrawer = true;
  }

  save(): void {
    const payload: Partial<Resource> = {
      key: (this.form.key || '').trim(),
      name: (this.form.name || '').trim(),
      description: (this.form.description || '').trim(),
      link: (this.form.link || '').trim(),
      link_backend: (this.form.link_backend || '').trim(),
      icon: (this.form.icon || '').trim(),
      order: Number(this.form.order ?? 0),
      is_menu: !!this.form.is_menu,
      parent: this.form.parent || null,
    };

    if (!payload.key || !payload.name) {
      this.toast('Key y Name son obligatorios.', 'danger');
      return;
    }

    if (this.isEditing && this.editingId) {
      this.svc.updateResource(this.editingId, payload).subscribe({
        next: () => {
          this.toast('Recurso actualizado.', 'success');
          this.showDrawer = false;
          this.loadResources(this.qResources);
          if (this.selectedRole) this.loadAssignedForRole();
        },
        error: () => this.toast('No se pudo actualizar el recurso.', 'danger'),
      });
    } else {
      this.svc.createResource(payload).subscribe({
        next: () => {
          this.toast('Recurso creado.', 'success');
          this.showDrawer = false;
          this.loadResources(this.qResources);
        },
        error: () => this.toast('No se pudo crear el recurso.', 'danger'),
      });
    }
  }

  askDelete(r: Resource): void {
    this.deleteTarget = r;
    this.showDeleteConfirm = true;
  }

  confirmDelete(): void {
    if (!this.deleteTarget) return;
    const id = this.deleteTarget.id;

    this.svc.deleteResource(id).subscribe({
      next: () => {
        this.resourceCatalog.delete(id);
        this.toast('Recurso eliminado.', 'success');
        this.showDeleteConfirm = false;
        this.deleteTarget = null;
        this.loadResources(this.qResources);
        if (this.selectedRole) this.loadAssignedForRole();
      },
      error: () => this.toast('No se pudo eliminar el recurso.', 'danger'),
    });
  }

  // Dropdown parent: evita seleccionarse a sí mismo
  parentOptions(): Resource[] {
    if (!this.isEditing || !this.editingId) return this.resources;
    return this.resources.filter(r => r.id !== this.editingId);
  }

  refreshView(): void {
    this.loadRoles();
    this.loadResources(this.qResources || '');
    if (this.selectedRole) this.loadAssignedForRole();
  }

  private upsertResourceCatalog(items: Resource[]): void {
    for (const item of items) {
      if (!item?.id) continue;
      this.resourceCatalog.set(item.id, item);
    }
  }
}
