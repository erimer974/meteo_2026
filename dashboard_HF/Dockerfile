FROM python:3.11-slim

WORKDIR /home/app

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py app.py

CMD ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0"]
