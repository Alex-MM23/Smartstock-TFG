import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Router } from '@angular/router';
import { CartService, Product } from '../../services/cart.service';
import { ApiService } from '../../services/api';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-cart',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './cart.html',
  styleUrl: './cart.css'
})
export class Cart implements OnInit {
  cartItems: Product[] = [];
  totalAmount: number = 0;
  isSubmitting: boolean = false;
  orderSuccess: boolean = false;
  errorMessage: string = '';
  placeholderImage: string = 'https://images.unsplash.com/photo-1518770660439-4636190af475?w=400';

  constructor(
    private cartService: CartService,
    private apiService: ApiService,
    private authService: AuthService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.cartService.myCart$.subscribe(items => {
      this.cartItems = items;
      this.totalAmount = this.cartService.totalCart();
    });
  }

  getTotalItems(): number {
    return this.cartItems.reduce((acc, item) => acc + item.cantidad, 0);
  }

  increaseQuantity(product: Product): void {
    this.cartService.addProduct({ ...product, cantidad: 1 });
  }

  decreaseQuantity(product: Product): void {
    if (product.cantidad > 1) {
      this.cartService.addProduct({ ...product, cantidad: -1 });
    } else {
      this.cartService.deleteProduct(product.id);
    }
  }

  removeItem(id: number): void {
    this.cartService.deleteProduct(id);
  }

  checkout(): void {
    if (this.cartItems.length === 0) return;

    const user = this.authService.getCurrentUser();
    if (!user) {
      this.errorMessage = 'Debe iniciar sesión para realizar un pedido';
      this.router.navigate(['/login'], { queryParams: { returnUrl: '/cart' } });
      return;
    }

    this.isSubmitting = true;
    this.errorMessage = '';

    const orderPayload = {
      user_id: user.id,
      items: this.cartItems.map(item => ({
        product_id: item.id,
        quantity: item.cantidad,
        price: item.price
      }))
    };

    this.apiService.createOrder(orderPayload).subscribe({
      next: (res: any) => {
        this.isSubmitting = false;
        this.orderSuccess = true;
        this.cartService.clearCart();

        setTimeout(() => {
          this.router.navigate(['/orders']);
        }, 2000);
      },
      error: (err: any) => {
        this.isSubmitting = false;
        this.errorMessage = err.error?.detail || 'Error al procesar el pedido. Intente de nuevo.';
        console.error('Error en checkout:', err);
      }
    });
  }
}