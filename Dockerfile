FROM python:3.11-slim

# Installiere System-Dependencies
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Erstelle Non-Root User
RUN useradd -m -u 1000 botuser && \
    mkdir -p /app/data && \
    chown -R botuser:botuser /app

# Setze Working Directory
WORKDIR /app

# Kopiere Requirements
COPY requirements.txt .

# Installiere Python Dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Kopiere Source Code
COPY src/ ./src/

# Setze Permissions
RUN chown -R botuser:botuser /app

# Wechsle zu Non-Root User
USER botuser

# Environment Variables
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99

# Entry Point
CMD ["python", "-m", "src.main"]

