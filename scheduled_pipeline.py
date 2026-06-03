"""
Exécution serverless du pipeline — équivalent des DAGs Airflow, mais SANS Airflow
ni machine allumée. Conçu pour être lancé par GitHub Actions (cron quotidien).

Reproduit :
  • Circuit 2 (production_pipeline) : ETL → monitoring drift → décision
  • Circuit 1 (training_pipeline) UNIQUEMENT si drift : retraining → validate →
    promote → reload du model-api

Toutes les dépendances réseau visent les Spaces HuggingFace (toujours en ligne),
donc aucun conteneur local n'est requis. Les variables viennent de l'environnement
(injectées par GitHub Actions depuis les secrets/variables du repo).
"""
import os
import logging

REGISTERED_MODEL_NAME = "rain_tomorrow_detector"


def _retrain_and_promote() -> None:
    """Circuit 1 : (prepare_data si Kaggle dispo) → train → validate → promote → reload."""
    import mlflow
    from mlflow.tracking import MlflowClient

    # prepare_data ne sert qu'à (re)télécharger Kaggle vers S3. Le dataset Kaggle
    # étant statique, on le saute si les identifiants Kaggle ne sont pas fournis :
    # l'entraînement lit alors le jeu déjà présent sur S3.
    if os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"):
        from train.prepare_data import run_prepare
        logging.info("prepare_data : rafraîchissement des données depuis Kaggle…")
        run_prepare()
    else:
        logging.warning("KAGGLE_* absents — prepare_data sauté, entraînement sur les données S3 existantes.")

    from train.train import train
    logging.info("train_model : entraînement + log MLflow (alias challenger)…")
    train()

    mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
    client = MlflowClient()
    version = client.get_model_version_by_alias(REGISTERED_MODEL_NAME, "challenger")
    run = client.get_run(version.run_id)
    f1 = run.data.metrics.get("f1_score", 0)
    min_f1 = float(os.environ.get("MIN_F1", 0.65))

    if f1 < min_f1:
        raise SystemExit(f"validate_model : F1={f1:.4f} < seuil={min_f1} → modèle rejeté, pas de promotion.")

    client.set_registered_model_alias(REGISTERED_MODEL_NAME, "production", version.version)
    logging.info(f"promote : version {version.version} promue 'production' (F1={f1:.4f}).")

    # refresh_model_api : recharge la nouvelle version dans le service (non bloquant)
    base = os.environ.get("MODEL_API_BASE_URL")
    if base:
        import requests
        try:
            resp = requests.post(f"{base}/reload", timeout=120)
            resp.raise_for_status()
            logging.info(f"refresh_model_api : {resp.json()}")
        except Exception as e:
            logging.warning(f"refresh_model_api échoué (non bloquant) : {e}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    from dotenv import load_dotenv
    load_dotenv()  # no-op en CI ; pratique en local

    from etl import run_pipeline
    from monitoring.monitor import run_monitoring

    logging.info("========== Circuit 2 — ETL ==========")
    run_pipeline()  # extract (data-api) → transform (/predict) → load (S3 + Neon)

    logging.info("========== Circuit 2 — Monitoring ==========")
    result = run_monitoring()
    drift = bool(result.get("drift_detected"))
    logging.info(f"Résultat monitoring : drift_detected={drift} | {result}")

    if not drift:
        logging.info("Aucun drift au-dessus du seuil — pas de retraining. Terminé.")
        return

    logging.info("========== Drift détecté → Circuit 1 — Retraining ==========")
    _retrain_and_promote()
    logging.info("Retraining terminé.")


if __name__ == "__main__":
    main()
