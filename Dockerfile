FROM python:3.12-slim

# git is required to pip-install agent-dna from its GitHub repo (see requirements.txt)
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first so this layer is cached across code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

EXPOSE 8000

# Bind to 0.0.0.0 so the server is reachable from outside the container.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${ADMIN_SERVER_PORT:-8000}"]
