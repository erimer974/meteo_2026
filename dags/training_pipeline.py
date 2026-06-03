"""
Circuit 1 — DAG Airflow : pipeline d'entraînement.

Tâches :
  1. prepare_data  → télécharge Kaggle, nettoie, uploade S3
  2. train_model   → entraîne, logge dans MLflow, alias "challenger"
  3. validate_model → vérifie que les métriques dépassent le seuil
  4. promote        → attribue l'alias "production" dans MLflow
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "meteo_mlops",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="training_pipeline",
    default_args=default_args,
    description="Circuit 1 — Entraînement du modèle météo",
    schedule_interval=None,   # déclenché manuellement ou par monitoring
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["circuit1", "training"],
) as dag:

    def task_prepare_data():
        from train.prepare_data import run_prepare
        run_prepare()

    def task_train_model():
        from train.train import train
        train()

    def task_validate_model(min_f1: float = 0.65):
        import mlflow
        import os
        from dotenv import load_dotenv
        load_dotenv()
        mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
        client = mlflow.tracking.MlflowClient()
        version = client.get_model_version_by_alias("rain_tomorrow_detector", "challenger")
        run = client.get_run(version.run_id)
        f1 = run.data.metrics.get("f1_score", 0)
        if f1 < min_f1:
            raise ValueError(f"F1={f1:.4f} < seuil={min_f1}. Modèle rejeté.")

    def task_promote():
        import mlflow
        import os
        from dotenv import load_dotenv
        load_dotenv()
        mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
        client = mlflow.tracking.MlflowClient()
        version = client.get_model_version_by_alias("rain_tomorrow_detector", "challenger")
        client.set_registered_model_alias("rain_tomorrow_detector", "production", version.version)

    def task_refresh_model_api():
        """
        Force le model-api à recharger la nouvelle version 'production'.
        Sans ça, le service continue de servir l'ancien modèle en cache.
        Non bloquant : un échec (service down) ne doit pas faire échouer la promo.
        """
        import os
        import logging
        import requests
        from dotenv import load_dotenv
        load_dotenv()
        base = os.environ.get("MODEL_API_BASE_URL")
        if not base:
            logging.warning("MODEL_API_BASE_URL absent — reload du model-api ignoré.")
            return
        try:
            resp = requests.post(f"{base}/reload", timeout=120)
            resp.raise_for_status()
            logging.info(f"model-api rechargé : {resp.json()}")
        except Exception as e:
            logging.warning(f"Reload du model-api échoué (non bloquant) : {e}")

    t1 = PythonOperator(task_id="prepare_data",     python_callable=task_prepare_data)
    t2 = PythonOperator(task_id="train_model",      python_callable=task_train_model)
    t3 = PythonOperator(task_id="validate_model",   python_callable=task_validate_model)
    t4 = PythonOperator(task_id="promote",          python_callable=task_promote)
    t5 = PythonOperator(task_id="refresh_model_api", python_callable=task_refresh_model_api)

    t1 >> t2 >> t3 >> t4 >> t5
