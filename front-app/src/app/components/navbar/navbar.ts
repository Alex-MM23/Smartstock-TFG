import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterModule } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import { CartService } from '../../services/cart.service';
import { map } from 'rxjs/operators';
import { Observable } from 'rxjs';

@Component({
  selector: 'app-navbar',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './navbar.html',
  styleUrl: './navbar.css'
})
export class Navbar implements OnInit {
  isLoggedIn: boolean = false;
  userName: string = 'Alex Santiago';
  userAvatar: string = 'https://api.dicebear.com/7.x/avataaars/svg?seed=Alex';

  // Observable para contar total de unidades en el carrito de forma reactiva
  cartItemCount$!: Observable<number>;

  constructor(
    private auth: AuthService,
    private router: Router,
    private cartService: CartService
  ) {}

  ngOnInit(): void {
    this.auth.user$.subscribe((user) => {
      this.isLoggedIn = !!user;
      if (user) {
        this.userName = user.user.email;
        this.userAvatar = user.user.avatarUrl || this.userAvatar;
      } else {
        this.userName = 'Alex Santiago';
        this.userAvatar = 'https://api.dicebear.com/7.x/avataaars/svg?seed=Alex';
      }
    });

    // Contador de carrito
    this.cartItemCount$ = this.cartService.myCart$.pipe(
      map(items => items.reduce((acc, item) => acc + item.cantidad, 0))
    );
  }

  isAdmin(): boolean {
    return this.auth.isAdmin();
  }

  logout(): void {
    this.auth.logout();
    this.router.navigate(['/home']);
  }
}