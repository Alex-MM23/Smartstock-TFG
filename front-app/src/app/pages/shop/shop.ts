import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { CartService, Product } from '../../services/cart.service';
import { ApiService } from '../../services/api';

@Component({
  selector: 'app-shop',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './shop.html',
  styleUrl: './shop.css'
})
export class Shop implements OnInit {
  products: Product[] = [];
  filteredProducts: Product[] = [];
  selectedCategory: string = 'All';
  searchTerm: string = '';
  sortBy: string = 'name';
  maxPrice: number = 500;
  showOnlyInStock: boolean = false;
  loading: boolean = true;
  errorMessage: string = '';
  placeholderImage: string = 'https://images.unsplash.com/photo-1518770660439-4636190af475?w=400';
  categories: string[] = ['Hardware', 'Software', 'Accesorios'];

  constructor(
    private cartService: CartService,
    private apiService: ApiService,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    console.log('[Shop] ngOnInit - Iniciando carga');
    this.loadProductsFromDatabase();
  }

  // Petición real al backend FastAPI para recuperar los productos de MySQL
  loadProductsFromDatabase(): void {
    this.loading = true;
    this.errorMessage = '';

    console.log('[Shop] Iniciando carga de productos desde:', this.apiService['baseUrl'] || 'ruta relativa');

    this.apiService.getProducts().subscribe({
      next: (data: any) => {
        try {
          console.log('[Shop] Respuesta recibida:', data);
          // Mapeamos los datos asegurando que coincidan con la interfaz Product
          this.products = Array.isArray(data) ? data : (data.items || data.products || []);
          console.log('[Shop] Productos parseados:', this.products.length);

          // Extraer categorías únicas de los productos
          const cats = new Set(this.products.map(p => p.category).filter((c): c is string => Boolean(c)));
          this.categories = ['Hardware', 'Software', 'Accesorios', ...Array.from(cats)].filter(
            (v, i, a) => a.indexOf(v) === i
          );

          console.log('[Shop] Categorías:', this.categories);
          console.log('[Shop] Llamando applyFilters...');
          this.applyFilters();
          console.log('[Shop] applyFilters completado, filteredProducts:', this.filteredProducts.length);

          this.loading = false;
          console.log('[Shop] loading = false, UI debería actualizarse');
          this.cdr.detectChanges();
        } catch (e) {
          console.error('[Shop] EXCEPCIÓN en next:', e);
          this.errorMessage = `Error procesando datos: ${e}`;
          this.loading = false;
          this.cdr.detectChanges();
        }
      },
      error: (err: any) => {
        console.error('[Shop] ERROR DETALLADO:', {
          status: err.status,
          statusText: err.statusText,
          url: err.url,
          message: err.message,
          error: err.error
        });
        this.loading = false;
        if (err.status === 0) {
          this.errorMessage = 'Error de red: No se puede conectar al servidor (¿CORS? ¿API apagada?)';
        } else if (err.status === 404) {
          this.errorMessage = 'Endpoint no encontrado (404). Verifica la URL de la API.';
        } else if (err.status === 503) {
          this.errorMessage = 'Servicio no disponible (503). ¿Base de datos caída?';
        } else {
          this.errorMessage = `Error ${err.status}: ${err.error?.detail || err.message || 'Desconocido'}`;
        }
        this.cdr.detectChanges();
      }
    });
  }

  get hasActiveFilters(): boolean {
    return this.searchTerm !== '' || this.selectedCategory !== 'All' || this.maxPrice < 500 || this.showOnlyInStock;
  }

  clearFilters(): void {
    this.searchTerm = '';
    this.selectedCategory = 'All';
    this.maxPrice = 500;
    this.sortBy = 'name';
    this.showOnlyInStock = false;
    this.applyFilters();
    this.cdr.detectChanges();
  }

  filterByCategory(category: string): void {
    this.selectedCategory = category;
    this.applyFilters();
    this.cdr.detectChanges();
  }

  getCategoryCount(category: string): number {
    if (category === 'All') return this.products.length;
    return this.products.filter(p => p.category === category).length;
  }

  getStockLabel(stock: number): string {
    if (stock <= 0) return 'Agotado';
    if (stock <= 5) return 'Pocas unidades';
    return 'En stock';
  }

  getProductDescription(product: Product): string {
    const descriptions: Record<string, string> = {
      'Hardware': 'Dispositivo IoT industrial para monitorización y control automatizado.',
      'Software': 'Licencia de algoritmo de predicción ML con actualizaciones incluidas.',
      'Accesorios': 'Componentes y consumibles para infraestructura de inventario inteligente.',
    };
    return descriptions[product.category || ''] || 'Producto integrado en el ecosistema SmartStock AI.';
  }

  applyFilters(): void {
    try {
      console.log('[Shop] applyFilters INICIO - products:', this.products.length, 'selectedCategory:', this.selectedCategory, 'searchTerm:', this.searchTerm, 'maxPrice:', this.maxPrice, 'showOnlyInStock:', this.showOnlyInStock);

      let filtered = [...this.products];

      // Filtro por búsqueda
      if (this.searchTerm.trim()) {
        const term = this.searchTerm.toLowerCase().trim();
        filtered = filtered.filter(item =>
          item.title?.toLowerCase().includes(term) ||
          item.category?.toLowerCase().includes(term)
        );
        console.log('[Shop] Tras filtro búsqueda:', filtered.length);
      }

      // Filtro por categoría
      if (this.selectedCategory !== 'All') {
        filtered = filtered.filter(item => item.category === this.selectedCategory);
        console.log('[Shop] Tras filtro categoría:', filtered.length);
      }

      // Filtro por precio
      filtered = filtered.filter(item => item.price <= this.maxPrice);
      console.log('[Shop] Tras filtro precio:', filtered.length);

      // Filtro solo en stock
      if (this.showOnlyInStock) {
        filtered = filtered.filter(item => item.cantidad > 0);
        console.log('[Shop] Tras filtro solo en stock:', filtered.length);
      }

      // Ordenación
      switch (this.sortBy) {
        case 'name':
          filtered.sort((a, b) => (a.title || '').localeCompare(b.title || ''));
          break;
        case 'name-desc':
          filtered.sort((a, b) => (b.title || '').localeCompare(a.title || ''));
          break;
        case 'price-asc':
          filtered.sort((a, b) => a.price - b.price);
          break;
        case 'price-desc':
          filtered.sort((a, b) => b.price - a.price);
          break;
        case 'stock':
          filtered.sort((a, b) => b.cantidad - a.cantidad);
          break;
      }

      this.filteredProducts = filtered;
      console.log('[Shop] applyFilters FIN - filteredProducts:', this.filteredProducts.length);
      this.cdr.detectChanges();
    } catch (e) {
      console.error('[Shop] EXCEPCIÓN en applyFilters:', e);
      this.filteredProducts = [];
    }
  }

  addToCart(product: Product): void {
    // Añadir 1 unidad por defecto, no todo el stock
    this.cartService.addProduct({ ...product, cantidad: 1 });
  }
}