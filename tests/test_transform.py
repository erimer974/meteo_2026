"""Tests unitaires — logique pure, zéro réseau, zéro mock."""
import pandas as pd
import pytest
from utils.transform import _clean, CATEGORICAL_COLS, NUMERIC_COLS


def test_clean_imputes_numeric_nan(sample_weather_df):
    df = sample_weather_df.copy()
    df.loc[0, "MinTemp"] = None
    result = _clean(df)
    assert result["MinTemp"].isna().sum() == 0


def test_clean_imputes_categorical_nan(sample_weather_df):
    df = sample_weather_df.copy()
    df.loc[0, "Location"] = None
    result = _clean(df)
    assert result["Location"].isna().sum() == 0


def test_clean_encodes_rain_today(sample_weather_df):
    df = sample_weather_df.copy()
    df["RainToday"] = "Yes"
    result = _clean(df)
    assert set(result["RainToday"].unique()).issubset({0, 1})


def test_clean_preserves_row_count(sample_weather_df):
    result = _clean(sample_weather_df)
    assert len(result) == len(sample_weather_df)


def test_clean_already_encoded_rain_today(sample_weather_df):
    """RainToday déjà en 0/1 ne doit pas devenir NaN."""
    result = _clean(sample_weather_df)
    assert result["RainToday"].isna().sum() == 0
