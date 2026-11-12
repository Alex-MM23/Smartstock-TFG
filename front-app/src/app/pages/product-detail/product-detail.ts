import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterModule, Router } from '@angular/router';
import { CartService, Product } from '../../services/cart.service';
import { ApiService } from '../../services/api';

@Component({
  selector: 'app-product-detail',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './product-detail.html',
  styleUrl: './product-detail.css'
})
export class ProductDetail implements OnInit {
  product: Product | undefined;
  quantity: number = 1;
  addedMessage: boolean = false;
  loading: boolean = true;
  errorMessage: string = '';
  placeholderImage: string = 'https://images.unsplash.com/photo-1518770660439-4636190af475?w=400';

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private cartService: CartService,
    private apiService: ApiService
  ) {}

  ngOnInit(): void {
    const productId = Number(this.route.snapshot.paramMap.get('id'));
    this.loadProduct(productId);
  }

  loadProduct(id: number): void {
    this.loading = true;
    this.errorMessage = '';

    // Primero intentamos cargar desde la API real
    this.apiService.getProducts().subscribe({
      next: (data: any) => {
        const products = Array.isArray(data) ? data : (data.items || data.products || []);
        this.product = products.find((p: Product) => p.id === id);

        if (!this.product) {
          // Fallback a datos locales si no se encuentra
          this.loadFallbackProduct(id);
        }
        this.loading = false;
      },
      error: (err) => {
        console.error('Error cargando producto:', err);
        this.loadFallbackProduct(id);
        this.loading = false;
      }
    });
  }

  loadFallbackProduct(id: number): void {
    const fallbackProducts: Product[] = [
      { id: 1, title: 'Sensor IoT Industrial ESP32', price: 45.00, cantidad: 1, category: 'Hardware', image: 'https://images.unsplash.com/photo-1518770660439-4636190af475?w=400' },
      { id: 2, title: 'Módulo de Cámara Alta Definición', price: 29.99, cantidad: 1, category: 'Hardware', image: 'https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=400' },
      { id: 3, title: 'Licencia Algoritmo Predicción ML (1 Mes)', price: 120.00, cantidad: 1, category: 'Software', image: 'https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=400' },
      { id: 4, title: 'Gateway LoRaWAN para Almacén', price: 210.50, cantidad: 1, category: 'Hardware', image: 'https://images.unsplash.com/photo-1544197150-b99a580bb7a8?w=400' },
      { id: 5, title: 'Kit de Etiquetas RFID para Inventario (100 uds)', price: 35.00, cantidad: 1, category: 'Accesorios', image: 'https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?w=400' },
      { id: 6, title: 'Suscripción Enterprise API SmartStock', price: 450.00, cantidad: 1, category: 'Software', image: 'https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=400' }
    ];
    this.product = fallbackProducts.find(p => p.id === id);
    if (!this.product) {
      this.errorMessage = 'Producto no encontrado';
    }
  }

  getStockText(stock: number): string {
    if (stock <= 0) return 'Agotado';
    if (stock <= 5) return 'Pocas unidades disponibles';
    return 'En stock - Envío inmediato';
  }

  getProductDescription(product: Product): string {
    const descriptions: Record<string, string> = {
      'Hardware': 'Dispositivo IoT industrial de alta precisión para monitorización y control automatizado en tiempo real. Compatible con protocolos MQTT, HTTP y WebSocket. Incluye SDK para integración rápida con SmartStock AI.',
      'Software': 'Licencia de algoritmo de predicción de demanda basado en Gradient Boosting. Incluye actualizaciones automáticas del modelo, API REST para integración, dashboard de métricas y soporte técnico prioritario.',
      'Accesorios': 'Componentes y consumibles certificados para infraestructura de inventario inteligente. Garantía de compatibilidad total con dispositivos SmartStock.',
    };
    return descriptions[product.category || ''] || 'Producto integrado en el ecosistema SmartStock AI. Optimizado para la monitorización en tiempo real y el control automatizado de inventarios en entornos industriales y de e-commerce.';
  }

  increment(): void {
    if (this.product && this.quantity < this.product.cantidad) {
      this.quantity++;
    }
  }

  decrement(): void {
    if (this.quantity > 1) {
      this.quantity--;
    }
  }

  addToCart(): void {
    if (this.product && this.product.cantidad > 0) {
      this.cartService.addProduct({ ...this.product, cantidad: this.quantity });
      this.addedMessage = true;
      setTimeout(() => {
        this.addedMessage = false;
      }, 2500);
    }
  }
}