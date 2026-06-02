"""
Tests de validation de données — inspirés du cours Jedha « Testing Data »
(pandas.testing) et adaptés au projet meteo.

On valide le schéma et les types produits par le nettoyage ETL, sur des
données mock (zéro réseau, zéro S3).
"""
import pandas as pd
from pandas.testing import assert_series_equal

from utils.transform import _clean, CATEGORICAL_COLS, NUMERIC_COLS


def test_clean_no_nan_in_known_columns(sample_weather_df):
    """Après nettoyage, aucune valeur manquante dans les colonnes connues."""
    df = sample_weather_df.copy()
    df.loc[0, "MinTemp"] = None
    df.loc[1, "Location"] = None

    result = _clean(df)

    present = [c for c in CATEGORICAL_COLS + NUMERIC_COLS if c in result.columns]
    assert result[present].isnull().sum().sum() == 0


def test_clean_numeric_columns_are_numeric(sample_weather_df):
    """Les colonnes numériques sont bien de type numérique après nettoyage."""
    result = _clean(sample_weather_df)
    for col in NUMERIC_COLS:
        if col in result.columns:
            assert pd.api.types.is_numeric_dtype(result[col]), f"{col} non numérique"


def test_clean_raintoday_encoded_as_int(sample_weather_df):
    """RainToday est encodé en 0/1 — validation via pandas.testing.assert_series_equal."""
    df = sample_weather_df.copy()
    df["RainToday"] = "Yes"

    result = _clean(df)

    expected = pd.Series([1] * len(df), name="RainToday")
    assert_series_equal(
        result["RainToday"].reset_index(drop=True),
        expected,
        check_dtype=False,
    )
    assert set(result["RainToday"].unique()).issubset({0, 1})


def test_clean_preserves_schema(sample_weather_df):
    """Le nettoyage ne doit ni ajouter ni retirer de colonne."""
    result = _clean(sample_weather_df)
    assert list(result.columns) == list(sample_weather_df.columns)
