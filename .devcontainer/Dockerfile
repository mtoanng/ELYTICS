FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y git ca-certificates curl redis-server \
    && rm -rf /var/lib/apt/lists/*

# Copy corporate root certificate into system trust store
COPY root_ca.pem /usr/local/share/ca-certificates/root_ca.crt
RUN update-ca-certificates

# Copy and install backend requirements
COPY backend/requirements.txt ./backend-requirements.txt
RUN pip install --upgrade pip && pip install -r backend-requirements.txt

# Copy and install frontend requirements
COPY frontend/requirements.txt ./frontend-requirements.txt
RUN pip install -r frontend-requirements.txt

COPY . .

EXPOSE 8501 8000