import os
import logging
import requests
import pandas as pd

CATEGORICAL_COLS = ["Location", "WindGustDir", "WindDir9am", "WindDir3pm"]
NUMERIC_COLS = [
    "MinTemp", "MaxTemp", "Rainfall", "Evaporation", "Sunshine",
    "WindGustSpeed", "WindSpeed9am", "WindSpeed3pm",
    "Humidity9am", "Humidity3pm", "Pressure9am", "Pressure3pm",
    "Cloud9am", "Cloud3pm", "Temp9am", "Temp3pm",
]


def transform_weather(df: pd.DataFrame) -> pd.DataFrame:
    """
    Applique le même nettoyage que prepare_data.py sur les données
    reçues de la data-api, puis appelle le modèle /predict.
    """
    df = _clean(df)
    df = _predict(df)
    return df


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """Nettoyage miroir de prepare_data.clean() — imputation + RainToday encodage."""
    df = df.copy()

    for col in CATEGORICAL_COLS:
        if col in df.columns:
            mode = df[col].mode()
            df[col] = df[col].fillna(mode[0] if not mode.empty else "Unknown")

    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            df[col] = df[col].fillna(df[col].mean())

    if "RainToday" in df.columns:
        # Robuste aux versions de pandas : en pandas 3.0 les chaînes ont un dtype
        # `str` dédié (≠ object), donc on teste le caractère numérique plutôt que
        # `dtype == object` (sinon "Yes"/"No" seraient coercés en NaN -> 0).
        if pd.api.types.is_numeric_dtype(df["RainToday"]):
            df["RainToday"] = pd.to_numeric(df["RainToday"], errors="coerce").fillna(0).astype(int)
        else:
            df["RainToday"] = df["RainToday"].map({"No": 0, "Yes": 1}).fillna(0).astype(int)

    return df


def _predict(df: pd.DataFrame) -> pd.DataFrame:
    """Appelle FastAPI /predict pour chaque ligne et ajoute les colonnes résultat."""
    base_url = os.environ["MODEL_API_BASE_URL"]
    endpoint = os.environ.get("MODEL_API_PREDICT_ENDPOINT", "/predict")
    timeout = int(os.environ.get("MODEL_API_TIMEOUT", 120))
    url = f"{base_url}{endpoint}"

    predictions, proba_0s, proba_1s = [], [], []

    for _, row in df.iterrows():
        payload = row.to_dict()
        try:
            resp = requests.post(url, json=payload, timeout=timeout)
            resp.raise_for_status()
            result = resp.json()
            predictions.append(result.get("prediction"))
            proba_0s.append(result.get("proba_0"))
            proba_1s.append(result.get("proba_1"))
        except Exception as e:
            logging.warning(f"Prédiction échouée : {e}")
            predictions.append(None)
            proba_0s.append(None)
            proba_1s.append(None)

    df = df.copy()
    df["prediction"] = predictions
    df["proba_0"] = proba_0s
    df["proba_1"] = proba_1s

    logging.info(f"Transformation : {len(df)} lignes prédites.")
    return df
