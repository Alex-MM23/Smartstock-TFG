"""Tests for ML preprocessing and training."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from src.data.preprocess import (
    CALENDAR_COLUMNS,
    FEATURE_COLUMNS,
    LAGS,
    MIN_HISTORY,
    add_features,
    build_feature_row,
    calendar_features,
    forecast_demand,
)


class TestPreprocess:
    """Tests for data preprocessing functions."""

    def test_lags_and_min_history(self):
        """Test LAGS and MIN_HISTORY constants."""
        assert LAGS == (1, 7, 14, 28)
        assert MIN_HISTORY == 28

    def test_calendar_features(self):
        """Test calendar feature generation."""
        fechas = pd.date_range("2024-01-01", periods=10, freq="D")
        cal = calendar_features(fechas)

        assert len(cal) == 10
        assert list(cal.columns) == CALENDAR_COLUMNS
        assert "dow" in cal.columns
        assert "dow_sin" in cal.columns
        assert "doy_cos" in cal.columns

    def test_calendar_features_cyclic(self):
        """Test cyclic encoding produces valid sin/cos values."""
        fechas = pd.date_range("2024-01-01", periods=7, freq="D")
        cal = calendar_features(fechas)

        # Sin^2 + Cos^2 should be ~1
        dow_sum = cal["dow_sin"]**2 + cal["dow_cos"]**2
        assert np.allclose(dow_sum, 1.0, atol=1e-6)

        doy_sum = cal["doy_sin"]**2 + cal["doy_cos"]**2
        assert np.allclose(doy_sum, 1.0, atol=1e-6)

    def test_add_features(self):
        """Test feature generation on sample data."""
        # Create sample data with enough history
        dates = pd.date_range("2024-01-01", periods=60, freq="D")
        df = pd.DataFrame({
            "id_producto": [1] * 60,
            "fecha": dates,
            "cantidad": np.random.poisson(10, 60),
            "precio": [50.0] * 60,
        })

        result = add_features(df)

        # Check all feature columns exist
        for col in FEATURE_COLUMNS:
            assert col in result.columns, f"Missing feature: {col}"

        # Check lags are shifted (lag_1 should be NaN for first row)
        assert pd.isna(result.loc[0, "lag_1"])
        assert not pd.isna(result.loc[1, "lag_1"])

    def test_build_feature_row(self):
        """Test building a single feature row for inference."""
        # Create calendar row
        cal_row = pd.Series({
            "dow": 1, "dia_mes": 15, "mes": 1, "semana": 3, "trimestre": 1,
            "es_finde": 0, "dow_sin": 0.5, "dow_cos": 0.866,
            "doy_sin": 0.1, "doy_cos": 0.995
        })

        # History of 28 values (minimum required)
        history = np.random.poisson(10, 28)

        row = build_feature_row(cal_row, history, 50.0)

        # Check all features present
        for col in FEATURE_COLUMNS:
            assert col in row

        # Check lags match last values
        assert row["lag_1"] == history[-1]
        assert row["lag_7"] == history[-7]
        assert row["lag_14"] == history[-14]
        assert row["lag_28"] == history[-28]

        # Check moving averages
        assert abs(row["media_7"] - history[-7:].mean()) < 0.001
        assert abs(row["media_28"] - history[-28:].mean()) < 0.001

    def test_build_feature_row_insufficient_history(self):
        """Test build_feature_row raises with insufficient history."""
        cal_row = pd.Series(dict.fromkeys(CALENDAR_COLUMNS, 0))
        history = np.random.poisson(10, 10)  # Less than MIN_HISTORY

        with pytest.raises(ValueError, match="al menos 28 días"):
            build_feature_row(cal_row, history, 50.0)

    def test_forecast_demand_shape(self):
        """Test forecast_demand returns correct shape."""
        from unittest.mock import MagicMock

        # Mock model that returns constant prediction
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([5.0])

        history = np.random.poisson(10, 28)
        ultima_fecha = date(2024, 6, 15)

        predictions = forecast_demand(mock_model, history, ultima_fecha, 50.0, 7)

        assert len(predictions) == 7
        for fecha, demanda in predictions:
            assert isinstance(fecha, date)
            assert isinstance(demanda, float)
            assert demanda >= 0

    def test_forecast_demand_recursive(self):
        """Test forecast_demand uses recursive predictions."""
        from unittest.mock import MagicMock

        call_count = [0]

        def mock_predict(x):
            call_count[0] += 1
            return np.array([float(call_count[0])])

        mock_model = MagicMock()
        mock_model.predict.side_effect = mock_predict

        history = np.random.poisson(10, 28)
        ultima_fecha = date(2024, 6, 15)

        predictions = forecast_demand(mock_model, history, ultima_fecha, 50.0, 5)

        # Should be called once per prediction day
        assert call_count[0] == 5
        assert len(predictions) == 5


class TestMetrics:
    """Tests for metric calculations."""

    def test_metricas_function(self):
        """Test metricas helper from train.py."""
        from src.models.train import metricas

        y_real = np.array([10, 12, 8, 15, 9])
        y_pred = np.array([11, 11, 9, 14, 10])

        result = metricas(y_real, y_pred)

        assert "rmse" in result
        assert "mae" in result
        assert result["rmse"] >= 0
        assert result["mae"] >= 0
