import { Component, CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { InputTextModule } from 'primeng/inputtext';
import { PasswordModule } from 'primeng/password';
import { CheckboxModule } from 'primeng/checkbox';
import { ButtonModule } from 'primeng/button';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../../services/auth/auth';
import { LoadingScreen } from '../../pages/loading-screen/loading-screen';
import { register } from 'swiper/element/bundle';

register();

@Component({
  standalone: true,
  selector: 'app-login',
  templateUrl: './login.html',
  styleUrls: ['./login.css'],
  imports: [
    CommonModule,
    ReactiveFormsModule,
    InputTextModule,
    PasswordModule,
    CheckboxModule,
    ButtonModule,
    RouterLink,
    LoadingScreen
  ],
  schemas: [CUSTOM_ELEMENTS_SCHEMA],
})
export class LoginComponent {
  loginForm: FormGroup;
  showLoading: boolean = false;
  errorMessage: string | null = null;
  errorType: 'error' | 'warn' | null = null;

  backgrounds = [
    'login/fondo-login-1.jpg',
    'login/fondo-login-2.jpg',
    'login/fondo-login-3.jpg',
    'login/fondo-login-4.jpg',
    'login/fondo-login-5.jpg',
    'login/fondo-login-6.jpg',
    'login/fondo-login-7.jpg',
    'login/fondo-login-8.jpg',
    'login/fondo-login-9.jpg',
    'login/fondo-login-10.jpg',
  ];

  swiperConfig = {
    loop: true,
    effect: 'fade',
    speed: 1500,
    allowTouchMove: false,
    autoplay: {
      delay: 4000,
      disableOnInteraction: false,
    },
  };

  constructor(
    private fb: FormBuilder,
    private authService: AuthService,
    private router: Router
  ) {
    this.loginForm = this.fb.group({
      username: ['', Validators.required],
      password: ['', Validators.required],
      rememberMe: [false],
    });
  }

  /**
   * Envía los datos del formulario al backend y gestiona la respuesta.
   * Incluye validaciones, manejo de errores y animación de carga con transición suave.
   */
  onSubmit() {
    if (this.loginForm.invalid) {
      this.errorMessage = 'Por favor completa todos los campos.';
      this.errorType = 'warn';
      setTimeout(() => (this.errorMessage = null), 4000);
      return;
    }

    const { username, password } = this.loginForm.value;

    this.authService.getCsrfToken().subscribe({
      next: () => {
        this.authService.login(username, password).subscribe({
          next: (res) => {
            console.log('Inicio de sesión correcto:', res);

            this.errorMessage = null;
            this.showLoading = true;

            // Se mantiene la pantalla de carga visible durante la transición
            setTimeout(() => {
              this.showLoading = false;
              this.router.navigate(['/dashboard']);
            }, 2000);
          },
          error: (err) => {
            console.error('Error en inicio de sesión:', err);
            const msg = err.error?.detail || '';

            if (msg.includes('Faltan credenciales')) {
              this.errorMessage = 'Por favor ingresa tu usuario y contraseña.';
              this.errorType = 'warn';
            } else if (msg.includes('Credenciales inválidas')) {
              this.errorMessage = 'Usuario o contraseña incorrectos.';
              this.errorType = 'error';
            } else if (msg.includes('Usuario inactivo')) {
              this.errorMessage = 'Tu cuenta está inactiva. Contacta al administrador.';
              this.errorType = 'warn';
            } else {
              this.errorMessage = 'No se pudo iniciar sesión. Intenta nuevamente.';
              this.errorType = 'error';
            }

            setTimeout(() => (this.errorMessage = null), 4000);
          },
        });
      },
      error: (err) => {
        console.error('Error al obtener el token CSRF:', err);
        this.errorMessage = 'No se pudo conectar con el servidor.';
        this.errorType = 'error';
        setTimeout(() => (this.errorMessage = null), 4000);
      },
    });
  }
}
