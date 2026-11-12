import { Injectable } from '@angular/core';
import { BehaviorSubject } from 'rxjs';

export interface Product {
  id: number;
  title: string;
  price: number;
  cantidad: number;
  image?: string;
  category?: string;
  rating?: number;
}

@Injectable({
  providedIn: 'root'
})
export class CartService {
  private cart: Product[] = [];
  private cartSubject = new BehaviorSubject<Product[]>([]);
  myCart$ = this.cartSubject.asObservable();

  constructor() {}

  // Añadir producto o incrementar cantidad si ya existe
  addProduct(product: Product): void {
    const existing = this.cart.find(item => item.id === product.id);
    if (existing) {
      existing.cantidad += (product.cantidad || 1);
    } else {
      this.cart.push({ ...product, cantidad: product.cantidad || 1 });
    }
    this.cartSubject.next([...this.cart]);
  }

  // Buscar producto dentro del carrito actual
  findProductById(id: number): Product | undefined {
    return this.cart.find(item => item.id === id);
  }

  // Eliminar un producto específico
  deleteProduct(id: number): void {
    this.cart = this.cart.filter(item => item.id !== id);
    this.cartSubject.next([...this.cart]);
  }

  // Vaciar el carrito por completo (tras realizar el pedido)
  clearCart(): void {
    this.cart = [];
    this.cartSubject.next([...this.cart]);
  }

  // Obtener instantánea para enviar al backend
  getCartSnapshot(): Product[] {
    return [...this.cart];
  }

  // Calcular el precio total del carrito
  totalCart(): number {
    return this.cart.reduce((acc, item) => acc + (item.price * item.cantidad), 0);
  }
}