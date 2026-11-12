"""API REST de SmartStock AI.

Arranque local:
    uvicorn src.api.main:app --reload
Documentación interactiva: http://localhost:8000/docs
"""
from __future__ import annotations

import logging
import math
import os
import threading
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database import Base
from src.config import MODEL_PATH, get_engine
from src.data.preprocess import MIN_HISTORY, forecast_demand
from src.schemas import OrderItemSchema

log = logging.getLogger("api")
Z_SERVICIO = float(os.getenv("SERVICE_LEVEL_Z", "1.645"))

engine = get_engine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.auth.models import User
    import models  # noqa: F401

    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        log.warning(f"Table creation failed: {e}")

    try:
        from src.data.migrations import create_views
        create_views(engine)
    except Exception as e:
        log.warning(f"View creation failed: {e}")

    from src.auth.routes import get_password_hash, get_user_by_email

    try:
        with Session(bind=engine) as db:
            # Usuario admin
            admin = get_user_by_email(db, "admin@smartstock.com")
            if not admin:
                admin_user = User(
                    email="admin@smartstock.com",
                    hashed_password=get_password_hash("admin123"),
                    role="admin",
                    is_active=True
                )
                db.add(admin_user)
                log.info("Usuario admin creado: admin@smartstock.com / admin123")

            # Usuario de prueba (cliente)
            test_user = get_user_by_email(db, "usuario@test.com")
            if not test_user:
                test_user_obj = User(
                    email="usuario@test.com",
                    hashed_password=get_password_hash("test123"),
                    role="client",
                    is_active=True
                )
                db.add(test_user_obj)
                log.info("Usuario de prueba creado: usuario@test.com / test123")

            db.commit()
    except Exception as e:
        log.warning(f"Could not create default users: {e}")

    try:
        from sqlalchemy import text
        with Session(bind=engine) as db:
            existing = db.execute(text("SELECT COUNT(*) FROM proveedores")).scalar()
            if existing == 0:
                suppliers = [
                    {"nombre": "TechSupply Global", "contacto_email": "ventas@techsupply.com", "telefono": "+34 900 111 222", "plazo_entrega_dias": 7},
                    {"nombre": "Industrial Components SL", "contacto_email": "pedidos@industrialcomp.es", "telefono": "+34 900 333 444", "plazo_entrega_dias": 10},
                    {"nombre": "IoT Hardware Distributors", "contacto_email": "comercial@iothwd.com", "telefono": "+34 900 555 666", "plazo_entrega_dias": 5},
                    {"nombre": "SmartLogistics Iberia", "contacto_email": "orders@smartlogistics.es", "telefono": "+34 900 777 888", "plazo_entrega_dias": 14},
                ]
                for s in suppliers:
                    db.execute(text("""
                        INSERT INTO proveedores (nombre, contacto_email, telefono, plazo_entrega_dias)
                        VALUES (:nombre, :contacto_email, :telefono, :plazo_entrega_dias)
                    """), s)
                db.commit()
                log.info(f"Seed: {len(suppliers)} proveedores creados")

            products = db.execute(text("SELECT id_producto FROM productos WHERE activo = 1 AND id_proveedor IS NULL")).fetchall()
            if products:
                supplier_ids = [row[0] for row in db.execute(text("SELECT id_proveedor FROM proveedores")).fetchall()]
                if supplier_ids:
                    for i, prod in enumerate(products):
                        supplier_id = supplier_ids[i % len(supplier_ids)]
                        db.execute(text("UPDATE productos SET id_proveedor = :sid WHERE id_producto = :pid"),
                                   {"sid": supplier_id, "pid": prod[0]})
                    db.commit()
                    log.info(f"Seed: {len(products)} productos vinculados a proveedores")
    except Exception as e:
        log.warning(f"Could not seed suppliers: {e}")

    yield


app = FastAPI(
    title="SmartStock AI",
    description="Predicción de demanda y optimización de inventario para e-commerce",
    version="1.0.0",
    lifespan=lifespan,
)

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

IS_DEV = os.getenv("ENVIRONMENT", "development") != "production"

if IS_DEV:
    class DevCORSMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            origin = request.headers.get("origin", "")
            allowed = (
                origin.startswith("http://localhost:") or
                origin.startswith("http://127.0.0.1:")
            )

            if request.method == "OPTIONS":
                if allowed:
                    response = Response(status_code=204)
                    response.headers["Access-Control-Allow-Origin"] = origin
                    response.headers["Access-Control-Allow-Credentials"] = "true"
                    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
                    response.headers["Access-Control-Allow-Headers"] = "*"
                    response.headers["Access-Control-Max-Age"] = "86400"
                    return response

            response = await call_next(request)

            if allowed:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Credentials"] = "true"
                response.headers["Vary"] = "Origin"

            return response

    app.add_middleware(DevCORSMiddleware)
else:
    allowed_origins = [
        "http://localhost:4200",
        "http://127.0.0.1:4200",
    ]
    prod_origin = os.getenv("CORS_ALLOWED_ORIGIN")
    if prod_origin:
        allowed_origins.append(prod_origin)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

from src.auth.routes import router as auth_router

app.include_router(auth_router)

_cache: dict = {"mtime": None, "bundle": None}
_lock = threading.Lock()


def get_bundle() -> dict:
    if not MODEL_PATH.exists():
        raise HTTPException(503, "Modelo no disponible. Entrénalo con: python -m src.models.train")
    mtime = MODEL_PATH.stat().st_mtime
    with _lock:
        if _cache["mtime"] != mtime:
            _cache.update(bundle=joblib.load(MODEL_PATH), mtime=mtime)
        return _cache["bundle"]


@app.exception_handler(SQLAlchemyError)
async def db_error_handler(_: Request, exc: SQLAlchemyError):
    log.exception("Error de base de datos")
    return JSONResponse(status_code=503, content={"detail": "Base de datos no disponible"})


class StockItem(BaseModel):
    id_producto: int
    sku: str
    nombre: str
    categoria: str
    stock_actual: int
    stock_seguridad_minimo: int
    bajo_minimo: bool


class StockStatusResponse(BaseModel):
    total_productos: int
    productos_en_alerta: int
    items: list[StockItem]


class AdminProductInsight(BaseModel):
    id_producto: int
    sku: str
    nombre: str
    categoria: str
    stock_actual: int
    precio_unitario: float
    dias_stock_restante: int | None = None
    velocidad_consumo_diaria: float | None = None
    riesgo_critico: bool = False
    demanda_estimada_7d: float | None = None
    stock_recomendado: int | None = None
    unidades_a_reponer: int | None = None
    ultima_fecha_venta: date | None = None


class AdminDashboardResponse(BaseModel):
    total_productos: int
    total_pedidos: int
    ingresos_totales: float
    productos_riesgo_critico: int
    productos_bajo_stock: int
    productos_agotados: int
    productos: list[AdminProductInsight]
    pedidos_recientes: list[OrderResponse]


class PrediccionRequest(BaseModel):
    id_producto: int | None = Field(None, ge=1, description="ID del producto")
    sku: str | None = Field(None, max_length=50, description="SKU del producto (alternativa al ID)")
    horizonte_dias: int = Field(7, ge=1, le=90, description="Días a predecir")
    guardar: bool = Field(True, description="Guardar el resultado en predicciones_demanda")

    model_config = {"json_schema_extra": {"example": {"sku": "SS-ELE-001", "horizonte_dias": 14}}}

    @model_validator(mode="after")
    def _uno_de_los_dos(self):
        if (self.id_producto is None) == (self.sku is None):
            raise ValueError("Indica exactamente uno de: id_producto o sku")
        return self


class PrediccionDia(BaseModel):
    fecha: date
    demanda_estimada: float
    stock_recomendado: int


class PrediccionResponse(BaseModel):
    id_producto: int
    sku: str
    nombre: str
    modelo_version: str
    ultima_fecha_historico: date
    horizonte_dias: int
    demanda_total: float
    stock_seguridad: int
    stock_recomendado: int
    stock_actual: int
    unidades_a_reponer: int
    plazo_entrega_dias: int | None
    guardado: bool
    predicciones: list[PrediccionDia]


# ---------- Order Schemas ----------
class OrderItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    price: float
    product_name: str | None = None

    class Config:
        from_attributes = True


class OrderResponse(BaseModel):
    id: int
    user_id: int
    total_amount: float
    status: str
    created_at: datetime
    items: list[OrderItemResponse] = []

    class Config:
        from_attributes = True


class PurchaseOrderItemResponse(BaseModel):
    id: int
    id_producto: int
    cantidad: int
    product_name: str | None = None
    product_sku: str | None = None

    class Config:
        from_attributes = True


class PurchaseOrderResponse(BaseModel):
    id_orden_compra: int
    id_proveedor: int
    proveedor_nombre: str
    fecha_creacion: datetime
    estado: str
    generada_por_ia: bool
    total_unidades: int
    items: list[PurchaseOrderItemResponse] = []

    class Config:
        from_attributes = True


class PurchaseOrderApproveRequest(BaseModel):
    pass  # Empty body for approve action


class PurchaseOrderReceiveRequest(BaseModel):
    pass  # Empty body for receive action


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health", tags=["sistema"])
def health():
    """Estado del servicio: base de datos y modelo."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db = "ok"
    except SQLAlchemyError:
        db = "error"
    cuerpo = {"status": "ok" if db == "ok" else "error", "database": db,
              "model": "loaded" if MODEL_PATH.exists() else "missing"}
    return JSONResponse(cuerpo, status_code=200 if db == "ok" else 503)


@app.get("/stock/status", response_model=StockStatusResponse, tags=["inventario"])
def stock_status(solo_alertas: bool = Query(False, description="Devolver solo productos bajo el mínimo")):
    """Productos y su situación respecto al stock de seguridad (vista v_stock_alerta)."""
    sql = ("SELECT id_producto, sku, nombre, categoria, stock_actual, stock_seguridad_minimo, bajo_minimo "
           "FROM v_stock_alerta")
    if solo_alertas:
        sql += " WHERE bajo_minimo = 1"
    sql += " ORDER BY bajo_minimo DESC, (stock_actual - stock_seguridad_minimo) ASC, nombre"
    with engine.connect() as conn:
        items = [StockItem(**r) for r in conn.execute(text(sql)).mappings()]
        resumen = conn.execute(text(
            "SELECT COUNT(*) AS total, COALESCE(SUM(bajo_minimo), 0) AS alertas FROM v_stock_alerta")).one()
    return StockStatusResponse(total_productos=int(resumen.total),
                               productos_en_alerta=int(resumen.alertas), items=items)


@app.post("/predict/demand", response_model=PrediccionResponse, tags=["predicción"])
def predict_demand(req: PrediccionRequest):
    """Predice la demanda diaria de un producto y recomienda stock.

    stock_recomendado = demanda total del horizonte + stock de seguridad, con
    seguridad = z · σ_diaria · √horizonte (σ = RMSE del backtest recursivo, z=1,645 → 95 %).
    """
    bundle = get_bundle()
    producto = _buscar_producto(req)
    serie, ultima = _cargar_historia(producto["id_producto"])

    pred = forecast_demand(bundle["model"], serie.to_numpy(), ultima,
                           float(producto["precio_unitario"]), req.horizonte_dias)
    sigma = float(bundle["sigma_dia"])
    dias = [PrediccionDia(fecha=f, demanda_estimada=round(y, 2),
                          stock_recomendado=math.ceil(y + Z_SERVICIO * sigma)) for f, y in pred]

    total = sum(y for _, y in pred)
    seguridad = math.ceil(Z_SERVICIO * sigma * math.sqrt(req.horizonte_dias))
    recomendado = math.ceil(total + seguridad)
    stock_actual = int(producto["stock_actual"])

    guardado = False
    if req.guardar:
        _guardar_predicciones(producto["id_producto"], dias, bundle["version"])
        guardado = True

    return PrediccionResponse(
        id_producto=producto["id_producto"], sku=producto["sku"], nombre=producto["nombre"],
        modelo_version=bundle["version"], ultima_fecha_historico=ultima,
        horizonte_dias=req.horizonte_dias, demanda_total=round(total, 2),
        stock_seguridad=seguridad, stock_recomendado=recomendado, stock_actual=stock_actual,
        unidades_a_reponer=max(0, recomendado - stock_actual),
        plazo_entrega_dias=producto["plazo_entrega_dias"], guardado=guardado, predicciones=dias)


@app.get("/orders", response_model=list[OrderResponse], tags=["pedidos"])
def get_orders():
    """Obtiene todos los pedidos con sus items usando la tabla existente 'pedidos' y 'detalle_pedido'."""
    try:
        with engine.connect() as conn:
            # Get orders from pedidos table (handle NULL fecha_pedido with COALESCE)
            orders_sql = text("""
                SELECT
                    id_pedido as id,
                    id_usuario as user_id,
                    total as total_amount,
                    estado as status,
                    COALESCE(fecha_pedido, datetime('now')) as created_at
                FROM pedidos
                ORDER BY created_at DESC
            """)
            orders = conn.execute(orders_sql).mappings().all()

            result = []
            for order in orders:
                # Get items from detalle_pedido table
                items_sql = text("""
                    SELECT
                        dp.id_detalle as id,
                        dp.id_producto as product_id,
                        dp.cantidad as quantity,
                        dp.precio_unitario as price,
                        p.nombre as product_name
                    FROM detalle_pedido dp
                    LEFT JOIN productos p ON p.id_producto = dp.id_producto
                    WHERE dp.id_pedido = :order_id
                """)
                items = conn.execute(items_sql, {"order_id": order["id"]}).mappings().all()

                order_items = [
                    OrderItemResponse(
                        id=item["id"],
                        product_id=item["product_id"],
                        quantity=item["quantity"],
                        price=float(item["price"]),
                        product_name=item["product_name"]
                    )
                    for item in items
                ]

                result.append(OrderResponse(
                    id=order["id"],
                    user_id=order["user_id"],
                    total_amount=float(order["total_amount"]),
                    status=order["status"],
                    created_at=order["created_at"],
                    items=order_items
                ))
            return result
    except Exception as e:
        log.error(f"Error in get_orders: {e}")
        raise HTTPException(503, "Base de datos no disponible")


@app.get("/orders/{order_id}", response_model=OrderResponse, tags=["pedidos"])
def get_order(order_id: int):
    """Obtiene un pedido específico por ID."""
    try:
        with engine.connect() as conn:
            # Get order from pedidos table (handle NULL fecha_pedido with COALESCE)
            order_sql = text("""
                SELECT
                    id_pedido as id,
                    id_usuario as user_id,
                    total as total_amount,
                    estado as status,
                    COALESCE(fecha_pedido, datetime('now')) as created_at
                FROM pedidos
                WHERE id_pedido = :order_id
            """)
            order = conn.execute(order_sql, {"order_id": order_id}).mappings().first()

            if not order:
                raise HTTPException(404, "Pedido no encontrado")

            # Get items from detalle_pedido table
            items_sql = text("""
                SELECT
                    dp.id_detalle as id,
                    dp.id_producto as product_id,
                    dp.cantidad as quantity,
                    dp.precio_unitario as price,
                    p.nombre as product_name
                FROM detalle_pedido dp
                LEFT JOIN productos p ON p.id_producto = dp.id_producto
                WHERE dp.id_pedido = :order_id
            """)
            items = conn.execute(items_sql, {"order_id": order_id}).mappings().all()

            order_items = [
                OrderItemResponse(
                    id=item["id"],
                    product_id=item["product_id"],
                    quantity=item["quantity"],
                    price=float(item["price"]),
                    product_name=item["product_name"]
                )
                for item in items
            ]

            return OrderResponse(
                id=order["id"],
                user_id=order["user_id"],
                total_amount=float(order["total_amount"]),
                status=order["status"],
                created_at=order["created_at"],
                items=order_items
            )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error in get_order: {e}")
        raise HTTPException(503, "Base de datos no disponible")


# ---------- Create Order Endpoint ----------
class OrderCreateRequest(BaseModel):
    user_id: int
    items: list[OrderItemSchema]


@app.post("/orders", response_model=OrderResponse, tags=["pedidos"])
def create_order(order_data: OrderCreateRequest):
    """Crea un nuevo pedido en la base de datos (tablas legacy pedidos/detalle_pedido)."""
    try:
        with engine.begin() as conn:
            # Calcular total
            total = sum(item.quantity * item.price for item in order_data.items)
            ahora = datetime.utcnow()

            # Insertar en pedidos (fecha_pedido se setea explícitamente porque SQLite no usa default del modelo en raw SQL)
            order_sql = text("""
                INSERT INTO pedidos (id_usuario, total, estado, fecha_pedido)
                VALUES (:user_id, :total, 'Completado', :fecha_pedido)
            """)
            result = conn.execute(order_sql, {
                "user_id": order_data.user_id,
                "total": total,
                "fecha_pedido": ahora
            })
            order_id = result.lastrowid

            # Insertar items en detalle_pedido
            for item in order_data.items:
                item_sql = text("""
                    INSERT INTO detalle_pedido (id_pedido, id_producto, cantidad, precio_unitario)
                    VALUES (:order_id, :product_id, :quantity, :price)
                """)
                conn.execute(item_sql, {
                    "order_id": order_id,
                    "product_id": item.product_id,
                    "quantity": item.quantity,
                    "price": item.price
                })

            # Recuperar el pedido creado con sus items
            order_sql = text("""
                SELECT
                    id_pedido as id,
                    id_usuario as user_id,
                    total as total_amount,
                    estado as status,
                    fecha_pedido as created_at
                FROM pedidos
                WHERE id_pedido = :order_id
            """)
            order = conn.execute(order_sql, {"order_id": order_id}).mappings().first()

            items_sql = text("""
                SELECT
                    dp.id_detalle as id,
                    dp.id_producto as product_id,
                    dp.cantidad as quantity,
                    dp.precio_unitario as price,
                    p.nombre as product_name
                FROM detalle_pedido dp
                LEFT JOIN productos p ON p.id_producto = dp.id_producto
                WHERE dp.id_pedido = :order_id
            """)
            items = conn.execute(items_sql, {"order_id": order_id}).mappings().all()

            order_items = [
                OrderItemResponse(
                    id=item["id"],
                    product_id=item["product_id"],
                    quantity=item["quantity"],
                    price=float(item["price"]),
                    product_name=item["product_name"]
                )
                for item in items
            ]

            return OrderResponse(
                id=order["id"],
                user_id=order["user_id"],
                total_amount=float(order["total_amount"]),
                status=order["status"],
                created_at=order["created_at"],
                items=order_items
            )
    except Exception as e:
        log.error(f"Error in create_order: {e}")
        raise HTTPException(503, "Error al crear el pedido") from None


@app.get("/products", response_model=list[dict], tags=["productos"])
def list_products():
    """Devuelve el catálogo completo de productos activos."""
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT p.id_producto as id, p.nombre as title, p.precio_unitario as price, "
                "p.stock_actual as cantidad, c.nombre as category, p.imagen_url as image "
                "FROM productos p LEFT JOIN categorias c ON c.id_categoria = p.id_categoria "
                "WHERE p.activo = 1"
            )).mappings()
            return [dict(r) for r in rows]
    except Exception as e:
        import logging
        log = logging.getLogger("api")
        log.error(f"Error in list_products: {e}")
        raise


@app.get("/admin/dashboard", response_model=AdminDashboardResponse, tags=["admin"])
@app.get("/api/admin/dashboard", response_model=AdminDashboardResponse, tags=["admin"], include_in_schema=False)
def get_admin_dashboard():
    """
    Devuelve métricas del panel de administración enriquecidas con predicciones de IA.
    Para cada producto calcula:
    - Días de stock restante basados en velocidad de consumo histórica
    - Riesgo crítico según consumo real vs stock
    - Demanda estimada a 7 días y stock recomendado
    """
    try:
        bundle = get_bundle()
        model = bundle["model"]
        sigma_dia = float(bundle["sigma_dia"])
        version = bundle["version"]

        with engine.connect() as conn:
            products_sql = text("""
                SELECT p.id_producto, p.sku, p.nombre, c.nombre as categoria, p.stock_actual,
                       p.precio_unitario, p.stock_seguridad_minimo, pr.plazo_entrega_dias
                FROM productos p
                LEFT JOIN proveedores pr ON pr.id_proveedor = p.id_proveedor
                LEFT JOIN categorias c ON c.id_categoria = p.id_categoria
                WHERE p.activo = 1
                ORDER BY p.nombre
            """)
            products = conn.execute(products_sql).mappings().all()

            orders_sql = text("""
                SELECT
                    id_pedido as id,
                    id_usuario as user_id,
                    total as total_amount,
                    estado as status,
                    COALESCE(fecha_pedido, datetime('now')) as created_at
                FROM pedidos
                ORDER BY created_at DESC
                LIMIT 10
            """)
            orders = conn.execute(orders_sql).mappings().all()

            recent_orders = []
            for order in orders:
                items_sql = text("""
                    SELECT
                        dp.id_detalle as id,
                        dp.id_producto as product_id,
                        dp.cantidad as quantity,
                        dp.precio_unitario as price,
                        p.nombre as product_name
                    FROM detalle_pedido dp
                    LEFT JOIN productos p ON p.id_producto = dp.id_producto
                    WHERE dp.id_pedido = :order_id
                """)
                items = conn.execute(items_sql, {"order_id": order["id"]}).mappings().all()

                order_items = [
                    OrderItemResponse(
                        id=item["id"],
                        product_id=item["product_id"],
                        quantity=item["quantity"],
                        price=float(item["price"]),
                        product_name=item["product_name"]
                    )
                    for item in items
                ]

                recent_orders.append(OrderResponse(
                    id=order["id"],
                    user_id=order["user_id"],
                    total_amount=float(order["total_amount"]),
                    status=order["status"],
                    created_at=order["created_at"],
                    items=order_items
                ))

        product_insights = []
        riesgo_critico_count = 0
        bajo_stock_count = 0
        agotados_count = 0

        for prod in products:
            id_producto = prod["id_producto"]
            stock_actual = int(prod["stock_actual"])
            precio = float(prod["precio_unitario"])
            stock_seguridad = prod["stock_seguridad_minimo"] or 0

            dias_stock = None
            velocidad_diaria = None
            riesgo_critico = False
            demanda_7d = None
            stock_recomendado = None
            unidades_reponer = None
            ultima_venta = None

            try:
                serie, ultima = _cargar_historia(id_producto)
                if serie is not None and len(serie) > 0:
                    ultima_venta = ultima
                    recent_30 = serie.tail(30)
                    velocidad_diaria = float(recent_30.mean()) if len(recent_30) > 0 else 0.0

                    if velocidad_diaria > 0:
                        dias_stock = int(stock_actual / velocidad_diaria)

                        pred = forecast_demand(model, serie.to_numpy(), ultima, precio, 7)
                        demanda_7d = round(sum(y for _, y in pred), 2)

                        seguridad = math.ceil(Z_SERVICIO * sigma_dia * math.sqrt(7))
                        stock_recomendado = math.ceil(demanda_7d + seguridad)
                        unidades_reponer = max(0, stock_recomendado - stock_actual)

                        plazo_entrega = prod["plazo_entrega_dias"] or 7
                        dias_cobertura_necesaria = plazo_entrega + 7

                        if stock_actual <= 0:
                            riesgo_critico = True
                            agotados_count += 1
                        elif dias_stock <= dias_cobertura_necesaria:
                            riesgo_critico = True
                            riesgo_critico_count += 1
                        elif stock_actual <= stock_seguridad and stock_seguridad > 0:
                            bajo_stock_count += 1
            except Exception as e:
                log.warning(f"No se pudo calcular insights IA para producto {id_producto}: {e}")
                if stock_actual <= 0:
                    riesgo_critico = True
                    agotados_count += 1
                elif stock_seguridad > 0 and stock_actual <= stock_seguridad:
                    bajo_stock_count += 1

            product_insights.append(AdminProductInsight(
                id_producto=id_producto,
                sku=prod["sku"],
                nombre=prod["nombre"],
                categoria=prod["categoria"] or "General",
                stock_actual=stock_actual,
                precio_unitario=precio,
                dias_stock_restante=dias_stock,
                velocidad_consumo_diaria=round(velocidad_diaria, 2) if velocidad_diaria else None,
                riesgo_critico=riesgo_critico,
                demanda_estimada_7d=demanda_7d,
                stock_recomendado=stock_recomendado,
                unidades_a_reponer=unidades_reponer,
                ultima_fecha_venta=ultima_venta
            ))

        # Total orders and revenue
        with engine.connect() as conn:
            total_pedidos = conn.execute(text("SELECT COUNT(*) FROM pedidos")).scalar() or 0
            ingresos_totales = conn.execute(text("SELECT COALESCE(SUM(total), 0) FROM pedidos")).scalar() or 0

        return AdminDashboardResponse(
            total_productos=len(products),
            total_pedidos=int(total_pedidos),
            ingresos_totales=float(ingresos_totales),
            productos_riesgo_critico=riesgo_critico_count,
            productos_bajo_stock=bajo_stock_count,
            productos_agotados=agotados_count,
            productos=product_insights,
            pedidos_recientes=recent_orders
        )
    except Exception as e:
        log.error(f"Error in get_admin_dashboard: {e}")
        raise HTTPException(503, "Error al obtener datos del panel de administración")


@app.get("/api/purchase-orders", response_model=list[PurchaseOrderResponse], tags=["ordenes-compra"])
def get_purchase_orders():
    """Lista todas las órdenes de compra con detalles de proveedor y productos."""
    try:
        with engine.connect() as conn:
            pos_sql = text("""
                SELECT po.id_orden_compra, po.id_proveedor, pr.nombre as proveedor_nombre,
                       po.fecha_creacion, po.estado, po.generada_por_ia, po.total_unidades
                FROM purchase_orders po
                JOIN proveedores pr ON pr.id_proveedor = po.id_proveedor
                ORDER BY po.fecha_creacion DESC
            """)
            pos = conn.execute(pos_sql).mappings().all()

            result = []
            for po in pos:
                items_sql = text("""
                    SELECT poi.id, poi.id_producto, poi.cantidad,
                           p.nombre as product_name, p.sku as product_sku
                    FROM purchase_order_items poi
                    JOIN productos p ON p.id_producto = poi.id_producto
                    WHERE poi.id_orden_compra = :po_id
                """)
                items = conn.execute(items_sql, {"po_id": po["id_orden_compra"]}).mappings().all()

                result.append(PurchaseOrderResponse(
                    id_orden_compra=po["id_orden_compra"],
                    id_proveedor=po["id_proveedor"],
                    proveedor_nombre=po["proveedor_nombre"],
                    fecha_creacion=po["fecha_creacion"],
                    estado=po["estado"],
                    generada_por_ia=bool(po["generada_por_ia"]),
                    total_unidades=po["total_unidades"],
                    items=[
                        PurchaseOrderItemResponse(
                            id=item["id"],
                            id_producto=item["id_producto"],
                            cantidad=item["cantidad"],
                            product_name=item["product_name"],
                            product_sku=item["product_sku"]
                        )
                        for item in items
                    ]
                ))
            return result
    except Exception as e:
        log.error(f"Error in get_purchase_orders: {e}")
        raise HTTPException(503, "Error al obtener órdenes de compra")


@app.put("/api/purchase-orders/{order_id}/approve", response_model=PurchaseOrderResponse, tags=["ordenes-compra"])
def approve_purchase_order(order_id: int):
    """Aprueba una orden de compra (cambia estado de 'Pendiente' a 'Aprobada')."""
    try:
        with engine.begin() as conn:
            check_sql = text("SELECT estado FROM purchase_orders WHERE id_orden_compra = :id")
            current = conn.execute(check_sql, {"id": order_id}).first()
            if not current:
                raise HTTPException(404, "Orden de compra no encontrada")
            if current[0] != "Pendiente":
                raise HTTPException(400, f"Solo se pueden aprobar órdenes en estado 'Pendiente'. Estado actual: {current[0]}")

            update_sql = text("UPDATE purchase_orders SET estado = 'Aprobada' WHERE id_orden_compra = :id")
            conn.execute(update_sql, {"id": order_id})

            po_sql = text("""
                SELECT po.id_orden_compra, po.id_proveedor, pr.nombre as proveedor_nombre,
                       po.fecha_creacion, po.estado, po.generada_por_ia, po.total_unidades
                FROM purchase_orders po
                JOIN proveedores pr ON pr.id_proveedor = po.id_proveedor
                WHERE po.id_orden_compra = :id
            """)
            po = conn.execute(po_sql, {"id": order_id}).mappings().first()

            items_sql = text("""
                SELECT poi.id, poi.id_producto, poi.cantidad,
                       p.nombre as product_name, p.sku as product_sku
                FROM purchase_order_items poi
                JOIN productos p ON p.id_producto = poi.id_producto
                WHERE poi.id_orden_compra = :po_id
            """)
            items = conn.execute(items_sql, {"po_id": order_id}).mappings().all()

            return PurchaseOrderResponse(
                id_orden_compra=po["id_orden_compra"],
                id_proveedor=po["id_proveedor"],
                proveedor_nombre=po["proveedor_nombre"],
                fecha_creacion=po["fecha_creacion"],
                estado=po["estado"],
                generada_por_ia=bool(po["generada_por_ia"]),
                total_unidades=po["total_unidades"],
                items=[
                    PurchaseOrderItemResponse(
                        id=item["id"],
                        id_producto=item["id_producto"],
                        cantidad=item["cantidad"],
                        product_name=item["product_name"],
                        product_sku=item["product_sku"]
                    )
                    for item in items
                ]
            )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error in approve_purchase_order: {e}")
        raise HTTPException(503, "Error al aprobar la orden de compra")


@app.put("/api/purchase-orders/{order_id}/receive", response_model=PurchaseOrderResponse, tags=["ordenes-compra"])
def receive_purchase_order(order_id: int):
    """Marca una orden de compra como recibida y actualiza el stock de los productos."""
    try:
        with engine.begin() as conn:
            check_sql = text("SELECT estado FROM purchase_orders WHERE id_orden_compra = :id")
            current = conn.execute(check_sql, {"id": order_id}).first()
            if not current:
                raise HTTPException(404, "Orden de compra no encontrada")
            if current[0] != "Aprobada":
                raise HTTPException(400, f"Solo se pueden recibir órdenes en estado 'Aprobada'. Estado actual: {current[0]}")

            items_sql = text("""
                SELECT id_producto, cantidad FROM purchase_order_items
                WHERE id_orden_compra = :po_id
            """)
            items = conn.execute(items_sql, {"po_id": order_id}).mappings().all()

            for item in items:
                update_stock_sql = text("""
                    UPDATE productos SET stock_actual = stock_actual + :cantidad
                    WHERE id_producto = :id_producto
                """)
                conn.execute(update_stock_sql, {
                    "id_producto": item["id_producto"],
                    "cantidad": item["cantidad"]
                })

            update_sql = text("UPDATE purchase_orders SET estado = 'Recibida' WHERE id_orden_compra = :id")
            conn.execute(update_sql, {"id": order_id})

            po_sql = text("""
                SELECT po.id_orden_compra, po.id_proveedor, pr.nombre as proveedor_nombre,
                       po.fecha_creacion, po.estado, po.generada_por_ia, po.total_unidades
                FROM purchase_orders po
                JOIN proveedores pr ON pr.id_proveedor = po.id_proveedor
                WHERE po.id_orden_compra = :id
            """)
            po = conn.execute(po_sql, {"id": order_id}).mappings().first()

            items_sql = text("""
                SELECT poi.id, poi.id_producto, poi.cantidad,
                       p.nombre as product_name, p.sku as product_sku
                FROM purchase_order_items poi
                JOIN productos p ON p.id_producto = poi.id_producto
                WHERE poi.id_orden_compra = :po_id
            """)
            items = conn.execute(items_sql, {"po_id": order_id}).mappings().all()

            return PurchaseOrderResponse(
                id_orden_compra=po["id_orden_compra"],
                id_proveedor=po["id_proveedor"],
                proveedor_nombre=po["proveedor_nombre"],
                fecha_creacion=po["fecha_creacion"],
                estado=po["estado"],
                generada_por_ia=bool(po["generada_por_ia"]),
                total_unidades=po["total_unidades"],
                items=[
                    PurchaseOrderItemResponse(
                        id=item["id"],
                        id_producto=item["id_producto"],
                        cantidad=item["cantidad"],
                        product_name=item["product_name"],
                        product_sku=item["product_sku"]
                    )
                    for item in items
                ]
            )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error in receive_purchase_order: {e}")
        raise HTTPException(503, "Error al recibir la orden de compra")


@app.post("/api/purchase-orders/auto-generate", tags=["ordenes-compra"])
def auto_generate_purchase_orders():
    """
    Genera automáticamente órdenes de compra para productos con riesgo crítico
    o que necesitan reponer, siempre que no exista ya una orden pendiente/aprobada.
    """
    try:
        bundle = get_bundle()
        model = bundle["model"]
        sigma_dia = float(bundle["sigma_dia"])
        version = bundle["version"]

        with engine.begin() as conn:
            products_sql = text("""
                SELECT p.id_producto, p.sku, p.nombre, p.stock_actual,
                       p.precio_unitario, p.stock_seguridad_minimo, p.id_proveedor,
                       pr.plazo_entrega_dias, pr.nombre as proveedor_nombre, pr.contacto_email
                FROM productos p
                LEFT JOIN proveedores pr ON pr.id_proveedor = p.id_proveedor
                WHERE p.activo = 1 AND p.id_proveedor IS NOT NULL
                ORDER BY p.nombre
            """)
            products = conn.execute(products_sql).mappings().all()

            generated_orders = []
            skipped_products = []

            for prod in products:
                id_producto = prod["id_producto"]
                stock_actual = int(prod["stock_actual"])
                precio = float(prod["precio_unitario"])
                stock_seguridad = prod["stock_seguridad_minimo"] or 0
                id_proveedor = prod["id_proveedor"]
                proveedor_nombre = prod["proveedor_nombre"]
                plazo_entrega = prod["plazo_entrega_dias"] or 7

                existing_po_sql = text("""
                    SELECT COUNT(*) FROM purchase_order_items poi
                    JOIN purchase_orders po ON po.id_orden_compra = poi.id_orden_compra
                    WHERE poi.id_producto = :pid AND po.estado IN ('Pendiente', 'Aprobada')
                """)
                existing_count = conn.execute(existing_po_sql, {"pid": id_producto}).scalar() or 0

                if existing_count > 0:
                    skipped_products.append({
                        "id_producto": id_producto,
                        "sku": prod["sku"],
                        "nombre": prod["nombre"],
                        "reason": "Orden pendiente/aprobada existente"
                    })
                    continue

                dias_stock = None
                velocidad_diaria = None
                riesgo_critico = False
                demanda_7d = None
                stock_recomendado = None
                unidades_reponer = None

                try:
                    serie, ultima = _cargar_historia(id_producto)
                    if serie is not None and len(serie) > 0:
                        recent_30 = serie.tail(30)
                        velocidad_diaria = float(recent_30.mean()) if len(recent_30) > 0 else 0.0

                        if velocidad_diaria > 0:
                            dias_stock = int(stock_actual / velocidad_diaria)

                            pred = forecast_demand(model, serie.to_numpy(), ultima, precio, 7)
                            demanda_7d = round(sum(y for _, y in pred), 2)

                            seguridad = math.ceil(Z_SERVICIO * sigma_dia * math.sqrt(7))
                            stock_recomendado = math.ceil(demanda_7d + seguridad)
                            unidades_reponer = max(0, stock_recomendado - stock_actual)

                            dias_cobertura_necesaria = plazo_entrega + 7

                            if stock_actual <= 0:
                                riesgo_critico = True
                            elif dias_stock <= dias_cobertura_necesaria:
                                riesgo_critico = True
                except Exception as e:
                    log.warning(f"No se pudo calcular insights IA para producto {id_producto}: {e}")

                should_generate = riesgo_critico or (unidades_reponer and unidades_reponer > 0)

                if should_generate and unidades_reponer and unidades_reponer > 0:
                    po_sql = text("""
                        INSERT INTO purchase_orders (id_proveedor, estado, generada_por_ia, total_unidades, fecha_creacion)
                        VALUES (:id_proveedor, 'Pendiente', 1, :total_unidades, datetime('now'))
                    """)
                    result = conn.execute(po_sql, {
                        "id_proveedor": id_proveedor,
                        "total_unidades": int(unidades_reponer)
                    })
                    po_id = result.lastrowid

                    item_sql = text("""
                        INSERT INTO purchase_order_items (id_orden_compra, id_producto, cantidad)
                        VALUES (:po_id, :pid, :cantidad)
                    """)
                    conn.execute(item_sql, {
                        "po_id": po_id,
                        "pid": id_producto,
                        "cantidad": int(unidades_reponer)
                    })

                    generated_orders.append({
                        "id_orden_compra": po_id,
                        "proveedor": proveedor_nombre,
                        "producto": prod["nombre"],
                        "sku": prod["sku"],
                        "cantidad": int(unidades_reponer),
                        "riesgo_critico": riesgo_critico,
                        "dias_stock_restante": dias_stock,
                        "velocidad_diaria": round(velocidad_diaria, 2) if velocidad_diaria else None
                    })
                else:
                    skipped_products.append({
                        "id_producto": id_producto,
                        "sku": prod["sku"],
                        "nombre": prod["nombre"],
                        "reason": "No requiere reorden (stock suficiente)"
                    })

            return {
                "generated": len(generated_orders),
                "skipped": len(skipped_products),
                "orders": generated_orders,
                "skipped_details": skipped_products
            }
    except Exception as e:
        log.error(f"Error in auto_generate_purchase_orders: {e}")
        raise HTTPException(503, "Error al generar órdenes de compra automáticas")


def _buscar_producto(req: PrediccionRequest) -> dict:
    filtro = "p.id_producto = :v" if req.id_producto is not None else "p.sku = :v"
    sql = text(
        "SELECT p.id_producto, p.sku, p.nombre, p.precio_unitario, p.stock_actual, pr.plazo_entrega_dias "
        "FROM productos p LEFT JOIN proveedores pr ON pr.id_proveedor = p.id_proveedor "
        f"WHERE p.activo = TRUE AND {filtro}")
    with engine.connect() as conn:
        fila = conn.execute(sql, {"v": req.id_producto if req.id_producto is not None else req.sku}).mappings().first()
    if fila is None:
        raise HTTPException(404, "Producto no encontrado o inactivo")
    return dict(fila)


def _cargar_historia(id_producto: int) -> tuple[pd.Series, date]:
    """Últimos ~60 días de ventas diarias (con ceros en los días sin venta)."""
    with engine.connect() as conn:
        primera, ultima = conn.execute(
            text("SELECT MIN(fecha), MAX(fecha) FROM historico_ventas WHERE id_producto = :p"),
            {"p": id_producto}).one()
        if ultima is None:
            raise HTTPException(422, "El producto no tiene histórico de ventas")
        if isinstance(primera, str):
            primera = pd.Timestamp(primera).date()
        if isinstance(ultima, str):
            ultima = pd.Timestamp(ultima).date()
        inicio = max(primera, ultima - timedelta(days=59))
        filas = conn.execute(
            text("SELECT fecha, SUM(cantidad_vendida) AS cantidad FROM historico_ventas "
                 "WHERE id_producto = :p AND fecha >= :d GROUP BY fecha"),
            {"p": id_producto, "d": inicio}).all()
    serie = pd.Series({pd.Timestamp(f): float(c) for f, c in filas})
    serie = serie.reindex(pd.date_range(pd.Timestamp(inicio), pd.Timestamp(ultima), freq="D"), fill_value=0.0)
    if len(serie) < MIN_HISTORY:
        raise HTTPException(422, f"Histórico insuficiente: se necesitan al menos {MIN_HISTORY} días")
    return serie, ultima


def _guardar_predicciones(id_producto: int, dias: list[PrediccionDia], version: str) -> None:
    """Reemplaza (de forma idempotente) las predicciones del producto para esas fechas."""
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM predicciones_demanda "
                 "WHERE id_producto = :p AND fecha_prediccion BETWEEN :a AND :b"),
            {"p": id_producto, "a": dias[0].fecha, "b": dias[-1].fecha})
        conn.execute(
            text("INSERT INTO predicciones_demanda "
                 "(id_producto, fecha_prediccion, demanda_estimada, stock_recomendado, modelo_version) "
                 "VALUES (:p, :f, :d, :s, :v)"),
            [{"p": id_producto, "f": d.fecha, "d": d.demanda_estimada,
              "s": d.stock_recomendado, "v": version} for d in dias])
