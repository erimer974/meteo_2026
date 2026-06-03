# Image Airflow optionnelle « pré-cuite ».
#
# Par défaut, docker-compose n'utilise PAS ce Dockerfile : il lance l'image
# officielle apache/airflow:2.10.5-python3.11 et installe les dépendances au
# démarrage via _PIP_ADDITIONAL_REQUIREMENTS. Ce Dockerfile est une alternative
# (deps figées dans l'image) — version et requirements maintenus alignés sur le
# compose pour éviter toute divergence.
#
# ⚠️ Ne PAS ajouter sqlalchemy>=2.0 : Airflow 2.10 épingle SQLAlchemy 1.4 et un
# bump 2.0 casse son ORM (MappedAnnotationError). monitor.py se contente de la 1.4.
FROM apache/airflow:2.10.5-python3.11

USER airflow

COPY requirements.txt /airflow-requirements.txt
RUN pip install --no-cache-dir -r /airflow-requirements.txt
