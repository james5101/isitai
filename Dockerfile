FROM python:3.12-slim

WORKDIR /app

# Install Python dependencies first — separate layer so Docker can cache it.
# If only app code changes, this layer is reused and pip doesn't re-run.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Chromium and all its Linux system dependencies in one shot.
# --with-deps handles libglib, libnss, libatk, etc. that slim doesn't include.
RUN playwright install --with-deps chromium

# Copy app code
COPY app/ app/
COPY static/ static/

EXPOSE 8000

# PORT is set dynamically by Render; defaults to 8000 for local use.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
