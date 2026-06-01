"""
Monitoring EvidentlyAI — Circuit 2 Étape 2.

Compare les prédictions récentes (Neon Postgres) avec les vraies valeurs
(S3 raw/meteo/monitor/) pour détecter le data drift et la dégradation
des performances du modèle.
"""
import os
import logging
import pandas as pd
import boto3
from io import StringIO
from datetime import datetime, timedelta
from dotenv import load_dotenv
from sqlalchemy import create_engine

# À implémenter en Phase 10
# from evidently.report import Report
# from evidently.metric_preset import DataDriftPreset, ClassificationPreset


def load_predictions(days: int = 7) -> pd.DataFrame:
    """Charge les prédictions récentes depuis Neon Postgres."""
    database_url = os.environ["DATABASE_URL"]
    table = os.environ.get("DB_TARGET_TABLE", "meteo_predictions")
    engine = create_engine(database_url)
    query = f"SELECT * FROM {table} ORDER BY created_at DESC LIMIT 1000"
    return pd.read_sql(query, engine)


def load_ground_truth() -> pd.DataFrame:
    """Charge les vraies valeurs RainTomorrow depuis S3 monitor/."""
    bucket = os.environ["S3_BUCKET_NAME"]
    prefix = os.environ.get("S3_MONITOR_PREFIX", "monitor/meteo")
    key = f"{prefix}/weatherAUS_monitor.csv"
    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=bucket, Key=key)
    return pd.read_csv(StringIO(obj["Body"].read().decode("utf-8")))


def run_monitoring() -> dict:
    """
    Génère les rapports EvidentlyAI et retourne un dict avec drift_detected.
    Utilisé comme tâche Airflow (résultat pushé via XCom).
    """
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    # Implémentation complète en Phase 10
    logging.info("Monitoring EvidentlyAI — squelette (Phase 10)")
    drift_detected = False

    return {"drift_detected": drift_detected, "timestamp": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    result = run_monitoring()
    logging.info(f"Résultat monitoring : {result}")
