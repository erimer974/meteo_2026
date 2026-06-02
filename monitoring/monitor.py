"""
Monitoring EvidentlyAI — Circuit 2 Étape 2.

Compare la distribution des features servies récemment (prédictions stockées
dans Neon Postgres) à la distribution de référence (S3 raw/meteo/monitor/,
vraies données 2016-2017) pour détecter le *data drift*.

Si le drift dépasse le seuil, `drift_detected=True` est remonté : le DAG
production déclenche alors automatiquement le `training_pipeline` (retraining).
Un rapport HTML est sauvegardé sur S3 pour le dashboard.
"""
import os
import logging
import pandas as pd
import boto3
from io import StringIO
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine

# Colonnes features comparées (miroir de train.py — hors target/prédictions).
CATEGORICAL_COLS = ["Location", "WindGustDir", "WindDir9am", "WindDir3pm"]
NUMERIC_COLS = [
    "MinTemp", "MaxTemp", "Rainfall", "Evaporation", "Sunshine",
    "WindGustSpeed", "WindSpeed9am", "WindSpeed3pm",
    "Humidity9am", "Humidity3pm", "Pressure9am", "Pressure3pm",
    "Cloud9am", "Cloud3pm", "Temp9am", "Temp3pm",
    "RainToday", "Month", "Day",
]
FEATURE_COLS = CATEGORICAL_COLS + NUMERIC_COLS

# Part de colonnes en drift au-delà de laquelle on déclenche un retraining.
DRIFT_SHARE_THRESHOLD = float(os.environ.get("DRIFT_SHARE_THRESHOLD", 0.5))


def load_predictions(limit: int = 1000) -> pd.DataFrame:
    """Charge les prédictions récentes (features servies) depuis Neon Postgres."""
    database_url = os.environ["DATABASE_URL"]
    table = os.environ.get("DB_TARGET_TABLE", "meteo_predictions")
    engine = create_engine(database_url)
    query = f"SELECT * FROM {table} ORDER BY created_at DESC NULLS LAST LIMIT {limit}"
    df = pd.read_sql(query, engine)
    logging.info(f"Prédictions récentes chargées : {len(df)} lignes.")
    return df


def load_ground_truth() -> pd.DataFrame:
    """
    Charge le jeu de référence (vraies données 2016-2017) depuis S3.

    Écrit par `train/prepare_data.py` dans `{S3_RAW_PREFIX}/monitor/`.
    """
    bucket = os.environ["S3_BUCKET_NAME"]
    prefix = os.environ.get("S3_RAW_PREFIX", "raw/meteo")
    key = f"{prefix}/monitor/weatherAUS_monitor.csv"
    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=bucket, Key=key)
    df = pd.read_csv(StringIO(obj["Body"].read().decode("utf-8")))
    logging.info(f"Référence chargée depuis s3://{bucket}/{key} : {len(df)} lignes.")
    return df


def _common_features(reference: pd.DataFrame, current: pd.DataFrame) -> list:
    """Features présentes dans les deux jeux (intersection avec FEATURE_COLS)."""
    return [c for c in FEATURE_COLS if c in reference.columns and c in current.columns]


def _save_report_html(report, bucket: str, prefix: str) -> str:
    """Sauvegarde le rapport Evidently en HTML sur S3 (consommé par le dashboard)."""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    key = f"{prefix}/monitoring/drift_report_{timestamp}.html"
    # Evidently écrit du HTML (str) dans le buffer → StringIO, puis encodage S3.
    buffer = StringIO()
    report.save_html(buffer)
    boto3.client("s3").put_object(
        Bucket=bucket, Key=key,
        Body=buffer.getvalue().encode("utf-8"), ContentType="text/html",
    )
    logging.info(f"Rapport drift : s3://{bucket}/{key}")
    return key


def _extract_drift(report_dict: dict) -> tuple:
    """
    Extrait (dataset_drift, drift_share) du dict Evidently de façon défensive
    (la structure varie selon la version d'evidently).
    """
    dataset_drift = False
    drift_share = 0.0
    for metric in report_dict.get("metrics", []):
        result = metric.get("result", {})
        if "dataset_drift" in result:
            dataset_drift = bool(result["dataset_drift"])
        if "share_of_drifted_columns" in result:
            drift_share = float(result["share_of_drifted_columns"])
    return dataset_drift, drift_share


def run_monitoring() -> dict:
    """
    Génère le rapport de drift EvidentlyAI et retourne un dict avec
    `drift_detected`. Utilisé comme tâche Airflow (résultat poussé via XCom).
    """
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    reference = load_ground_truth()
    current = load_predictions()

    if current.empty:
        logging.warning("Aucune prédiction en base — monitoring ignoré.")
        return {"drift_detected": False, "reason": "no_predictions",
                "timestamp": datetime.utcnow().isoformat()}

    features = _common_features(reference, current)
    if not features:
        logging.warning("Aucune feature commune — monitoring ignoré.")
        return {"drift_detected": False, "reason": "no_common_features",
                "timestamp": datetime.utcnow().isoformat()}

    from evidently.report import Report
    from evidently.metric_preset import DataDriftPreset

    report = Report(metrics=[DataDriftPreset()])
    report.run(reference_data=reference[features], current_data=current[features])

    dataset_drift, drift_share = _extract_drift(report.as_dict())
    drift_detected = dataset_drift or drift_share >= DRIFT_SHARE_THRESHOLD

    try:
        report_key = _save_report_html(
            report,
            os.environ["S3_BUCKET_NAME"],
            os.environ.get("S3_PROD_PREFIX", "production/meteo"),
        )
    except Exception as e:  # le rapport est secondaire, ne doit pas casser le DAG
        logging.warning(f"Sauvegarde du rapport HTML échouée : {e}")
        report_key = None

    logging.info(
        f"Drift dataset={dataset_drift} | part colonnes en drift={drift_share:.2%} "
        f"| seuil={DRIFT_SHARE_THRESHOLD:.0%} → drift_detected={drift_detected}"
    )

    return {
        "drift_detected": bool(drift_detected),
        "dataset_drift": bool(dataset_drift),
        "drift_share": drift_share,
        "n_features": len(features),
        "report_key": report_key,
        "timestamp": datetime.utcnow().isoformat(),
    }


if __name__ == "__main__":
    result = run_monitoring()
    logging.info(f"Résultat monitoring : {result}")
