import logging
import sys
from dotenv import load_dotenv

from utils import extract_weather, transform_weather, load_weather

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def run_pipeline():
    logging.info("=" * 50)
    logging.info("DEBUT DU PIPELINE ETL — Circuit 2 Production")
    logging.info("=" * 50)

    try:
        load_dotenv()
        logging.info("Variables d'environnement chargées.")

        logging.info("--- Étape 1 : Extraction (data-api → S3 backup) ---")
        raw_df = extract_weather()

        logging.info("--- Étape 2 : Transformation (nettoyage + /predict) ---")
        predicted_df = transform_weather(raw_df)

        logging.info("--- Étape 3 : Chargement (S3 clean + Neon Postgres) ---")
        summary = load_weather(predicted_df)

        logging.info("=" * 50)
        logging.info("PIPELINE EXECUTE AVEC SUCCES")
        logging.info(f"Résumé : {summary}")
        logging.info("=" * 50)

    except Exception as e:
        logging.error("=" * 50)
        logging.error("LE PIPELINE A ECHOUE")
        logging.error(f"Détail : {e}", exc_info=True)
        logging.error("=" * 50)
        sys.exit(1)


if __name__ == "__main__":
    run_pipeline()
