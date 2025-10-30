import { Component, EventEmitter, Output, ViewChild, ElementRef } from '@angular/core';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { UserService } from '../../../services/user';
import { MessageService } from 'primeng/api';
import { CommonModule } from '@angular/common';
import { ToastModule } from 'primeng/toast';

@Component({
  selector: 'app-user-register',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, ToastModule],
  templateUrl: './register.html',
})
export class UserRegister {
  @Output() close = new EventEmitter<void>();
  @ViewChild('fileInput') fileInput!: ElementRef<HTMLInputElement>; // referencia directa al input

  form!: FormGroup;
  avatarFile?: File;
  avatarPreview: string | ArrayBuffer | null = null;
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
      password: ['', Validators.required],
      status: ['ACTIVE'] // ✅ Usuario activo por defecto
    });
  }

  /**  Carga archivo y previsualiza */
  onFileChange(event: any) {
    const file = event.target.files[0];
    if (file) {
      this.avatarFile = file;
      const reader = new FileReader();
      reader.onload = () => (this.avatarPreview = reader.result);
      reader.readAsDataURL(file);
    }
  }

  /**  Enviar formulario */
  onSubmit() {
    if (this.form.invalid) return;

    this.loading = true;
    this.userService.createUser(this.form.value, this.avatarFile).subscribe({
      next: (user) => {
        this.messageService.add({
          severity: 'success',
          summary: 'Usuario registrado',
          detail: `El usuario ${user.username} fue creado correctamente.`,
          life: 3000
        });
        this.loading = false;
        this.resetForm(); //  limpiar todo
        this.close.emit();
      },
      error: (err) => {
        console.error(err);
        this.messageService.add({
          severity: 'error',
          summary: 'Error',
          detail: 'No se pudo registrar el usuario.',
          life: 3000
        });
        this.loading = false;
      }
    });
  }

  /**  Cancela registro */
  onCancel(): void {
    this.resetForm();
    this.close.emit();
  }

  /**  Limpia formulario, preview e input file */
  private resetForm(): void {
    this.form.reset({
      status: 'ACTIVE' // Valor por defecto
    });
    this.avatarFile = undefined;
    this.avatarPreview = null;

    //  Limpia visualmente el campo de archivo
    if (this.fileInput) {
      this.fileInput.nativeElement.value = '';
    }
  }
}
