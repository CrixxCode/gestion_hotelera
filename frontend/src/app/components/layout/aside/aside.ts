import { Component } from '@angular/core';
import { RouterModule } from '@angular/router'; // ✅ IMPORTANTE
import { CommonModule } from '@angular/common'; // opcional, útil para *ngIf, *ngFor, etc.

@Component({
  selector: 'app-aside',
  standalone: true,
  imports: [RouterModule, CommonModule], // ✅ necesario para routerLink y routerLinkActive
  templateUrl: './aside.html',
  styleUrls: ['./aside.css']
})
export class Aside {
  
}