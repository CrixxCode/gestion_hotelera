import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule, NgClass } from '@angular/common';
import { ButtonModule } from 'primeng/button';
import { UserI } from '../user-model';

@Component({
  selector: 'app-user-profile',
  standalone: true,
  imports: [CommonModule, NgClass, ButtonModule],
  templateUrl: './profile.html'
})
export class UserProfile {
  @Input() user: UserI | null = null;

  @Output() close = new EventEmitter<void>();

  closeDialog(): void {
    this.close.emit();
  }

  resolveAvatar(src?: string | null): string | null {
    if (!src) return null;
    if (src.startsWith('http://') || src.startsWith('https://')) return src;
    return `http://127.0.0.1:8000${src.startsWith('/') ? '' : '/'}${src}`;
  }
}
