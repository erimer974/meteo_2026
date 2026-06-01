import os
import mlflow
import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Union
from dotenv import load_dotenv

load_dotenv()

REGISTERED_MODEL_NAME = "rain_tomorrow_detector"
MODEL_ALIAS = "production"
MODEL = mlflow.sklearn.load_model(f"models:/{REGISTERED_MODEL_NAME}@{MODEL_ALIAS}")

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
    return {"message": "Meteo Model API — /predict pour les prédictions, /docs pour la documentation."}


@app.post("/predict")
async def predict(features: WeatherFeatures):
    df = pd.DataFrame([features.model_dump()])
    prediction = MODEL.predict(df)[0]
    proba = MODEL.predict_proba(df)[0]
    return {
        "prediction": int(prediction),
        "proba_0": round(float(proba[0]), 4),
        "proba_1": round(float(proba[1]), 4),
    }
