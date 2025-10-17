import { Component, CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { InputTextModule } from 'primeng/inputtext';
import { PasswordModule } from 'primeng/password';
import { CheckboxModule } from 'primeng/checkbox';
import { ButtonModule } from 'primeng/button';
import { ToastModule } from 'primeng/toast';
import { MessageService } from 'primeng/api';
import { AuthService } from '../../../services/auth/auth';
import { RouterLink } from '@angular/router';

// ✅ Registrar componentes Web de Swiper
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
    ToastModule,
    RouterLink,
  ],
  providers: [MessageService],
  schemas: [CUSTOM_ELEMENTS_SCHEMA],
})
export class LoginComponent {
  loginForm: FormGroup;

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
    private messageService: MessageService
  ) {
    this.loginForm = this.fb.group({
      username: ['', Validators.required],
      password: ['', Validators.required],
      rememberMe: [false],
    });
  }

  onSubmit() {
    if (this.loginForm.valid) {
      const { username, password } = this.loginForm.value;
      this.authService.login(username, password).subscribe({
        next: () => this.messageService.add({
          severity: 'success',
          summary: 'Bienvenido',
          detail: 'Inicio de sesión exitoso',
        }),
        error: () => this.messageService.add({
          severity: 'error',
          summary: 'Error',
          detail: 'Credenciales incorrectas o usuario no encontrado',
        }),
      });
    } else {
      this.messageService.add({
        severity: 'warn',
        summary: 'Campos incompletos',
        detail: 'Por favor completa todos los campos',
      });
    }
  }
}
