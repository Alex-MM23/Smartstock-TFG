import { Routes } from '@angular/router';
import { AuthGuard } from './guards/auth.guard';

export const routes: Routes = [
  { path: '', redirectTo: 'home', pathMatch: 'full' },

  // Home (pública)
  { path: 'home', loadComponent: () => import('./pages/home/home').then(m => m.Home) },

  // Login (página dedicada solo login)
  { path: 'login', loadComponent: () => import('./pages/login/login.component').then(m => m.LoginComponent) },

  // Auth (login + registro combinados)
  { path: 'auth', loadComponent: () => import('./pages/auth/auth').then(m => m.Auth) },

  // Tienda (protegida)
  { path: 'shop', loadComponent: () => import('./pages/shop/shop').then(m => m.Shop), canActivate: [AuthGuard] },

  // Producto
  { path: 'product/:id', loadComponent: () => import('./pages/product-detail/product-detail').then(m => m.ProductDetail) },

  // Carrito
  { path: 'cart', loadComponent: () => import('./pages/cart/cart').then(m => m.Cart) },

  // Pedidos (protegida)
  { path: 'orders', loadComponent: () => import('./pages/orders/orders').then(m => m.Orders), canActivate: [AuthGuard] },

  // Detalle de Pedido (protegida)
  { path: 'orders/:id', loadComponent: () => import('./pages/orders/order-detail').then(m => m.OrderDetail), canActivate: [AuthGuard] },

  // Panel de Administración (protegida, solo admin)
  { path: 'admin', loadComponent: () => import('./pages/admin/admin-dashboard.component').then(m => m.AdminDashboardComponent), canActivate: [AuthGuard] },

  // Diagnóstico API (pública)
  { path: 'health', loadComponent: () => import('./pages/health/health').then(m => m.Health) },

  // fallback
  { path: '**', redirectTo: 'home' }
];