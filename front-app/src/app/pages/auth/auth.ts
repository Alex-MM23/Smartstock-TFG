import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService, RegisterRequest } from '../../services/auth.service';

@Component({
  selector: 'app-auth',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './auth.html',
  styleUrl: './auth.css'
})
export class Auth {
  isLoginMode: boolean = true;
  showPassword: boolean = false;

  credentials = {
    email: '',
    password: '',
    name: ''
  };

  errorMessage: string = '';
  loading: boolean = false;

  constructor(private authService: AuthService, private router: Router) {}

  toggleMode(): void {
    this.isLoginMode = !this.isLoginMode;
    this.errorMessage = '';
    this.credentials = { email: '', password: '', name: '' };
  }

  onSubmit(): void {
    this.loading = true;
    this.errorMessage = '';

    if (this.isLoginMode) {
      this.authService.login(this.credentials.email, this.credentials.password).subscribe({
        next: () => {
          this.loading = false;
          // Navigation handled in service
        },
        error: (err) => {
          this.loading = false;
          this.errorMessage = err.error?.detail || 'Email o contraseña incorrectos';
        }
      });
    } else {
      const registerData: RegisterRequest = {
        email: this.credentials.email,
        password: this.credentials.password,
        role: 'client'
      };
      this.authService.register(registerData).subscribe({
        next: () => {
          this.loading = false;
          // Navigation handled in service
        },
        error: (err) => {
          this.loading = false;
          this.errorMessage = err.error?.detail || 'Error al registrar usuario';
        }
      });
    }
  }
}