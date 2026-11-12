import { Injectable } from '@angular/core';
import {
  CanActivate,
  ActivatedRouteSnapshot,
  RouterStateSnapshot,
  UrlTree,
  Router
} from '@angular/router';
import { Observable } from 'rxjs';
import { AuthService } from '../services/auth.service';

@Injectable({
  providedIn: 'root'
})
export class AuthGuard implements CanActivate {
  constructor(private auth: AuthService, private router: Router) {}

  canActivate(
    route: ActivatedRouteSnapshot,
    state: RouterStateSnapshot
  ): Observable<boolean | UrlTree> | Promise<boolean | UrlTree> | boolean | UrlTree {
    const token = localStorage.getItem('token');
    const isAuthenticated = !!token;

    // Allow access to login/auth pages even if not authenticated
    const publicUrls = ['/auth', '/login'];
    if (publicUrls.some(url => state.url.startsWith(url))) {
      return true;
    }

    if (isAuthenticated) {
      // If the route requires admin, verify role
      if (state.url.includes('admin')) {
        const role = this.auth.userValue?.user?.role;
        if (role !== 'admin') {
          this.router.navigate(['/shop']);
          return false;
        }
      }
      return true;
    }

    // Not authenticated and trying to access a protected route
    return this.router.createUrlTree(['/login'], {
      queryParams: { returnUrl: state.url }
    });
  }
}