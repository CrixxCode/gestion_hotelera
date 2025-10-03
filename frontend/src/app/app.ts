import { Component, HostListener, signal } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { Header } from './components/layout/header/header';
import { Aside } from './components/layout/aside/aside';
import { Content } from './components/layout/content/content';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [Header, Aside, Content],
  templateUrl: './app.html'
})
export class App {
  isAsideOpen = signal(true); // aside abierto por defecto
  toggleAside = () => this.isAsideOpen.update(v => !v);
}
