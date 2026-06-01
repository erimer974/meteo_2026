FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY etl.py etl.py
COPY utils/ utils/

CMD ["python", "etl.py"]
