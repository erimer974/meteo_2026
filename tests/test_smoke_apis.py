"""
Smoke tests — appellent réellement les APIs déployées.
Skippés si les variables d'environnement ne sont pas définies.
"""
import os
import pytest
import requests


DATA_API_BASE = os.environ.get("DATA_API_BASE_URL")
MODEL_API_BASE = os.environ.get("MODEL_API_BASE_URL")


@pytest.mark.skipif(not DATA_API_BASE, reason="DATA_API_BASE_URL non défini")
def test_data_api_returns_rows():
    url = f"{DATA_API_BASE}/current-weather"
    resp = requests.get(url, params={"n": 5}, timeout=30)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0


@pytest.mark.skipif(not DATA_API_BASE, reason="DATA_API_BASE_URL non défini")
def test_data_api_health():
    resp = requests.get(f"{DATA_API_BASE}/", timeout=10)
    assert resp.status_code == 200


@pytest.mark.skipif(not MODEL_API_BASE, reason="MODEL_API_BASE_URL non défini")
def test_model_api_predict(sample_weather_row):
    url = f"{MODEL_API_BASE}/predict"
    resp = requests.post(url, json=sample_weather_row, timeout=120)
    assert resp.status_code == 200
    result = resp.json()
    assert "prediction" in result
    assert result["prediction"] in [0, 1]


@pytest.mark.skipif(not MODEL_API_BASE, reason="MODEL_API_BASE_URL non défini")
def test_model_api_health():
    resp = requests.get(f"{MODEL_API_BASE}/", timeout=10)
    assert resp.status_code == 200
