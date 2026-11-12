import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { FormBuilder, Validators } from '@angular/forms';
import { AuthService } from '../../services/auth.service';
import { Router } from '@angular/router';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule, ReactiveFormsModule],
  templateUrl: './login.html',
  styleUrl: './login.css'
})
export class LoginComponent {
  private fb = inject(FormBuilder);
  private auth = inject(AuthService);
  private router = inject(Router);

  loginForm = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', Validators.required]
  });

  errorMsg = '';
  isLoading = false;
  showPassword = false;

  onSubmit(): void {
    if (this.loginForm.invalid) {
      this.errorMsg = 'Completa todos los campos correctamente.';
      return;
    }

    this.isLoading = true;
    this.errorMsg = '';

    this.auth.login(this.loginForm.value.email!, this.loginForm.value.password!).subscribe({
      next: (res) => {
        // Redirigir según rol
        res.user.role === 'admin' ? this.router.navigate(['/admin']) : this.router.navigate(['/shop']);
      },
      error: (err) => {
        this.errorMsg = err.error?.detail || 'Credenciales incorrectas o el servidor no responde.';
        console.error(err);
      },
      complete: () => {
        this.isLoading = false;
      }
    });
  }

  goToRegister(): void {
    this.router.navigate(['/auth']);
  }

  get email() { return this.loginForm.get('email'); }
  get password() { return this.loginForm.get('password'); }
}