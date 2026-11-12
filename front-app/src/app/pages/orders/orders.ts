import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Router } from '@angular/router';
import { ApiService } from '../../services/api';
import { AuthService } from '../../services/auth.service';

export interface OrderItem {
  product_id: number;
  product_name?: string;
  quantity: number;
  price: number;
}

export interface Order {
  id?: number;
  user_id: number;
  items: OrderItem[];
  total_amount: number;
  created_at?: string;
  status?: string;
}

@Component({
  selector: 'app-orders',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './orders.html',
  styleUrl: './orders.css'
})
export class Orders implements OnInit {
  ordersList: Order[] = [];
  loading: boolean = true;
  errorMessage: string = '';

  constructor(
    private apiService: ApiService,
    private authService: AuthService,
    private router: Router,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    this.loadOrders();
  }

  loadOrders(): void {
    this.loading = true;
    this.errorMessage = '';

    this.apiService.getOrders().subscribe({
      next: (data: any) => {
        this.ordersList = Array.isArray(data) ? data : (data.items || data.orders || []);
        this.loading = false;
        this.cdr.detectChanges();
      },
      error: (err: any) => {
        console.error('Error al cargar pedidos:', err);
        this.loading = false;
        this.errorMessage = 'No se pudieron cargar los pedidos. ' + (err.error?.detail || 'Intente de nuevo más tarde.');
        this.cdr.detectChanges();
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

  getItemCategory(item: OrderItem): string {
    // This would come from the product data in a real app
    return 'General';
  }

  viewOrderDetails(orderId: number): void {
    this.router.navigate(['/orders', orderId]);
  }

  canReorder(order: Order): boolean {
    return (order.status || '').toLowerCase() === 'completed' ||
           (order.status || '').toLowerCase() === 'delivered';
  }

  reorder(order: Order): void {
    // Navigate to cart with these items (would need cart service integration)
    console.log('Reorder:', order);
    // For now, just navigate to shop
    this.router.navigate(['/shop']);
  }
}