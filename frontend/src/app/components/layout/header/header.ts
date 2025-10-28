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
  userAvatar = 'avatar/default-avatar.png';
  private readonly defaultAvatar = 'avatar/default-avatar.png';
  private readonly logoutAnimationDuration = 1000;

  constructor(private authService: AuthService, private router: Router) { }

  ngOnInit() {
    // Asegura que la aplicación arranque siempre en modo claro
    this.darkMode = false;
    document.documentElement.classList.remove('dark');
    this.loadUserInfo();
  }

  // Cargar la información del usuario (nombre y rol)
  loadUserInfo(): void {
    this.authService.getUserInfo().subscribe({
      next: (res: any) => {
        this.userName = res.username || 'Usuario';  // Asignar nombre de usuario
        this.userRole = this.resolveUserRole(res);
        const resolvedAvatar = this.authService.buildMediaUrl(res.avatar);
        this.userAvatar = resolvedAvatar || this.defaultAvatar;
      },
      error: () => {
        this.userName = 'Invitado';
        this.userRole = 'Sin rol';
        this.userAvatar = this.defaultAvatar;
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
      next: () => this.finishLogoutTransition(),
      error: () => this.finishLogoutTransition(),
    });
  }

  private finishLogoutTransition(): void {
    setTimeout(() => {
      this.router.navigate(['/login']).finally(() => {
        this.showLogout = false;
      });
    }, this.logoutAnimationDuration);
  }

  private resolveUserRole(user: any): string {
    if (user?.role) {
      return user.role;
    }
    const firstRole = Array.isArray(user?.roles) ? user.roles[0]?.name : null;
    return firstRole || 'Usuario';
  }
}
