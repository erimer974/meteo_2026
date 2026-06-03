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

- Backend : `BACKEND_STORE_URI` = **le même Neon que `DATABASE_URL`**
- Artefacts : `ARTIFACT_ROOT` = **le même S3 que `MLFLOW_ARTIFACT_ROOT`**
- Port conteneur : 7860 → mappé sur 5000 en local

> **Source de vérité unique (UI local == UI HF).** Le conteneur local et le Space
> HF font tourner le *même* binaire (`mlflow server`), mais affichent les mêmes
> runs/modèles **uniquement si leur `BACKEND_STORE_URI` pointe vers la même base
> Neon** (les artefacts sont déjà mutualisés sur le même bucket S3). En local,
> `docker-compose` injecte `BACKEND_STORE_URI: ${DATABASE_URL}`. Côté HF, le secret
> `BACKEND_STORE_URI` du Space **doit valoir exactement la même URL** que `DATABASE_URL`,
> et `ARTIFACT_ROOT` la même valeur que `MLFLOW_ARTIFACT_ROOT`. Toute divergence de ces
> deux secrets fait diverger les deux UI (cause historique du bug « run non visible »).

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

Deux workflows GitHub Actions enchaînés : `push/PR → CI → (sur main, si verte) → CD`.

### CI — `.github/workflows/ci.yaml`

Déclenché sur chaque push/PR sur `main` :

1. Installation des dépendances
2. Exécution des tests `pytest` (unitaires + validation de données via `pandas.testing`)
3. Build de l'image Docker ETL
4. Run du conteneur ETL en intégration

### CD — `.github/workflows/deploy-hf.yml`

Déclenché automatiquement **à la fin d'une CI verte sur `main`** (`workflow_run`), ou
manuellement (*Run workflow*). Pour chaque service (`mlflow`, `data_api`, `model_api`,
`dashboard`), pousse le dossier source vers le Space HF correspondant **si son contenu a
changé** (sinon no-op), en préservant le `README` de configuration du Space.

Secrets GitHub requis : `AWS_*`, `DATABASE_URL`, URLs des APIs (CI) et **`HF_TOKEN`** (CD).

---

## Services déployés (HuggingFace Spaces)

Les 4 services tournent en ligne (déploiement continu via la CD). URLs publiques :

| Service | URL en ligne | Usage |
|---|---|---|
| **MLflow** | https://erimer974-meteo-mlflow.hf.space | UI tracking + Model Registry (experiments, runs, alias `production`) |
| **Data API** | https://erimer974-meteo-data-api.hf.space/docs | Flux météo simulé — `/current-weather`, `/info` |
| **Model API** | https://erimer974-meteo-model-api.hf.space/docs | Prédictions — `POST /predict` |
| **Dashboard** | https://erimer974-meteo-dashboard.hf.space | Visualisation Streamlit des prédictions |

### Utiliser les services en ligne

**Récupérer des données météo simulées :**

```bash
curl "https://erimer974-meteo-data-api.hf.space/current-weather?n=5"
```

**Faire une prédiction (pluie demain ? 0/1 + probabilités) :**

```bash
curl -X POST https://erimer974-meteo-model-api.hf.space/predict \
  -H "Content-Type: application/json" \
  -d '{"Location":"Sydney","MinTemp":13.4,"MaxTemp":22.9,"Rainfall":0.6,
       "WindGustDir":"W","WindDir9am":"W","WindDir3pm":"WNW",
       "RainToday":0,"Month":1,"Day":1}'
# → {"prediction":0,"proba_0":0.83,"proba_1":0.17}
```

Documentation interactive (Swagger) sur `/docs` pour chaque API. Le **dashboard** et
l'**UI MLflow** s'ouvrent directement dans le navigateur via leurs URLs.

### Basculer le pipeline local vers le cloud

Pour que l'ETL/Airflow utilisent les services **hébergés** plutôt que les conteneurs
locaux, pointer ces variables de `.env` vers les URLs HF :

```bash
MLFLOW_TRACKING_URI=https://erimer974-meteo-mlflow.hf.space
MODEL_API_BASE_URL=https://erimer974-meteo-model-api.hf.space
DATA_API_BASE_URL=https://erimer974-meteo-data-api.hf.space
```

### Déploiement et secrets

- Le déploiement est **automatique** : tout merge sur `main` (CI verte) pousse les
  services modifiés vers leurs Spaces (voir [CI/CD](#cicd)).
- Chaque Space lit ses propres **secrets côté HuggingFace** (Settings du Space →
  *Variables and secrets*) : `AWS_*`, `DATABASE_URL`, `MLFLOW_TRACKING_URI`, préfixes S3…
  La CD pousse le **code**, pas les secrets — ceux-ci se configurent une fois sur HF.
- **Space `meteo-mlflow`** — pour que son UI affiche les mêmes runs que le MLflow
  local, ses secrets doivent être :
  - `BACKEND_STORE_URI` = **la valeur exacte de `DATABASE_URL`** du `.env` local
    (même base Neon `neondb`) ;
  - `ARTIFACT_ROOT` = `s3://meteo-mlops-2026/mlflow-artifacts` (= `MLFLOW_ARTIFACT_ROOT`) ;
  - `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (lecture/écriture des artefacts S3).
- Les dossiers locaux `*_HF/` sont des clones des Spaces (dépôts git séparés) ; la source
  de vérité reste les dossiers `mlflow/`, `data_api/`, `model_api/`, `dashboard/` du repo.

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
