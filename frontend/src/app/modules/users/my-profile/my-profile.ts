import { CommonModule } from '@angular/common';
import { Component, OnInit, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AuthService, MeResponse } from '../../../services/auth/auth';

type ProfileTab = 'profile' | 'password' | 'work';
type PersonalFormValue = {
  full_name: string;
  email: string;
  avatar: string;
  phone: string;
  department: string;
  location: string;
};

type WorkFormValue = {
  hotel_name: string;
  job_title: string;
  work_role: string;
};

@Component({
  selector: 'app-my-profile-page',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  templateUrl: './my-profile.html',
  styleUrls: ['./my-profile.css'],
})
export class MyProfilePage implements OnInit {
  private readonly fb = inject(FormBuilder);

  activeTab: ProfileTab = 'profile';
  loading = true;
  loadError = '';

  avatarUrl = '';
  fullName = 'Usuario';
  roleLabel = 'Usuario';
  contactEmail = 'Sin correo';
  locationLabel = 'No definido';
  joinedLabel = 'Sin fecha';

  profileSavedMessage = '';
  profileErrorMessage = '';
  passwordSavedMessage = '';
  workSavedMessage = '';
  passwordErrorMessage = '';
  passwordLoading = false;
  showCurrentPassword = false;
  showNewPassword = false;
  showConfirmPassword = false;
  isEditingProfile = false;
  isEditingWork = false;
  private personalSnapshot: PersonalFormValue | null = null;
  private workSnapshot: WorkFormValue | null = null;

  personalForm = this.fb.nonNullable.group({
    full_name: ['', Validators.required],
    email: ['', [Validators.required, Validators.email]],
    avatar: [''],
    phone: [''],
    department: [''],
    location: [''],
  });

  passwordForm = this.fb.nonNullable.group({
    current_password: ['', Validators.required],
    new_password: ['', [Validators.required, Validators.minLength(8)]],
    confirm_password: ['', [Validators.required, Validators.minLength(8)]],
  });

  workForm = this.fb.nonNullable.group({
    hotel_name: ['', Validators.required],
    job_title: ['', Validators.required],
    work_role: ['', Validators.required],
  });

  constructor(private authService: AuthService) {
    this.personalForm.disable({ emitEvent: false });
    this.workForm.disable({ emitEvent: false });
  }

  ngOnInit(): void {
    this.loadCurrentUser();
  }

  selectTab(tab: ProfileTab): void {
    if (this.activeTab === 'profile' && this.isEditingProfile && tab !== 'profile') {
      this.cancelProfileEditing();
    }
    if (this.activeTab === 'work' && this.isEditingWork && tab !== 'work') {
      this.cancelWorkEditing();
    }
    this.activeTab = tab;
    this.clearMessages();
  }

  savePersonalInfo(): void {
    if (!this.isEditingProfile) return;
    this.personalForm.markAllAsTouched();
    if (this.personalForm.invalid) return;

    const formValue = this.personalForm.getRawValue();
    const { firstName, lastName } = this.splitFullName(formValue.full_name);
    const payload = {
      first_name: firstName,
      last_name: lastName,
      email: formValue.email.trim(),
      avatar: formValue.avatar.trim(),
    };

    this.authService.updateMyProfile(payload).subscribe({
      next: (updatedUser) => {
        this.profileErrorMessage = '';
        this.hydrateFromUser(updatedUser);
        this.profileSavedMessage = 'Perfil actualizado correctamente.';
        this.finishProfileEditing();
      },
      error: () => {
        this.profileSavedMessage = '';
        this.profileErrorMessage = 'No se pudo actualizar la informacion de perfil.';
      },
    });
  }

  startProfileEditing(): void {
    this.clearMessages();
    this.personalSnapshot = this.personalForm.getRawValue();
    this.isEditingProfile = true;
    this.personalForm.enable({ emitEvent: false });
  }

  cancelProfileEditing(): void {
    if (this.personalSnapshot) {
      this.personalForm.reset(this.personalSnapshot);
    }
    this.finishProfileEditing();
  }

  savePassword(): void {
    this.passwordForm.markAllAsTouched();
    this.passwordErrorMessage = '';
    this.passwordSavedMessage = '';

    if (this.passwordForm.invalid) return;

    const { new_password, confirm_password } = this.passwordForm.getRawValue();
    if (new_password !== confirm_password) {
      this.passwordErrorMessage = 'La confirmacion de la nueva contrasena no coincide.';
      return;
    }

    const { current_password } = this.passwordForm.getRawValue();
    this.passwordLoading = true;

    this.authService.getCsrfToken().subscribe({
      next: () => {
        this.authService.changePassword(current_password, new_password).subscribe({
          next: () => {
            this.passwordLoading = false;
            this.passwordSavedMessage = 'Contrasena actualizada correctamente.';
            this.showCurrentPassword = false;
            this.showNewPassword = false;
            this.showConfirmPassword = false;
            this.passwordForm.reset({
              current_password: '',
              new_password: '',
              confirm_password: '',
            });
          },
          error: (err) => {
            this.passwordLoading = false;
            const details = err?.error;
            this.passwordErrorMessage =
              details?.old_password?.[0] ||
              details?.new_password?.[0] ||
              details?.detail ||
              'No fue posible cambiar la contrasena. Intenta nuevamente.';
          },
        });
      },
      error: () => {
        this.passwordLoading = false;
        this.passwordErrorMessage = 'No fue posible conectar con el servidor.';
      },
    });
  }

  togglePasswordVisibility(field: 'current' | 'new' | 'confirm'): void {
    if (field === 'current') this.showCurrentPassword = !this.showCurrentPassword;
    if (field === 'new') this.showNewPassword = !this.showNewPassword;
    if (field === 'confirm') this.showConfirmPassword = !this.showConfirmPassword;
  }

  passwordInputType(field: 'current' | 'new' | 'confirm'): 'text' | 'password' {
    if (field === 'current') return this.showCurrentPassword ? 'text' : 'password';
    if (field === 'new') return this.showNewPassword ? 'text' : 'password';
    return this.showConfirmPassword ? 'text' : 'password';
  }

  saveWorkInfo(): void {
    if (!this.isEditingWork) return;
    this.workForm.markAllAsTouched();
    if (this.workForm.invalid) return;
    this.workSavedMessage = 'Interfaz lista. Pendiente conectar endpoint para informacion laboral.';
    this.finishWorkEditing();
  }

  startWorkEditing(): void {
    this.clearMessages();
    this.workSnapshot = this.workForm.getRawValue();
    this.isEditingWork = true;
    this.workForm.enable({ emitEvent: false });
  }

  cancelWorkEditing(): void {
    if (this.workSnapshot) {
      this.workForm.reset(this.workSnapshot);
    }
    this.finishWorkEditing();
  }

  private loadCurrentUser(): void {
    this.loading = true;
    this.loadError = '';

    this.authService.getUserInfo().subscribe({
      next: (user) => {
        this.hydrateFromUser(user);
        this.loading = false;
      },
      error: () => {
        this.loading = false;
        this.loadError = 'No se pudo cargar la informacion de perfil.';
      },
    });
  }

  private hydrateFromUser(user: MeResponse): void {
    const firstName = user.first_name?.trim() || '';
    const lastName = user.last_name?.trim() || '';
    const composedName = `${firstName} ${lastName}`.trim();
    const fallbackName = user.username?.trim() || 'Usuario';
    const finalName = composedName || fallbackName;

    const roleName = this.resolvePrimaryRole(user);
    const location =
      this.getString(user, 'location') ||
      this.getString(user, 'city') ||
      this.getString(user, 'address') ||
      'No definido';

    const department = this.getString(user, 'department');
    const phone = this.getString(user, 'phone') || this.getString(user, 'phone_number');
    const hotelName =
      this.getString(user, 'hotel_name') ||
      this.getString(user.hotel_settings, 'hotel_name');
    const joined =
      this.getString(user, 'date_joined') ||
      this.getString(user, 'created_at') ||
      this.getString(user, 'createdAt');

    this.avatarUrl = this.authService.buildMediaUrl(user.avatar || '');
    this.fullName = finalName;
    this.roleLabel = roleName;
    this.contactEmail = user.email || 'Sin correo';
    this.locationLabel = location;
    this.joinedLabel = this.formatJoinedDate(joined);

    this.personalForm.reset({
      full_name: finalName,
      email: user.email || '',
      avatar: user.avatar || '',
      phone,
      department,
      location,
    });
    this.finishProfileEditing();

    this.workForm.reset({
      hotel_name: hotelName,
      job_title: this.getString(user, 'job_title'),
      work_role: roleName,
    });
    this.finishWorkEditing();
  }

  private resolvePrimaryRole(user: MeResponse): string {
    const firstRole = Array.isArray(user.roles) ? user.roles[0] : null;

    if (typeof firstRole === 'string' && firstRole.trim()) {
      return firstRole.trim();
    }

    if (firstRole && typeof firstRole === 'object') {
      const roleName = this.getString(firstRole, 'name') || this.getString(firstRole, 'slug');
      if (roleName) return roleName;
    }

    const roleFromUser = this.getString(user, 'role');
    return roleFromUser || 'Usuario';
  }

  private formatJoinedDate(rawDate: string): string {
    if (!rawDate) return 'Sin fecha';

    const parsedDate = new Date(rawDate);
    if (Number.isNaN(parsedDate.getTime())) return 'Sin fecha';

    return new Intl.DateTimeFormat('es-CO', {
      day: '2-digit',
      month: 'long',
      year: 'numeric',
    }).format(parsedDate);
  }

  private getString(source: unknown, key: string): string {
    if (!source || typeof source !== 'object') return '';
    const value = (source as Record<string, unknown>)[key];
    return typeof value === 'string' ? value.trim() : '';
  }

  private clearMessages(): void {
    this.loadError = '';
    this.profileSavedMessage = '';
    this.profileErrorMessage = '';
    this.passwordSavedMessage = '';
    this.workSavedMessage = '';
    this.passwordErrorMessage = '';
  }

  private finishProfileEditing(): void {
    this.isEditingProfile = false;
    this.personalSnapshot = null;
    this.personalForm.disable({ emitEvent: false });
  }

  private finishWorkEditing(): void {
    this.isEditingWork = false;
    this.workSnapshot = null;
    this.workForm.disable({ emitEvent: false });
  }

  private splitFullName(fullName: string): { firstName: string; lastName: string } {
    const normalized = (fullName || '').trim().replace(/\s+/g, ' ');
    if (!normalized) return { firstName: '', lastName: '' };

    const parts = normalized.split(' ');
    if (parts.length === 1) return { firstName: parts[0], lastName: '' };

    return {
      firstName: parts[0],
      lastName: parts.slice(1).join(' '),
    };
  }
}
