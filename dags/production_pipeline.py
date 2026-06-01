"""
Circuit 2 — DAG Airflow : pipeline de production (serving).

Tâches :
  1. run_etl       → extract (data-api) → transform (/predict) → load (S3 + Postgres)
  2. run_monitoring → EvidentlyAI : drift + performance
  3. check_alert   → si drift détecté, déclenche le DAG training_pipeline
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
    dag_id="production_pipeline",
    default_args=default_args,
    description="Circuit 2 — Serving et monitoring",
    schedule_interval="0 6 * * *",   # tous les jours à 6h UTC
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["circuit2", "production"],
) as dag:

    def task_run_etl():
        from etl import run_pipeline
        run_pipeline()

    def task_run_monitoring():
        from monitoring.monitor import run_monitoring
        run_monitoring()

    def task_check_alert(**context):
        drift_detected = context["ti"].xcom_pull(task_ids="run_monitoring", key="drift_detected")
        if drift_detected:
            from airflow.api.client.local_client import Client
            Client(None, None).trigger_dag("training_pipeline")

    t1 = PythonOperator(task_id="run_etl",        python_callable=task_run_etl)
    t2 = PythonOperator(task_id="run_monitoring",  python_callable=task_run_monitoring)
    t3 = PythonOperator(task_id="check_alert",     python_callable=task_check_alert)

    t1 >> t2 >> t3
