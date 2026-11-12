import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterModule, Router } from '@angular/router';
import { ApiService } from '../../services/api';
import { finalize } from 'rxjs/operators';

// Interfaces que coinciden EXACTAMENTE con la respuesta del backend (OrderResponse / OrderItemResponse)
export interface OrderItem {
  id: number;
  product_id: number;
  quantity: number;
  price: number;
  product_name: string | null;
}

export interface Order {
  id: number;
  user_id: number;
  total_amount: number;
  status: string;
  created_at: string; // ISO string desde datetime del backend
  items: OrderItem[];
}

@Component({
  selector: 'app-order-detail',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './order-detail.html',
  styleUrl: './order-detail.css'
})
export class OrderDetail implements OnInit {
  order: Order | undefined;
  loading: boolean = true;
  errorMessage: string = '';

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private apiService: ApiService
  ) {}

  ngOnInit(): void {
    const orderId = Number(this.route.snapshot.paramMap.get('id'));
    if (!isNaN(orderId)) {
      this.loadOrder(orderId);
    } else {
      this.loading = false;
      this.errorMessage = 'ID de pedido inválido.';
    }
  }

  loadOrder(id: number): void {
    this.loading = true;
    this.errorMessage = '';

    this.apiService.getOrderById(id).pipe(
      finalize(() => this.loading = false) // Garantiza loading=false siempre (éxito o error)
    ).subscribe({
      next: (data: Order) => {
        this.order = data;
      },
      error: (err) => {
        console.error('Error cargando pedido:', err);
        this.errorMessage = 'No se pudo cargar el pedido. ' + (err.error?.detail || 'Intente de nuevo más tarde.');
      }
    });
  }

  getStatusLabel(status?: string): string {
    const labels: Record<string, string> = {
      'completed': 'Completado',
      'processing': 'Procesando',
      'shipped': 'Enviado',
      'delivered': 'Entregado',
      'cancelled': 'Cancelado',
      'pending': 'Pendiente',
    };
    return labels[status?.toLowerCase() || ''] || status || 'Completado';
  }

  getStatusClass(status?: string): string {
    const classes: Record<string, string> = {
      'completed': 'badge-success',
      'delivered': 'badge-success',
      'processing': 'badge-warning',
      'shipped': 'badge-primary',
      'cancelled': 'badge-error',
      'pending': 'badge-warning',
    };
    return classes[status?.toLowerCase() || ''] || 'badge-primary';
  }

  goBack(): void {
    this.router.navigate(['/orders']);
  }
}