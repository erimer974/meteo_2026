# Meteo MLOps 2026

Pipeline MLOps complet de prédiction de pluie pour l'Australie (dataset [Rain in Australia](https://www.kaggle.com/datasets/jsphyg/weather-dataset-rattle-package)).

## Architecture

```
Kaggle ──► S3 (raw)
              │
              ▼
         [Circuit 1 — Entraînement]
         Airflow DAG: training_pipeline
           prepare_data → train_model → validate_model → promote
                                │
                                ▼
                           MLflow Registry
                         (alias: production)
                                │
              ┌─────────────────┘
              ▼
         [Circuit 2 — Production]
         Airflow DAG: production_pipeline (quotidien 6h UTC)
           run_etl → run_monitoring → check_alert
              │
    ┌─────────┴──────────┐
    ▼                    ▼
 data-api            model-api
 (S3 prod)         (MLflow model)
    │                    │
    └─────────┬──────────┘
              ▼
        Neon Postgres          S3 (clean)
        (predictions)
              │
              ▼
          dashboard
```

## Prérequis

- Docker Desktop (avec Docker Compose v2)
- Compte Kaggle avec token API
- Bucket AWS S3
- Base de données Neon PostgreSQL (deux instances : app + Airflow)

## Configuration

Copier `.env.example` en `.env` et renseigner toutes les variables :

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `KAGGLE_USERNAME` | Nom d'utilisateur Kaggle |
| `KAGGLE_KEY` | Token API Kaggle ([générer ici](https://www.kaggle.com/settings/api)) |
| `AWS_ACCESS_KEY_ID` | Clé d'accès AWS |
| `AWS_SECRET_ACCESS_KEY` | Secret AWS |
| `AWS_DEFAULT_REGION` | Région AWS (ex : `eu-west-3`) |
| `S3_BUCKET_NAME` | Nom du bucket S3 |
| `S3_RAW_PREFIX` | Préfixe S3 données brutes (ex : `raw/meteo`) |
| `S3_PROD_PREFIX` | Préfixe S3 données production (ex : `production/meteo`) |
| `DATABASE_URL` | URL Neon Postgres — prédictions (postgresql://...) |
| `AIRFLOW_DB_URL` | URL Neon Postgres — Airflow metadata (postgresql+psycopg2://...) |
| `MLFLOW_TRACKING_URI` | `http://mlflow:7860` en local (port **interne** du conteneur ; `5000` n'est que le mapping hôte de l'UI), URL HF Spaces en prod |
| `MLFLOW_ARTIFACT_ROOT` | Chemin S3 artefacts MLflow (ex : `s3://bucket/mlflow-artifacts`) |

---

## Démarrage rapide

### Stack principale (sans Airflow)

Démarre data-api, model-api, dashboard et MLflow :

```bash
docker compose up -d
```

| Service | URL locale | Description |
|---|---|---|
| MLflow | http://localhost:5000 | Tracking + Model Registry |
| Data API | http://localhost:8001 | Flux météo simulé (S3 → JSON) |
| Model API | http://localhost:8002 | Prédictions `/predict` |
| Dashboard | http://localhost:8501 | Visualisation Streamlit |

### Stack complète (avec Airflow)

```bash
docker compose --profile airflow up -d
```

Ajoute les services Airflow au stack ci-dessus :

| Service | URL locale | Description |
|---|---|---|
| Airflow UI | http://localhost:8080 | Scheduler + DAGs (admin/admin) |

### Lancer uniquement l'ETL (ponctuel)

```bash
docker compose --profile etl run --rm etl
```

### Arrêter tout

```bash
docker compose --profile airflow down
```

---

## Services en détail

### MLflow (`./mlflow`)

Serveur de tracking MLflow avec backend Neon PostgreSQL et artefacts sur S3.

- Backend : `DATABASE_URL` (Neon)
- Artefacts : `MLFLOW_ARTIFACT_ROOT` (S3)
- Port conteneur : 7860 → mappé sur 5000 en local

### Data API (`./data_api`)

FastAPI qui sert des lignes aléatoires du dataset météo 2016-2017 depuis S3, simulant un flux de données live.

```
GET  /                    → statut
GET  /current-weather?n=  → n lignes météo aléatoires (sans RainTomorrow)
GET  /info                → métadonnées du dataset
```

### Model API (`./model_api`)

FastAPI qui charge le modèle tagué `production` depuis le MLflow Registry et expose une route de prédiction.

```
GET  /                    → statut
POST /predict             → prédiction RainTomorrow (0/1 + probabilités)
```

Le modèle est chargé au premier appel (lazy loading).

### Dashboard (`./dashboard`)

Application Streamlit de visualisation des prédictions et des métriques de drift.

---

## Circuit 1 — Entraînement

DAG Airflow : `training_pipeline` (déclenchement manuel ou par le monitoring)

```
prepare_data → train_model → validate_model → promote
```

| Tâche | Description |
|---|---|
| `prepare_data` | Télécharge weatherAUS depuis Kaggle, nettoie, splitte par année (≤2015 train / >2015 prod+monitor), uploade sur S3 |
| `train_model` | Entraîne un `HistGradientBoostingClassifier` avec `sample_weight` balancé, logge dans MLflow, enregistre avec l'alias `challenger` |
| `validate_model` | Vérifie que le F1-score du challenger dépasse le seuil (0.65) |
| `promote` | Attribue l'alias `production` au modèle validé dans le MLflow Registry |

**Lancer manuellement via l'UI Airflow :**
1. Aller sur http://localhost:8080
2. Activer le DAG `training_pipeline`
3. Cliquer sur "Trigger DAG"

---

## Circuit 2 — Production

DAG Airflow : `production_pipeline` (planifié tous les jours à 6h UTC)

```
run_etl → run_monitoring → check_alert
```

| Tâche | Description |
|---|---|
| `run_etl` | Appelle la data-api, transforme (nettoyage + prédiction via model-api), charge dans Neon + S3 |
| `run_monitoring` | Analyse le drift EvidentlyAI (comparaison prédictions vs vérité terrain S3 monitor) |
| `check_alert` | Si drift détecté, déclenche automatiquement `training_pipeline` |

---

## Tests

```bash
pip install -r requirements-tests.txt
pytest -v
```

Les tests couvrent :
- Smoke tests des APIs (data-api et model-api)
- Tests unitaires de la transformation ETL

Les URLs des APIs sont injectées via variables d'environnement (`DATA_API_BASE_URL`, `MODEL_API_BASE_URL`).

---

## CI/CD

GitHub Actions (`.github/workflows/ci.yaml`) déclenché sur chaque push/PR sur `main` :

1. Installation des dépendances
2. Exécution des tests pytest
3. Build de l'image Docker ETL
4. Run du conteneur ETL en intégration

Les secrets (`AWS_*`, `DATABASE_URL`, URLs des APIs) sont configurés dans les Settings GitHub du repo.

---

## Déploiement HuggingFace Spaces (optionnel)

Chaque service dispose d'un dossier `*_HF/` contenant le Dockerfile adapté pour HF Spaces (port 7860).

| Service | Space HF |
|---|---|
| MLflow | `meteo-mlflow_HF/` → `erimer974-meteo-mlflow.hf.space` |
| Data API | `meteo-data-api_HF/` → `erimer974-meteo-data-api.hf.space` |
| Model API | `meteo-model-api_HF/` → `erimer974-meteo-model-api.hf.space` |
| Dashboard | `meteo-dashboard_HF/` → `erimer974-meteo-dashboard.hf.space` |

Pour basculer de local vers HF, modifier dans `.env` :

```bash
MLFLOW_TRACKING_URI=https://erimer974-meteo-mlflow.hf.space
```

---

## Structure du projet

```
.
├── dags/                    # DAGs Airflow
│   ├── training_pipeline.py # Circuit 1
│   └── production_pipeline.py # Circuit 2
├── train/                   # Scripts d'entraînement
│   ├── prepare_data.py      # Kaggle → S3
│   └── train.py             # Entraînement + MLflow
├── monitoring/              # Monitoring EvidentlyAI
│   └── monitor.py
├── utils/                   # ETL helpers
│   ├── extract.py
│   ├── transform.py
│   └── load.py
├── data_api/                # Service data-api
├── model_api/               # Service model-api
├── dashboard/               # Dashboard Streamlit
├── mlflow/                  # Serveur MLflow
├── airflow/                 # Image Airflow custom
├── tests/                   # Tests pytest
├── etl.py                   # Point d'entrée ETL
├── docker-compose.yml       # Orchestration Docker
└── .env                     # Variables d'environnement (non versionné)
```
