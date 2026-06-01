"""
meteo-data-api — HuggingFace Space #3

Sert des lignes aléatoires du dataset météo 2016-2017 (sans RainTomorrow)
comme s'il s'agissait d'un flux de données live.
Source : S3 raw/meteo/prod/weatherAUS_prod.csv
"""
import os
import boto3
import pandas as pd
from io import StringIO
from fastapi import FastAPI, Query
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Meteo Data API",
    description="Flux de données météo australiennes 2016-2017 — simulation production",
    version="1.0",
)

_df_cache: pd.DataFrame | None = None


def _load_prod_data() -> pd.DataFrame:
    global _df_cache
    if _df_cache is None:
        bucket = os.environ["S3_BUCKET_NAME"]
        prefix = os.environ.get("S3_RAW_PREFIX", "raw/meteo")
        key = f"{prefix}/prod/weatherAUS_prod.csv"
        s3 = boto3.client("s3")
        obj = s3.get_object(Bucket=bucket, Key=key)
        _df_cache = pd.read_csv(StringIO(obj["Body"].read().decode("utf-8")))
    return _df_cache


@app.get("/")
async def index():
    return {"message": "Meteo Data API opérationnelle — GET /current-weather?n=20"}


@app.get("/current-weather")
async def current_weather(n: int = Query(default=20, ge=1, le=200)):
    """
    Retourne n lignes aléatoires du dataset de production (2016-2017).
    Simule un flux de données live sans la colonne RainTomorrow.
    """
    df = _load_prod_data()
    sample = df.sample(n=min(n, len(df))).reset_index(drop=True)
    return sample.to_dict(orient="records")


@app.get("/info")
async def info():
    df = _load_prod_data()
    return {
        "total_rows": len(df),
        "columns": list(df.columns),
        "period": "2016-2017",
    }
