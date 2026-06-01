FROM python:3.11-slim

WORKDIR /home/app

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py app.py

CMD ["bash", "-lc", "fastapi run app.py --host 0.0.0.0 --port ${PORT}"]
