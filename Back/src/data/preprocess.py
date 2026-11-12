"""Preprocesamiento: limpieza, agregación diaria y generación de features.

Este módulo se usa tanto en el entrenamiento (vectorizado con pandas) como en la
API (fila a fila, de forma recursiva). Las definiciones de los lags y de las
medias móviles son idénticas en ambos caminos para evitar "train/serve skew":

    lag_k    = ventas de hace k días
    media_n  = media de los n días anteriores (sin incluir el día a predecir)
    std_7    = desviación típica muestral (ddof=1) de los 7 días anteriores
"""
from __future__ import annotations

import numpy as np
import pandas as pd

LAGS = (1, 7, 14, 28)
MIN_HISTORY = max(LAGS)
TARGET = "cantidad"

CALENDAR_COLUMNS = ["dow", "dia_mes", "mes", "semana", "trimestre", "es_finde",
                    "dow_sin", "dow_cos", "doy_sin", "doy_cos"]
FEATURE_COLUMNS = (CALENDAR_COLUMNS + ["precio"] + [f"lag_{k}" for k in LAGS]
                   + ["media_7", "media_28", "std_7"])


# ---------------------------------------------------------------------------
# Carga y limpieza
# ---------------------------------------------------------------------------
def load_history(engine) -> pd.DataFrame:
    """Lee `historico_ventas` agregado por producto y día."""
    query = (
        "SELECT id_producto, fecha, SUM(cantidad_vendida) AS cantidad, AVG(precio_venta) AS precio "
        "FROM historico_ventas GROUP BY id_producto, fecha"
    )
    return pd.read_sql(query, engine)


def clean_history(raw: pd.DataFrame, winsor_q: float = 0.995) -> pd.DataFrame:
    """Limpia y agrega a granularidad diaria con calendario completo por producto.

    - Convierte tipos (MySQL devuelve DECIMAL) y descarta nulos y cantidades negativas.
    - Agrega duplicados (producto, fecha).
    - Rellena los días sin venta con 0 y propaga el último precio conocido.
    - Recorta los valores atípicos extremos por producto (winsorizing).
    """
    df = raw.copy()
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce")
    df["precio"] = pd.to_numeric(df["precio"], errors="coerce")
    df = df.dropna(subset=["id_producto", "fecha", "cantidad"])
    df = df[df["cantidad"] >= 0]
    if df.empty:
        raise ValueError("No hay datos en historico_ventas. Ejecuta antes: python -m src.data.ingest")

    df = df.groupby(["id_producto", "fecha"], as_index=False).agg(
        cantidad=("cantidad", "sum"), precio=("precio", "mean"))

    fin = df["fecha"].max()
    partes = []
    for pid, g in df.groupby("id_producto"):
        g = g.set_index("fecha").sort_index()
        g = g.reindex(pd.date_range(g.index.min(), fin, freq="D", name="fecha"))
        g["cantidad"] = g["cantidad"].fillna(0.0)
        g["precio"] = g["precio"].ffill().bfill()
        g["id_producto"] = pid
        partes.append(g.reset_index())
    out = pd.concat(partes, ignore_index=True).dropna(subset=["precio"])

    tope = out.groupby("id_producto")["cantidad"].transform(lambda s: s.quantile(winsor_q))
    out["cantidad"] = out["cantidad"].clip(upper=tope).astype(float)
    return (out[["id_producto", "fecha", "cantidad", "precio"]]
            .sort_values(["id_producto", "fecha"]).reset_index(drop=True))


# ---------------------------------------------------------------------------
# Features
# ---------------------------------------------------------------------------
def calendar_features(fechas) -> pd.DataFrame:
    """Features temporales (con codificación cíclica de día de la semana y del año)."""
    f = pd.DatetimeIndex(fechas)
    dow = f.dayofweek.to_numpy()
    doy = f.dayofyear.to_numpy()
    return pd.DataFrame({
        "dow": dow,
        "dia_mes": f.day.to_numpy(),
        "mes": f.month.to_numpy(),
        "semana": f.isocalendar().week.to_numpy().astype(int),
        "trimestre": f.quarter.to_numpy(),
        "es_finde": (dow >= 5).astype(int),
        "dow_sin": np.sin(2 * np.pi * dow / 7),
        "dow_cos": np.cos(2 * np.pi * dow / 7),
        "doy_sin": np.sin(2 * np.pi * doy / 365.25),
        "doy_cos": np.cos(2 * np.pi * doy / 365.25),
    })


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Añade features temporales, lags y medias móviles (todo con datos anteriores al día)."""
    df = df.sort_values(["id_producto", "fecha"]).reset_index(drop=True)
    cal = calendar_features(df["fecha"])
    cal.index = df.index
    df = pd.concat([df, cal], axis=1)

    ventas = df.groupby("id_producto")["cantidad"]
    for k in LAGS:
        df[f"lag_{k}"] = ventas.shift(k)
    previo = ventas.shift(1).groupby(df["id_producto"])
    df["media_7"] = previo.transform(lambda s: s.rolling(7).mean())
    df["media_28"] = previo.transform(lambda s: s.rolling(28).mean())
    df["std_7"] = previo.transform(lambda s: s.rolling(7).std())
    return df


def make_dataset(clean: pd.DataFrame) -> pd.DataFrame:
    """Dataset de entrenamiento: features + objetivo, sin filas con lags incompletos."""
    return add_features(clean).dropna(subset=FEATURE_COLUMNS).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Inferencia recursiva (la usa la API y el backtest)
# ---------------------------------------------------------------------------
def build_feature_row(cal_row, history, precio: float) -> dict:
    """Features de un día a partir de las ventas anteriores (history[-1] = ayer)."""
    h = np.asarray(history, dtype=float)
    if len(h) < MIN_HISTORY:
        raise ValueError(f"Se necesitan al menos {MIN_HISTORY} días de histórico")
    fila = {c: float(cal_row[c]) for c in CALENDAR_COLUMNS}
    fila["precio"] = float(precio)
    for k in LAGS:
        fila[f"lag_{k}"] = h[-k]
    fila["media_7"] = h[-7:].mean()
    fila["media_28"] = h[-28:].mean()
    fila["std_7"] = h[-7:].std(ddof=1)
    return fila


def forecast_demand(model, history, ultima_fecha, precio: float, horizonte: int):
    """Predice `horizonte` días a partir de `ultima_fecha` de forma recursiva.

    Cada predicción se añade al histórico para construir los lags del día siguiente.
    Devuelve una lista de tuplas (fecha, demanda_estimada).
    """
    hist = [float(x) for x in history][-MIN_HISTORY:]
    fechas = pd.date_range(pd.Timestamp(ultima_fecha) + pd.Timedelta(days=1), periods=horizonte, freq="D")
    cal = calendar_features(fechas)
    salida = []
    for i, f in enumerate(fechas):
        x = pd.DataFrame([build_feature_row(cal.iloc[i], hist, precio)], columns=FEATURE_COLUMNS)
        y = max(0.0, float(model.predict(x)[0]))
        salida.append((f.date(), y))
        hist = (hist + [y])[-MIN_HISTORY:]
    return salida
