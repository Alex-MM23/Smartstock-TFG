"""Entrenamiento y evaluación del modelo de demanda.

Uso (desde la raíz del repositorio):
    python -m src.models.train
    python -m src.models.train --test-days 60 --output artifacts/demand_model.joblib

Pasos:
  1. Lee historico_ventas, limpia y genera features (src.data.preprocess).
  2. Split temporal (los últimos N días son el test; nunca se mezcla el futuro).
  3. Compara una línea base ingenua (ventas de hace 7 días) con Random Forest y
     Gradient Boosting; elige el de menor RMSE.
  4. Backtest recursivo a 7 días (el modo real de uso de la API) para estimar el
     error de predicción que se usará como incertidumbre del stock de seguridad.
  5. Reentrena el mejor modelo con todos los datos y lo guarda con joblib.
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

from src.config import MODEL_PATH, get_engine
from src.data.preprocess import (FEATURE_COLUMNS, MIN_HISTORY, TARGET, clean_history,
                                 forecast_demand, load_history, make_dataset)

log = logging.getLogger("train")


def metricas(y_real, y_pred) -> dict:
    return {"rmse": float(np.sqrt(mean_squared_error(y_real, y_pred))),
            "mae": float(mean_absolute_error(y_real, y_pred))}


def candidatos(seed: int) -> dict:
    return {
        "random_forest": RandomForestRegressor(
            n_estimators=300, min_samples_leaf=3, max_features=0.7, n_jobs=-1, random_state=seed),
        "gradient_boosting": HistGradientBoostingRegressor(
            max_iter=400, learning_rate=0.05, max_leaf_nodes=31, l2_regularization=1.0,
            early_stopping=False, random_state=seed),
    }


def backtest_recursivo(model, clean: pd.DataFrame, cutoff, horizonte: int = 7, paso: int = 14) -> dict:
    """Simula el uso real: desde varios orígenes del periodo de test, predice `horizonte`
    días encadenando sus propias predicciones y compara con las ventas reales."""
    origenes = pd.date_range(cutoff, clean["fecha"].max() - pd.Timedelta(days=horizonte), freq=f"{paso}D")
    reales, preds = [], []
    for _, g in clean.groupby("id_producto"):
        g = g.set_index("fecha")
        for o in origenes:
            if o not in g.index:
                continue
            hist = g.loc[:o, "cantidad"].to_numpy()
            real = g.loc[o + pd.Timedelta(days=1): o + pd.Timedelta(days=horizonte), "cantidad"].to_numpy()
            if len(hist) < MIN_HISTORY or len(real) < horizonte:
                continue
            pred = forecast_demand(model, hist, o, g.loc[o, "precio"], horizonte)
            reales.extend(real)
            preds.extend(p for _, p in pred)
    if not reales:
        raise ValueError("No hay suficientes datos para el backtest recursivo")
    return {**metricas(reales, preds), "n": len(reales), "horizonte_dias": horizonte}


def entrenar(clean: pd.DataFrame, test_days: int = 90, seed: int = 42) -> tuple[dict, dict]:
    """Entrena, evalúa y devuelve (bundle_serializable, resumen_de_metricas)."""
    ds = make_dataset(clean)
    cutoff = ds["fecha"].max() - pd.Timedelta(days=test_days)
    train, test = ds[ds["fecha"] <= cutoff], ds[ds["fecha"] > cutoff]
    if len(train) < 500 or test.empty:
        raise ValueError("Histórico insuficiente: reduce --test-days o carga más datos")
    log.info("Dataset: %d filas | train hasta %s (%d) | test %d filas | %d productos",
             len(ds), cutoff.date(), len(train), len(test), ds["id_producto"].nunique())

    resultados = {"baseline_lag_7": metricas(test[TARGET], test["lag_7"])}
    modelos = {}
    for nombre, modelo in candidatos(seed).items():
        modelo.fit(train[FEATURE_COLUMNS], train[TARGET])
        resultados[nombre] = metricas(test[TARGET], modelo.predict(test[FEATURE_COLUMNS]))
        modelos[nombre] = modelo
    for nombre, m in resultados.items():
        log.info("%-20s RMSE=%.3f  MAE=%.3f", nombre, m["rmse"], m["mae"])

    mejor = min(modelos, key=lambda n: resultados[n]["rmse"])
    if hasattr(modelos[mejor], "n_jobs"):
        modelos[mejor].set_params(n_jobs=1)          # predicciones fila a fila más rápidas
    log.info("Mejor modelo: %s → backtest recursivo a 7 días...", mejor)
    recursivo = backtest_recursivo(modelos[mejor], clean, cutoff)
    log.info("Backtest recursivo 7d: RMSE=%.3f  MAE=%.3f (n=%d)",
             recursivo["rmse"], recursivo["mae"], recursivo["n"])

    final = candidatos(seed)[mejor]
    final.fit(ds[FEATURE_COLUMNS], ds[TARGET])
    if hasattr(final, "n_jobs"):
        final.set_params(n_jobs=1)

    ahora = datetime.now(timezone.utc)
    resumen = {"modelo": mejor, "test_days": test_days, "metricas_test": resultados,
               "backtest_recursivo_7d": recursivo}
    bundle = {
        "model": final,
        "model_name": mejor,
        "version": f"{mejor[:14]}-{ahora:%Y%m%d%H%M}",   # cabe en modelo_version VARCHAR(50)
        "feature_columns": FEATURE_COLUMNS,
        "sigma_dia": recursivo["rmse"],                   # incertidumbre diaria para el stock de seguridad
        "metrics": resumen,
        "trained_at": ahora.isoformat(),
        "n_rows": int(len(ds)),
        "n_products": int(ds["id_producto"].nunique()),
        "data_until": ds["fecha"].max().date().isoformat(),
    }
    return bundle, resumen


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="Entrena el modelo de predicción de demanda")
    ap.add_argument("--test-days", type=int, default=90, help="Días finales reservados para test")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--output", type=Path, default=MODEL_PATH)
    args = ap.parse_args()

    clean = clean_history(load_history(get_engine()))
    bundle, resumen = entrenar(clean, args.test_days, args.seed)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, args.output, compress=3)
    args.output.with_suffix(".metrics.json").write_text(
        json.dumps({**resumen, "version": bundle["version"], "trained_at": bundle["trained_at"]},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Modelo %s guardado en %s", bundle["version"], args.output)


if __name__ == "__main__":
    main()
