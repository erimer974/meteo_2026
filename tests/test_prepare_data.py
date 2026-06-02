"""
Tests unitaires purs (sans réseau) de la préparation des données — Circuit 1.
Vérifie clean() et split_by_year() sur un mini jeu de données.
"""
import pandas as pd
import pytest

from train.prepare_data import clean, split_by_year


@pytest.fixture
def raw_df():
    """Jeu brut minimal couvrant les deux côtés du cutoff temporel (2015)."""
    return pd.DataFrame({
        "Date": ["2014-01-01", "2014-01-02", "2016-06-01", "2017-03-03"],
        "Location": ["Sydney"] * 4,
        "RainToday": ["No", "Yes", "No", "Yes"],
        "RainTomorrow": ["Yes", "No", "Yes", None],
        "MinTemp": [10.0, 11.0, 12.0, 13.0],
    })


def test_clean_parses_date_into_parts(raw_df):
    result = clean(raw_df)
    assert {"Year", "Month", "Day"}.issubset(result.columns)
    assert "Date" not in result.columns


def test_clean_encodes_raintoday(raw_df):
    result = clean(raw_df)
    assert set(result["RainToday"].dropna().unique()).issubset({0, 1})


def test_split_train_respects_cutoff_and_target(raw_df):
    """train : Year <= 2015, RainTomorrow non nul, sans colonne Year."""
    train_df, _, _ = split_by_year(clean(raw_df))
    assert "Year" not in train_df.columns
    assert train_df["RainTomorrow"].notna().all()
    assert len(train_df) == 2  # les deux lignes de 2014


def test_split_prod_has_no_target(raw_df):
    """prod : Year > 2015, sans la cible RainTomorrow."""
    _, prod_df, _ = split_by_year(clean(raw_df))
    assert "RainTomorrow" not in prod_df.columns
    assert len(prod_df) == 2  # 2016 + 2017


def test_split_monitor_keeps_target(raw_df):
    """monitor : Year > 2015, conserve la cible pour EvidentlyAI."""
    _, _, monitor_df = split_by_year(clean(raw_df))
    assert "RainTomorrow" in monitor_df.columns
    assert len(monitor_df) == 2
