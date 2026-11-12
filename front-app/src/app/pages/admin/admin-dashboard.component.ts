import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api';

interface AdminProductInsight {
  id_producto: number;
  sku: string;
  nombre: string;
  categoria: string;
  stock_actual: number;
  precio_unitario: number;
  dias_stock_restante: number | null;
  velocidad_consumo_diaria: number | null;
  riesgo_critico: boolean;
  demanda_estimada_7d: number | null;
  stock_recomendado: number | null;
  unidades_a_reponer: number | null;
  ultima_fecha_venta: string | null;
}

interface AdminDashboardResponse {
  total_productos: number;
  total_pedidos: number;
  ingresos_totales: number;
  productos_riesgo_critico: number;
  productos_bajo_stock: number;
  productos_agotados: number;
  productos: AdminProductInsight[];
  pedidos_recientes: Order[];
}

interface OrderItem {
  id: number;
  product_id: number;
  quantity: number;
  price: number;
  product_name?: string;
}

interface Order {
  id?: number;
  user_id: number;
  total_amount: number;
  status?: string;
  created_at?: string;
  items?: OrderItem[];
}

interface PurchaseOrderItem {
  id: number;
  id_producto: number;
  cantidad: number;
  product_name?: string;
  product_sku?: string;
}

interface PurchaseOrder {
  id_orden_compra: number;
  id_proveedor: number;
  proveedor_nombre: string;
  fecha_creacion: string;
  estado: string;
  generada_por_ia: boolean;
  total_unidades: number;
  items: PurchaseOrderItem[];
}

interface StatCard {
  title: string;
  value: number | string;
  icon: string;
  color: string;
}

@Component({
  selector: 'app-admin-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './admin-dashboard.component.html',
  styleUrl: './admin-dashboard.component.css'
})
export class AdminDashboardComponent implements OnInit {
  stats: StatCard[] = [];
  products: AdminProductInsight[] = [];
  filteredProducts: AdminProductInsight[] = [];
  orders: Order[] = [];
  filteredOrders: Order[] = [];
  purchaseOrders: PurchaseOrder[] = [];
  filteredPurchaseOrders: PurchaseOrder[] = [];
  loading = true;
  errorMessage = '';
  activeTab = 'overview';
  placeholderImage: string = 'https://images.unsplash.com/photo-1518770660439-4636190af475?w=400';

  productSearchTerm: string = '';
  productStockFilter: string = 'all';

  orderStatusFilter: string = 'all';
  orderDateFrom: string = '';
  orderDateTo: string = '';

  poStatusFilter: string = 'all';
  poSearchTerm: string = '';

  constructor(private apiService: ApiService, private cdr: ChangeDetectorRef) {}

  ngOnInit(): void {
    this.loadDashboardData();
  }

  loadDashboardData(): void {
    this.loading = true;
    this.errorMessage = '';

    this.apiService.getAdminDashboard().subscribe({
      next: (data: AdminDashboardResponse) => {
        this.stats = [
          { title: 'Productos', value: data.total_productos, icon: '📦', color: '#3b82f6' },
          { title: 'Pedidos', value: data.total_pedidos, icon: '📋', color: '#8b5cf6' },
          { title: 'Ingresos', value: `${data.ingresos_totales.toFixed(2)} €`, icon: '💰', color: '#10b981' },
          { title: 'Riesgo Crítico (IA)', value: data.productos_riesgo_critico, icon: '🚨', color: '#ef4444' },
          { title: 'Bajo Stock (IA)', value: data.productos_bajo_stock, icon: '⚠️', color: '#f59e0b' },
          { title: 'Agotados', value: data.productos_agotados, icon: '🔴', color: '#6b7280' },
        ];

        this.products = data.productos;
        this.filteredProducts = [...this.products];

        this.orders = data.pedidos_recientes;
        this.filteredOrders = [...this.orders];

        this.loading = false;
        this.cdr.detectChanges();
        this.loadPurchaseOrders();
      },
      error: (err) => {
        console.error('Error cargando dashboard IA:', err);
        this.loading = false;
        this.errorMessage = 'Error al cargar datos del panel: ' + (err.error?.detail || 'Intente de nuevo');
        this.cdr.detectChanges();
      }
    });
  }

  loadPurchaseOrders(): void {
    this.apiService.getPurchaseOrders().subscribe({
      next: (data: PurchaseOrder[]) => {
        this.purchaseOrders = data;
        this.filteredPurchaseOrders = [...this.purchaseOrders];
        this.cdr.detectChanges();
      },
      error: (err: any) => {
        console.error('Error cargando órdenes de compra:', err);
        this.cdr.detectChanges();
      }
    });
  }

  applyProductFilters(): void {
    let filtered = [...this.products];

    if (this.productSearchTerm.trim()) {
      const term = this.productSearchTerm.toLowerCase().trim();
      filtered = filtered.filter(p =>
        p.nombre?.toLowerCase().includes(term) ||
        p.categoria?.toLowerCase().includes(term) ||
        p.sku?.toLowerCase().includes(term)
      );
    }

    switch (this.productStockFilter) {
      case 'critical':
        filtered = filtered.filter(p => p.riesgo_critico === true);
        break;
      case 'normal':
        filtered = filtered.filter(p => p.riesgo_critico === false && p.stock_actual > 0 && (p.unidades_a_reponer === null || p.unidades_a_reponer === 0));
        break;
      case 'low':
        filtered = filtered.filter(p => p.riesgo_critico === false && p.unidades_a_reponer && p.unidades_a_reponer > 0);
        break;
      case 'out':
        filtered = filtered.filter(p => p.stock_actual <= 0);
        break;
    }

    this.filteredProducts = filtered;
    this.cdr.detectChanges();
  }

  onProductSearchChange(): void {
    this.applyProductFilters();
  }

  onProductStockFilterChange(): void {
    this.applyProductFilters();
  }

  clearProductFilters(): void {
    this.productSearchTerm = '';
    this.productStockFilter = 'all';
    this.applyProductFilters();
  }

  // Order filters
  applyOrderFilters(): void {
    let filtered = [...this.orders];

    if (this.orderStatusFilter !== 'all') {
      filtered = filtered.filter(o => (o.status || '').toLowerCase() === this.orderStatusFilter);
    }

    if (this.orderDateFrom) {
      const fromDate = new Date(this.orderDateFrom);
      filtered = filtered.filter(o => o.created_at && new Date(o.created_at) >= fromDate);
    }

    if (this.orderDateTo) {
      const toDate = new Date(this.orderDateTo);
      toDate.setHours(23, 59, 59, 999);
      filtered = filtered.filter(o => o.created_at && new Date(o.created_at) <= toDate);
    }

    this.filteredOrders = filtered;
    this.cdr.detectChanges();
  }

  onOrderStatusFilterChange(): void {
    this.applyOrderFilters();
  }

  onOrderDateFilterChange(): void {
    this.applyOrderFilters();
  }

  clearOrderFilters(): void {
    this.orderStatusFilter = 'all';
    this.orderDateFrom = '';
    this.orderDateTo = '';
    this.applyOrderFilters();
  }

  applyPOFilters(): void {
    let filtered = [...this.purchaseOrders];

    if (this.poStatusFilter !== 'all') {
      filtered = filtered.filter(po => po.estado === this.poStatusFilter);
    }

    if (this.poSearchTerm.trim()) {
      const term = this.poSearchTerm.toLowerCase().trim();
      filtered = filtered.filter(po =>
        po.proveedor_nombre?.toLowerCase().includes(term) ||
        po.items?.some(item => item.product_name?.toLowerCase().includes(term) || item.product_sku?.toLowerCase().includes(term))
      );
    }

    this.filteredPurchaseOrders = filtered;
    this.cdr.detectChanges();
  }

  onPOStatusFilterChange(): void {
    this.applyPOFilters();
  }

  onPOSearchChange(): void {
    this.applyPOFilters();
  }

  clearPOFilters(): void {
    this.poStatusFilter = 'all';
    this.poSearchTerm = '';
    this.applyPOFilters();
  }

  approvePurchaseOrder(orderId: number): void {
    this.apiService.approvePurchaseOrder(orderId).subscribe({
      next: (updatedOrder: PurchaseOrder) => {
        const index = this.purchaseOrders.findIndex(po => po.id_orden_compra === orderId);
        if (index !== -1) {
          this.purchaseOrders[index] = updatedOrder;
        }
        this.filteredPurchaseOrders = [...this.purchaseOrders];
        this.applyPOFilters();
        this.cdr.detectChanges();
      },
      error: (err: any) => {
        console.error('Error aprobando orden:', err);
        this.errorMessage = 'Error al aprobar la orden: ' + (err.error?.detail || 'Intente de nuevo');
        this.cdr.detectChanges();
      }
    });
  }

  receivePurchaseOrder(orderId: number): void {
    this.apiService.receivePurchaseOrder(orderId).subscribe({
      next: (updatedOrder: PurchaseOrder) => {
        const index = this.purchaseOrders.findIndex(po => po.id_orden_compra === orderId);
        if (index !== -1) {
          this.purchaseOrders[index] = updatedOrder;
        }
        this.filteredPurchaseOrders = [...this.purchaseOrders];
        this.applyPOFilters();
        this.loadDashboardData();
        this.cdr.detectChanges();
      },
      error: (err: any) => {
        console.error('Error recibiendo orden:', err);
        this.errorMessage = 'Error al recibir la orden: ' + (err.error?.detail || 'Intente de nuevo');
        this.cdr.detectChanges();
      }
    });
  }

  autoGeneratePOs(): void {
    this.apiService.autoGeneratePurchaseOrders().subscribe({
      next: (result: any) => {
        console.log('Órdenes generadas automáticamente:', result);
        this.loadPurchaseOrders();
        this.loadDashboardData();
        this.cdr.detectChanges();
      },
      error: (err: any) => {
        console.error('Error generando órdenes automáticas:', err);
        this.errorMessage = 'Error al generar órdenes: ' + (err.error?.detail || 'Intente de nuevo');
        this.cdr.detectChanges();
      }
    });
  }

  setActiveTab(tab: string): void {
    this.activeTab = tab;
  }

  getStockStatus(insight: AdminProductInsight): string {
    if (insight.stock_actual <= 0) return 'Agotado';
    if (insight.riesgo_critico) return 'Riesgo Crítico';
    if (insight.unidades_a_reponer && insight.unidades_a_reponer > 0) return 'Bajo Stock';
    return 'Normal';
  }

  getStockBadgeClass(insight: AdminProductInsight): string {
    if (insight.stock_actual <= 0) return 'badge-error';
    if (insight.riesgo_critico) return 'badge-error';
    if (insight.unidades_a_reponer && insight.unidades_a_reponer > 0) return 'badge-warning';
    return 'badge-success';
  }

  getVelocityLabel(velocidad: number | null): string {
    if (velocidad === null || velocidad === 0) return 'Sin ventas recientes';
    if (velocidad < 0.5) return 'Muy baja';
    if (velocidad < 2) return 'Baja';
    if (velocidad < 5) return 'Media';
    if (velocidad < 10) return 'Alta';
    return 'Muy alta';
  }

  getDaysStockLabel(dias: number | null): string {
    if (dias === null) return 'N/A';
    if (dias <= 0) return 'Agotado';
    if (dias <= 7) return `${dias} días (Crítico)`;
    if (dias <= 14) return `${dias} días (Bajo)`;
    if (dias <= 30) return `${dias} días`;
    return `>30 días`;
  }

  getDaysStockBadgeClass(dias: number | null): string {
    if (dias === null) return 'badge-neutral';
    if (dias <= 0) return 'badge-error';
    if (dias <= 7) return 'badge-error';
    if (dias <= 14) return 'badge-warning';
    return 'badge-success';
  }

  getOrderStatusLabel(status?: string): string {
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

  getOrderStatusClass(status?: string): string {
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

  getPOStatusClass(status?: string): string {
    const classes: Record<string, string> = {
      'Pendiente': 'badge-warning',
      'Aprobada': 'badge-primary',
      'Recibida': 'badge-success',
    };
    return classes[status || ''] || 'badge-neutral';
  }
}