import { Component, signal } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { Header } from '../header/header';
import { Aside } from '../aside/aside';
import { Content } from '../content/content';

@Component({
  selector: 'app-layout-main',
  imports: [Header, Aside, Content, RouterOutlet],
  templateUrl: './layout-main.html',
  styleUrl: './layout-main.css'
})
export class LayoutMain {
  isAsideOpen = signal(true); // aside abierto por defecto
  toggleAside = () => this.isAsideOpen.update(v => !v);
}
