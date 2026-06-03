import os
import mlflow
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Union
from dotenv import load_dotenv

load_dotenv()

REGISTERED_MODEL_NAME = "rain_tomorrow_detector"
MODEL_ALIAS = "production"

# Cache process-global du modèle servi + sa version (alias 'production').
_MODEL = None
_MODEL_VERSION = None


def _resolve_version():
    """Version actuellement pointée par l'alias 'production' dans le Registry."""
    from mlflow.tracking import MlflowClient
    mv = MlflowClient().get_model_version_by_alias(REGISTERED_MODEL_NAME, MODEL_ALIAS)
    return mv.version


def load_model(force: bool = False):
    """
    Charge — ou recharge si force=True — le modèle 'production' depuis MLflow.

    Le rechargement est nécessaire après un `promote` (Circuit 1) : sans lui, le
    process continuerait de servir l'ancienne version mise en cache.
    """
    global _MODEL, _MODEL_VERSION
    if _MODEL is None or force:
        mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
        _MODEL = mlflow.sklearn.load_model(f"models:/{REGISTERED_MODEL_NAME}@{MODEL_ALIAS}")
        try:
            _MODEL_VERSION = _resolve_version()
        except Exception:
            _MODEL_VERSION = None
    return _MODEL


def get_model():
    return load_model(force=False)


app = FastAPI(
    title="Meteo Model API",
    description="Prédiction de pluie J+1 — Rain in Australia",
    version="1.0",
)


class WeatherFeatures(BaseModel):
    Location: str
    MinTemp: Union[float, None] = None
    MaxTemp: Union[float, None] = None
    Rainfall: Union[float, None] = None
    Evaporation: Union[float, None] = None
    Sunshine: Union[float, None] = None
    WindGustDir: Union[str, None] = None
    WindGustSpeed: Union[float, None] = None
    WindDir9am: Union[str, None] = None
    WindDir3pm: Union[str, None] = None
    WindSpeed9am: Union[float, None] = None
    WindSpeed3pm: Union[float, None] = None
    Humidity9am: Union[float, None] = None
    Humidity3pm: Union[float, None] = None
    Pressure9am: Union[float, None] = None
    Pressure3pm: Union[float, None] = None
    Cloud9am: Union[float, None] = None
    Cloud3pm: Union[float, None] = None
    Temp9am: Union[float, None] = None
    Temp3pm: Union[float, None] = None
    RainToday: Union[int, None] = None
    Month: Union[int, None] = None
    Day: Union[int, None] = None


@app.get("/")
async def index():
    return {
        "message": "Meteo Model API — /predict pour les prédictions, /docs pour la documentation.",
        "model": REGISTERED_MODEL_NAME,
        "model_version": _MODEL_VERSION,  # None tant qu'aucune prédiction n'a chargé le modèle
    }


@app.post("/reload")
async def reload_model():
    """
    Recharge le modèle 'production' (à appeler après un `promote` MLflow).
    Boucle le retraining : le DAG training_pipeline appelle cette route après
    avoir promu une nouvelle version.
    """
    try:
        load_model(force=True)
        return {"status": "reloaded", "model": REGISTERED_MODEL_NAME, "version": _MODEL_VERSION}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict")
async def predict(features: WeatherFeatures):
    try:
        model = get_model()
        df = pd.DataFrame([features.model_dump()])
        prediction = model.predict(df)[0]
        proba = model.predict_proba(df)[0]
        return {
            "prediction": int(prediction),
            "proba_0": round(float(proba[0]), 4),
            "proba_1": round(float(proba[1]), 4),
            "model_version": _MODEL_VERSION,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
