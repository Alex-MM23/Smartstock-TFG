import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from '../../services/api';

@Component({
  selector: 'app-health',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="health-page container" style="max-width: 800px; margin: 2rem auto; padding: 1rem;">
      <h1>🔍 Diagnóstico de Conectividad API</h1>
      <p class="text-secondary">Verifica que el frontend puede comunicarse con el backend FastAPI</p>

      <div class="card p-6 mb-6">
        <h2>Estado del Servidor</h2>
        <button class="btn btn-primary mb-4" (click)="checkHealth()" [disabled]="healthLoading">
          {{ healthLoading ? 'Comprobando...' : 'Verificar /health' }}
        </button>
        <div *ngIf="healthResult" class="result-box" [class.success]="healthResult.ok" [class.error]="!healthResult.ok">
          <pre>{{ healthResult | json }}</pre>
        </div>
      </div>

      <div class="card p-6 mb-6">
        <h2>Catálogo de Productos</h2>
        <button class="btn btn-primary mb-4" (click)="checkProducts()" [disabled]="productsLoading">
          {{ productsLoading ? 'Cargando...' : 'Verificar /products' }}
        </button>
        <div *ngIf="productsResult" class="result-box" [class.success]="productsResult.ok" [class.error]="!productsResult.ok">
          <p><strong>Productos encontrados:</strong> {{ productsResult.count }}</p>
          <details>
            <summary>Ver respuesta completa</summary>
            <pre>{{ productsResult.data | json }}</pre>
          </details>
        </div>
        <div *ngIf="productsError" class="result-box error">
          <strong>Error:</strong> {{ productsError }}
        </div>
      </div>

      <div class="card p-6 mb-6">
        <h2>Stock Status</h2>
        <button class="btn btn-primary mb-4" (click)="checkStock()" [disabled]="stockLoading">
          {{ stockLoading ? 'Cargando...' : 'Verificar /stock/status' }}
        </button>
        <div *ngIf="stockResult" class="result-box" [class.success]="stockResult.ok" [class.error]="!stockResult.ok">
          <p><strong>Total productos:</strong> {{ stockResult.total }}</p>
          <p><strong>En alerta:</strong> {{ stockResult.alerts }}</p>
        </div>
      </div>

      <div class="card p-6">
        <h2>Configuración</h2>
        <ul>
          <li><strong>API URL:</strong> <code>{{ apiUrl }}</code></li>
          <li><strong>Origen actual:</strong> <code>{{ windowOrigin }}</code></li>
        </ul>
      </div>
    </div>
  `,
  styles: [`
    .result-box {
      padding: 1rem;
      border-radius: 8px;
      margin-top: 1rem;
      background: #f5f5f5;
      overflow-x: auto;
    }
    .result-box.success { border-left: 4px solid #10b981; }
    .result-box.error { border-left: 4px solid #ef4444; background: #fef2f2; }
    pre { margin: 0; font-size: 0.85rem; }
    code { background: #e5e7eb; padding: 0.1rem 0.4rem; border-radius: 4px; }
  `]
})
export class Health implements OnInit {
  apiUrl = '';
  windowOrigin = '';

  healthLoading = false;
  healthResult: any = null;

  productsLoading = false;
  productsResult: any = null;
  productsError = '';

  stockLoading = false;
  stockResult: any = null;

  constructor(private apiService: ApiService) {}

  ngOnInit(): void {
    this.apiUrl = this.apiService['baseUrl'] || '(ruta relativa - producción)';
    this.windowOrigin = typeof window !== 'undefined' ? window.location.origin : 'SSR';
  }

  checkHealth(): void {
    this.healthLoading = true;
    this.healthResult = null;
    this.apiService.getHealth().subscribe({
      next: (data) => {
        this.healthResult = { ok: true, ...data };
        this.healthLoading = false;
      },
      error: (err) => {
        this.healthResult = { ok: false, status: err.status, error: err.error?.detail || err.message };
        this.healthLoading = false;
      }
    });
  }

  checkProducts(): void {
    this.productsLoading = true;
    this.productsResult = null;
    this.productsError = '';
    this.apiService.getProducts().subscribe({
      next: (data) => {
        const arr = Array.isArray(data) ? data : (data.items || data.products || []);
        this.productsResult = { ok: true, count: arr.length, data: arr.slice(0, 5) };
        this.productsLoading = false;
      },
      error: (err) => {
        this.productsError = `${err.status}: ${err.error?.detail || err.message}`;
        this.productsLoading = false;
      }
    });
  }

  checkStock(): void {
    this.stockLoading = true;
    this.stockResult = null;
    this.apiService.getStockStatus().subscribe({
      next: (data) => {
        this.stockResult = { ok: true, total: data.total_productos, alerts: data.productos_en_alerta };
        this.stockLoading = false;
      },
      error: (err) => {
        this.stockResult = { ok: false, status: err.status, error: err.error?.detail || err.message };
        this.stockLoading = false;
      }
    });
  }
}