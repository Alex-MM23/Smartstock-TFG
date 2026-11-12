"""Ingesta de datos históricos en MySQL (tablas `productos` e `historico_ventas`).

Uso (desde la raíz del repositorio):
    python -m src.data.ingest                         # simula 2 años de ventas
    python -m src.data.ingest --dias 1095 --reset     # regenera el histórico
    python -m src.data.ingest --csv train.csv         # dataset público (p. ej. Kaggle
                                                      # "Store Item Demand Forecasting")

El script es idempotente: los productos se identifican por SKU y, si un producto
ya tiene histórico, se omite salvo que se use --reset.
"""
from __future__ import annotations

import argparse
import logging
from datetime import date, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, text

from src.config import get_engine

log = logging.getLogger("ingest")
CHUNK = 5000

# nombre, precio (€), demanda media diaria (uds)
CATALOGO = {
    "Electrónica": [
        ("Auriculares Bluetooth", 49.90, 22), ("Cargador USB-C 65W", 29.90, 30),
        ("Smartwatch Fit", 89.00, 12), ("Altavoz portátil", 39.90, 15),
        ("Webcam Full HD", 34.50, 10), ("Power bank 20000 mAh", 27.90, 25),
    ],
    "Hogar": [
        ("Lámpara LED de escritorio", 24.90, 18), ("Set de sartenes", 59.00, 9),
        ("Aspiradora robot", 199.00, 4), ("Juego de sábanas", 32.50, 14),
        ("Cafetera de cápsulas", 79.00, 7), ("Organizador de cocina", 14.90, 20),
    ],
    "Ropa": [
        ("Camiseta básica algodón", 12.90, 35), ("Vaqueros slim fit", 39.90, 16),
        ("Sudadera con capucha", 34.90, 18), ("Chaqueta impermeable", 69.00, 8),
        ("Zapatillas urbanas", 54.90, 13), ("Calcetines (pack 5)", 9.90, 40),
    ],
    "Deportes": [
        ("Esterilla de yoga", 19.90, 17), ("Mancuernas 2x5 kg", 29.90, 11),
        ("Botella térmica 750 ml", 16.90, 24), ("Zapatillas running", 79.90, 9),
        ("Banda elástica (set)", 12.50, 21), ("Balón de fútbol", 22.90, 12),
    ],
}

# (fase, amplitud): sin(2π·(día_del_año − fase)/365.25) → el pico cae ~91 días después de la fase
ESTACIONALIDAD = {
    "Electrónica": (249, 0.25),   # pico en diciembre
    "Hogar": (29, 0.10),          # pico en primavera
    "Ropa": (99, 0.30),           # pico en verano (rebajas)
    "Deportes": (74, 0.20),       # pico a principios de verano
}
FACTOR_BLACK_FRIDAY = {"Electrónica": 1.9, "Hogar": 1.4, "Ropa": 1.5, "Deportes": 1.3}
PROVEEDORES = [("Distribuciones Norte", 5), ("Iberlogística", 10), ("GlobalSupply", 21)]


# ---------------------------------------------------------------------------
# Fuentes de datos
# ---------------------------------------------------------------------------
def _mascara_black_friday(fechas: pd.DatetimeIndex) -> np.ndarray:
    """True en los ±3 días alrededor del último viernes de noviembre."""
    viernes = fechas[(fechas.month == 11) & (fechas.dayofweek == 4) & (fechas.day >= 23)]
    mascara = np.zeros(len(fechas), dtype=bool)
    for d in viernes:
        mascara |= np.abs((fechas - d).days.to_numpy()) <= 3
    return mascara


def _serie_ventas(fechas, categoria, precio, base, rng):
    """Demanda diaria simulada: nivel × semana × año × tendencia × promociones (Poisson)."""
    n = len(fechas)
    semanal = 1 + np.array([0.0, -0.05, -0.05, 0.0, 0.10, 0.20, 0.10])[fechas.dayofweek.to_numpy()]
    fase, amp = ESTACIONALIDAD[categoria]
    anual = 1 + amp * np.sin(2 * np.pi * (fechas.dayofyear.to_numpy() - fase) / 365.25)
    tendencia = 1 + 0.15 * np.arange(n) / n
    promo = rng.random(n) < 0.04
    f_promo = np.where(promo, rng.uniform(1.3, 1.8, n), 1.0)
    f_bf = np.where(_mascara_black_friday(fechas), FACTOR_BLACK_FRIDAY[categoria], 1.0)
    lam = base * semanal * anual * tendencia * f_promo * f_bf
    cantidad = rng.poisson(lam)
    precio_venta = np.round(precio * np.where(promo, 0.85, 1.0), 2)
    return cantidad, precio_venta


def simular(dias: int, seed: int):
    """Devuelve (lista de productos, DataFrame de ventas) simulados hasta ayer."""
    rng = np.random.default_rng(seed)
    fechas = pd.date_range(end=date.today() - timedelta(days=1), periods=dias, freq="D")
    productos, bloques = [], []
    for categoria, items in CATALOGO.items():
        for i, (nombre, precio, base) in enumerate(items, start=1):
            sku = f"SS-{categoria[:3].upper()}-{i:03d}"
            productos.append({"sku": sku, "nombre": nombre, "categoria": categoria, "precio": precio,
                                  "costo": round(precio * 0.6, 2), "demanda_media": float(base)})
            cantidad, pv = _serie_ventas(fechas, categoria, precio, base, rng)
            bloques.append(pd.DataFrame({"sku": sku, "fecha": fechas, "cantidad": cantidad, "precio": pv}))
    return productos, pd.concat(bloques, ignore_index=True)


def cargar_csv(args):
    """Carga un CSV público (fecha, item, unidades[, precio]) agregando por producto y día."""
    columnas = [c for c in (args.col_fecha, args.col_item, args.col_cantidad, args.col_precio) if c]
    df = pd.read_csv(args.csv, usecols=columnas)
    df = df.rename(columns={args.col_fecha: "fecha", args.col_item: "item", args.col_cantidad: "cantidad"})
    df["fecha"] = pd.to_datetime(df["fecha"])
    items = sorted(df["item"].unique())[: args.max_items]
    df = df[df["item"].isin(items)]

    agregados = {"cantidad": ("cantidad", "sum")}
    if args.col_precio:
        df = df.rename(columns={args.col_precio: "precio"})
        agregados["precio"] = ("precio", "mean")
    df = df.groupby(["item", "fecha"], as_index=False).agg(**agregados)

    rng = np.random.default_rng(args.seed)
    categorias = list(CATALOGO)
    medias = df.groupby("item")["cantidad"].mean()
    productos, precios = [], {}
    for n, item in enumerate(items):
        precio = round(float(rng.uniform(10, 150)), 2)
        sku = f"CSV-{item}"
        precios[item] = precio
        productos.append({"sku": sku, "nombre": f"Producto {item}", "categoria": categorias[n % len(categorias)],
                              "precio": precio, "costo": round(precio * 0.6, 2), "demanda_media": float(medias[item])})
    if "precio" not in df:
        df["precio"] = df["item"].map(precios)
    df["sku"] = "CSV-" + df["item"].astype(str)
    return productos, df[["sku", "fecha", "cantidad", "precio"]]


# ---------------------------------------------------------------------------
# Persistencia
# ---------------------------------------------------------------------------
def _asegurar_categorias(conn, nombres) -> dict:
    """Devuelve {nombre: id}. Se comprueba a mano porque UNIQUE(padre, nombre) no
    evita duplicados cuando id_categoria_padre es NULL."""
    sql = "SELECT id_categoria, nombre FROM categorias WHERE id_categoria_padre IS NULL"
    existentes = {r.nombre: r.id_categoria for r in conn.execute(text(sql))}
    faltan = [n for n in nombres if n not in existentes]
    if faltan:
        conn.execute(text("INSERT INTO categorias (nombre) VALUES (:n)"), [{"n": n} for n in faltan])
        existentes = {r.nombre: r.id_categoria for r in conn.execute(text(sql))}
    return existentes


def _asegurar_proveedores(conn) -> list[int]:
    # Use INSERT OR IGNORE for SQLite compatibility
    conn.execute(
        text("INSERT OR IGNORE INTO proveedores (nombre, plazo_entrega_dias) VALUES (:n, :p)"),
        [{"n": n, "p": p} for n, p in PROVEEDORES],
    )
    sql = text("SELECT id_proveedor FROM proveedores WHERE nombre IN :n ORDER BY id_proveedor")
    sql = sql.bindparams(bindparam("n", expanding=True))
    return [r.id_proveedor for r in conn.execute(sql, {"n": [n for n, _ in PROVEEDORES]})]


def _ids_por_sku(conn, skus) -> dict:
    sql = text("SELECT sku, id_producto FROM productos WHERE sku IN :s")
    sql = sql.bindparams(bindparam("s", expanding=True))
    return {r.sku: r.id_producto for r in conn.execute(sql, {"s": list(skus)})}


def persistir(engine, productos, ventas, reset: bool, seed: int) -> None:
    rng = np.random.default_rng(seed)
    with engine.begin() as conn:
        categorias = _asegurar_categorias(conn, {p["categoria"] for p in productos})
        proveedores = _asegurar_proveedores(conn)

        # --- productos (solo los que no existen; no se pisa el stock real) ---
        ids = _ids_por_sku(conn, [p["sku"] for p in productos])
        nuevos = []
        for n, p in enumerate(p for p in productos if p["sku"] not in ids):
            media = p["demanda_media"]
            nuevos.append({
                "cat": categorias[p["categoria"]], "prov": proveedores[n % len(proveedores)], "sku": p["sku"],
                "nombre": p["nombre"], "desc": f"Producto de {p['categoria']} (datos de ejemplo)",
                "precio": p["precio"], "costo": p["costo"],
                "stock": int(media * rng.uniform(1.5, 25)),     # algunos quedarán bajo el mínimo → alertas
                "minimo": max(1, int(media * 5)),
            })
        if nuevos:
            conn.execute(text(
                "INSERT INTO productos (id_categoria, id_proveedor, sku, nombre, descripcion, "
                "precio_unitario, costo_unitario, stock_actual, stock_seguridad_minimo) "
                "VALUES (:cat, :prov, :sku, :nombre, :desc, :precio, :costo, :stock, :minimo)"), nuevos)
        ids = _ids_por_sku(conn, [p["sku"] for p in productos])
        log.info("Productos: %d nuevos, %d totales", len(nuevos), len(ids))

        # --- histórico de ventas ---
        todos = list(ids.values())
        if reset:
            borrar = text("DELETE FROM historico_ventas WHERE id_producto IN :ids")
            conn.execute(borrar.bindparams(bindparam("ids", expanding=True)), {"ids": todos})
        con_datos = {r[0] for r in conn.execute(text("SELECT DISTINCT id_producto FROM historico_ventas"))}
        pendientes = {sku: pid for sku, pid in ids.items() if pid not in con_datos}
        omitidos = len(ids) - len(pendientes)
        if omitidos:
            log.info("%d productos ya tenían histórico (usa --reset para regenerarlo)", omitidos)

        df = ventas[ventas["sku"].isin(pendientes)].copy()
        df["id_producto"] = df["sku"].map(pendientes)
        df["fecha"] = df["fecha"].dt.date
        df["cantidad"] = df["cantidad"].round().clip(lower=0).astype(int)
        df["precio"] = df["precio"].round(2)
        filas = [{"p": int(a), "f": b, "c": int(c), "pv": float(d)}
                 for a, b, c, d in df[["id_producto", "fecha", "cantidad", "precio"]].itertuples(index=False, name=None)]
        insertar = text("INSERT INTO historico_ventas (id_producto, fecha, cantidad_vendida, precio_venta) "
                        "VALUES (:p, :f, :c, :pv)")
        for i in range(0, len(filas), CHUNK):
            conn.execute(insertar, filas[i:i + CHUNK])
        log.info("historico_ventas: %d filas insertadas", len(filas))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="Carga datos históricos de ventas en MySQL")
    ap.add_argument("--csv", help="Ruta a un CSV público de ventas; si se omite se simulan datos")
    ap.add_argument("--dias", type=int, default=730, help="Días a simular (por defecto 730)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--reset", action="store_true", help="Borra y regenera el histórico de los productos")
    ap.add_argument("--col-fecha", default="date")
    ap.add_argument("--col-item", default="item")
    ap.add_argument("--col-cantidad", default="sales")
    ap.add_argument("--col-precio", default=None, help="Columna de precio (opcional)")
    ap.add_argument("--max-items", type=int, default=50, help="Máximo de productos a cargar desde el CSV")
    args = ap.parse_args()

    productos, ventas = cargar_csv(args) if args.csv else simular(args.dias, args.seed)
    log.info("Fuente: %s → %d productos, %d filas", args.csv or "simulación", len(productos), len(ventas))
    persistir(get_engine(), productos, ventas, args.reset, args.seed)


if __name__ == "__main__":
    main()
