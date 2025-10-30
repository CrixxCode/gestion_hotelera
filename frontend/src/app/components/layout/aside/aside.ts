import { AfterViewInit, Component, OnInit } from '@angular/core';
import { RouterModule } from '@angular/router';
import { CommonModule } from '@angular/common';
import { AuthService } from '../../../services/auth/auth'; // Ojo: importa tu servicio
import { initFlowbite } from 'flowbite';

@Component({
  selector: 'app-aside',
  standalone: true,
  imports: [RouterModule, CommonModule],
  templateUrl: './aside.html',
  styleUrls: ['./aside.css']
})
export class Aside implements OnInit, AfterViewInit {
  userRole: string | null = null;

  constructor(private authService: AuthService) {}

  ngAfterViewInit(): void {
    initFlowbite();
  }

  ngOnInit(): void {
    // Ojo: llama al endpoint /api/auth/me/ para obtener info del usuario autenticado
    this.authService.getUserInfo().subscribe({
      next: (user) => {
        this.userRole = this.resolveRole(user);
        // Reactiva los componentes basados en data-* (Flowbite) para menús dinámicos
        setTimeout(() => initFlowbite(), 0);

        // Guarda en localStorage si deseas persistir el rol
        if (this.userRole) {
          localStorage.setItem('role', this.userRole);
        }
      },
      error: () => {
        // Si no responde el backend, intenta leer del localStorage
        const storedRole = localStorage.getItem('role');
        this.userRole = storedRole ? storedRole.toUpperCase() : null;
      }
    });
  }

  private resolveRole(user: any): string | null {
    if (!user) {
      return null;
    }

    if (user.role) {
      return String(user.role).toUpperCase();
    }

    const firstRole = Array.isArray(user.roles) ? user.roles[0] : null;
    if (!firstRole) {
      return null;
    }

    const slugOrName = firstRole.slug || firstRole.name;
    return slugOrName ? String(slugOrName).toUpperCase() : null;
  }
}
