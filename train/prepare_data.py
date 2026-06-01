"""
Circuit 1 — Étape 1 : télécharge weatherAUS.csv depuis Kaggle,
nettoie les données, splitte par année et uploade sur S3.

  S3 raw/meteo/train/   → 2008-2015 avec RainTomorrow  (entraînement)
  S3 raw/meteo/prod/    → 2016-2017 sans RainTomorrow   (data-api / serving)
  S3 raw/meteo/monitor/ → 2016-2017 avec RainTomorrow   (EvidentlyAI)
"""
import os
import logging
import pandas as pd
import boto3

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

TRAIN_CUTOFF_YEAR = 2015
DATASET_ID = "jsphyg/weather-dataset-rattle-package"
RAW_FILENAME = "weatherAUS.csv"


def download_from_kaggle(output_dir: str = "data/raw") -> str:
    import kaggle
    os.makedirs(output_dir, exist_ok=True)
    kaggle.api.dataset_download_files(DATASET_ID, path=output_dir, unzip=True)
    path = os.path.join(output_dir, RAW_FILENAME)
    logging.info(f"Dataset téléchargé : {path}")
    return path


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """
    Nettoyage de base commun à toutes les données :
    - Suppression des doublons
    - Parse Date → Year, Month, Day (Year conservé pour le split temporel)
    - RainToday → 0/1
    """
    df = df.drop_duplicates()

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df[df["Date"].notna()].copy()
    df["Year"] = df["Date"].dt.year
    df["Month"] = df["Date"].dt.month
    df["Day"] = df["Date"].dt.day
    df.drop(columns=["Date"], inplace=True)

    df["RainToday"] = df["RainToday"].map({"No": 0, "Yes": 1})

    logging.info(f"Nettoyage terminé : {len(df)} lignes.")
    return df


def split_by_year(df: pd.DataFrame):
    """
    Retourne (train_df, prod_df, monitor_df) :
      train_df   : Year <= TRAIN_CUTOFF_YEAR, avec RainTomorrow, sans Year
      prod_df    : Year >  TRAIN_CUTOFF_YEAR, sans RainTomorrow, sans Year
      monitor_df : Year >  TRAIN_CUTOFF_YEAR, avec RainTomorrow, sans Year
    """
    train_mask = df["Year"] <= TRAIN_CUTOFF_YEAR
    prod_mask = ~train_mask

    train_df = df[train_mask].copy()
    train_df = train_df[train_df["RainTomorrow"].notna()].copy()
    train_df.drop(columns=["Year"], inplace=True)

    prod_base = df[prod_mask].copy()
    prod_base.drop(columns=["Year"], inplace=True)

    prod_df = prod_base.drop(columns=["RainTomorrow"], errors="ignore")
    monitor_df = prod_base.copy()

    logging.info(f"Split : {len(train_df)} lignes train | {len(prod_df)} lignes prod/monitor")
    return train_df, prod_df, monitor_df


def upload_to_s3(df: pd.DataFrame, key: str) -> None:
    bucket = os.environ["S3_BUCKET_NAME"]
    s3 = boto3.client("s3")
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=df.to_csv(index=False).encode("utf-8"),
        ContentType="text/csv",
    )
    logging.info(f"Uploadé → s3://{bucket}/{key}")


def run_prepare():
    from dotenv import load_dotenv
    load_dotenv()

    raw_path = download_from_kaggle()
    df = pd.read_csv(raw_path, on_bad_lines="skip")
    df = clean(df)
    train_df, prod_df, monitor_df = split_by_year(df)

    raw_prefix = os.environ.get("S3_RAW_PREFIX", "raw/meteo")
    upload_to_s3(train_df,   f"{raw_prefix}/train/weatherAUS_train.csv")
    upload_to_s3(prod_df,    f"{raw_prefix}/prod/weatherAUS_prod.csv")
    upload_to_s3(monitor_df, f"{raw_prefix}/monitor/weatherAUS_monitor.csv")

    logging.info("prepare_data terminé.")


if __name__ == "__main__":
    run_prepare()
