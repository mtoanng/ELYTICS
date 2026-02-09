FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install git, tmux and clean up apt cache
RUN apt-get update \
    && apt-get install -y git tmux redis-server \
    && rm -rf /var/lib/apt/lists/*

# Copy and install backend requirements
COPY backend/requirements.txt ./backend-requirements.txt
RUN pip install --upgrade pip && pip install -r backend-requirements.txt

# Copy and install frontend requirements
COPY frontend/requirements.txt ./frontend-requirements.txt
RUN pip install -r frontend-requirements.txt

# Copy startup script and make it executable
COPY .devcontainer/start-services.sh /workspaces/TBP-HOLMES/.devcontainer/start-services.sh
RUN chmod +x /workspaces/TBP-HOLMES/.devcontainer/start-services.sh

COPY . .

EXPOSE 8501 8000