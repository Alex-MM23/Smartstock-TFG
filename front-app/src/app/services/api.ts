import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private baseUrl = environment.apiUrl;

  constructor(private http: HttpClient) {}

  private getUrl(path: string): string {
    if (!this.baseUrl) {
      return path;
    }
    return `${this.baseUrl}${path}`;
  }

  private logRequest(method: string, url: string): void {
    console.log(`[ApiService] ${method} ${url}`);
  }

  private logResponse(method: string, url: string, data: any): void {
    console.log(`[ApiService] ${method} ${url} ✓`, data);
  }

  private logError(method: string, url: string, error: any): void {
    console.error(`[ApiService] ${method} ${url} ✗`, error);
  }

  getHealth(): Observable<any> {
    const url = this.getUrl('/health');
    this.logRequest('GET', url);
    return this.http.get(url).pipe(
      tap(data => this.logResponse('GET', url, data)),
      tap({ error: err => this.logError('GET', url, err) })
    );
  }

  getStockStatus(): Observable<any> {
    const url = this.getUrl('/stock/status');
    this.logRequest('GET', url);
    return this.http.get(url).pipe(
      tap(data => this.logResponse('GET', url, data)),
      tap({ error: err => this.logError('GET', url, err) })
    );
  }

  getProducts(): Observable<any> {
    const url = this.getUrl('/products');
    this.logRequest('GET', url);
    return this.http.get(url).pipe(
      tap(data => this.logResponse('GET', url, data)),
      tap({ error: err => this.logError('GET', url, err) })
    );
  }

  predictDemand(payload: any): Observable<any> {
    const url = this.getUrl('/predict/demand');
    this.logRequest('POST', url);
    return this.http.post(url, payload).pipe(
      tap(data => this.logResponse('POST', url, data)),
      tap({ error: err => this.logError('POST', url, err) })
    );
  }

  createOrder(orderData: any): Observable<any> {
    const url = this.getUrl('/orders');
    this.logRequest('POST', url);
    return this.http.post(url, orderData).pipe(
      tap(data => this.logResponse('POST', url, data)),
      tap({ error: err => this.logError('POST', url, err) })
    );
  }

  getOrders(): Observable<any> {
    const url = this.getUrl('/orders');
    this.logRequest('GET', url);
    return this.http.get(url).pipe(
      tap(data => this.logResponse('GET', url, data)),
      tap({ error: err => this.logError('GET', url, err) })
    );
  }

  getOrderById(orderId: number): Observable<any> {
    const url = this.getUrl(`/orders/${orderId}`);
    this.logRequest('GET', url);
    return this.http.get(url).pipe(
      tap(data => this.logResponse('GET', url, data)),
      tap({ error: err => this.logError('GET', url, err) })
    );
  }

  getAdminDashboard(): Observable<any> {
    const url = this.getUrl('/admin/dashboard');
    this.logRequest('GET', url);
    return this.http.get(url).pipe(
      tap(data => this.logResponse('GET', url, data)),
      tap({ error: err => this.logError('GET', url, err) })
    );
  }

  getPurchaseOrders(): Observable<any> {
    const url = this.getUrl('/api/purchase-orders');
    this.logRequest('GET', url);
    return this.http.get(url).pipe(
      tap(data => this.logResponse('GET', url, data)),
      tap({ error: err => this.logError('GET', url, err) })
    );
  }

  approvePurchaseOrder(orderId: number): Observable<any> {
    const url = this.getUrl(`/api/purchase-orders/${orderId}/approve`);
    this.logRequest('PUT', url);
    return this.http.put(url, {}).pipe(
      tap(data => this.logResponse('PUT', url, data)),
      tap({ error: err => this.logError('PUT', url, err) })
    );
  }

  receivePurchaseOrder(orderId: number): Observable<any> {
    const url = this.getUrl(`/api/purchase-orders/${orderId}/receive`);
    this.logRequest('PUT', url);
    return this.http.put(url, {}).pipe(
      tap(data => this.logResponse('PUT', url, data)),
      tap({ error: err => this.logError('PUT', url, err) })
    );
  }

  autoGeneratePurchaseOrders(): Observable<any> {
    const url = this.getUrl('/api/purchase-orders/auto-generate');
    this.logRequest('POST', url);
    return this.http.post(url, {}).pipe(
      tap(data => this.logResponse('POST', url, data)),
      tap({ error: err => this.logError('POST', url, err) })
    );
  }
}