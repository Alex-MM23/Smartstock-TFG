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
from datetime import date, timedelta

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.config import MODEL_PATH, get_engine
from src.data.preprocess import MIN_HISTORY, forecast_demand

log = logging.getLogger("api")
Z_SERVICIO = float(os.getenv("SERVICE_LEVEL_Z", "1.645"))   # 95 % de nivel de servicio

app = FastAPI(
    title="SmartStock AI",
    description="Predicción de demanda y optimización de inventario para e-commerce",
    version="1.0.0",
)
engine = get_engine()


# ---------------------------------------------------------------------------
# Modelo (se recarga solo si el fichero .joblib cambia → no hace falta reiniciar tras reentrenar)
# ---------------------------------------------------------------------------
_cache: dict = {"mtime": None, "bundle": None}
_lock = threading.Lock()


def get_bundle() -> dict:
    if not MODEL_PATH.exists():
        raise HTTPException(503, "Modelo no disponible. Entrénalo con: python -m src.models.train")
    mtime = MODEL_PATH.stat().st_mtime
    with _lock:
        if _cache["mtime"] != mtime:
            # joblib usa pickle: cargar solo ficheros generados por train.py (de confianza)
            _cache.update(bundle=joblib.load(MODEL_PATH), mtime=mtime)
        return _cache["bundle"]


@app.exception_handler(SQLAlchemyError)
async def db_error_handler(_: Request, exc: SQLAlchemyError):
    log.exception("Error de base de datos")
    return JSONResponse(status_code=503, content={"detail": "Base de datos no disponible"})


# ---------------------------------------------------------------------------
# Esquemas
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Acceso a datos
# ---------------------------------------------------------------------------
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
