import { Injectable } from '@angular/core';
import {
  HttpRequest,
  HttpHandler,
  HttpEvent,
  HttpInterceptor,
  HttpErrorResponse
} from '@angular/common/http';
import { Observable, throwError, BehaviorSubject } from 'rxjs';
import { catchError, filter, take, switchMap } from 'rxjs/operators';
import { AuthService } from '../services/auth.service';
import { Router } from '@angular/router';

@Injectable()
export class AuthInterceptor implements HttpInterceptor {
  private isRefreshing = false;
  private refreshTokenSubject: BehaviorSubject<string | null> = new BehaviorSubject<string | null>(null);

  constructor(private authService: AuthService, private router: Router) {}

  intercept(request: HttpRequest<unknown>, next: HttpHandler): Observable<HttpEvent<unknown>> {
    // No añadir token a peticiones de auth (login, register, refresh)
    if (request.url.includes('/auth/')) {
      console.log('[AuthInterceptor] Skipping auth for:', request.url);
      return next.handle(request);
    }

    const token = localStorage.getItem('token');

    if (token) {
      console.log('[AuthInterceptor] Adding token to:', request.url);
      request = this.addToken(request, token);
    } else {
      console.log('[AuthInterceptor] No token for:', request.url);
    }

    return next.handle(request).pipe(
      catchError((error: HttpErrorResponse) => {
        console.error('[AuthInterceptor] Error:', error.status, request.url);
        if (error.status === 401 && !request.url.includes('/auth/')) {
          return this.handle401Error(request, next);
        }
        return throwError(() => error);
      })
    );
  }

  private addToken(request: HttpRequest<unknown>, token: string): HttpRequest<unknown> {
    return request.clone({
      setHeaders: {
        Authorization: `Bearer ${token}`
      }
    });
  }

  private handle401Error(request: HttpRequest<unknown>, next: HttpHandler): Observable<HttpEvent<unknown>> {
    if (!this.isRefreshing) {
      this.isRefreshing = true;
      this.refreshTokenSubject.next(null);
      console.log('[AuthInterceptor] Token expired, attempting refresh...');

      return this.authService.refreshToken().pipe(
        switchMap((response: any) => {
          this.isRefreshing = false;
          this.refreshTokenSubject.next(response.access_token);
          console.log('[AuthInterceptor] Token refreshed, retrying request');
          return next.handle(this.addToken(request, response.access_token));
        }),
        catchError((err) => {
          this.isRefreshing = false;
          console.error('[AuthInterceptor] Refresh failed, logging out');
          this.authService.logout();
          return throwError(() => err);
        })
      );
    } else {
      console.log('[AuthInterceptor] Already refreshing, waiting...');
      return this.refreshTokenSubject.pipe(
        filter(token => token !== null),
        take(1),
        switchMap(token => next.handle(this.addToken(request, token!)))
      );
    }
  }
}