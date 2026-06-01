FROM apache/airflow:2.9.1-python3.11

USER airflow

COPY requirements.txt /airflow-requirements.txt
RUN pip install --no-cache-dir -r /airflow-requirements.txt
