"""
meteo-dashboard — HuggingFace Space #4

Dashboard Streamlit : KPIs, distribution des prédictions,
drift et performances du modèle.
Source : Neon Postgres (table meteo_predictions)
"""
import os
import boto3
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Meteo MLOps Dashboard", layout="wide")
st.title("Dashboard — Prédictions météo australiennes")


@st.cache_data(ttl=300)
def load_predictions() -> pd.DataFrame:
    try:
        engine = create_engine(os.environ["DATABASE_URL"])
        return pd.read_sql("SELECT * FROM meteo_predictions ORDER BY created_at DESC NULLS LAST LIMIT 5000", engine)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=300)
def load_latest_drift_report():
    """
    Récupère le dernier rapport de drift EvidentlyAI déposé sur S3 par le
    monitoring (Circuit 2). Retourne (html, key, last_modified) ou (None, None, None).

    Requiert les accès S3 côté environnement (S3_BUCKET_NAME + AWS_*). Sur le
    Space HF, ajouter ces secrets pour activer l'affichage.
    """
    bucket = os.environ.get("S3_BUCKET_NAME")
    if not bucket:
        return None, None, None
    prefix = os.environ.get("S3_PROD_PREFIX", "production/meteo")
    try:
        s3 = boto3.client("s3")
        resp = s3.list_objects_v2(Bucket=bucket, Prefix=f"{prefix}/monitoring/")
        reports = [o for o in resp.get("Contents", []) if o["Key"].endswith(".html")]
        if not reports:
            return None, None, None
        latest = max(reports, key=lambda o: o["LastModified"])
        body = s3.get_object(Bucket=bucket, Key=latest["Key"])["Body"].read().decode("utf-8")
        return body, latest["Key"], latest["LastModified"]
    except Exception:
        return None, None, None


df = load_predictions()

if df.empty:
    st.warning("Aucune prédiction disponible. Lancez d'abord le pipeline ETL.")
    st.stop()

# ── KPIs ────────────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
col1.metric("Prédictions totales", len(df))
col2.metric("Prédictions Pluie (1)", int((df["prediction"] == 1).sum()))
col3.metric("Prédictions Pas de pluie (0)", int((df["prediction"] == 0).sum()))

st.divider()

# ── Distribution des probabilités ───────────────────────────────────────────
st.subheader("Distribution de proba_1 (probabilité de pluie)")
st.bar_chart(df["proba_1"].dropna())

# ── Prédictions par ville ────────────────────────────────────────────────────
if "Location" in df.columns:
    st.subheader("Prédictions par ville")
    city_stats = (
        df.groupby("Location")["prediction"]
        .agg(["count", "mean"])
        .rename(columns={"count": "Nb prédictions", "mean": "Taux pluie"})
        .sort_values("Taux pluie", ascending=False)
    )
    st.dataframe(city_stats, use_container_width=True)

st.divider()

# ── Monitoring du drift (EvidentlyAI) ────────────────────────────────────────
st.subheader("Monitoring du drift (EvidentlyAI)")
report_html, report_key, report_date = load_latest_drift_report()
if report_html:
    when = report_date.strftime("%Y-%m-%d %H:%M UTC") if report_date else "?"
    st.caption(f"Dernier rapport : `{report_key}` — {when}")
    components.html(report_html, height=600, scrolling=True)
else:
    st.info(
        "Aucun rapport de drift disponible. Lancez le DAG `production_pipeline` "
        "(tâche `run_monitoring`) pour en générer un. "
        "Sur HuggingFace, vérifiez que le Space dispose des secrets `S3_BUCKET_NAME` et `AWS_*`."
    )

st.caption("Données rafraîchies toutes les 5 minutes — monitoring EvidentlyAI intégré")
