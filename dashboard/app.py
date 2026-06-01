"""
meteo-dashboard — HuggingFace Space #4

Dashboard Streamlit : KPIs, distribution des prédictions,
drift et performances du modèle.
Source : Neon Postgres (table meteo_predictions)
"""
import os
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Meteo MLOps Dashboard", layout="wide")
st.title("Dashboard — Prédictions météo australiennes")


@st.cache_data(ttl=300)
def load_predictions() -> pd.DataFrame:
    try:
        engine = create_engine(os.environ["DATABASE_URL"])
        return pd.read_sql("SELECT * FROM meteo_predictions ORDER BY id DESC LIMIT 5000", engine)
    except Exception:
        return pd.DataFrame()


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

st.caption("Données rafraîchies toutes les 5 minutes — Phase 11 : ajout monitoring EvidentlyAI")
