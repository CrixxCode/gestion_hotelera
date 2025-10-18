import { Component, HostListener, signal } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { LayoutMain } from "./components/layout/layout-main/layout-main";

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet],
  templateUrl: './app.html'
})
export class App {
}
