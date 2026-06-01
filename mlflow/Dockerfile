FROM python:3.11

WORKDIR /home/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends nano unzip curl \
    && rm -rf /var/lib/apt/lists/*

RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
RUN unzip awscliv2.zip
RUN ./aws/install

RUN useradd -m -u 1000 user
USER user

ENV HOME=/home/user
ENV PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

COPY --chown=user . $HOME/app

RUN pip install -r requirements.txt

CMD mlflow server --port 7860 \
--host 0.0.0.0 \
--backend-store-uri $BACKEND_STORE_URI \
--default-artifact-root $ARTIFACT_ROOT \
--allowed-hosts "*"
