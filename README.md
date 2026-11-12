# SmartStock AI

Sistema de predicción de demanda y optimización de inventario para e-commerce, construido con **FastAPI** (Python), **Angular 22**, **MySQL** y **scikit-learn**.

## 🏗️ Arquitectura

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Angular 22    │────▶│    FastAPI      │────▶│     MySQL 8     │
│   (Frontend)    │     │    (Backend)    │     │   (Database)    │
│   Puerto 4200   │     │   Puerto 8000   │     │   Puerto 3306   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                              │
                              ▼
                      ┌─────────────────┐
                      │  ML Model       │
                      │  (joblib)       │
                      │  Random Forest  │
                      │  / Gradient     │
                      │  Boosting       │
                      └─────────────────┘
```

## ✨ Características

- **Predicción de demanda** con ML (Random Forest / HistGradientBoosting)
- **Stock de seguridad** calculado con nivel de servicio configurable (z-score)
- **Autenticación JWT** con access + refresh tokens
- **Panel de administración** con métricas en tiempo real
- **Catálogo de productos** con filtros, búsqueda y paginación
- **Carrito de compras** y gestión de pedidos
- **Docker Compose** para desarrollo y producción
- **CI/CD** con GitHub Actions

## 🚀 Inicio Rápido

### Prerrequisitos

- Docker y Docker Compose
- O bien: Python 3.12+, Node.js 22+, MySQL 8+

### Con Docker (Recomendado)

```bash
# Clonar y configurar
git clone <repo-url>
cd Smartstock-TFG

# Configurar variables de entorno
cp Back/.env.example Back/.env
# Editar Back/.env si es necesario

# Levantar servicios
docker-compose up -d

# Inicializar base de datos, cargar datos y entrenar modelo
docker exec -it smartstock_api python -m src.data.migrations
docker exec -it smartstock_api python -m src.data.ingest --dias 730
docker exec -it smartstock_api python -m src.models.train

# Acceder a la aplicación
# Frontend: http://localhost:4200
# API Docs: http://localhost:8000/docs
# Admin: admin@smartstock.com / admin123
```

### Desarrollo Local (sin Docker)

```bash
# Backend
cd Back
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Configurar MySQL local en .env
python -m src.data.migrations
python -m src.data.ingest --dias 730
python -m src.models.train
uvicorn src.api.main:app --reload

# Frontend (en otra terminal)
cd front-app
npm install
npm start
```

## 📋 Comandos Útiles (Makefile)

```bash
make help          # Ver todos los comandos disponibles
make dev           # Iniciar desarrollo completo (Docker)
make test          # Ejecutar todos los tests
make test-backend  # Tests solo backend
make test-frontend # Tests solo frontend
make lint          # Linting (ruff + prettier)
make db-init       # Crear tablas y vistas
make db-ingest     # Cargar datos de ejemplo
make db-train      # Entrenar modelo ML
make db-reset      # Reset completo BD + datos + modelo
make docker-up     # Levantar stack Docker
make docker-down   # Bajar stack Docker
make prod-up       # Levantar stack producción
make clean         # Limpiar cachés y artefactos
```

## 🔧 Configuración

### Variables de Entorno Principales (`.env`)

| Variable | Descripción | Default |
|----------|-------------|---------|
| `DB_HOST` | Host MySQL | `localhost` |
| `DB_PORT` | Puerto MySQL | `3306` |
| `DB_USER` | Usuario BD | `smartstock` |
| `DB_PASSWORD` | Contraseña BD | `smartstock_pass` |
| `DB_NAME` | Nombre BD | `smartstock` |
| `SECRET_KEY` | Clave JWT **(cambiar en prod!)** | `super-secret...` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Expiración access token | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Expiración refresh token | `7` |
| `SERVICE_LEVEL_Z` | Nivel servicio (z-score) | `1.645` (95%) |
| `MODEL_PATH` | Ruta modelo ML | `artifacts/demand_model.joblib` |

### Niveles de Servicio (SERVICE_LEVEL_Z)

| Z-score | Nivel de Servicio |
|---------|-------------------|
| 1.28 | 90% |
| 1.645 | 95% |
| 1.96 | 97.5% |
| 2.33 | 99% |

## 📚 API Endpoints

### Sistema
- `GET /health` - Estado del servicio

### Autenticación
- `POST /auth/register` - Registrar usuario
- `POST /auth/login` - Login (devuelve access + refresh token)
- `POST /auth/refresh` - Renovar access token
- `GET /auth/me` - Info usuario actual

### Inventario
- `GET /stock/status` - Stock con alertas (usa vista `v_stock_alerta`)
- `GET /products` - Catálogo productos activos

### Predicción
- `POST /predict/demand` - Predecir demanda y stock recomendado
  ```json
  {
    "sku": "SS-ELE-001",
    "horizonte_dias": 14,
    "guardar": true
  }
  ```

### Pedidos
- `GET /orders` - Listar pedidos (usa tablas legacy `pedidos`/`detalle_pedido`)
- `GET /orders/{id}` - Detalle de pedido

## 🧪 Tests

```bash
# Backend
cd Back
pytest tests/ -v

# Frontend
cd front-app
npm test -- --run
```

## 🐳 Docker Producción

```bash
# Configurar variables de producción
cp .env.production.example .env
# Editar .env con valores seguros

# Construir y levantar
docker-compose -f docker-compose.prod.yml up -d --build

# Ver logs
docker-compose -f docker-compose.prod.yml logs -f
```

### Puertos en Producción
- **80** - Frontend (nginx) + API proxy
- **8000** - API directa (opcional, solo interno)

## 📁 Estructura del Proyecto

```
Smartstock-TFG/
├── Back/                    # Backend FastAPI
│   ├── src/
│   │   ├── api/            # Endpoints REST
│   │   ├── auth/           # Autenticación JWT
│   │   ├── config.py       # Configuración centralizada
│   │   ├── data/           # Ingesta, preprocesamiento, migraciones
│   │   └── models/         # Entrenamiento ML
│   ├── models.py           # Modelos SQLAlchemy
│   ├── database.py         # Configuración BD
│   ├── requirements.txt
│   ├── Dockerfile
│   └── tests/              # Tests pytest
├── front-app/              # Frontend Angular 22
│   ├── src/
│   │   ├── app/
│   │   │   ├── components/ # Navbar, etc.
│   │   │   ├── pages/      # Home, Shop, Cart, Orders, Admin, Auth
│   │   │   ├── services/   # ApiService, AuthService, CartService
│   │   │   ├── guards/     # AuthGuard
│   │   │   └── interceptors/ # AuthInterceptor (auto-refresh)
│   │   └── environments/
│   ├── nginx.conf          # Config nginx producción
│   ├── Dockerfile.prod
│   └── package.json
├── docker-compose.yml      # Desarrollo
├── docker-compose.prod.yml # Producción
├── Makefile                # Comandos de desarrollo
├── .github/workflows/      # CI/CD GitHub Actions
└── .pre-commit-config.yaml # Pre-commit hooks
```

## 🤝 Contribuir

1. Fork el repositorio
2. Crea una rama: `git checkout -b feature/nueva-funcionalidad`
3. Instala pre-commit: `pip install pre-commit && pre-commit install`
4. Haz tus cambios y commit: `git commit -m "feat: nueva funcionalidad"`
5. Push: `git push origin feature/nueva-funcionalidad`
6. Abre un Pull Request

## 📄 Licencia

TFG - Trabajo de Fin de Grado. Uso educativo.

## 👨‍💻 Autor

Alex Santiago - SmartStock AI TFG