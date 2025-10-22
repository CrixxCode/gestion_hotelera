import { Component, EventEmitter, Output, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { AuthService } from '../../../services/auth/auth';  // Asegúrate de que esté bien importado
import { LogoutScreen } from '../../pages/logout-screen/logout-screen';

@Component({
  selector: 'app-header',
  standalone: true,
  imports: [CommonModule, LogoutScreen],
  templateUrl: './header.html',
})
export class Header {
  @Output() menuToggle = new EventEmitter<void>();

  menuOpen = false;
  darkMode = false;
  showLogout = false;
  userName = '';
  userRole = '';

  constructor(private authService: AuthService, private router: Router) { }

  ngOnInit() {
    this.loadUserInfo();
  }

  // Cargar la información del usuario (nombre y rol)
  loadUserInfo(): void {
    this.authService.getUserInfo().subscribe({
      next: (res: any) => {
        this.userName = res.username || 'Usuario';  // Asignar nombre de usuario
        this.userRole = res.role || 'Usuario';  // Asignar rol de usuario
      },
      error: () => {
        this.userName = 'Invitado';
        this.userRole = 'Sin rol';
      }
    });
  }

  toggleMenu(): void {
    this.menuOpen = !this.menuOpen;
  }

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    const target = event.target as HTMLElement;
    const clickedInside = target.closest('.relative');
    if (!clickedInside) this.menuOpen = false;
  }

  openProfile(): void {
    this.menuOpen = false;
  }

  openSettings(): void {
    this.menuOpen = false;
  }

  toggleTheme(): void {
    this.darkMode = !this.darkMode;
    document.documentElement.classList.toggle('dark', this.darkMode);
    this.menuOpen = false;
  }

  logout(): void {
    this.showLogout = true;
    this.authService.logout().subscribe({
      next: () => {
        setTimeout(() => {
          this.showLogout = false;
          this.router.navigate(['/login']);
        }, 1200);
      },
      error: () => {
        this.showLogout = false;
        this.router.navigate(['/login']);
      },
    });
  }
}
