import { Component, EventEmitter, Output } from '@angular/core';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { UserService } from '../../../services/user';
import { MessageService } from 'primeng/api';
import { CommonModule } from '@angular/common';
import { ToastModule } from 'primeng/toast';
import {
  ACTION_ALERT_ERROR_SUMMARY,
  ACTION_ALERT_SUCCESS_SUMMARY,
  errorActionAlert,
  successActionAlert
} from '../../../services/action-alerts';

@Component({
  selector: 'app-user-register',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, ToastModule],
  templateUrl: './register.html',
  styleUrls: ['./register.css'],
})
export class UserRegister {
  @Output() close = new EventEmitter<void>();

  form!: FormGroup;
  avatarPreview: string | null = null;
  loading = false;

  constructor(
    private fb: FormBuilder,
    private userService: UserService,
    private messageService: MessageService
  ) {}

  ngOnInit() {
    this.form = this.fb.group({
      first_name: ['', Validators.required],
      last_name: ['', Validators.required],
      username: ['', Validators.required],
      email: ['', [Validators.required, Validators.email]],
      job_title: [''],
      avatar: [''],
      password: ['', Validators.required],
      is_active: [true]
    });

    this.form.get('avatar')?.valueChanges.subscribe((value) => {
      const normalized = `${value || ''}`.trim();
      this.avatarPreview = normalized || null;
    });
  }

  onSubmit() {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    this.loading = true;
    this.userService.createUser(this.form.value).subscribe({
      next: (user) => {
        this.messageService.add({
          severity: 'success',
          summary: ACTION_ALERT_SUCCESS_SUMMARY,
          detail: successActionAlert('create', `usuario ${user.username}`),
          life: 3000
        });
        this.loading = false;
        this.resetForm();
        setTimeout(() => {
          this.close.emit();
        }, 500);
      },
      error: (err) => {
        console.error('Error creando usuario:', err);
        this.messageService.add({
          severity: 'error',
          summary: ACTION_ALERT_ERROR_SUMMARY,
          detail: this.getCreateErrorMessage(err),
          life: 3000
        });
        this.loading = false;
      }
    });
  }

  onCancel(): void {
    this.resetForm();
    this.close.emit();
  }

  private resetForm(): void {
    this.form.reset({
      is_active: true,
      avatar: ''
    });
    this.avatarPreview = null;
  }

  private getCreateErrorMessage(err: any): string {
    const backendError = err?.error;
    const fieldErrors = backendError?.errors;

    if (fieldErrors && typeof fieldErrors === 'object') {
      const messages = Object.entries(fieldErrors).flatMap(([field, value]) => {
        const values = Array.isArray(value) ? value : [value];
        return values
          .filter((item) => item !== null && item !== undefined && `${item}`.trim() !== '')
          .map((item) => `${this.getFieldLabel(field)}: ${item}`);
      });

      if (messages.length > 0) {
        return messages.join(' | ');
      }
    }

    if (typeof backendError?.detail === 'string' && backendError.detail.trim()) {
      return backendError.detail;
    }

    return errorActionAlert('register', 'usuario');
  }

  private getFieldLabel(field: string): string {
    const labels: Record<string, string> = {
      username: 'Usuario',
      email: 'Correo',
      password: 'Contrasena',
      first_name: 'Nombre',
      last_name: 'Apellido',
      job_title: 'Cargo',
      avatar: 'Avatar URL',
      non_field_errors: 'Validacion'
    };

    return labels[field] || field;
  }
}
