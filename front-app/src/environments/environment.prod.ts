// src/environments/environment.prod.ts
// En producción (Docker), el frontend se sirve desde nginx en el puerto 80
// y las peticiones API se hacen al mismo origen (nginx hace proxy al backend)
export const environment = {
  production: true,
  apiUrl: ''
};