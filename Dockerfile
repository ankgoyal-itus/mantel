# syntax=docker/dockerfile:1

# One container: the API with the kiosk built into it, exactly as `make build`
# and the launchd agent do it on the Mac. Production runs it on Albert (Linux,
# Docker) from a tagged release; see docs/DEPLOY.md. Nothing here is Mac-only
# and nothing assumes a LAN.

# ---- the kiosk -------------------------------------------------------------
# Built here rather than copied in, so the image always carries a bundle that
# matches the source it was built from.
FROM node:22-slim AS kiosk
WORKDIR /build
COPY apps/kiosk/package.json apps/kiosk/package-lock.json ./
RUN npm ci --no-fund --no-audit
COPY apps/kiosk/ ./
RUN npm run build -- --outDir /out --emptyOutDir

# ---- the API ---------------------------------------------------------------
FROM python:3.11-slim AS api

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MANTEL_ROOT=/app \
    MANTEL_STATIC=/app/static \
    MANTEL_HOME=/app/home \
    MANTEL_BIND=0.0.0.0 \
    MANTEL_PORT=8000

WORKDIR /app

COPY services/api/pyproject.toml ./services/api/pyproject.toml
COPY services/api/mantel_api ./services/api/mantel_api
RUN pip install --no-cache-dir ./services/api

COPY VERSION ./VERSION
COPY --from=kiosk /out ./static

# home/ is mounted at run time (see docker-compose.yml), so a meal can be
# changed without rebuilding. A deploy with no volumes would COPY it here.
RUN useradd --system --create-home --uid 10001 mantel && chown -R mantel /app
USER mantel

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import os, urllib.request as r; r.urlopen('http://127.0.0.1:%s/api/health' % os.environ.get('MANTEL_PORT', '8000'), timeout=3)"]

CMD ["python", "-m", "mantel_api"]
