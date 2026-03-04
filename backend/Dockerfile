# ✅ Base image: Python 3.12.2 on Debian Bookworm slim (secure & stable)
FROM python:3.12.2-slim-bookworm

# ✅ Environment
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# ✅ Update, upgrade, and install system dependencies in one RUN
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        gettext \
        supervisor \
        # (add other deps if needed, e.g. libpq-dev for PostgreSQL)
    && apt-get autoremove -y && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# ✅ Set working directory
WORKDIR /app

# ✅ Create logs folder for supervisor
RUN mkdir -p /var/log/supervisor

# ✅ Copy project files
COPY . /app/

# ✅ Upgrade pip & install Python dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Set the command to run our web service using Gunicorn, binding it to 0.0.0.0 and the PORT environment variable
#CMD ["gunicorn", "server.wsgi:application", "--bind", "0.0.0.0:${PORT}"]
#CMD ["python", "manage.py", "runserver", "0.0.0.0:${PORT}"]
#CMD ["daphne", "-b", "0.0.0.0", "-p", "${WS_INTERNAL_PORT}", "backend.asgi:application"]
# Use supervisord to run both Django and Daphne
CMD ["supervisord", "-c", "/app/supervisord.conf"]
