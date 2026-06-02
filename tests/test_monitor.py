"""
Tests unitaires purs des helpers de monitoring — Circuit 2.
Aucune dépendance à evidently, S3 ou Postgres (fonctions logiques isolées).
"""
import pandas as pd

from monitoring.monitor import _common_features, _extract_drift, FEATURE_COLS


def test_common_features_keeps_only_shared_feature_cols():
    reference = pd.DataFrame(columns=["Location", "MinTemp", "RainTomorrow"])
    current = pd.DataFrame(columns=["Location", "MinTemp", "prediction"])

    feats = _common_features(reference, current)

    assert "Location" in feats and "MinTemp" in feats
    assert "RainTomorrow" not in feats  # cible, pas une feature
    assert "prediction" not in feats    # sortie modèle, pas une feature
    assert set(feats).issubset(set(FEATURE_COLS))


def test_extract_drift_reads_flag_and_share():
    report = {"metrics": [
        {"result": {"dataset_drift": True, "share_of_drifted_columns": 0.6}},
    ]}

    drift, share = _extract_drift(report)

    assert drift is True
    assert share == 0.6


def test_extract_drift_defaults_when_metrics_empty():
    drift, share = _extract_drift({"metrics": []})
    assert drift is False
    assert share == 0.0
