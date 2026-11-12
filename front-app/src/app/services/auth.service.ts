import { Injectable } from '@angular/core';
import { Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable, tap } from 'rxjs';
import { environment } from '../../environments/environment';

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  refresh_token: string;
  user: {
    id: number;
    email: string;
    role: 'client' | 'admin';
    is_active: boolean;
    avatarUrl?: string;
  };
}

export interface RegisterRequest {
  email: string;
  password: string;
  role?: 'client' | 'admin';
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private apiUrl = environment.apiUrl;
  private _user$ = new BehaviorSubject<LoginResponse | null>(null);
  user$: Observable<LoginResponse | null> = this._user$.asObservable();

  constructor(private http: HttpClient, private router: Router) {
    // Intentar restaurar sesión al iniciar
    const token = localStorage.getItem('token');
    if (token) {
      // El interceptor manejará el refresh si es necesario
      this.loadUserFromToken(token);
    }
  }

  private getAuthUrl(path: string): string {
    if (!this.apiUrl) {
      return `/auth${path}`;
    }
    return `${this.apiUrl}/auth${path}`;
  }

  private loadUserFromToken(token: string): void {
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      this._user$.next({
        access_token: token,
        token_type: 'bearer',
        expires_in: payload.exp - Math.floor(Date.now() / 1000),
        refresh_token: localStorage.getItem('refresh_token') || '',
        user: {
          id: payload.user_id,
          email: payload.sub,
          role: payload.role,
          is_active: true
        }
      });
    } catch {
      // Token inválido, limpiar
      this.logout();
    }
  }

  login(email: string, password: string): Observable<LoginResponse> {
    return this.http.post<LoginResponse>(this.getAuthUrl('/login'), { email, password })
      .pipe(
        tap(res => {
          localStorage.setItem('token', res.access_token);
          localStorage.setItem('refresh_token', res.refresh_token);
          this._user$.next(res);
          this.router.navigate(['/shop']);
        })
      );
  }

  register(data: RegisterRequest): Observable<LoginResponse> {
    return this.http.post<LoginResponse>(this.getAuthUrl('/register'), data)
      .pipe(
        tap(res => {
          localStorage.setItem('token', res.access_token);
          localStorage.setItem('refresh_token', res.refresh_token);
          this._user$.next(res);
          this.router.navigate(['/shop']);
        })
      );
  }

  logout(): void {
    localStorage.removeItem('token');
    localStorage.removeItem('refresh_token');
    this._user$.next(null);
    this.router.navigate(['/login']);
  }

  isAuthenticated(): boolean {
    return !!localStorage.getItem('token');
  }

  getToken(): string | null {
    return localStorage.getItem('token');
  }

  getRefreshToken(): string | null {
    return localStorage.getItem('refresh_token');
  }

  refreshToken(): Observable<LoginResponse> {
    const refreshToken = this.getRefreshToken();
    if (!refreshToken) {
      throw new Error('No hay refresh token disponible');
    }
    return this.http.post<LoginResponse>(this.getAuthUrl('/refresh'), { refresh_token: refreshToken })
      .pipe(tap(res => {
        localStorage.setItem('token', res.access_token);
        localStorage.setItem('refresh_token', res.refresh_token);
        this._user$.next(res);
      }));
  }

  getCurrentUser(): LoginResponse['user'] | null {
    return this._user$.value?.user || null;
  }

  isAdmin(): boolean {
    return this.getCurrentUser()?.role === 'admin';
  }

  // Public getter for current user value (for guards)
  get userValue(): LoginResponse | null {
    return this._user$.value;
  }
}