import os
import logging
import pandas as pd
import boto3
from datetime import datetime
from sqlalchemy import create_engine


def load_weather(df: pd.DataFrame) -> dict:
    """
    Charge les données prédites :
    - CSV sur S3 production/clean/
    - INSERT dans Neon Postgres (mode append)
    """
    s3_key = _load_to_s3(df)
    rows_inserted = _load_to_postgres(df)
    return {"s3_key": s3_key, "rows_inserted": rows_inserted}


def _load_to_s3(df: pd.DataFrame) -> str:
    bucket = os.environ["S3_BUCKET_NAME"]
    prefix = os.environ.get("S3_PROD_PREFIX", "production/meteo")
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    key = f"{prefix}/clean/predictions_{timestamp}.csv"

    s3 = boto3.client("s3")
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=df.to_csv(index=False).encode("utf-8"),
        ContentType="text/csv",
    )
    logging.info(f"CSV S3 : s3://{bucket}/{key}")
    return key


def _load_to_postgres(df: pd.DataFrame) -> int:
    database_url = os.environ["DATABASE_URL"]
    table = os.environ.get("DB_TARGET_TABLE", "meteo_predictions")

    engine = create_engine(database_url)
    df.to_sql(table, engine, if_exists="append", index=False)
    logging.info(f"Postgres : {len(df)} lignes insérées dans '{table}'.")
    return len(df)
