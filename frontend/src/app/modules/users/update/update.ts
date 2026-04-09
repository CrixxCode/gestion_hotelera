import { Component, EventEmitter, Input, Output, OnChanges, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { UserI } from '../user-model';
import { UserService } from '../../../services/user';
import { MessageService } from 'primeng/api';
import {
  ACTION_ALERT_ERROR_SUMMARY,
  errorActionAlert
} from '../../../services/action-alerts';

@Component({
  selector: 'app-user-update',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './update.html',
  styleUrls: ['./update.css']
})
export class UserUpdate implements OnChanges {
  @Input() user: UserI | null = null;
  @Output() close = new EventEmitter<void>();
  @Output() updated = new EventEmitter<void>();

  form!: FormGroup;
  avatarPreview: string | ArrayBuffer | null = null;
  avatarFile: File | null = null;

  constructor(
    private fb: FormBuilder,
    private userService: UserService,
    private messageService: MessageService
  ) {
    this.form = this.fb.group({
      first_name: ['', Validators.required],
      last_name: ['', Validators.required],
      username: ['', Validators.required],
      email: ['', [Validators.required, Validators.email]],
      status: ['ACTIVE']
    });
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['user'] && this.user) {
      this.form.patchValue(this.user);
      this.form.patchValue({
        status: this.user.is_active ? 'ACTIVE' : 'INACTIVE'
      });

      this.avatarPreview = this.user.avatar ? this.resolveAvatar(this.user.avatar) : null;
    }
  }

  onAvatarChange(event: any): void {
    const file = event.target.files[0];
    if (file) {
      this.avatarFile = file;
      const reader = new FileReader();
      reader.onload = () => (this.avatarPreview = reader.result);
      reader.readAsDataURL(file);
    }
  }

  onSubmit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    if (!this.user?.id) return;

    const statusValue = this.form.value.status === 'ACTIVE';
    const updatedUser: UserI = {
      ...this.user,
      ...this.form.value,
      is_active: statusValue,
    };

    this.userService.updateUser(this.user.id, updatedUser, this.avatarFile || undefined).subscribe({
      next: () => {
        this.updated.emit();
        this.close.emit();
      },
      error: () => {
        this.messageService.add({
          severity: 'error',
          summary: ACTION_ALERT_ERROR_SUMMARY,
          detail: errorActionAlert('update', 'usuario'),
          life: 3000
        });
      }
    });
  }


  cancel(): void {
    this.close.emit();
  }

  resolveAvatar(src?: string | null): string | null {
    if (!src) return null;
    if (src.startsWith('http://') || src.startsWith('https://')) return src;
    return `http://127.0.0.1:8000${src.startsWith('/') ? '' : '/'}${src}`;
  }
}
