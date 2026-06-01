"""
Circuit 1 — Étape 2 : entraîne le modèle sur les données historiques
(2008-2015) et logge tout dans MLflow.

Le modèle est un sklearn Pipeline auto-suffisant :
  ColumnTransformer (imputation + OHE)
  + HistGradientBoostingClassifier avec sample_weight balancé

Après entraînement, le modèle est enregistré dans le Model Registry
avec l'alias "challenger". L'alias "production" est attribué manuellement
(ou par le DAG Airflow après validation CI/CD).
"""
import os
import time
import logging
import pandas as pd
import mlflow
import mlflow.sklearn
import boto3
from io import StringIO
from dotenv import load_dotenv
from mlflow.tracking import MlflowClient
from mlflow.models.signature import infer_signature

from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.utils.class_weight import compute_sample_weight
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

load_dotenv()

REGISTERED_MODEL_NAME = "rain_tomorrow_detector"
EXPERIMENT_NAME = "meteo_australie"
TARGET_COL = "RainTomorrow"

CATEGORICAL_COLS = ["Location", "WindGustDir", "WindDir9am", "WindDir3pm"]
NUMERIC_COLS = [
    "MinTemp", "MaxTemp", "Rainfall", "Evaporation", "Sunshine",
    "WindGustSpeed", "WindSpeed9am", "WindSpeed3pm",
    "Humidity9am", "Humidity3pm", "Pressure9am", "Pressure3pm",
    "Cloud9am", "Cloud3pm", "Temp9am", "Temp3pm",
    "RainToday", "Month", "Day",
]


def load_train_data() -> pd.DataFrame:
    bucket = os.environ["S3_BUCKET_NAME"]
    prefix = os.environ.get("S3_RAW_PREFIX", "raw/meteo")
    key = f"{prefix}/train/weatherAUS_train.csv"

    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=bucket, Key=key)
    df = pd.read_csv(StringIO(obj["Body"].read().decode("utf-8")))
    logging.info(f"Données chargées depuis S3 : {len(df)} lignes.")
    return df


def build_pipeline() -> Pipeline:
    categorical_transformer = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("ohe", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])
    numerical_transformer = Pipeline([
        ("imputer", SimpleImputer(strategy="mean")),
    ])
    preprocessor = ColumnTransformer([
        ("cat", categorical_transformer, CATEGORICAL_COLS),
        ("num", numerical_transformer, NUMERIC_COLS),
    ])
    return Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", HistGradientBoostingClassifier(
            max_iter=400,
            learning_rate=0.05,
            max_depth=6,
            min_samples_leaf=20,
            l2_regularization=0.1,
            random_state=42,
        )),
    ])


def train():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
    mlflow.set_experiment(EXPERIMENT_NAME)
    client = MlflowClient()

    df = load_train_data()
    df[TARGET_COL] = df[TARGET_COL].map({"No": 0, "Yes": 1}).fillna(df[TARGET_COL])

    X = df[CATEGORICAL_COLS + NUMERIC_COLS]
    y = df[TARGET_COL].astype(int)

    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    pipeline = build_pipeline()
    start = time.time()

    # Pondération inversement proportionnelle à la fréquence de chaque classe
    sample_weight = compute_sample_weight("balanced", y_train)

    mlflow.sklearn.autolog(log_models=False)
    with mlflow.start_run() as run:

        pipeline.fit(X_train, y_train, classifier__sample_weight=sample_weight)
        y_pred = pipeline.predict(X_test)

        accuracy  = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred)
        recall    = recall_score(y_test, y_pred)
        f1        = f1_score(y_test, y_pred)

        mlflow.log_metrics({
            "accuracy": accuracy, "precision": precision,
            "recall": recall, "f1_score": f1,
        })

        signature = infer_signature(X_train, pipeline.predict(X_train))
        model_info = mlflow.sklearn.log_model(
            sk_model=pipeline,
            artifact_path="model",
            registered_model_name=REGISTERED_MODEL_NAME,
            signature=signature,
            input_example=X_train.head(3),
        )

        version = model_info.registered_model_version
        client.set_registered_model_alias(REGISTERED_MODEL_NAME, "challenger", version)

        logging.info(f"Modèle version {version} enregistré — alias 'challenger' attribué.")
        logging.info(f"Accuracy={accuracy:.4f} | F1={f1:.4f} | Durée={time.time()-start:.1f}s")


if __name__ == "__main__":
    train()
