import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from '../../services/api';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './home.html',
  styleUrl: './home.css'
})
export class Home implements OnInit {
  // Estado del servidor para el indicador de confianza
  healthStatus: string = 'Comprobando...';
  isOnline: boolean = false;

  constructor(private apiService: ApiService) {}

  ngOnInit(): void {
    this.checkHealth();
  }

  checkHealth(): void {
    this.apiService.getHealth().subscribe({
      next: (res: any) => {
        this.healthStatus = 'Servidor Conectado ✓';
        this.isOnline = true;
      },
      error: () => {
        this.healthStatus = 'Modo Demo (Servidor Offline)';
        this.isOnline = false;
      }
    });
  }
}