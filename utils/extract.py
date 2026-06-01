import os
import json
import logging
import requests
import pandas as pd
import boto3
from datetime import datetime


def extract_weather() -> pd.DataFrame:
    """
    Appelle meteo-data-api (HF Space) pour récupérer un batch de lignes
    météo 2016-2017, sauvegarde un backup JSON brut sur S3.
    """
    base_url = os.environ["DATA_API_BASE_URL"]
    endpoint = os.environ.get("DATA_API_ENDPOINT", "/current-weather")
    batch_size = int(os.environ.get("DATA_API_BATCH_SIZE", 20))

    url = f"{base_url}{endpoint}"
    response = requests.get(url, params={"n": batch_size}, timeout=30)
    response.raise_for_status()
    data = response.json()

    df = pd.DataFrame(data)
    logging.info(f"Extraction : {len(df)} lignes reçues de la data-api.")

    _backup_to_s3(data)
    return df


def _backup_to_s3(data: list) -> None:
    bucket = os.environ["S3_BUCKET_NAME"]
    prefix = os.environ.get("S3_PROD_PREFIX", "production/meteo")
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    key = f"{prefix}/raw/backup_{timestamp}.json"

    s3 = boto3.client("s3")
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(data, default=str),
        ContentType="application/json",
    )
    logging.info(f"Backup S3 : s3://{bucket}/{key}")
